import csv
from pathlib import Path

from target_glyph_generation.review_finalization import (
    DRAFT_FIELDNAMES,
    LABEL_REQUIRED_FIELDNAMES,
    finalize_review_drafts,
    load_ocr_labels,
    load_review_draft,
)


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _label(
    raw_filename: str,
    character: str,
    *,
    style_id: str = "lishu",
    source_split: str = "train",
) -> dict[str, str]:
    return {
        "dataset_id": "chinese_style",
        "style_id": style_id,
        "source_split": source_split,
        "raw_filename": raw_filename,
        "image_path": f"D:/source/{raw_filename}",
        "ocr_text": character,
        "character": character,
        "review_state": "required_review",
    }


def _draft(
    raw_filename: str,
    *,
    decision: str = "",
    manual_character: str = "",
    style_id: str = "lishu",
    source_split: str = "train",
    note: str = "",
) -> dict[str, str]:
    return {
        "dataset_id": "chinese_style",
        "style_id": style_id,
        "source_split": source_split,
        "raw_filename": raw_filename,
        "manual_character": manual_character,
        "decision": decision,
        "note": note,
    }


def test_finalization_defaults_to_valid_ocr_excludes_reject_and_applies_manual_character(
    tmp_path: Path,
):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(
        labels_path,
        LABEL_REQUIRED_FIELDNAMES,
        [
            _label("lishu_1.jpg", "一"),
            _label("lishu_2.jpg", "二"),
            _label("lishu_3.jpg", "三"),
        ],
    )
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [
            _draft("lishu_2.jpg", decision="reject"),
            _draft("lishu_3.jpg", decision="accept", manual_character="亖"),
        ],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert result.is_finalizable
    assert [(candidate.raw_filename, candidate.character, candidate.review_state) for candidate in result.candidates] == [
        ("lishu_1.jpg", "一", "default_ocr"),
        ("lishu_3.jpg", "亖", "manual_override"),
    ]
    assert result.unresolved == ()
    assert result.conflicts == ()


def test_finalization_marks_blank_accept_and_invalid_default_ocr_as_unresolved(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(
        labels_path,
        LABEL_REQUIRED_FIELDNAMES,
        [
            _label("lishu_1.jpg", "一"),
            _label("lishu_2.jpg", "",),
        ],
    )
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="accept")],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert not result.is_finalizable
    assert {issue.code for issue in result.unresolved} == {
        "manual_character_needed",
        "invalid_ocr_character",
    }
    assert result.candidates == ()


def test_finalization_rejects_a_non_cjk_manual_character(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_1.jpg", "一")])
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="accept", manual_character="AB")],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert [issue.code for issue in result.unresolved] == ["invalid_manual_character"]


def test_finalization_marks_reject_with_manual_character_as_unresolved(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_1.jpg", "一")])
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="reject", manual_character="二")],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert not result.is_finalizable
    assert [issue.code for issue in result.unresolved] == ["manual_character_with_reject"]


def test_finalization_keeps_an_auditable_rejected_row(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_1.jpg", "一")])
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="reject", note="无法确认")],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert result.is_finalizable
    assert [(item.raw_filename, item.target_path, item.note) for item in result.rejected] == [
        ("lishu_1.jpg", "D:/source/lishu_1.jpg", "无法确认")
    ]


def test_legacy_swapped_columns_and_aceept_are_normalized_only_in_memory(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "legacy.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_6.jpg", "甲")])
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [
            _draft(
                "train",
                source_split="lishu_6.jpg",
                decision="aceept",
                manual_character="乙",
            )
        ],
    )
    before = draft_path.read_bytes()

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert result.is_finalizable
    assert [(candidate.raw_filename, candidate.character) for candidate in result.candidates] == [
        ("lishu_6.jpg", "乙"),
    ]
    assert {item.code for item in result.normalizations} == {
        "legacy_columns_swapped",
        "decision_aceept_normalized",
    }
    assert draft_path.read_bytes() == before


def test_review_draft_accepts_gb18030_saved_by_excel_without_rewriting_it(tmp_path: Path):
    draft_path = tmp_path / "excel_saved.csv"
    rows = [
        ",".join(DRAFT_FIELDNAMES),
        "chinese_style,lishu,train,lishu_6.jpg,甙,accept,Excel 保存",
    ]
    draft_path.write_text("\n".join(rows) + "\n", encoding="gb18030")
    before = draft_path.read_bytes()

    draft = load_review_draft(draft_path)

    assert draft.entries[0].manual_character == "甙"
    assert draft.entries[0].note == "Excel 保存"
    assert draft_path.read_bytes() == before


def test_later_manual_character_resolves_an_earlier_pending_accept(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    first_draft_path = tmp_path / "review.csv"
    correction_path = tmp_path / "correction.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_7.jpg", "甲")])
    _write_csv(first_draft_path, DRAFT_FIELDNAMES, [_draft("lishu_7.jpg", decision="accept")])
    _write_csv(
        correction_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_7.jpg", decision="accept", manual_character="乙")],
    )

    result = finalize_review_drafts(
        load_ocr_labels(labels_path),
        [load_review_draft(first_draft_path), load_review_draft(correction_path)],
    )

    assert result.is_finalizable
    assert [(candidate.raw_filename, candidate.character) for candidate in result.candidates] == [
        ("lishu_7.jpg", "乙"),
    ]


def test_finalization_reports_unknown_keys_and_duplicate_style_characters(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    draft_path = tmp_path / "review.csv"
    _write_csv(
        labels_path,
        LABEL_REQUIRED_FIELDNAMES,
        [
            _label("lishu_1.jpg", "甲"),
            _label("lishu_2.jpg", "甲"),
        ],
    )
    _write_csv(
        draft_path,
        DRAFT_FIELDNAMES,
        [_draft("missing.jpg", decision="reject")],
    )

    result = finalize_review_drafts(load_ocr_labels(labels_path), [load_review_draft(draft_path)])

    assert not result.is_finalizable
    assert {issue.code for issue in result.conflicts} == {
        "unknown_source_key",
        "duplicate_style_character",
    }
    assert len(result.candidates) == 2


def test_finalization_reports_conflicting_manual_characters(tmp_path: Path):
    labels_path = tmp_path / "ocr_labels.csv"
    one_path = tmp_path / "one.csv"
    two_path = tmp_path / "two.csv"
    _write_csv(labels_path, LABEL_REQUIRED_FIELDNAMES, [_label("lishu_1.jpg", "甲")])
    _write_csv(
        one_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="accept", manual_character="乙")],
    )
    _write_csv(
        two_path,
        DRAFT_FIELDNAMES,
        [_draft("lishu_1.jpg", decision="accept", manual_character="丙")],
    )

    result = finalize_review_drafts(
        load_ocr_labels(labels_path), [load_review_draft(one_path), load_review_draft(two_path)]
    )

    assert not result.is_finalizable
    assert [issue.code for issue in result.conflicts] == ["conflicting_draft_decision"]
