"""Check a makemeahanzi-derived stroke classification dataset."""

import argparse
import csv
from collections import Counter
from pathlib import Path

import cv2


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR / "stroke_cls_dataset"
CLASSES = ["heng", "shu", "pie", "na", "dian", "ti", "zhe", "unknown"]


def check_dataset(data_dir: Path) -> int:
    metadata = data_dir / "metadata.csv"
    errors = 0
    counts = Counter()
    total = 0
    if metadata.exists():
        with metadata.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            required = {"sample_id", "char", "stroke_index", "class_name", "image_path", "median_points", "source"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                print(f"metadata warning: missing columns {sorted(missing)}; directory labels will still be checked")
            else:
                for row in reader:
                    total += 1
                    class_name = row["class_name"]
                    counts[class_name] += 1
                    if class_name not in CLASSES:
                        print(f"[ERROR] {row['sample_id']}: unknown class label {class_name!r}")
                        errors += 1
                    image_path = data_dir / row["image_path"]
                    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
                    if image is None:
                        print(f"[ERROR] {row['sample_id']}: image not readable: {image_path}")
                        errors += 1
                    elif image.shape[0] != image.shape[1]:
                        print(f"[ERROR] {row['sample_id']}: image is not square: {image.shape}")
                        errors += 1
    else:
        print(f"metadata.csv not found: {metadata}; directory labels will still be checked")

    dir_counts = Counter()
    for class_name in CLASSES:
        class_dir = data_dir / class_name
        if not class_dir.exists():
            continue
        for path in class_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
                dir_counts[class_name] += 1
                image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    print(f"[ERROR] class image not readable: {path}")
                    errors += 1
                elif image.shape[0] != image.shape[1]:
                    print(f"[ERROR] class image is not square: {path} {image.shape}")
                    errors += 1

    unknown_ratio = dir_counts["unknown"] / sum(dir_counts.values()) if sum(dir_counts.values()) else 0.0
    print(f"Dataset: {data_dir}")
    print(f"Total metadata rows: {total}")
    print(f"Total class images: {sum(dir_counts.values())}")
    for class_name in CLASSES:
        print(f"  {class_name}: {dir_counts[class_name]}")
    print(f"unknown_ratio={unknown_ratio:.2%}")
    print(f"errors={errors}")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check stroke classification dataset")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()
    raise SystemExit(check_dataset(Path(args.data_dir).resolve()))


if __name__ == "__main__":
    main()
