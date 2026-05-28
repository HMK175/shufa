"""Teacher-forced prediction for the next-stroke segmentation experiment."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch

from stroke_next_model import (
    StrokeNextDataset,
    StrokeNextUNet,
    build_next_stroke_samples,
    next_dice_score,
    resolve_next_threshold,
    split_next_samples,
)
from stroke_seg_model import load_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_next_unet.pt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "output" / "stroke_next_predictions"


def load_model(model_path: Path, device):
    checkpoint = torch.load(model_path, map_location=device)
    model = StrokeNextUNet(
        in_channels=int(checkpoint.get("in_channels", 3)),
        base_channels=int(checkpoint.get("base_channels", 16)),
    ).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint


def _make_overlay(image: np.ndarray, mask: np.ndarray, color: tuple[float, float, float]) -> np.ndarray:
    base = np.stack([image, image, image], axis=-1).astype(np.float32) / 255.0
    active = mask > 0
    out = base.copy()
    out[active] = out[active] * 0.45 + np.array(color, dtype=np.float32) * 0.55
    return np.clip(out, 0, 1)


def _write_sequence_preview(char_id: str, rows: list[dict], out_path: Path) -> None:
    cols = min(4, len(rows))
    fig = Figure(figsize=(cols * 3.0, len(rows) * 2.4), dpi=120)
    canvas = FigureCanvas(fig)
    for idx, row in enumerate(rows):
        y0 = 1.0 - (idx + 1) / len(rows)
        height = 0.86 / len(rows)
        panels = [
            ("full", row["full_rgb"]),
            ("previous", row["prev_rgb"]),
            (f"gt {row['stroke_index']}", row["gt_rgb"]),
            (f"pred dice={row['dice']:.2f}", row["pred_rgb"]),
        ]
        for col, (title, image) in enumerate(panels):
            ax = fig.add_axes([col / 4 + 0.015, y0 + 0.02, 0.22, height])
            ax.imshow(image)
            ax.set_title(title, fontsize=8)
            ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def predict(args) -> int:
    manifest = Path(args.manifest)
    glyph_samples = load_manifest(manifest)
    stroke_samples = split_next_samples(build_next_stroke_samples(glyph_samples), args.split)
    if args.limit_chars is not None:
        selected_ids = []
        for sample in stroke_samples:
            if sample.char_id not in selected_ids:
                selected_ids.append(sample.char_id)
            if len(selected_ids) >= args.limit_chars:
                break
        stroke_samples = [sample for sample in stroke_samples if sample.char_id in set(selected_ids)]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint = load_model(Path(args.model), device)
    image_size = int(checkpoint.get("image_size", 256))
    threshold = resolve_next_threshold(args.threshold, checkpoint)
    dataset = StrokeNextDataset(stroke_samples, image_size=image_size)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    preview_rows: dict[str, list[dict]] = defaultdict(list)
    with torch.no_grad():
        for item in dataset:
            char_id = str(item["char_id"])
            stroke_index = int(item["stroke_index"])
            sample_dir = out_dir / char_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            inputs = item["input"].unsqueeze(0).to(device)
            target = item["target"].unsqueeze(0)
            logits = model(inputs).cpu()
            probs = torch.sigmoid(logits)[0, 0].numpy()
            pred = (probs >= threshold).astype(np.uint8) * 255
            dice = float(next_dice_score(logits, target, threshold=threshold).mean().item())

            mask_path = sample_dir / f"pred_{stroke_index:02d}.png"
            cv2.imwrite(str(mask_path), pred)
            summary_rows.append(
                {
                    "char_id": char_id,
                    "stroke_index": stroke_index,
                    "stroke_count": int(item["stroke_count"]),
                    "dice": f"{dice:.6f}",
                    "pred_foreground_px": int((pred > 0).sum()),
                    "target_foreground_px": int(item["target"].sum().item()),
                    "mask_path": str(mask_path),
                    "threshold": f"{threshold:.3f}",
                }
            )

            full = ((1.0 - item["input"][0].numpy()) * 255).astype(np.uint8)
            prev = (item["input"][1].numpy() * 255).astype(np.uint8)
            gt = (item["target"][0].numpy() * 255).astype(np.uint8)
            preview_rows[char_id].append(
                {
                    "stroke_index": stroke_index,
                    "dice": dice,
                    "full_rgb": np.stack([full, full, full], axis=-1),
                    "prev_rgb": _make_overlay(full, prev, (0.2, 0.4, 1.0)),
                    "gt_rgb": _make_overlay(full, gt, (0.0, 0.7, 0.2)),
                    "pred_rgb": _make_overlay(full, pred, (0.9, 0.2, 0.2)),
                }
            )

    per_char = {}
    for row in summary_rows:
        per_char.setdefault(row["char_id"], []).append(float(row["dice"]))
    for char_id, dice_values in per_char.items():
        for row in summary_rows:
            if row["char_id"] == char_id:
                row["char_mean_dice"] = f"{float(np.mean(dice_values)):.6f}"

    for char_id, rows in preview_rows.items():
        rows.sort(key=lambda row: row["stroke_index"])
        _write_sequence_preview(char_id, rows, out_dir / char_id / "sequence_preview.png")

    summary_path = out_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "char_id",
                "stroke_index",
                "stroke_count",
                "dice",
                "char_mean_dice",
                "pred_foreground_px",
                "target_foreground_px",
                "mask_path",
                "threshold",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"threshold={threshold}")
    print(f"stroke_samples={len(stroke_samples)} chars={len(preview_rows)}")
    print(f"mean_dice={np.mean([float(row['dice']) for row in summary_rows]) if summary_rows else 0.0:.4f}")
    print(f"wrote summary: {summary_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict next-stroke masks with teacher-forced previous masks")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--limit-chars", type=int, default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    raise SystemExit(predict(args))


if __name__ == "__main__":
    main()
