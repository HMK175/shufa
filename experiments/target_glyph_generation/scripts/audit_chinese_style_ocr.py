"""Audit independent ChineseStyle image labels with local OCR."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.characters import load_characters
from target_glyph_generation.external_dataset_discovery import discover_chinese_style_images
from target_glyph_generation.ocr_runtime import run_local_ocr
from target_glyph_generation.single_image_ocr import (
    apply_manual_overrides,
    build_label_records,
    create_review_pages,
    dataset_fingerprint,
    load_manual_overrides,
    select_review_sample,
    write_audit_outputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit independent ChineseStyle OCR labels")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--characters", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--model-name", default="PP-OCRv5_server_rec")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--review-per-style", type=int, default=200)
    arguments = parser.parse_args()

    images = discover_chinese_style_images(arguments.dataset_root)
    labels = build_label_records(
        images,
        run_local_ocr(images, model_name=arguments.model_name, batch_size=arguments.batch_size),
    )
    if arguments.overrides is not None:
        labels = apply_manual_overrides(labels, load_manual_overrides(arguments.overrides))
    summary = write_audit_outputs(
        labels,
        arguments.output_dir,
        set(load_characters(arguments.characters)),
        arguments.model_name,
        dataset_fingerprint(images),
        review_per_style=arguments.review_per_style,
    )
    page_paths = create_review_pages(
        _review_labels(labels, arguments.review_per_style), arguments.output_dir / "review_pages"
    )
    print(
        json.dumps(
            {
                "label_count": summary["label_count"],
                "required_review_count": summary["required_review_count"],
                "review_page_count": len(page_paths),
            },
            ensure_ascii=False,
        )
    )


def _review_labels(labels, review_per_style: int):
    required_review = [label for label in labels if label.review_state == "required_review"]
    ordered_labels = [*required_review, *select_review_sample(labels, per_style=review_per_style)]
    seen_keys = set()
    unique_labels = []
    for label in ordered_labels:
        if label.key not in seen_keys:
            seen_keys.add(label.key)
            unique_labels.append(label)
    return unique_labels


if __name__ == "__main__":
    main()
