"""Train sequence-style current-stroke segmentation baseline."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, Sequence

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from stroke_next_model import (
    THRESHOLDS,
    StrokeNextDataset,
    PredPreviousCache,
    PreviousMaskNoiseConfig,
    StrokeNextUNet,
    best_threshold_from_metrics,
    build_next_stroke_samples,
    next_dice_score,
    next_soft_dice_loss,
    next_threshold_sweep,
    overlap_penalty_loss,
    split_next_samples,
)
from stroke_seg_model import load_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_OUT = SCRIPT_DIR / "models" / "stroke_next_unet.pt"
DEFAULT_DEBUG_DIR = SCRIPT_DIR / "output" / "stroke_next_debug"


def _collate(batch):
    return {
        "input": torch.stack([item["input"] for item in batch], dim=0),
        "target": torch.stack([item["target"] for item in batch], dim=0),
        "char_id": [str(item["char_id"]) for item in batch],
        "char": [str(item["char"]) for item in batch],
        "stroke_index": torch.tensor([int(item["stroke_index"]) for item in batch], dtype=torch.long),
        "stroke_count": torch.tensor([int(item["stroke_count"]) for item in batch], dtype=torch.long),
        "image_path": [str(item["image_path"]) for item in batch],
        "target_mask_path": [str(item["target_mask_path"]) for item in batch],
    }


def _make_loader(
    samples,
    image_size: int,
    batch_size: int,
    shuffle: bool,
    previous_noise=None,
    pred_previous_cache=None,
    pred_previous_prob: float = 0.0,
    use_remaining_channel: bool = False,
    remaining_previous_dilate: int = 0,
):
    if not samples:
        return None
    return DataLoader(
        StrokeNextDataset(
            samples,
            image_size=image_size,
            previous_noise=previous_noise,
            pred_previous_cache=pred_previous_cache,
            pred_previous_prob=pred_previous_prob,
            use_remaining_channel=use_remaining_channel,
            remaining_previous_dilate=remaining_previous_dilate,
        ),
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=_collate,
    )


def weighted_bce_loss(logits: torch.Tensor, targets: torch.Tensor, pos_weight: float = 12.0) -> torch.Tensor:
    raw = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    weights = torch.where(targets > 0.5, torch.full_like(targets, pos_weight), torch.ones_like(targets))
    return (raw * weights).sum() / weights.sum().clamp_min(1.0)


def segmentation_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    dice_weight: float = 0.5,
    pos_weight: float = 12.0,
    previous_masks: torch.Tensor | None = None,
    overlap_penalty_weight: float = 0.0,
) -> torch.Tensor:
    loss = weighted_bce_loss(logits, targets, pos_weight=pos_weight) + dice_weight * next_soft_dice_loss(logits, targets)
    if previous_masks is not None and overlap_penalty_weight > 0:
        loss = loss + float(overlap_penalty_weight) * overlap_penalty_loss(logits, previous_masks)
    return loss


def foreground_ratio(tensor: torch.Tensor) -> float:
    return float(tensor.float().mean().item())


def evaluate(
    model,
    loader,
    device,
    dice_weight: float,
    pos_weight: float,
    overlap_penalty_weight: float = 0.0,
    thresholds: Sequence[float] = THRESHOLDS,
) -> Dict[str, object]:
    if loader is None:
        return {
            "loss": None,
            "mean_dice": None,
            "target_fg_ratio": None,
            "pred_fg_ratio": None,
            "threshold_sweep": {float(t): None for t in thresholds},
        }
    model.eval()
    total_loss = 0.0
    total_seen = 0
    dice_sum = 0.0
    target_fg_sum = 0.0
    pred_fg_sum = 0.0
    sweep_sum = {float(t): 0.0 for t in thresholds}
    with torch.no_grad():
        for batch in loader:
            inputs = batch["input"].to(device)
            targets = batch["target"].to(device)
            logits = model(inputs)
            previous_masks = inputs[:, 1:2]
            loss = segmentation_loss(
                logits,
                targets,
                dice_weight=dice_weight,
                pos_weight=pos_weight,
                previous_masks=previous_masks,
                overlap_penalty_weight=overlap_penalty_weight,
            )
            batch_size = int(inputs.shape[0])
            total_loss += float(loss.item()) * batch_size
            total_seen += batch_size
            dice_sum += float(next_dice_score(logits.cpu(), targets.cpu()).mean().item()) * batch_size
            preds = (torch.sigmoid(logits) >= 0.5).float()
            target_fg_sum += foreground_ratio(targets) * batch_size
            pred_fg_sum += foreground_ratio(preds) * batch_size
            sweep = next_threshold_sweep(logits, targets, thresholds)
            for threshold, value in sweep.items():
                sweep_sum[threshold] += float(value) * batch_size
    return {
        "loss": total_loss / total_seen if total_seen else None,
        "mean_dice": dice_sum / total_seen if total_seen else None,
        "target_fg_ratio": target_fg_sum / total_seen if total_seen else None,
        "pred_fg_ratio": pred_fg_sum / total_seen if total_seen else None,
        "threshold_sweep": {
            threshold: (sweep_sum[threshold] / total_seen if total_seen else None)
            for threshold in sweep_sum
        },
    }


def _format_optional(value) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _print_metrics(prefix: str, metrics: Dict[str, object]) -> None:
    print(
        f"{prefix}_loss={_format_optional(metrics['loss'])} "
        f"{prefix}_mean_dice={_format_optional(metrics['mean_dice'])} "
        f"{prefix}_target_fg={_format_optional(metrics.get('target_fg_ratio'))} "
        f"{prefix}_pred_fg={_format_optional(metrics.get('pred_fg_ratio'))}"
    )
    sweep = metrics.get("threshold_sweep") or {}
    if sweep:
        print(
            f"{prefix}_threshold_sweep="
            + ", ".join(f"{threshold:.1f}:{_format_optional(value)}" for threshold, value in sweep.items())
        )


def write_rows(rows: Sequence[Dict[str, object]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def snapshot_state_dict(model) -> dict:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def train(args) -> int:
    start_time = time.perf_counter()
    manifest = Path(args.manifest)
    glyph_samples = load_manifest(manifest)
    if not glyph_samples:
        print(f"No samples found in manifest: {manifest}")
        return 2
    stroke_samples = build_next_stroke_samples(glyph_samples)
    train_samples = split_next_samples(stroke_samples, "train")
    val_samples = split_next_samples(stroke_samples, "val")
    test_samples = split_next_samples(stroke_samples, "test")
    if args.overfit_count:
        glyph_ids = []
        for sample in train_samples:
            if sample.char_id not in glyph_ids:
                glyph_ids.append(sample.char_id)
            if len(glyph_ids) >= args.overfit_count:
                break
        train_samples = [sample for sample in train_samples if sample.char_id in set(glyph_ids)]
        val_samples = list(train_samples)
        test_samples = []
        print(f"overfit_mode=true glyph_count={len(glyph_ids)} stroke_samples={len(train_samples)}")

    print(f"glyphs={len(glyph_samples)} strokes={len(stroke_samples)}")
    print(f"stroke_samples train={len(train_samples)} val={len(val_samples)} test={len(test_samples)}")
    if not train_samples:
        print("No train stroke samples; cannot train.")
        return 2

    previous_noise = PreviousMaskNoiseConfig(
        apply_prob=args.previous_noise_apply_prob,
        dropout_prob=args.previous_dropout_prob,
        morph_prob=args.previous_morph_prob,
        false_positive_prob=args.previous_false_positive_prob,
        false_positive_ratio=args.previous_false_positive_ratio,
    )
    if any(
        value > 0
        for value in [
            previous_noise.dropout_prob,
            previous_noise.morph_prob,
            previous_noise.false_positive_prob,
        ]
    ):
        print(
            "previous_mask_noise="
            f"apply:{previous_noise.apply_prob} "
            f"dropout:{previous_noise.dropout_prob} "
            f"morph:{previous_noise.morph_prob} "
            f"false_positive:{previous_noise.false_positive_prob} "
            f"false_positive_ratio:{previous_noise.false_positive_ratio}"
        )
    else:
        previous_noise = None

    pred_previous_cache = PredPreviousCache.from_csv(args.pred_prev_cache) if args.pred_prev_cache else None
    if pred_previous_cache is not None:
        print(f"pred_previous_cache={args.pred_prev_cache} pred_prev_prob={args.pred_prev_prob}")

    train_loader = _make_loader(
        train_samples,
        args.image_size,
        args.batch_size,
        shuffle=True,
        previous_noise=previous_noise,
        pred_previous_cache=pred_previous_cache,
        pred_previous_prob=args.pred_prev_prob,
        use_remaining_channel=args.use_remaining_channel,
        remaining_previous_dilate=args.remaining_previous_dilate,
    )
    train_eval_loader = _make_loader(
        train_samples,
        args.image_size,
        args.batch_size,
        shuffle=False,
        use_remaining_channel=args.use_remaining_channel,
        remaining_previous_dilate=args.remaining_previous_dilate,
    )
    val_loader = _make_loader(
        val_samples,
        args.image_size,
        args.batch_size,
        shuffle=False,
        use_remaining_channel=args.use_remaining_channel,
        remaining_previous_dilate=args.remaining_previous_dilate,
    )
    test_loader = _make_loader(
        test_samples,
        args.image_size,
        args.batch_size,
        shuffle=False,
        use_remaining_channel=args.use_remaining_channel,
        remaining_previous_dilate=args.remaining_previous_dilate,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    in_channels = 4 if args.use_remaining_channel else 3
    model = StrokeNextUNet(in_channels=in_channels, base_channels=args.base_channels).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_val = -1.0
    best_payload = None
    train_rows = []
    val_rows = []
    epochs_without_improvement = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        step_loss = 0.0
        step_seen = 0
        for batch in train_loader:
            inputs = batch["input"].to(device)
            targets = batch["target"].to(device)
            optimizer.zero_grad()
            logits = model(inputs)
            loss = segmentation_loss(
                logits,
                targets,
                dice_weight=args.dice_weight,
                pos_weight=args.pos_weight,
                previous_masks=inputs[:, 1:2],
                overlap_penalty_weight=args.overlap_penalty_weight,
            )
            loss.backward()
            optimizer.step()
            step_loss += float(loss.item()) * int(inputs.shape[0])
            step_seen += int(inputs.shape[0])

        train_metrics = evaluate(model, train_eval_loader, device, args.dice_weight, args.pos_weight, args.overlap_penalty_weight)
        val_metrics = evaluate(model, val_loader, device, args.dice_weight, args.pos_weight, args.overlap_penalty_weight)
        epoch_step_loss = step_loss / step_seen if step_seen else 0.0
        if epoch == 1 or epoch == args.epochs or epoch % args.print_interval == 0:
            print(f"epoch {epoch}/{args.epochs}: train_step_loss={epoch_step_loss:.4f}")
            _print_metrics("train", train_metrics)
            _print_metrics("val", val_metrics)

        row = {
            "epoch": epoch,
            "step_loss": f"{epoch_step_loss:.6f}",
            "train_loss": _format_optional(train_metrics["loss"]),
            "train_mean_dice": _format_optional(train_metrics["mean_dice"]),
            "train_target_fg_ratio": _format_optional(train_metrics["target_fg_ratio"]),
            "train_pred_fg_ratio": _format_optional(train_metrics["pred_fg_ratio"]),
            "val_loss": _format_optional(val_metrics["loss"]),
            "val_mean_dice": _format_optional(val_metrics["mean_dice"]),
            "val_target_fg_ratio": _format_optional(val_metrics["target_fg_ratio"]),
            "val_pred_fg_ratio": _format_optional(val_metrics["pred_fg_ratio"]),
            "best_threshold": best_threshold_from_metrics(val_metrics),
        }
        for threshold, value in (val_metrics.get("threshold_sweep") or {}).items():
            row[f"val_dice_t{str(threshold).replace('.', '_')}"] = _format_optional(value)
        train_rows.append(row)
        val_rows.append({"epoch": epoch, "mean_dice": _format_optional(val_metrics["mean_dice"]), **{
            f"dice_t{str(threshold).replace('.', '_')}": _format_optional(value)
            for threshold, value in (val_metrics.get("threshold_sweep") or {}).items()
        }})

        val_score = -1.0 if val_metrics["mean_dice"] is None else float(val_metrics["mean_dice"])
        if val_score > best_val:
            best_val = val_score
            epochs_without_improvement = 0
            best_payload = {
                "model_state": snapshot_state_dict(model),
                "image_size": args.image_size,
                "base_channels": args.base_channels,
                "in_channels": in_channels,
                "train_stroke_samples": len(train_samples),
                "val_stroke_samples": len(val_samples),
                "test_stroke_samples": len(test_samples),
                "val_mean_dice": val_metrics["mean_dice"],
                "best_threshold": best_threshold_from_metrics(val_metrics),
                "val_threshold_sweep": val_metrics["threshold_sweep"],
                "pos_weight": args.pos_weight,
                "dice_weight": args.dice_weight,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
                "overfit_count": args.overfit_count,
                "previous_mask_noise": None
                if previous_noise is None
                else {
                    "dropout_prob": previous_noise.dropout_prob,
                    "apply_prob": previous_noise.apply_prob,
                    "morph_prob": previous_noise.morph_prob,
                    "false_positive_prob": previous_noise.false_positive_prob,
                    "false_positive_ratio": previous_noise.false_positive_ratio,
                },
                "pred_prev_cache": args.pred_prev_cache,
                "pred_prev_prob": args.pred_prev_prob,
                "use_remaining_channel": args.use_remaining_channel,
                "remaining_previous_dilate": args.remaining_previous_dilate,
                "overlap_penalty_weight": args.overlap_penalty_weight,
            }
        else:
            epochs_without_improvement += 1
        if args.early_stopping_patience and epochs_without_improvement >= args.early_stopping_patience:
            print(f"early_stopping epoch={epoch} patience={args.early_stopping_patience} best_val_mean_dice={best_val:.4f}")
            break

    if best_payload is None:
        best_payload = {
            "model_state": snapshot_state_dict(model),
            "image_size": args.image_size,
            "base_channels": args.base_channels,
            "in_channels": in_channels,
        }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_payload, out_path)
    out_path.with_suffix(".json").write_text(
        json.dumps({key: value for key, value in best_payload.items() if key != "model_state"}, indent=2),
        encoding="utf-8",
    )
    write_rows(train_rows, Path(args.train_log))
    write_rows(val_rows, Path(args.val_metrics))
    model.load_state_dict(best_payload["model_state"])
    final_val = evaluate(model, val_loader, device, args.dice_weight, args.pos_weight, args.overlap_penalty_weight)
    final_test = evaluate(model, test_loader, device, args.dice_weight, args.pos_weight, args.overlap_penalty_weight)
    print(f"Saved best model: {out_path}")
    print(f"Saved metadata: {out_path.with_suffix('.json')}")
    print(f"Saved train log: {args.train_log}")
    print(f"Saved val metrics: {args.val_metrics}")
    _print_metrics("final_val", final_val)
    _print_metrics("final_test", final_test)
    print(f"best_threshold={best_payload.get('best_threshold', 0.5)}")
    print(f"elapsed_sec={time.perf_counter() - start_time:.1f}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Train next-stroke mask segmentation baseline")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dice-weight", type=float, default=0.5)
    parser.add_argument("--pos-weight", type=float, default=12.0)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--early-stopping-patience", type=int, default=12)
    parser.add_argument("--overfit-count", type=int, default=None)
    parser.add_argument("--print-interval", type=int, default=5)
    parser.add_argument("--train-log", default=str(DEFAULT_DEBUG_DIR / "train_log.csv"))
    parser.add_argument("--val-metrics", default=str(DEFAULT_DEBUG_DIR / "val_metrics.csv"))
    parser.add_argument("--previous-dropout-prob", type=float, default=0.0)
    parser.add_argument("--previous-noise-apply-prob", type=float, default=1.0)
    parser.add_argument("--previous-morph-prob", type=float, default=0.0)
    parser.add_argument("--previous-false-positive-prob", type=float, default=0.0)
    parser.add_argument("--previous-false-positive-ratio", type=float, default=0.002)
    parser.add_argument("--pred-prev-cache", default=None)
    parser.add_argument("--pred-prev-prob", type=float, default=0.0)
    parser.add_argument("--use-remaining-channel", action="store_true")
    parser.add_argument("--remaining-previous-dilate", type=int, default=0)
    parser.add_argument("--overlap-penalty-weight", type=float, default=0.0)
    args = parser.parse_args()
    raise SystemExit(train(args))


if __name__ == "__main__":
    main()
