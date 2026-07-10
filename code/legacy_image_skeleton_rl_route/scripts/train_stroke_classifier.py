"""Train a stroke type classifier from reviewed class folders."""

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Sequence, Tuple

import cv2
import numpy as np

try:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset, Subset
except ImportError:  # pragma: no cover
    torch = None
    DataLoader = None
    Dataset = object
    Subset = None

from stroke_classifier import StrokeClassifier


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR / "stroke_cls_dataset"
DEFAULT_OUT = SCRIPT_DIR / "models" / "stroke_classifier.pt"
DEFAULT_CLASSES_JSON = SCRIPT_DIR / "models" / "stroke_classifier_classes.json"
ALL_CLASSES = ["heng", "shu", "pie", "na", "dian", "ti", "zhe", "unknown"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def discover_samples(data_dir: Path) -> Tuple[List[str], List[Tuple[Path, int]]]:
    classes = []
    samples: List[Tuple[Path, int]] = []
    for class_name in ALL_CLASSES:
        class_dir = data_dir / class_name
        if not class_dir.exists():
            continue
        images = sorted(path for path in class_dir.iterdir() if path.suffix.lower() in IMAGE_EXTS)
        if not images:
            continue
        class_idx = len(classes)
        classes.append(class_name)
        for path in images:
            samples.append((path, class_idx))
    return classes, samples


def make_split(samples: Sequence[Tuple[Path, int]], val_ratio: float = 0.25, seed: int = 42):
    by_class = defaultdict(list)
    for idx, (_, label) in enumerate(samples):
        by_class[label].append(idx)

    rng = random.Random(seed)
    train_indices = []
    val_indices = []
    for label, indices in by_class.items():
        indices = list(indices)
        rng.shuffle(indices)
        if len(indices) >= 2:
            val_count = max(1, int(round(len(indices) * val_ratio)))
            val_count = min(val_count, len(indices) - 1)
            val_indices.extend(indices[:val_count])
            train_indices.extend(indices[val_count:])
        else:
            train_indices.extend(indices)

    if not val_indices and len(samples) >= 2:
        val_indices.append(train_indices.pop())
    return train_indices, val_indices


class StrokeClassDataset(Dataset):
    def __init__(self, samples: Sequence[Tuple[Path, int]], image_size: int):
        self.samples = list(samples)
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"image not readable: {path}")
        image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        # Invert so stroke foreground has high activation.
        image = 1.0 - (image.astype(np.float32) / 255.0)
        tensor = torch.from_numpy(image).unsqueeze(0)
        return tensor, int(label)


def _eval_stats(model, loader, device, num_classes: int):
    if loader is None or len(loader.dataset) == 0:
        return None
    correct = 0
    total = 0
    confusion = torch.zeros((num_classes, num_classes), dtype=torch.int64)
    model.eval()
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            pred = logits.argmax(dim=1)
            correct += int((pred == labels).sum().item())
            total += int(labels.numel())
            for truth, guess in zip(labels.cpu(), pred.cpu()):
                confusion[int(truth), int(guess)] += 1
    if not total:
        return None
    per_class = []
    for i in range(num_classes):
        row_total = int(confusion[i].sum().item())
        row_correct = int(confusion[i, i].item())
        per_class.append(None if row_total == 0 else row_correct / row_total)
    return {
        "accuracy": correct / total,
        "confusion": confusion,
        "per_class_accuracy": per_class,
    }


def _accuracy(model, loader, device, num_classes: int):
    stats = _eval_stats(model, loader, device, num_classes)
    return None if stats is None else stats["accuracy"]


def _print_eval_details(prefix: str, classes: Sequence[str], stats) -> None:
    if stats is None:
        print(f"{prefix}_accuracy=n/a")
        return
    print(f"{prefix}_accuracy={stats['accuracy']:.3f}")
    print(f"{prefix}_per_class_accuracy:")
    for class_name, acc in zip(classes, stats["per_class_accuracy"]):
        text = "n/a" if acc is None else f"{acc:.3f}"
        print(f"  {class_name}: {text}")
    print(f"{prefix}_confusion_matrix rows=true cols=pred")
    header = "true\\pred," + ",".join(classes)
    print(header)
    confusion = stats["confusion"]
    for i, class_name in enumerate(classes):
        row = [str(int(confusion[i, j].item())) for j in range(len(classes))]
        print(class_name + "," + ",".join(row))


def train(args) -> int:
    if torch is None:
        print("PyTorch is not installed. Install torch before training.")
        return 2

    data_dir = Path(args.data_dir).resolve()
    classes, samples = discover_samples(data_dir)
    if not samples:
        print(f"No class images found in {data_dir}. Rebuild the dataset first.")
        return 0
    if len(classes) < 2:
        print(f"Need at least two non-empty classes for training, found: {classes}")
        return 0

    counts = Counter(label for _, label in samples)
    print(f"Using classes: {classes}")
    for class_name, idx in zip(classes, range(len(classes))):
        print(f"  {class_name}: {counts[idx]}")

    dataset = StrokeClassDataset(samples, image_size=args.image_size)
    train_indices, val_indices = make_split(samples, val_ratio=args.val_ratio, seed=args.seed)
    train_loader = DataLoader(Subset(dataset, train_indices), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(Subset(dataset, val_indices), batch_size=args.batch_size, shuffle=False) if val_indices else None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StrokeClassifier(num_classes=len(classes)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    last_train_acc = 0.0
    last_val_acc = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        seen = 0
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = F.cross_entropy(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * labels.numel()
            seen += int(labels.numel())
        last_train_acc = _accuracy(model, train_loader, device, len(classes)) or 0.0
        last_val_acc = _accuracy(model, val_loader, device, len(classes))
        avg_loss = total_loss / seen if seen else 0.0
        val_text = "n/a" if last_val_acc is None else f"{last_val_acc:.3f}"
        print(
            f"epoch {epoch}/{args.epochs}: loss={avg_loss:.4f} "
            f"train_acc={last_train_acc:.3f} val_acc={val_text}"
        )

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    train_stats = _eval_stats(model, train_loader, device, len(classes))
    val_stats = _eval_stats(model, val_loader, device, len(classes))
    last_train_acc = train_stats["accuracy"] if train_stats else 0.0
    last_val_acc = val_stats["accuracy"] if val_stats else None
    checkpoint = {
        "model_state": model.state_dict(),
        "classes": classes,
        "image_size": args.image_size,
        "train_accuracy": last_train_acc,
        "val_accuracy": last_val_acc,
        "val_per_class_accuracy": None if val_stats is None else {
            class_name: acc for class_name, acc in zip(classes, val_stats["per_class_accuracy"])
        },
        "val_confusion_matrix": None if val_stats is None else val_stats["confusion"].tolist(),
    }
    torch.save(checkpoint, out_path)
    classes_json = Path(args.classes_json).resolve()
    classes_json.parent.mkdir(parents=True, exist_ok=True)
    classes_json.write_text(json.dumps({"classes": classes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved model: {out_path}")
    print(f"Saved classes: {classes_json}")
    print(f"final_train_accuracy={last_train_acc:.3f}")
    print(f"final_val_accuracy={'n/a' if last_val_acc is None else f'{last_val_acc:.3f}'}")
    _print_eval_details("final_val", classes, val_stats)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Train stroke type classifier")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--classes-json", default=str(DEFAULT_CLASSES_JSON))
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-ratio", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    raise SystemExit(train(args))


if __name__ == "__main__":
    main()
