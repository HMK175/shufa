"""Audit the configured Calligrapher8 image sources with local OCR."""

import argparse
import json
from pathlib import Path
import sys

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.characters import load_characters
from target_glyph_generation.external_dataset_discovery import (
    discover_calligrapher_images,
    validate_calligrapher_audit_inventory,
)
from target_glyph_generation.ocr_runtime import run_local_ocr
from target_glyph_generation.single_image_ocr import (
    apply_manual_overrides,
    build_label_records,
    create_review_pages,
    dataset_fingerprint,
    load_manual_overrides,
    select_review_sample,
    validate_override_keys,
    write_audit_outputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit configured Calligrapher8 OCR labels")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--characters", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--model-name", default="PP-OCRv5_server_rec")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--review-per-style", type=int, default=200)
    parser.add_argument("--progress", action="store_true")
    arguments = parser.parse_args()

    if arguments.review_per_style <= 0:
        parser.error("--review-per-style must be a positive integer")
    model_name = arguments.model_name.strip()
    if not model_name:
        parser.error("--model-name must be a nonempty string")
    allowed_characters = set(load_characters(arguments.characters))
    overrides = (
        load_manual_overrides(arguments.overrides) if arguments.overrides is not None else None
    )

    sources = _load_sources(arguments.sources)
    images = discover_calligrapher_images(arguments.dataset_root, sources)
    validate_calligrapher_audit_inventory(arguments.dataset_root, images, sources)
    if overrides is not None:
        validate_override_keys(overrides, (image.key for image in images))
    ocr_arguments = {"model_name": model_name, "batch_size": arguments.batch_size}
    if arguments.progress:
        ocr_arguments["progress_callback"] = _emit_ocr_progress
    labels = build_label_records(images, run_local_ocr(images, **ocr_arguments))
    if overrides is not None:
        labels = apply_manual_overrides(labels, overrides)
    summary = write_audit_outputs(
        labels,
        arguments.output_dir,
        allowed_characters,
        model_name,
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


def _load_sources(path: Path) -> dict[str, dict[str, object]]:
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        raise ValueError(f"sources YAML is invalid: {path}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), dict):
        raise ValueError("sources YAML must contain a sources mapping")
    return payload["sources"]


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


def _emit_ocr_progress(completed: int, total: int) -> None:
    print(json.dumps({"ocr_progress": {"completed": completed, "total": total}}), flush=True)


if __name__ == "__main__":
    main()
