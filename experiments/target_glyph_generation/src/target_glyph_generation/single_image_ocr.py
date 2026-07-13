"""Single-image OCR label normalization and manual review helpers."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import csv
import hashlib
import json
import math
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

from target_glyph_generation.external_dataset_discovery import ImageRecord


LOW_CONFIDENCE_THRESHOLD = 0.90
_CJK_RANGES = (
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
)

OverrideKey = tuple[str, str, str, str]
OverridePayload = Mapping[str, object]
OverrideItems = Mapping[OverrideKey, OverridePayload] | Iterable[tuple[OverrideKey, OverridePayload]]

_LABEL_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "style_display_name",
    "source_split",
    "raw_filename",
    "raw_index",
    "image_path",
    "ocr_text",
    "ocr_score",
    "manual_character",
    "character",
    "review_state",
    "flags",
)
_MANUAL_OVERRIDE_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "source_split",
    "raw_filename",
    "manual_character",
    "decision",
    "note",
)
_CANDIDATE_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "character",
    "source_split",
    "target_path",
    "raw_filename",
    "review_state",
)
_JOIN_CANDIDATE_STATES = frozenset({"provisional", "sample_checked", "manual_override"})


@dataclass(frozen=True)
class LabelRecord:
    """OCR result and review status for one independently discovered image."""

    image: ImageRecord
    ocr_text: str | None
    ocr_score: float
    manual_character: str | None
    character: str | None
    review_state: str
    flags: tuple[str, ...]

    @property
    def key(self) -> OverrideKey:
        """Return the stable image key used by manual override files."""
        return self.image.key


def build_label_records(
    images: Sequence[ImageRecord], predictions: Sequence[object]
) -> list[LabelRecord]:
    """Normalize OCR predictions and identify duplicate characters within one style."""
    if len(images) != len(predictions):
        raise ValueError("images and predictions must have equal length")

    labels = [_build_label(image, prediction) for image, prediction in zip(images, predictions)]
    return _mark_duplicate_characters(labels)


def _mark_duplicate_characters(labels: Sequence[LabelRecord]) -> list[LabelRecord]:
    result = list(labels)
    duplicate_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, label in enumerate(result):
        if label.character is not None:
            duplicate_groups[(label.image.dataset_id, label.image.style_id, label.character)].append(index)

    for indices in duplicate_groups.values():
        if len(indices) > 1:
            for index in indices:
                label = result[index]
                result[index] = replace(
                    label,
                    review_state="required_review",
                    flags=_append_flag(label.flags, "duplicate_character"),
                )
    return result


def select_review_sample(
    labels: Sequence[LabelRecord], per_style: int = 200, seed: int = 20260713
) -> list[LabelRecord]:
    """Return a deterministic independent sample for each dataset/style group."""
    if isinstance(per_style, bool) or not isinstance(per_style, int) or per_style <= 0:
        raise ValueError("per_style must be a positive integer")

    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        grouped[(label.image.dataset_id, label.image.style_id)].append(index)

    selected_indices: set[int] = set()
    for group_key, group_indices in grouped.items():
        if len(group_indices) <= per_style:
            selected_indices.update(group_indices)
            continue
        ordered_indices = sorted(group_indices, key=lambda index: (labels[index].key, index))
        group_seed = _group_seed(seed, group_key)
        selected_indices.update(random.Random(group_seed).sample(ordered_indices, per_style))
    return [label for index, label in enumerate(labels) if index in selected_indices]


def apply_manual_overrides(
    labels: Sequence[LabelRecord], overrides: OverrideItems
) -> list[LabelRecord]:
    """Apply validated accept/reject decisions keyed by the original image record."""
    override_items = list(overrides.items()) if isinstance(overrides, Mapping) else list(overrides)
    overrides_by_key = _validate_overrides(override_items)
    labels_by_key = {label.key: label for label in labels}

    unknown_keys = set(overrides_by_key).difference(labels_by_key)
    if unknown_keys:
        raise ValueError(f"override key does not map to an existing label: {sorted(unknown_keys)!r}")

    applied_labels = [
        _apply_override(label, overrides_by_key[label.key]) if label.key in overrides_by_key else label
        for label in labels
    ]
    return _mark_duplicate_characters(applied_labels)


def dataset_fingerprint(records: Sequence[ImageRecord]) -> str:
    """Hash stable image metadata and source bytes without decoding image pixels."""
    digest = hashlib.sha256()
    entries: list[tuple[str, str, str, str, str, int, bytes]] = []
    for record in records:
        image_path = Path(record.image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f"source image is missing: {image_path}")
        entries.append(
            (
                record.dataset_id,
                record.style_id,
                record.source_split,
                record.raw_filename,
                record.raw_index,
                image_path.stat().st_size,
                _source_file_digest(image_path),
            )
        )
    for (
        dataset_id,
        style_id,
        source_split,
        raw_filename,
        raw_index,
        source_file_size,
        source_file_digest,
    ) in sorted(entries):
        metadata = {
            "dataset_id": dataset_id,
            "style_id": style_id,
            "source_split": source_split,
            "raw_filename": raw_filename,
            "raw_index": raw_index,
            "source_file_size": source_file_size,
            "source_file_sha256": source_file_digest.hex(),
        }
        digest.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def write_audit_outputs(
    labels: Sequence[LabelRecord],
    output_dir: Path,
    allowed_characters: Iterable[str],
    model_name: str,
    dataset_fingerprint: str,
    review_per_style: int = 200,
) -> dict:
    """Write auditable OCR labels, review queues, join candidates, and summary data."""
    allowed_character_set = _validate_allowed_characters(allowed_characters)
    normalized_model_name = _validate_model_name(model_name)
    _validate_dataset_fingerprint(dataset_fingerprint)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(labels)
    required_review = [label for label in labels if label.review_state == "required_review"]
    review_sample = select_review_sample(labels, per_style=review_per_style)
    candidates = [
        label
        for label in labels
        if label.character in allowed_character_set and label.review_state in _JOIN_CANDIDATE_STATES
    ]

    _write_csv(output_dir / "ocr_labels.csv", _LABEL_FIELDNAMES, (_label_row(label) for label in labels))
    _write_csv(
        output_dir / "required_review.csv",
        _LABEL_FIELDNAMES,
        (_label_row(label) for label in required_review),
    )
    _write_csv(
        output_dir / "review_sample.csv",
        _LABEL_FIELDNAMES,
        (_label_row(label) for label in review_sample),
    )
    _write_manual_override_template(output_dir / "manual_overrides.csv")
    _write_csv(
        output_dir / "target_glyph_candidates.csv",
        _CANDIDATE_FIELDNAMES,
        (_candidate_row(label) for label in candidates),
    )

    summary = {
        "label_count": len(labels),
        "required_review_count": len(required_review),
        "review_sample_count": len(review_sample),
        "join_candidate_count": len(candidates),
        "unique_candidate_character_count": len({label.character for label in candidates}),
        "per_style_counts": _per_style_counts(labels, review_sample, candidates),
        "model_name": normalized_model_name,
        "dataset_fingerprint": dataset_fingerprint,
    }
    (output_dir / "ocr_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def create_review_pages(
    labels: Sequence[LabelRecord], output_dir: Path, page_size: int = 25
) -> list[Path]:
    """Render read-only source-image pages for efficient manual OCR review."""
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 25:
        raise ValueError("page_size must be an integer from 1 through 25")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    font = _load_review_font(14)
    page_paths: list[Path] = []
    tile_width, tile_height = 250, 225
    for page_number, start in enumerate(range(0, len(labels), page_size), start=1):
        page_labels = labels[start : start + page_size]
        columns = min(5, len(page_labels))
        rows = math.ceil(len(page_labels) / columns)
        page = Image.new("RGB", (columns * tile_width, rows * tile_height), "white")
        draw = ImageDraw.Draw(page)
        for index, label in enumerate(page_labels):
            column, row = index % columns, index // columns
            x, y = column * tile_width, row * tile_height
            _draw_review_tile(draw, page, label, x, y, tile_width, tile_height, font)
        page_path = output_dir / f"review_page_{page_number:03d}.png"
        page.save(page_path, format="PNG")
        page_paths.append(page_path)
    return page_paths


def _build_label(image: ImageRecord, prediction: object) -> LabelRecord:
    if not isinstance(prediction, (tuple, list)) or len(prediction) != 2:
        raw_ocr, raw_score = None, None
    else:
        raw_ocr, raw_score = prediction

    ocr_text = raw_ocr if isinstance(raw_ocr, str) else None
    ocr_score = _normalize_score(raw_score)
    character = _normalize_cjk_glyph(ocr_text)
    if character is None:
        return LabelRecord(
            image=image,
            ocr_text=ocr_text,
            ocr_score=ocr_score,
            manual_character=None,
            character=None,
            review_state="required_review",
            flags=("invalid_prediction",),
        )

    flags = ("low_confidence",) if ocr_score < LOW_CONFIDENCE_THRESHOLD else ()
    return LabelRecord(
        image=image,
        ocr_text=ocr_text,
        ocr_score=ocr_score,
        manual_character=None,
        character=character,
        review_state="provisional",
        flags=flags,
    )


def _normalize_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) and 0.0 <= score <= 1.0 else 0.0


def _normalize_cjk_glyph(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if len(candidate) != 1:
        return None
    codepoint = ord(candidate)
    return candidate if any(start <= codepoint <= end for start, end in _CJK_RANGES) else None


def _append_flag(flags: tuple[str, ...], flag: str) -> tuple[str, ...]:
    return flags if flag in flags else (*flags, flag)


def _group_seed(seed: int, group_key: tuple[str, str]) -> int:
    payload = f"{seed}\x1f{group_key[0]}\x1f{group_key[1]}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest(), "big")


def _validate_allowed_characters(allowed_characters: Iterable[str]) -> set[str]:
    try:
        values = set(allowed_characters)
    except TypeError as error:
        raise ValueError("allowed_characters must be a nonempty iterable of strings") from error
    if not values or any(not isinstance(character, str) or not character for character in values):
        raise ValueError("allowed_characters must be a nonempty iterable of strings")
    return values


def _validate_model_name(model_name: object) -> str:
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a nonempty string")
    return model_name.strip()


def _validate_dataset_fingerprint(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("dataset_fingerprint must be a nonempty string")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_sanitize_csv_row(row) for row in rows)


def _sanitize_csv_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        fieldname: _neutralize_formula_cell(value)
        for fieldname, value in row.items()
    }


def _neutralize_formula_cell(value: object) -> object:
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _source_file_digest(image_path: Path) -> bytes:
    digest = hashlib.sha256()
    with image_path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.digest()


def _write_manual_override_template(path: Path) -> None:
    if path.exists():
        if not path.is_file():
            raise ValueError(f"manual overrides path is not a file: {path}")
        return
    _write_csv(path, _MANUAL_OVERRIDE_FIELDNAMES, ())


def _label_row(label: LabelRecord) -> dict[str, object]:
    return {
        "dataset_id": label.image.dataset_id,
        "style_id": label.image.style_id,
        "style_display_name": label.image.style_display_name,
        "source_split": label.image.source_split,
        "raw_filename": label.image.raw_filename,
        "raw_index": label.image.raw_index,
        "image_path": str(label.image.image_path),
        "ocr_text": label.ocr_text or "",
        "ocr_score": label.ocr_score,
        "manual_character": label.manual_character or "",
        "character": label.character or "",
        "review_state": label.review_state,
        "flags": ";".join(label.flags),
    }


def _candidate_row(label: LabelRecord) -> dict[str, object]:
    return {
        "dataset_id": label.image.dataset_id,
        "style_id": label.image.style_id,
        "character": label.character,
        "source_split": label.image.source_split,
        "target_path": str(label.image.image_path),
        "raw_filename": label.image.raw_filename,
        "review_state": label.review_state,
    }


def _per_style_counts(
    labels: Sequence[LabelRecord], review_sample: Sequence[LabelRecord], candidates: Sequence[LabelRecord]
) -> list[dict[str, object]]:
    label_counts: dict[tuple[str, str], int] = defaultdict(int)
    required_review_counts: dict[tuple[str, str], int] = defaultdict(int)
    review_sample_counts: dict[tuple[str, str], int] = defaultdict(int)
    candidate_counts: dict[tuple[str, str], int] = defaultdict(int)
    for label in labels:
        key = (label.image.dataset_id, label.image.style_id)
        label_counts[key] += 1
        if label.review_state == "required_review":
            required_review_counts[key] += 1
    for label in review_sample:
        review_sample_counts[(label.image.dataset_id, label.image.style_id)] += 1
    for label in candidates:
        candidate_counts[(label.image.dataset_id, label.image.style_id)] += 1
    return [
        {
            "dataset_id": dataset_id,
            "style_id": style_id,
            "label_count": label_counts[(dataset_id, style_id)],
            "required_review_count": required_review_counts[(dataset_id, style_id)],
            "review_sample_count": review_sample_counts[(dataset_id, style_id)],
            "join_candidate_count": candidate_counts[(dataset_id, style_id)],
        }
        for dataset_id, style_id in sorted(label_counts)
    ]


def _load_review_font(size: int) -> ImageFont.ImageFont:
    for windows_font in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyh.ttf")):
        if windows_font.is_file():
            try:
                return ImageFont.truetype(str(windows_font), size)
            except OSError:
                pass
    return ImageFont.load_default()


def _draw_review_tile(
    draw: ImageDraw.ImageDraw,
    page: Image.Image,
    label: LabelRecord,
    x: int,
    y: int,
    tile_width: int,
    tile_height: int,
    font: ImageFont.ImageFont,
) -> None:
    draw.rectangle((x, y, x + tile_width - 1, y + tile_height - 1), outline="black", width=1)
    image_path = Path(label.image.image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"source image is missing: {image_path}")
    with Image.open(image_path) as source_image:
        preview = source_image.convert("RGB")
    preview.thumbnail((tile_width - 20, 115))
    preview_x = x + (tile_width - preview.width) // 2
    page.paste(preview, (preview_x, y + 5))
    details = (
        f"dataset: {label.image.dataset_id}",
        f"style: {label.image.style_id}",
        f"file: {label.image.raw_filename}",
        f"ocr: {label.ocr_text or '-'} score: {label.ocr_score:.3f}",
        f"final: {label.character or '-'} state: {label.review_state}",
    )
    for line_index, detail in enumerate(details):
        _draw_text(draw, (x + 6, y + 120 + line_index * 20), detail, font)


def _draw_text(
    draw: ImageDraw.ImageDraw, position: tuple[int, int], text: str, font: ImageFont.ImageFont
) -> None:
    try:
        draw.text(position, text, fill="black", font=font)
    except UnicodeEncodeError:
        draw.text(position, text.encode("ascii", "replace").decode("ascii"), fill="black", font=font)


def _validate_overrides(
    override_items: Sequence[tuple[OverrideKey, OverridePayload]],
) -> dict[OverrideKey, OverridePayload]:
    validated: dict[OverrideKey, OverridePayload] = {}
    for item in override_items:
        try:
            key, payload = item
        except (TypeError, ValueError):
            raise ValueError("override entries must contain a key and payload") from None
        _validate_override_key(key)
        if key in validated:
            raise ValueError(f"duplicate override key: {key!r}")
        if not isinstance(payload, Mapping):
            raise ValueError(f"override payload must be a mapping: {key!r}")
        decision = payload.get("decision")
        if decision not in {"accept", "reject"}:
            raise ValueError(f"invalid override decision for {key!r}: {decision!r}")
        _validate_manual_character(payload.get("manual_character"), decision)
        validated[key] = payload
    return validated


def _validate_override_key(key: object) -> None:
    if (
        not isinstance(key, tuple)
        or len(key) != 4
        or any(not isinstance(part, str) for part in key)
    ):
        raise ValueError(f"invalid override key: {key!r}")


def _validate_manual_character(value: object, decision: object) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if decision == "accept":
            raise ValueError("manual_character is required for an accept override")
        return None
    character = _normalize_cjk_glyph(value)
    if character is None:
        raise ValueError("manual_character must be one CJK glyph")
    return character


def _apply_override(label: LabelRecord, payload: OverridePayload) -> LabelRecord:
    decision = payload["decision"]
    manual_character = _validate_manual_character(payload.get("manual_character"), decision)
    if decision == "accept":
        return replace(
            label,
            manual_character=manual_character,
            character=manual_character,
            review_state="manual_override",
        )
    return replace(
        label,
        manual_character=manual_character,
        character=None,
        review_state="rejected",
    )
