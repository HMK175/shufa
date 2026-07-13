"""Single-image OCR label normalization and manual review helpers."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import math
import random

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
