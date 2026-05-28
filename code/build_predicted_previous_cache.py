"""Build offline predicted-previous masks for next-stroke DAgger-style training."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch

from predict_stroke_next_model import load_model
from predict_stroke_next_rollout import _predict_mask, update_previous_mask
from stroke_next_model import _read_foreground, build_next_stroke_samples, resolve_next_threshold
from stroke_seg_model import load_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "stroke_seg_dataset" / "manifest.csv"
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_next_unet.pt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "stroke_next_predprev_cache"


def cache_metadata_fields() -> list[str]:
    return [
        "char_id",
        "split",
        "stroke_index",
        "stroke_count",
        "pred_previous_path",
        "target_mask_path",
    ]


def write_cache_metadata(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cache_metadata_fields())
        writer.writeheader()
        writer.writerows(rows)


def _load_strokes_for_char(stroke_samples: list) -> dict[str, list]:
    by_char: dict[str, list] = defaultdict(list)
    for sample in stroke_samples:
        by_char[sample.char_id].append(sample)
    for rows in by_char.values():
        rows.sort(key=lambda sample: sample.stroke_index)
    return by_char


def build_cache(args) -> int:
    manifest = Path(args.manifest)
    glyph_samples = load_manifest(manifest)
    stroke_samples = [sample for sample in build_next_stroke_samples(glyph_samples) if sample.split == args.split]
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

    metadata_rows = []
    for char_id, rows in by_char.items():
        if not rows:
            continue
        first = rows[0]
        full = _read_foreground(first.image_path, image_size, nearest=False)
        gt_previous = np.zeros((image_size, image_size), dtype=np.float32)
        pred_previous = np.zeros((image_size, image_size), dtype=np.float32)
        char_dir = out_dir / char_id
        char_dir.mkdir(parents=True, exist_ok=True)
        for sample in rows:
            pred_previous_path = char_dir / f"pred_previous_{sample.stroke_index:02d}.png"
            cv2.imwrite(str(pred_previous_path), (pred_previous > 0.5).astype(np.uint8) * 255)
            _, auto_pred = _predict_mask(
                model,
                full,
                gt_previous,
                pred_previous,
                sample,
                "autoregressive",
                threshold,
                device,
            )
            metadata_rows.append(
                {
                    "char_id": char_id,
                    "split": sample.split,
                    "stroke_index": sample.stroke_index,
                    "stroke_count": sample.stroke_count,
                    "pred_previous_path": str(pred_previous_path),
                    "target_mask_path": str(sample.target_mask_path),
                }
            )
            pred_previous = update_previous_mask(pred_previous, auto_pred, mode=args.previous_update)

    metadata_path = out_dir / "metadata.csv"
    write_cache_metadata(metadata_rows, metadata_path)
    print(f"threshold={threshold}")
    print(f"chars={len(by_char)} cache_samples={len(metadata_rows)}")
    print(f"wrote metadata: {metadata_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build predicted-previous cache from autoregressive train rollout")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--split", default="train", choices=["train", "val", "test"])
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--previous-update", choices=["union", "replace"], default="union")
    parser.add_argument("--limit-chars", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(build_cache(args))


if __name__ == "__main__":
    main()
