"""Train the lightweight stroke mask segmenter from a manifest CSV."""

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

try:
    import torch
    from torch.utils.data import DataLoader, Dataset
except ImportError:  # pragma: no cover - depends on local environment
    torch = None
    DataLoader = None
    Dataset = object

try:
    from stroke_segmenter import MiniUNet, segmentation_loss
except ImportError:  # pragma: no cover - depends on local environment
    MiniUNet = None
    segmentation_loss = None


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "dataset" / "manifest.csv"
DEFAULT_OUT = SCRIPT_DIR / "models" / "stroke_segmenter.pt"
MASK_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def _resolve_path(path_text: str, base_dir: Path) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _read_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if any((v or "").strip() for v in row.values())]


def _mask_files(mask_dir: Path) -> List[Path]:
    if not mask_dir.exists():
        return []
    return sorted(p for p in mask_dir.iterdir() if p.suffix.lower() in MASK_EXTS)


def _collect_train_rows(manifest: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    rows = _read_manifest(manifest)
    base_dir = manifest.parent
    valid_rows = []
    problems = []
    for row in rows:
        split = (row.get("split") or "").strip().lower()
        if split and split != "train":
            continue
        char_id = (row.get("char_id") or "").strip() or "<missing>"
        image_path = _resolve_path(row.get("image_path", ""), base_dir)
        mask_dir = _resolve_path(row.get("mask_dir", ""), base_dir)
        try:
            stroke_count = int((row.get("stroke_count") or "").strip())
        except ValueError:
            problems.append(f"{char_id}: invalid stroke_count")
            continue
        masks = _mask_files(mask_dir)
        if not image_path.exists():
            problems.append(f"{char_id}: image not found: {image_path}")
            continue
        if not mask_dir.exists():
            problems.append(f"{char_id}: mask_dir not found: {mask_dir}")
            continue
        if len(masks) != stroke_count:
            problems.append(f"{char_id}: mask count {len(masks)} != stroke_count {stroke_count}")
            continue
        valid_rows.append(row)
    return valid_rows, problems


class StrokeMaskDataset(Dataset):
    def __init__(self, rows: List[Dict[str, str]], manifest_dir: Path, max_strokes: int, image_size: int):
        self.rows = rows
        self.manifest_dir = manifest_dir
        self.max_strokes = max_strokes
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        image_path = _resolve_path(row["image_path"], self.manifest_dir)
        mask_dir = _resolve_path(row["mask_dir"], self.manifest_dir)
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"image not readable: {image_path}")
        image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        image_t = torch.from_numpy(image.astype(np.float32) / 255.0).unsqueeze(0)

        target = np.zeros((self.max_strokes, self.image_size, self.image_size), dtype=np.float32)
        for i, mask_path in enumerate(_mask_files(mask_dir)[: self.max_strokes]):
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise RuntimeError(f"mask not readable: {mask_path}")
            mask = cv2.resize(mask, (self.image_size, self.image_size), interpolation=cv2.INTER_NEAREST)
            target[i] = (mask > 0).astype(np.float32)
        target_t = torch.from_numpy(target)
        return image_t, target_t


def train(args) -> int:
    if torch is None or MiniUNet is None:
        print("PyTorch is not installed in this environment. Install torch before training.")
        return 2

    manifest = Path(args.manifest).resolve()
    rows, problems = _collect_train_rows(manifest)
    if not manifest.exists():
        print(f"Dataset manifest not found: {manifest}")
        print("Create code/dataset/manifest.csv and add at least one train sample.")
        return 0
    if problems:
        print("Dataset issues:")
        for problem in problems:
            print(f"  - {problem}")
    if not rows:
        print("No usable training samples found.")
        print("Add rows with split=train, readable image_path, mask_dir, and ordered masks 01.png, 02.png, ...")
        return 0

    dataset = StrokeMaskDataset(rows, manifest.parent, args.max_strokes, args.image_size)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MiniUNet(max_strokes=args.max_strokes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    model.train()
    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = segmentation_loss(logits, targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * images.size(0)
        avg_loss = total_loss / len(dataset)
        print(f"epoch {epoch}/{args.epochs}: loss={avg_loss:.4f}")

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "max_strokes": args.max_strokes,
            "image_size": args.image_size,
        },
        out_path,
    )
    print(f"Saved model: {out_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MiniUNet stroke segmenter")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-strokes", type=int, default=12)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    raise SystemExit(train(args))


if __name__ == "__main__":
    main()
