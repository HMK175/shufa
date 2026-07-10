"""Check a makemeahanzi-derived stroke instance segmentation dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import cv2


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR / "stroke_seg_dataset"


def check_dataset(data_dir: Path) -> int:
    manifest = data_dir / "manifest.csv"
    errors = 0
    split_counts = Counter()
    glyph_count = 0
    stroke_total = 0

    if not manifest.exists():
        print(f"[ERROR] manifest not found: {manifest}")
        return 1

    with manifest.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {
            "char_id",
            "char",
            "split",
            "image_path",
            "mask_dir",
            "median_dir",
            "stroke_count",
            "width",
            "height",
            "source",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            print(f"[ERROR] manifest missing columns: {sorted(missing)}")
            return 1

        for row in reader:
            glyph_count += 1
            char_id = row["char_id"]
            split = row["split"]
            split_counts[split] += 1

            try:
                stroke_count = int(row["stroke_count"])
                width = int(row["width"])
                height = int(row["height"])
            except ValueError:
                print(f"[ERROR] {char_id}: invalid numeric field")
                errors += 1
                continue
            stroke_total += stroke_count

            image_path = data_dir / row["image_path"]
            mask_dir = data_dir / row["mask_dir"]
            median_dir = data_dir / row["median_dir"]
            preview_path = data_dir / "preview" / f"{char_id}_preview.png"

            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                print(f"[ERROR] {char_id}: image not readable: {image_path}")
                errors += 1
            elif image.shape != (height, width):
                print(f"[ERROR] {char_id}: image shape {image.shape} != {(height, width)}")
                errors += 1

            if not mask_dir.exists():
                print(f"[ERROR] {char_id}: mask_dir missing: {mask_dir}")
                errors += 1
            if not median_dir.exists():
                print(f"[ERROR] {char_id}: median_dir missing: {median_dir}")
                errors += 1

            mask_files = sorted(mask_dir.glob("*.png")) if mask_dir.exists() else []
            median_files = sorted(median_dir.glob("*.csv")) if median_dir.exists() else []
            if len(mask_files) != stroke_count:
                print(f"[ERROR] {char_id}: mask count {len(mask_files)} != stroke_count {stroke_count}")
                errors += 1
            if len(median_files) != stroke_count:
                print(f"[ERROR] {char_id}: median count {len(median_files)} != stroke_count {stroke_count}")
                errors += 1

            for mask_path in mask_files:
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is None:
                    print(f"[ERROR] {char_id}: mask not readable: {mask_path}")
                    errors += 1
                elif mask.shape != (height, width):
                    print(f"[ERROR] {char_id}: mask shape {mask.shape} != {(height, width)}: {mask_path}")
                    errors += 1
                elif int((mask > 0).sum()) == 0:
                    print(f"[ERROR] {char_id}: empty mask: {mask_path}")
                    errors += 1

            for median_path in median_files:
                with median_path.open(newline="", encoding="utf-8") as mf:
                    rows = list(csv.DictReader(mf))
                if not rows:
                    print(f"[ERROR] {char_id}: empty median csv: {median_path}")
                    errors += 1
                elif {"y", "x"} - set(rows[0].keys()):
                    print(f"[ERROR] {char_id}: median csv missing y/x: {median_path}")
                    errors += 1

            preview = cv2.imread(str(preview_path), cv2.IMREAD_COLOR)
            if preview is None:
                print(f"[ERROR] {char_id}: preview not readable: {preview_path}")
                errors += 1

    print(f"Dataset: {data_dir}")
    print(f"glyphs={glyph_count}")
    print(f"total_strokes={stroke_total}")
    print(f"split train={split_counts['train']} val={split_counts['val']} test={split_counts['test']}")
    print(f"errors={errors}")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check makemeahanzi stroke segmentation dataset")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()
    raise SystemExit(check_dataset(Path(args.data_dir).resolve()))


if __name__ == "__main__":
    main()
