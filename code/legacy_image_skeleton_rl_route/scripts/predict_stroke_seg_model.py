"""Run ordered stroke-mask segmentation predictions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch

from stroke_seg_model import StrokeSegUNet, load_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_seg_unet.pt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "output" / "stroke_seg_predictions"


def load_model(checkpoint_path: Path, device):
    checkpoint = torch.load(checkpoint_path, map_location=device)
    max_strokes = int(checkpoint["max_strokes"])
    image_size = int(checkpoint.get("image_size", 256))
    base_channels = int(checkpoint.get("base_channels", 16))
    model = StrokeSegUNet(max_strokes=max_strokes, in_channels=1, base_channels=base_channels).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint


def resolve_threshold(cli_threshold: float | None, checkpoint: dict) -> float:
    if cli_threshold is not None:
        return float(cli_threshold)
    value = checkpoint.get("best_threshold", 0.5)
    return 0.5 if value is None else float(value)


def read_image_tensor(path: Path, image_size: int):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"image not readable: {path}")
    if image.shape != (image_size, image_size):
        image = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
    foreground = 1.0 - image.astype(np.float32) / 255.0
    tensor = torch.from_numpy(foreground).unsqueeze(0).unsqueeze(0)
    return image, tensor


def make_overlay(image: np.ndarray, masks: np.ndarray, out_path: Path, title: str) -> None:
    fig = Figure(figsize=(6.0, 6.0), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92])
    ax.imshow(image, cmap="gray", vmin=0, vmax=255)
    colors = matplotlib.colormaps["tab20"].colors
    for idx, mask in enumerate(masks):
        if mask.max() <= 0:
            continue
        color = np.array(colors[idx % len(colors)])
        rgba = np.zeros((*mask.shape, 4), dtype=float)
        rgba[..., :3] = color[:3]
        rgba[..., 3] = (mask > 0).astype(float) * 0.38
        ax.imshow(rgba)
        ys, xs = np.where(mask > 0)
        if len(xs):
            ax.text(float(xs.mean()), float(ys.mean()), str(idx + 1), color="black", fontsize=9, weight="bold")
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def predict_one(model, image_path: Path, out_dir: Path, image_size: int, threshold: float, device, char_id: str):
    image, tensor = read_image_tensor(image_path, image_size)
    tensor = tensor.to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)[0].cpu().numpy()
    masks = (probs >= threshold).astype(np.uint8) * 255

    sample_dir = out_dir / char_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, mask in enumerate(masks, start=1):
        mask_path = sample_dir / f"pred_{idx:02d}.png"
        cv2.imwrite(str(mask_path), mask)
        rows.append(
            {
                "char_id": char_id,
                "channel": idx,
                "mask_path": str(mask_path),
                "foreground_px": int((mask > 0).sum()),
                "mean_prob": f"{float(probs[idx - 1].mean()):.6f}",
                "max_prob": f"{float(probs[idx - 1].max()):.6f}",
            }
        )
    overlay_path = sample_dir / "overlay.png"
    make_overlay(image, masks, overlay_path, f"{char_id} predicted ordered masks")
    return rows, overlay_path


def choose_samples(args) -> List[tuple[str, Path]]:
    if args.image:
        image_path = Path(args.image)
        char_id = args.char_id or image_path.stem
        return [(char_id, image_path)]
    samples = load_manifest(Path(args.manifest))
    selected = [(sample.char_id, sample.image_path) for sample in samples if sample.split == args.split]
    if args.limit is not None:
        selected = selected[: args.limit]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict ordered stroke masks")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--image", default=None, help="Optional single glyph image path")
    parser.add_argument("--char-id", default=None)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint = load_model(Path(args.model), device)
    image_size = int(checkpoint.get("image_size", 256))
    threshold = resolve_threshold(args.threshold, checkpoint)
    print(f"threshold={threshold}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    overlays = []
    for char_id, image_path in choose_samples(args):
        rows, overlay_path = predict_one(model, image_path, out_dir, image_size, threshold, device, char_id)
        all_rows.extend(rows)
        overlays.append(overlay_path)
        print(f"predicted {char_id}: overlay={overlay_path}")

    summary_path = out_dir / "prediction_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["char_id", "channel", "mask_path", "foreground_px", "mean_prob", "max_prob"],
        )
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"wrote summary: {summary_path}")
    print(f"samples={len(overlays)} channels={len(all_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
