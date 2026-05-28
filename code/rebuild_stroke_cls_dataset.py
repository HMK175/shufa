"""Rebuild stroke classification folders from editable metadata.csv."""

import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA = SCRIPT_DIR / "stroke_cls_dataset" / "metadata.csv"
DEFAULT_OUT_DIR = SCRIPT_DIR / "stroke_cls_dataset"
CLASSES = ["heng", "shu", "pie", "na", "dian", "ti", "zhe", "unknown"]
LEGACY_CLASS_MAP = {"gou": "zhe"}


def normalize_class(label: str) -> str:
    label = (label or "").strip()
    label = LEGACY_CLASS_MAP.get(label, label)
    return label if label in CLASSES else "unknown"


def _clear_class_dirs(out_dir: Path) -> None:
    for class_name in CLASSES + list(LEGACY_CLASS_MAP.keys()):
        class_dir = out_dir / class_name
        if class_dir.exists():
            shutil.rmtree(class_dir)


def rebuild_dataset(metadata: Path, out_dir: Path, clear: bool = False) -> Counter:
    if not metadata.exists():
        print(f"metadata.csv not found: {metadata}")
        return Counter()

    out_dir.mkdir(parents=True, exist_ok=True)
    if clear:
        _clear_class_dirs(out_dir)
    for class_name in CLASSES:
        (out_dir / class_name).mkdir(parents=True, exist_ok=True)

    counts = Counter()
    errors = 0
    base_dir = metadata.parent
    with metadata.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"sample_id", "class_name", "image_path"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            print(f"metadata missing columns: {sorted(missing)}")
            return Counter()
        for row in reader:
            class_name = normalize_class(row.get("class_name", ""))
            src = base_dir / row.get("image_path", "")
            dst = out_dir / class_name / f"{row.get('sample_id')}.png"
            if not src.exists():
                print(f"[ERROR] missing source image for {row.get('sample_id')}: {src}")
                errors += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            counts[class_name] += 1

    total = sum(counts.values())
    print(f"Rebuilt class folders in: {out_dir}")
    print(f"Total samples: {total}")
    for class_name in CLASSES:
        print(f"  {class_name}: {counts[class_name]}")
    print(f"errors={errors}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild stroke class folders from metadata.csv")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    rebuild_dataset(Path(args.metadata).resolve(), Path(args.out_dir).resolve(), clear=args.clear)


if __name__ == "__main__":
    main()
