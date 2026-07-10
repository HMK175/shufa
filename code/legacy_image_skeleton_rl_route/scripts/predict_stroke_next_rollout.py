"""Compare teacher-forced and autoregressive next-stroke rollout."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch

from predict_stroke_next_model import load_model
from stroke_next_model import (
    _read_foreground,
    build_next_stroke_samples,
    compute_remaining_mask,
    next_dice_score,
    resolve_next_threshold,
)
from stroke_seg_model import load_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_next_unet.pt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "output" / "stroke_next_rollout"


@dataclass
class RolloutState:
    previous_mask: np.ndarray

    @classmethod
    def empty(cls, image_size: int) -> "RolloutState":
        return cls(previous_mask=np.zeros((image_size, image_size), dtype=np.float32))


def update_previous_mask(previous: np.ndarray, pred_mask: np.ndarray, mode: str = "union") -> np.ndarray:
    pred = (pred_mask > 0).astype(np.float32)
    if mode == "replace":
        return pred
    return np.maximum(previous.astype(np.float32), pred)


def build_rollout_input(
    full: np.ndarray,
    gt_previous: np.ndarray,
    pred_previous: np.ndarray,
    stroke_index: int,
    stroke_count: int,
    mode: str,
    use_remaining_channel: bool = False,
    remaining_previous_dilate: int = 0,
) -> torch.Tensor:
    previous = gt_previous if mode == "teacher_forcing" else pred_previous
    progress = float(stroke_index) / max(1.0, float(stroke_count))
    step_map = np.full_like(full, progress, dtype=np.float32)
    channels = [full, previous.astype(np.float32)]
    if use_remaining_channel:
        channels.append(compute_remaining_mask(full, previous, remaining_previous_dilate))
    channels.append(step_map)
    stacked = np.stack(channels, axis=0).astype(np.float32)
    return torch.from_numpy(stacked).unsqueeze(0)


def make_summary_row(
    char_id: str,
    stroke_index: int,
    stroke_count: int,
    teacher_dice: float,
    autoregressive_dice: float,
    pred_fg_ratio: float,
    accumulated_coverage: float,
    overlap_ratio: float,
    overflow_ratio: float,
    mask_path: str,
    threshold: float,
) -> dict:
    return {
        "char_id": char_id,
        "stroke_index": stroke_index,
        "stroke_count": stroke_count,
        "teacher_dice": f"{teacher_dice:.6f}",
        "autoregressive_dice": f"{autoregressive_dice:.6f}",
        "dice_drop": f"{teacher_dice - autoregressive_dice:.6f}",
        "pred_fg_ratio": f"{pred_fg_ratio:.6f}",
        "accumulated_previous_coverage": f"{accumulated_coverage:.6f}",
        "overlap_ratio": f"{overlap_ratio:.6f}",
        "overflow_ratio": f"{overflow_ratio:.6f}",
        "mask_path": mask_path,
        "threshold": f"{threshold:.3f}",
    }


def _mode_value(args, field: str, value: float | None) -> float:
    if args.mode == "teacher_forcing" and field == "autoregressive":
        return 0.0
    if args.mode == "autoregressive" and field == "teacher":
        return 0.0
    return 0.0 if value is None else float(value)


def apply_remaining_constraint(
    pred_mask: np.ndarray,
    full: np.ndarray,
    previous: np.ndarray,
    previous_dilate: int = 0,
) -> np.ndarray:
    remaining = compute_remaining_mask(full, previous, previous_dilate)
    return np.where(remaining > 0.5, pred_mask, 0).astype(np.uint8)


def _mask_overlay(image: np.ndarray, mask: np.ndarray, color: tuple[float, float, float]) -> np.ndarray:
    base = np.stack([image, image, image], axis=-1).astype(np.float32) / 255.0
    active = mask > 0
    out = base.copy()
    out[active] = out[active] * 0.45 + np.array(color, dtype=np.float32) * 0.55
    return np.clip(out, 0, 1)


def _diff_rgb(gt: np.ndarray, pred: np.ndarray) -> np.ndarray:
    gt_bool = gt > 0
    pred_bool = pred > 0
    out = np.zeros((*gt.shape, 3), dtype=np.float32)
    out[gt_bool & pred_bool] = [0.1, 0.7, 0.1]
    out[gt_bool & ~pred_bool] = [0.9, 0.1, 0.1]
    out[~gt_bool & pred_bool] = [0.1, 0.2, 0.9]
    return out


def _write_rollout_preview(char_id: str, rows: list[dict], out_path: Path) -> None:
    fig = Figure(figsize=(16.5, max(2.4, len(rows) * 2.2)), dpi=120)
    canvas = FigureCanvas(fig)
    titles = ["full", "pred previous", "remaining", "GT current", "pred current", "diff"]
    for row_idx, row in enumerate(rows):
        y0 = 1.0 - (row_idx + 1) / len(rows)
        height = 0.84 / len(rows)
        panels = [
            row["full_rgb"],
            row["pred_previous_rgb"],
            row["remaining_rgb"],
            row["gt_current_rgb"],
            row["pred_current_rgb"],
            row["diff_rgb"],
        ]
        for col, image in enumerate(panels):
            ax = fig.add_axes([0.01 + col * 0.163, y0 + 0.02, 0.15, height])
            ax.imshow(image)
            ax.set_title(f"k={row['stroke_index']} {titles[col]}", fontsize=8)
            ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def _load_strokes_for_char(stroke_samples: list) -> dict[str, list]:
    by_char: dict[str, list] = defaultdict(list)
    for sample in stroke_samples:
        by_char[sample.char_id].append(sample)
    for rows in by_char.values():
        rows.sort(key=lambda sample: sample.stroke_index)
    return by_char


def _gt_previous(mask_dir: Path, stroke_index: int, image_size: int) -> np.ndarray:
    previous = np.zeros((image_size, image_size), dtype=np.float32)
    for idx in range(1, stroke_index):
        previous = np.maximum(previous, _read_foreground(mask_dir / f"{idx:02d}.png", image_size, nearest=True))
    return previous


def _predict_mask(model, full, gt_previous, pred_previous, sample, mode, threshold, device, checkpoint):
    input_tensor = build_rollout_input(
        full,
        gt_previous,
        pred_previous,
        sample.stroke_index,
        sample.stroke_count,
        mode=mode,
        use_remaining_channel=bool(checkpoint.get("in_channels", 3) == 4),
        remaining_previous_dilate=int(checkpoint.get("remaining_previous_dilate", 0)),
    ).to(device)
    with torch.no_grad():
        logits = model(input_tensor).cpu()
    prob = torch.sigmoid(logits)[0, 0].numpy()
    pred = (prob >= threshold).astype(np.uint8) * 255
    return logits, pred


def _binary_dice(pred_mask: np.ndarray, target: np.ndarray, eps: float = 1e-6) -> float:
    pred = (pred_mask > 0).astype(np.float32)
    tgt = (target > 0.5).astype(np.float32)
    intersection = float((pred * tgt).sum())
    denom = float(pred.sum() + tgt.sum())
    return (2.0 * intersection + eps) / (denom + eps)


def run_rollout(args) -> int:
    manifest = Path(args.manifest)
    glyph_samples = load_manifest(manifest)
    stroke_samples = [s for s in build_next_stroke_samples(glyph_samples) if s.split == args.split]
    by_char = _load_strokes_for_char(stroke_samples)
    if args.limit_chars is not None:
        keep = set(list(by_char.keys())[: args.limit_chars])
        by_char = {key: value for key, value in by_char.items() if key in keep}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint = load_model(Path(args.model), device)
    image_size = int(checkpoint.get("image_size", 256))
    threshold = resolve_next_threshold(args.threshold, checkpoint)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    char_rows = []
    for char_id, rows in by_char.items():
        if not rows:
            continue
        first = rows[0]
        full = _read_foreground(first.image_path, image_size, nearest=False)
        full_gray = ((1.0 - full) * 255).astype(np.uint8)
        pred_previous = np.zeros((image_size, image_size), dtype=np.float32)
        char_preview_rows = []
        auto_dice_values = []
        teacher_dice_values = []
        overlap_values = []
        overflow_values = []
        sample_dir = out_dir / char_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        for sample in rows:
            gt_previous = _gt_previous(sample.mask_dir, sample.stroke_index, image_size)
            target = _read_foreground(sample.target_mask_path, image_size, nearest=True)

            teacher_logits = teacher_pred = None
            auto_logits = auto_pred = None
            if args.mode in {"teacher_forcing", "both"}:
                teacher_logits, teacher_pred = _predict_mask(
                    model, full, gt_previous, pred_previous, sample, "teacher_forcing", threshold, device, checkpoint
                )
            if args.mode in {"autoregressive", "both"}:
                auto_logits, auto_pred = _predict_mask(
                    model, full, gt_previous, pred_previous, sample, "autoregressive", threshold, device, checkpoint
                )
            target_tensor = torch.from_numpy(target[None, None, ...].astype(np.float32))
            teacher_dice = (
                float(next_dice_score(teacher_logits, target_tensor, threshold=threshold).mean().item())
                if teacher_logits is not None
                else None
            )
            pred_previous_before = pred_previous.copy()
            effective_auto_pred = auto_pred if auto_pred is not None else teacher_pred
            if effective_auto_pred is None:
                effective_auto_pred = np.zeros_like(target, dtype=np.uint8)
            if args.constrain_remaining:
                effective_auto_pred = apply_remaining_constraint(
                    effective_auto_pred,
                    full,
                    pred_previous,
                    previous_dilate=args.constraint_previous_dilate,
                )
            auto_dice = _binary_dice(effective_auto_pred, target) if auto_logits is not None else None
            overlap = np.logical_and(pred_previous > 0.5, effective_auto_pred > 0).sum() / max(1, (effective_auto_pred > 0).sum())
            target_union = np.maximum(gt_previous, target)
            overflow = np.logical_and(effective_auto_pred > 0, target_union <= 0.5).sum() / max(1, (effective_auto_pred > 0).sum())
            pred_fg_ratio = float((effective_auto_pred > 0).mean())
            if args.mode in {"autoregressive", "both"}:
                pred_previous = update_previous_mask(pred_previous, effective_auto_pred, mode=args.previous_update)
            accumulated_coverage = float((pred_previous > 0.5).mean())

            mask_path = sample_dir / f"{args.mode}_pred_{sample.stroke_index:02d}.png"
            cv2.imwrite(str(mask_path), effective_auto_pred)
            summary_rows.append(
                make_summary_row(
                    char_id=char_id,
                    stroke_index=sample.stroke_index,
                    stroke_count=sample.stroke_count,
                    teacher_dice=_mode_value(args, "teacher", teacher_dice),
                    autoregressive_dice=_mode_value(args, "autoregressive", auto_dice),
                    pred_fg_ratio=pred_fg_ratio,
                    accumulated_coverage=accumulated_coverage,
                    overlap_ratio=float(overlap),
                    overflow_ratio=float(overflow),
                    mask_path=str(mask_path),
                    threshold=threshold,
                )
            )
            if auto_dice is not None:
                auto_dice_values.append(auto_dice)
            if teacher_dice is not None:
                teacher_dice_values.append(teacher_dice)
            overlap_values.append(float(overlap))
            overflow_values.append(float(overflow))
            char_preview_rows.append(
                {
                    "stroke_index": sample.stroke_index,
                    "full_rgb": np.stack([full_gray, full_gray, full_gray], axis=-1),
                    "pred_previous_rgb": _mask_overlay(full_gray, (pred_previous_before * 255).astype(np.uint8), (0.5, 0.2, 0.9)),
                    "remaining_rgb": _mask_overlay(
                        full_gray,
                        (compute_remaining_mask(full, pred_previous_before, args.constraint_previous_dilate) * 255).astype(np.uint8),
                        (0.1, 0.55, 0.9),
                    ),
                    "gt_current_rgb": _mask_overlay(full_gray, (target * 255).astype(np.uint8), (0.0, 0.7, 0.2)),
                    "pred_current_rgb": _mask_overlay(full_gray, effective_auto_pred, (0.9, 0.2, 0.2)),
                    "diff_rgb": _diff_rgb((target * 255).astype(np.uint8), effective_auto_pred),
                }
            )
        preview_path = sample_dir / "rollout_preview.png"
        _write_rollout_preview(char_id, char_preview_rows, preview_path)
        char_rows.append(
            {
                "char_id": char_id,
                "stroke_count": len(rows),
                "teacher_mean_dice": f"{float(np.mean(teacher_dice_values)):.6f}" if teacher_dice_values else "",
                "autoregressive_mean_dice": f"{float(np.mean(auto_dice_values)):.6f}" if auto_dice_values else "",
                "dice_drop": f"{float(np.mean(teacher_dice_values) - np.mean(auto_dice_values)):.6f}"
                if teacher_dice_values and auto_dice_values
                else "",
                "mean_overlap_ratio": f"{float(np.mean(overlap_values)):.6f}",
                "mean_overflow_ratio": f"{float(np.mean(overflow_values)):.6f}",
                "preview_path": str(preview_path),
            }
        )

    for row in summary_rows:
        char_id = row["char_id"]
        match = next((c for c in char_rows if c["char_id"] == char_id), None)
        if match:
            row["teacher_char_mean_dice"] = match["teacher_mean_dice"]
            row["autoregressive_char_mean_dice"] = match["autoregressive_mean_dice"]
            row["char_dice_drop"] = match["dice_drop"]

    summary_path = out_dir / "rollout_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "char_id",
            "stroke_index",
            "stroke_count",
            "teacher_dice",
            "autoregressive_dice",
            "dice_drop",
            "teacher_char_mean_dice",
            "autoregressive_char_mean_dice",
            "char_dice_drop",
            "pred_fg_ratio",
            "accumulated_previous_coverage",
            "overlap_ratio",
            "overflow_ratio",
            "mask_path",
            "threshold",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    char_summary_path = out_dir / "rollout_char_summary.csv"
    with char_summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "char_id",
                "stroke_count",
                "teacher_mean_dice",
                "autoregressive_mean_dice",
                "dice_drop",
                "mean_overlap_ratio",
                "mean_overflow_ratio",
                "preview_path",
            ],
        )
        writer.writeheader()
        writer.writerows(char_rows)

    teacher_values = [float(r["teacher_dice"]) for r in summary_rows if r["teacher_dice"]]
    auto_values = [float(r["autoregressive_dice"]) for r in summary_rows if r["autoregressive_dice"]]
    teacher_mean = float(np.mean(teacher_values)) if teacher_values else 0.0
    auto_mean = float(np.mean(auto_values)) if auto_values else 0.0
    print(f"threshold={threshold}")
    print(f"chars={len(char_rows)} stroke_steps={len(summary_rows)}")
    print(f"teacher_forcing_mean_dice={teacher_mean:.4f}")
    print(f"autoregressive_mean_dice={auto_mean:.4f}")
    print(f"dice_drop={teacher_mean - auto_mean:.4f}")
    print(f"wrote summary: {summary_path}")
    print(f"wrote char summary: {char_summary_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate next-stroke teacher-forcing vs autoregressive rollout")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--mode", choices=["both", "teacher_forcing", "autoregressive"], default="both")
    parser.add_argument("--limit-chars", type=int, default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--previous-update", choices=["union", "replace"], default="union")
    parser.add_argument("--constrain-remaining", action="store_true")
    parser.add_argument("--constraint-previous-dilate", type=int, default=0)
    args = parser.parse_args()
    raise SystemExit(run_rollout(args))


if __name__ == "__main__":
    main()
