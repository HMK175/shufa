"""Train a lightweight ordered stroke-mask segmentation baseline."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, Sequence

import cv2
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from stroke_seg_model import (
    StrokeSegAugmentConfig,
    StrokeSegDataset,
    StrokeSegUNet,
    dice_score_per_channel,
    infer_max_strokes,
    load_manifest,
    soft_dice_loss,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_OUT = SCRIPT_DIR / "models" / "stroke_seg_unet.pt"
DEFAULT_DEBUG_DIR = SCRIPT_DIR / "output" / "stroke_seg_debug"
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]


def _split_samples(samples, split: str):
    return [sample for sample in samples if sample.split == split]


def _collate(batch):
    return {
        "image": torch.stack([item["image"] for item in batch], dim=0),
        "masks": torch.stack([item["masks"] for item in batch], dim=0),
        "stroke_count": torch.tensor([int(item["stroke_count"]) for item in batch], dtype=torch.long),
        "char_id": [str(item["char_id"]) for item in batch],
        "char": [str(item["char"]) for item in batch],
        "image_path": [str(item["image_path"]) for item in batch],
    }


def _make_loader(samples, max_strokes: int, image_size: int, batch_size: int, shuffle: bool, augment: bool = False):
    if not samples:
        return None
    dataset = StrokeSegDataset(samples, max_strokes=max_strokes, image_size=image_size, augment=augment)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=_collate)


def weighted_bce_loss(logits: torch.Tensor, targets: torch.Tensor, pos_weight: float = 8.0, empty_channel_weight: float = 0.2) -> torch.Tensor:
    """Foreground-weighted BCE with reduced weight for target-empty channels.

    Empty channels remain in the loss as background constraints, but they are
    down-weighted so the model cannot optimize mostly by predicting all zeros.
    """
    raw = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    weights = torch.ones_like(targets)
    weights = torch.where(targets > 0.5, weights * pos_weight, weights)
    channel_has_fg = targets.flatten(2).sum(dim=2) > 0
    empty_weights = torch.where(
        channel_has_fg[:, :, None, None],
        torch.ones_like(weights),
        torch.full_like(weights, empty_channel_weight),
    )
    weights = weights * empty_weights
    return (raw * weights).sum() / weights.sum().clamp_min(1.0)


def segmentation_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    dice_weight: float = 0.5,
    pos_weight: float = 8.0,
    empty_channel_weight: float = 0.2,
    loss_mode: str = "dice",
    focal_gamma: float = 2.0,
    tversky_alpha: float = 0.7,
    tversky_beta: float = 0.3,
) -> torch.Tensor:
    bce = weighted_bce_loss(logits, targets, pos_weight, empty_channel_weight)
    if loss_mode == "focal":
        shape_loss = focal_loss(logits, targets, pos_weight, empty_channel_weight, gamma=focal_gamma)
    elif loss_mode == "tversky":
        shape_loss = tversky_loss(logits, targets, alpha=tversky_alpha, beta=tversky_beta)
    else:
        shape_loss = soft_dice_loss(logits, targets)
    return bce + dice_weight * shape_loss


def focal_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    pos_weight: float = 8.0,
    empty_channel_weight: float = 0.2,
    gamma: float = 2.0,
) -> torch.Tensor:
    raw = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    probs = torch.sigmoid(logits)
    pt = torch.where(targets > 0.5, probs, 1.0 - probs)
    focal = raw * (1.0 - pt).clamp_min(0.0).pow(gamma)
    weights = torch.ones_like(targets)
    weights = torch.where(targets > 0.5, weights * pos_weight, weights)
    channel_has_fg = targets.flatten(2).sum(dim=2) > 0
    empty_weights = torch.where(
        channel_has_fg[:, :, None, None],
        torch.ones_like(weights),
        torch.full_like(weights, empty_channel_weight),
    )
    weights = weights * empty_weights
    return (focal * weights).sum() / weights.sum().clamp_min(1.0)


def tversky_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    alpha: float = 0.7,
    beta: float = 0.3,
    eps: float = 1e-6,
) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    dims = (0, 2, 3)
    tp = (probs * targets).sum(dim=dims)
    fp = (probs * (1.0 - targets)).sum(dim=dims)
    fn = ((1.0 - probs) * targets).sum(dim=dims)
    score = (tp + eps) / (tp + alpha * fn + beta * fp + eps)
    valid = targets.sum(dim=dims) > 0
    if valid.any():
        return 1.0 - score[valid].mean()
    return logits.new_tensor(0.0)


def foreground_ratios(mask_tensor: torch.Tensor) -> torch.Tensor:
    return mask_tensor.float().flatten(1).mean(dim=1)


def threshold_sweep(logits: torch.Tensor, targets: torch.Tensor, thresholds: Sequence[float] = THRESHOLDS) -> Dict[float, float]:
    scores: Dict[float, float] = {}
    for threshold in thresholds:
        dice, valid = dice_score_per_channel(logits.cpu(), targets.cpu(), threshold=threshold)
        if valid.any():
            scores[float(threshold)] = float(dice[valid].mean().item())
        else:
            scores[float(threshold)] = 0.0
    return scores


def evaluate(
    model,
    loader,
    device,
    max_strokes: int,
    dice_weight: float = 0.5,
    pos_weight: float = 8.0,
    empty_channel_weight: float = 0.2,
    loss_mode: str = "dice",
    focal_gamma: float = 2.0,
    tversky_alpha: float = 0.7,
    tversky_beta: float = 0.3,
    thresholds: Sequence[float] = THRESHOLDS,
) -> Dict[str, object]:
    if loader is None:
        return {
            "loss": None,
            "mean_dice": None,
            "per_channel_dice": [None] * max_strokes,
            "target_fg_ratio": None,
            "pred_fg_ratio": None,
            "nearly_zero_channels": [None] * max_strokes,
            "threshold_sweep": {float(t): None for t in thresholds},
        }
    model.eval()
    total_loss = 0.0
    total_seen = 0
    dice_sum = torch.zeros(max_strokes, dtype=torch.float64)
    dice_count = torch.zeros(max_strokes, dtype=torch.float64)
    pred_fg_sum = 0.0
    target_fg_sum = 0.0
    sample_count = 0
    pred_channel_fg_sum = torch.zeros(max_strokes, dtype=torch.float64)
    sweep_sum = {float(t): 0.0 for t in thresholds}
    sweep_count = {float(t): 0 for t in thresholds}
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device)
            targets = batch["masks"].to(device)
            logits = model(images)
            loss = segmentation_loss(
                logits,
                targets,
                dice_weight,
                pos_weight,
                empty_channel_weight,
                loss_mode,
                focal_gamma,
                tversky_alpha,
                tversky_beta,
            )
            total_loss += float(loss.item()) * images.shape[0]
            total_seen += int(images.shape[0])
            dice, valid = dice_score_per_channel(logits.cpu(), targets.cpu())
            dice_sum[valid] += dice[valid].double()
            dice_count[valid] += 1
            probs = torch.sigmoid(logits)
            preds = (probs >= 0.5).float()
            pred_fg_sum += float(preds.mean().item()) * images.shape[0]
            target_fg_sum += float(targets.mean().item()) * images.shape[0]
            sample_count += int(images.shape[0])
            pred_channel_fg_sum += preds.cpu().flatten(2).mean(dim=2).sum(dim=0).double()
            sweep = threshold_sweep(logits, targets, thresholds)
            for threshold, score in sweep.items():
                sweep_sum[threshold] += score
                sweep_count[threshold] += 1

    per_channel = []
    for idx in range(max_strokes):
        if dice_count[idx] > 0:
            per_channel.append(float((dice_sum[idx] / dice_count[idx]).item()))
        else:
            per_channel.append(None)
    valid_values = [value for value in per_channel if value is not None]
    return {
        "loss": total_loss / total_seen if total_seen else None,
        "mean_dice": sum(valid_values) / len(valid_values) if valid_values else None,
        "per_channel_dice": per_channel,
        "target_fg_ratio": target_fg_sum / sample_count if sample_count else None,
        "pred_fg_ratio": pred_fg_sum / sample_count if sample_count else None,
        "nearly_zero_channels": [
            bool((pred_channel_fg_sum[idx] / sample_count).item() < 1e-4) if sample_count else None
            for idx in range(max_strokes)
        ],
        "threshold_sweep": {
            threshold: (sweep_sum[threshold] / sweep_count[threshold] if sweep_count[threshold] else None)
            for threshold in sweep_sum
        },
    }


def _format_optional(value) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _print_metrics(prefix: str, metrics: Dict[str, object]) -> None:
    print(
        f"{prefix}_loss={_format_optional(metrics['loss'])} "
        f"{prefix}_mean_dice={_format_optional(metrics['mean_dice'])} "
        f"{prefix}_target_fg={_format_optional(metrics.get('target_fg_ratio'))} "
        f"{prefix}_pred_fg={_format_optional(metrics.get('pred_fg_ratio'))}"
    )
    sweep = metrics.get("threshold_sweep") or {}
    if sweep:
        sweep_text = ", ".join(f"{threshold:.1f}:{_format_optional(value)}" for threshold, value in sweep.items())
        print(f"{prefix}_threshold_sweep={sweep_text}")
    per_channel = metrics["per_channel_dice"]
    print(f"{prefix}_per_channel_dice:")
    for idx, value in enumerate(per_channel, start=1):
        zero_flags = metrics.get("nearly_zero_channels") or []
        zero_text = " nearly_zero" if idx - 1 < len(zero_flags) and zero_flags[idx - 1] else ""
        print(f"  stroke_{idx:02d}: {_format_optional(value)}{zero_text}")


def _best_threshold(metrics: Dict[str, object]) -> float | None:
    sweep = metrics.get("threshold_sweep") or {}
    usable = [(float(k), v) for k, v in sweep.items() if v is not None]
    if not usable:
        return None
    return max(usable, key=lambda item: float(item[1]))[0]


def snapshot_state_dict(model) -> dict:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def write_overfit_curve(rows: Sequence[Dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["epoch", "loss", "mean_dice", "target_fg_ratio", "pred_fg_ratio"] + [
            f"dice_t{str(t).replace('.', '_')}" for t in THRESHOLDS
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metric_rows(rows: Sequence[Dict[str, object]], out_path: Path) -> None:
    if not rows:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_mask_overlay(image: np.ndarray, masks: np.ndarray) -> np.ndarray:
    base = np.stack([image, image, image], axis=-1).astype(np.float32) / 255.0
    colors = np.array([
        [0.121, 0.466, 0.705],
        [1.000, 0.498, 0.054],
        [0.172, 0.627, 0.172],
        [0.839, 0.153, 0.157],
        [0.580, 0.404, 0.741],
        [0.549, 0.337, 0.294],
        [0.890, 0.467, 0.761],
        [0.498, 0.498, 0.498],
        [0.737, 0.741, 0.133],
        [0.090, 0.745, 0.811],
    ])
    out = base.copy()
    for idx, mask in enumerate(masks):
        active = mask > 0
        if not active.any():
            continue
        color = colors[idx % len(colors)]
        out[active] = out[active] * 0.45 + color * 0.55
    return np.clip(out, 0.0, 1.0)


def save_debug_overlays(model, loader, device, out_dir: Path, threshold: float = 0.5, max_samples: int = 5) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    model.eval()
    written = 0
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device)
            targets = batch["masks"].cpu().numpy()
            probs = torch.sigmoid(model(images)).cpu().numpy()
            preds = (probs >= threshold).astype(np.float32)
            for idx, char_id in enumerate(batch["char_id"]):
                image = (1.0 - batch["image"][idx, 0].cpu().numpy()) * 255.0
                image = image.astype(np.uint8)
                gt_overlay = _make_mask_overlay(image, targets[idx] * 255.0)
                pred_overlay = _make_mask_overlay(image, preds[idx] * 255.0)
                diff = np.zeros((*image.shape, 3), dtype=np.float32)
                gt_any = targets[idx].max(axis=0) > 0.5
                pred_any = preds[idx].max(axis=0) > 0.5
                diff[gt_any & pred_any] = [0.1, 0.7, 0.1]
                diff[gt_any & ~pred_any] = [0.9, 0.1, 0.1]
                diff[~gt_any & pred_any] = [0.1, 0.2, 0.9]

                fig = Figure(figsize=(9.0, 3.2), dpi=130)
                canvas = FigureCanvas(fig)
                axes = [
                    fig.add_axes([0.02, 0.10, 0.30, 0.82]),
                    fig.add_axes([0.35, 0.10, 0.30, 0.82]),
                    fig.add_axes([0.68, 0.10, 0.30, 0.82]),
                ]
                axes[0].imshow(gt_overlay)
                axes[0].set_title("target")
                axes[1].imshow(pred_overlay)
                axes[1].set_title("prediction")
                axes[2].imshow(diff)
                axes[2].set_title("diff green=hit red=miss blue=extra")
                for ax in axes:
                    ax.axis("off")
                out_path = out_dir / f"{char_id}_debug_overlay.png"
                canvas.print_png(str(out_path))
                paths.append(out_path)
                written += 1
                if written >= max_samples:
                    return paths
    return paths


def train(args) -> int:
    start_time = time.perf_counter()
    manifest = Path(args.manifest)
    samples = load_manifest(manifest)
    if not samples:
        print(f"No samples found in manifest: {manifest}")
        return 2

    inferred_max = infer_max_strokes(samples)
    max_strokes = args.max_strokes or inferred_max
    train_samples = _split_samples(samples, "train")
    val_samples = _split_samples(samples, "val")
    test_samples = _split_samples(samples, "test")
    overfit_mode = args.overfit_count is not None and args.overfit_count > 0
    if overfit_mode:
        train_samples = train_samples[: args.overfit_count]
        val_samples = list(train_samples)
        test_samples = []
        print(f"overfit_mode=true overfit_count={len(train_samples)}")
    print(f"max_strokes={max_strokes} (inferred={inferred_max})")
    print(f"samples train={len(train_samples)} val={len(val_samples)} test={len(test_samples)}")
    print(
        "Empty channels: target tensors are all zero beyond each glyph's stroke_count; "
        f"they participate in BCE as background with weight={args.empty_channel_weight}."
    )
    print("Dice metrics only average channels that contain at least one foreground target in the evaluated split.")

    if not train_samples:
        print("No train split samples; cannot train.")
        return 2

    use_augment = bool(args.augment) and not overfit_mode
    print(f"augment={use_augment}")
    print(f"loss_mode={args.loss_mode}")

    train_loader = _make_loader(
        train_samples,
        max_strokes,
        args.image_size,
        args.batch_size,
        shuffle=True,
        augment=use_augment,
    )
    eval_train_loader = _make_loader(train_samples, max_strokes, args.image_size, args.batch_size, shuffle=False)
    val_loader = _make_loader(val_samples, max_strokes, args.image_size, args.batch_size, shuffle=False)
    test_loader = _make_loader(test_samples, max_strokes, args.image_size, args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StrokeSegUNet(max_strokes=max_strokes, in_channels=1, base_channels=args.base_channels).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_val = -1.0
    best_payload = None
    curve_rows = []
    train_rows = []
    val_rows = []
    epochs_without_improvement = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total_seen = 0
        for batch in train_loader:
            images = batch["image"].to(device)
            targets = batch["masks"].to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = segmentation_loss(
                logits,
                targets,
                args.dice_weight,
                args.pos_weight,
                args.empty_channel_weight,
                args.loss_mode,
                args.focal_gamma,
                args.tversky_alpha,
                args.tversky_beta,
            )
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * images.shape[0]
            total_seen += int(images.shape[0])

        train_metrics = evaluate(
            model,
            eval_train_loader,
            device,
            max_strokes,
            args.dice_weight,
            args.pos_weight,
            args.empty_channel_weight,
            args.loss_mode,
            args.focal_gamma,
            args.tversky_alpha,
            args.tversky_beta,
        )
        val_metrics = evaluate(
            model,
            val_loader,
            device,
            max_strokes,
            args.dice_weight,
            args.pos_weight,
            args.empty_channel_weight,
            args.loss_mode,
            args.focal_gamma,
            args.tversky_alpha,
            args.tversky_beta,
        )
        epoch_loss = total_loss / total_seen if total_seen else 0.0
        should_print = (not overfit_mode) or epoch == 1 or epoch == args.epochs or epoch % args.debug_interval == 0
        if should_print:
            print(f"epoch {epoch}/{args.epochs}: train_step_loss={epoch_loss:.4f}")
            _print_metrics("train", train_metrics)
            _print_metrics("val", val_metrics)

        if overfit_mode:
            sweep = train_metrics.get("threshold_sweep") or {}
            curve_row = {
                "epoch": epoch,
                "loss": _format_optional(train_metrics["loss"]),
                "mean_dice": _format_optional(train_metrics["mean_dice"]),
                "target_fg_ratio": _format_optional(train_metrics.get("target_fg_ratio")),
                "pred_fg_ratio": _format_optional(train_metrics.get("pred_fg_ratio")),
            }
            for threshold in THRESHOLDS:
                curve_row[f"dice_t{str(threshold).replace('.', '_')}"] = _format_optional(sweep.get(float(threshold)))
            curve_rows.append(curve_row)
        train_row = {
            "epoch": epoch,
            "step_loss": f"{epoch_loss:.6f}",
            "train_loss": _format_optional(train_metrics["loss"]),
            "train_mean_dice": _format_optional(train_metrics["mean_dice"]),
            "train_target_fg_ratio": _format_optional(train_metrics.get("target_fg_ratio")),
            "train_pred_fg_ratio": _format_optional(train_metrics.get("pred_fg_ratio")),
            "val_loss": _format_optional(val_metrics["loss"]),
            "val_mean_dice": _format_optional(val_metrics["mean_dice"]),
            "val_target_fg_ratio": _format_optional(val_metrics.get("target_fg_ratio")),
            "val_pred_fg_ratio": _format_optional(val_metrics.get("pred_fg_ratio")),
            "best_threshold": _best_threshold(val_metrics),
        }
        for threshold, value in (val_metrics.get("threshold_sweep") or {}).items():
            train_row[f"val_dice_t{str(threshold).replace('.', '_')}"] = _format_optional(value)
        train_rows.append(train_row)

        val_row = {"epoch": epoch, "mean_dice": _format_optional(val_metrics["mean_dice"])}
        for idx, value in enumerate(val_metrics["per_channel_dice"], start=1):
            val_row[f"stroke_{idx:02d}_dice"] = _format_optional(value)
        for threshold, value in (val_metrics.get("threshold_sweep") or {}).items():
            val_row[f"dice_t{str(threshold).replace('.', '_')}"] = _format_optional(value)
        val_rows.append(val_row)

        val_score = val_metrics["mean_dice"]
        score = -1.0 if val_score is None else float(val_score)
        if score > best_val:
            best_val = score
            epochs_without_improvement = 0
            best_payload = {
                "model_state": snapshot_state_dict(model),
                "max_strokes": max_strokes,
                "image_size": args.image_size,
                "base_channels": args.base_channels,
                "in_channels": 1,
                "train_samples": len(train_samples),
                "val_samples": len(val_samples),
                "test_samples": len(test_samples),
                "val_mean_dice": val_metrics["mean_dice"],
                "val_per_channel_dice": val_metrics["per_channel_dice"],
                "best_threshold": _best_threshold(val_metrics),
                "val_threshold_sweep": val_metrics["threshold_sweep"],
                "pos_weight": args.pos_weight,
                "empty_channel_weight": args.empty_channel_weight,
                "loss_mode": args.loss_mode,
                "focal_gamma": args.focal_gamma,
                "tversky_alpha": args.tversky_alpha,
                "tversky_beta": args.tversky_beta,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
                "augment": use_augment,
                "overfit_count": args.overfit_count,
            }
        else:
            epochs_without_improvement += 1
        if args.early_stopping_patience and epochs_without_improvement >= args.early_stopping_patience:
            print(
                f"early_stopping epoch={epoch} patience={args.early_stopping_patience} "
                f"best_val_mean_dice={best_val:.4f}"
            )
            break

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if best_payload is None:
        best_payload = {
            "model_state": snapshot_state_dict(model),
            "max_strokes": max_strokes,
            "image_size": args.image_size,
            "base_channels": args.base_channels,
            "in_channels": 1,
        }
    torch.save(best_payload, out_path)
    meta_path = out_path.with_suffix(".json")
    meta_path.write_text(json.dumps({k: v for k, v in best_payload.items() if k != "model_state"}, indent=2), encoding="utf-8")
    print(f"Saved best model: {out_path}")
    print(f"Saved metadata: {meta_path}")
    train_log_path = Path(args.train_log)
    val_metrics_path = Path(args.val_metrics)
    write_metric_rows(train_rows, train_log_path)
    write_metric_rows(val_rows, val_metrics_path)
    print(f"Saved train log: {train_log_path}")
    print(f"Saved val metrics: {val_metrics_path}")
    if best_payload and "model_state" in best_payload:
        model.load_state_dict(best_payload["model_state"])
    final_val = evaluate(
        model,
        val_loader,
        device,
        max_strokes,
        args.dice_weight,
        args.pos_weight,
        args.empty_channel_weight,
        args.loss_mode,
        args.focal_gamma,
        args.tversky_alpha,
        args.tversky_beta,
    )
    final_test = evaluate(
        model,
        test_loader,
        device,
        max_strokes,
        args.dice_weight,
        args.pos_weight,
        args.empty_channel_weight,
        args.loss_mode,
        args.focal_gamma,
        args.tversky_alpha,
        args.tversky_beta,
    )
    _print_metrics("final_val", final_val)
    _print_metrics("final_test", final_test)
    print(f"best_threshold={_best_threshold(final_val)}")
    print(f"elapsed_sec={time.perf_counter() - start_time:.1f}")
    if overfit_mode:
        debug_dir = Path(args.debug_dir)
        curve_path = debug_dir / "overfit_curves.csv"
        write_overfit_curve(curve_rows, curve_path)
        overlay_paths = save_debug_overlays(
            model,
            val_loader,
            device,
            debug_dir / "overfit_overlays",
            threshold=_best_threshold(final_val) or 0.5,
            max_samples=args.overfit_count,
        )
        print(f"wrote overfit curves: {curve_path}")
        for overlay_path in overlay_paths:
            print(f"wrote overfit overlay: {overlay_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ordered stroke mask segmentation baseline")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--max-strokes", type=int, default=None)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dice-weight", type=float, default=0.5)
    parser.add_argument("--pos-weight", type=float, default=8.0)
    parser.add_argument("--empty-channel-weight", type=float, default=0.2)
    parser.add_argument("--loss-mode", choices=["dice", "focal", "tversky"], default="dice")
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--tversky-alpha", type=float, default=0.7)
    parser.add_argument("--tversky-beta", type=float, default=0.3)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--overfit-count", type=int, default=None)
    parser.add_argument("--debug-dir", default=str(DEFAULT_DEBUG_DIR))
    parser.add_argument("--debug-interval", type=int, default=10)
    parser.add_argument("--augment", dest="augment", action="store_true", default=True)
    parser.add_argument("--no-augment", dest="augment", action="store_false")
    parser.add_argument("--early-stopping-patience", type=int, default=20)
    parser.add_argument("--train-log", default=str(SCRIPT_DIR / "output" / "stroke_seg_debug" / "train_log.csv"))
    parser.add_argument("--val-metrics", default=str(SCRIPT_DIR / "output" / "stroke_seg_debug" / "val_metrics.csv"))
    args = parser.parse_args()
    raise SystemExit(train(args))


if __name__ == "__main__":
    main()
