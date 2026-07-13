from pathlib import Path

import pytest

from target_glyph_generation.external_dataset_discovery import ImageRecord
from target_glyph_generation.single_image_ocr import (
    LabelRecord,
    apply_manual_overrides,
    build_label_records,
    select_review_sample,
)


def _image_record(path: Path, *, dataset_id: str = "calligrapher20", style_id: str = "wxz") -> ImageRecord:
    return ImageRecord(
        dataset_id=dataset_id,
        style_id=style_id,
        style_display_name=style_id,
        source_split="train",
        raw_filename=path.name,
        raw_index=path.stem,
        image_path=path,
    )


def _label_record(
    path: Path,
    *,
    ocr_text: str | None = "山",
    character: str | None = "山",
    review_state: str = "provisional",
) -> LabelRecord:
    return LabelRecord(
        image=_image_record(path),
        ocr_text=ocr_text,
        ocr_score=0.99,
        manual_character=None,
        character=character,
        review_state=review_state,
        flags=(),
    )


def test_build_label_records_marks_duplicate_character_only_within_same_style(tmp_path: Path):
    images = [
        _image_record(tmp_path / "wxz" / "1.jpg", style_id="wxz"),
        _image_record(tmp_path / "wxz" / "2.jpg", style_id="wxz"),
        _image_record(tmp_path / "mf" / "1.jpg", style_id="mf"),
    ]

    labels = build_label_records(images, [("永", 0.99), ("永", 0.98), ("永", 0.97)])

    assert [label.review_state for label in labels] == [
        "required_review",
        "required_review",
        "provisional",
    ]
    assert [label.flags for label in labels] == [
        ("duplicate_character",),
        ("duplicate_character",),
        (),
    ]


def test_build_label_records_marks_invalid_prediction_and_keeps_original_ocr_text(tmp_path: Path):
    original_ocr = " 山水 "

    label = build_label_records([_image_record(tmp_path / "1.jpg")], [(original_ocr, 0.99)])[0]

    assert label.ocr_text == original_ocr
    assert label.character is None
    assert label.review_state == "required_review"
    assert label.flags == ("invalid_prediction",)


def test_build_label_records_keeps_low_confidence_single_cjk_prediction_provisional(tmp_path: Path):
    label = build_label_records([_image_record(tmp_path / "1.jpg")], [(" 山 ", "not-a-score")])[0]

    assert label.ocr_text == " 山 "
    assert label.ocr_score == 0.0
    assert label.character == "山"
    assert label.review_state == "provisional"
    assert label.flags == ("low_confidence",)


def test_build_label_records_uses_point_nine_as_low_confidence_boundary(tmp_path: Path):
    labels = build_label_records(
        [_image_record(tmp_path / "at-threshold.jpg"), _image_record(tmp_path / "below-threshold.jpg")],
        [("山", 0.90), ("水", 0.899)],
    )

    assert labels[0].review_state == "provisional"
    assert labels[0].flags == ()
    assert labels[1].review_state == "provisional"
    assert labels[1].flags == ("low_confidence",)


def test_build_label_records_rejects_prediction_count_mismatch(tmp_path: Path):
    with pytest.raises(ValueError, match="length"):
        build_label_records([_image_record(tmp_path / "1.jpg")], [])


def test_select_review_sample_is_deterministic_per_style_and_returns_under_cap_groups(tmp_path: Path):
    wxz_labels = [_label_record(tmp_path / "wxz" / f"{index}.jpg") for index in range(5)]
    mf_labels = [
        LabelRecord(
            image=_image_record(tmp_path / "mf" / f"{index}.jpg", style_id="mf"),
            ocr_text="山",
            ocr_score=0.99,
            manual_character=None,
            character="山",
            review_state="provisional",
            flags=(),
        )
        for index in range(2)
    ]
    labels = [*wxz_labels, *mf_labels]

    first = select_review_sample(labels, per_style=2, seed=42)
    second = select_review_sample([*mf_labels, *wxz_labels], per_style=2, seed=42)
    under_cap = select_review_sample(mf_labels, per_style=2, seed=999)

    assert {label.key for label in first if label.image.style_id == "wxz"} == {
        label.key for label in second if label.image.style_id == "wxz"
    }
    assert under_cap == mf_labels
    assert all(label.review_state == "provisional" for label in labels)


@pytest.mark.parametrize("per_style", [0, -1, True, 1.5])
def test_select_review_sample_rejects_invalid_per_style(per_style: object):
    with pytest.raises(ValueError, match="per_style"):
        select_review_sample([], per_style=per_style)  # type: ignore[arg-type]


def test_apply_manual_overrides_accepts_corrected_character_and_rejects_label(tmp_path: Path):
    accepted = _label_record(
        tmp_path / "accepted.jpg", ocr_text="误", character="误", review_state="required_review"
    )
    rejected = _label_record(
        tmp_path / "rejected.jpg", ocr_text="山水", character=None, review_state="required_review"
    )

    labels = apply_manual_overrides(
        [accepted, rejected],
        {
            accepted.key: {"manual_character": "永", "decision": "accept"},
            rejected.key: {"manual_character": "", "decision": "reject"},
        },
    )

    assert labels[0].ocr_text == "误"
    assert labels[0].manual_character == "永"
    assert labels[0].character == "永"
    assert labels[0].review_state == "manual_override"
    assert labels[1].character is None
    assert labels[1].review_state == "rejected"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        pytest.param(
            {("calligrapher20", "wxz", "train", "unknown.jpg"): {"decision": "reject"}},
            "existing label",
            id="unknown-key",
        ),
        pytest.param(
            {("calligrapher20", "wxz", "train", "1.jpg"): {"decision": "defer"}},
            "decision",
            id="invalid-decision",
        ),
        pytest.param(
            {
                ("calligrapher20", "wxz", "train", "1.jpg"): {
                    "manual_character": "山水",
                    "decision": "accept",
                }
            },
            "manual_character",
            id="invalid-character",
        ),
        pytest.param(
            [
                (("calligrapher20", "wxz", "train", "1.jpg"), {"decision": "reject"}),
                (("calligrapher20", "wxz", "train", "1.jpg"), {"decision": "reject"}),
            ],
            "duplicate",
            id="duplicate-key",
        ),
    ],
)
def test_apply_manual_overrides_rejects_invalid_overrides(
    tmp_path: Path, overrides: object, match: str
):
    label = _label_record(tmp_path / "1.jpg")

    with pytest.raises(ValueError, match=match):
        apply_manual_overrides([label], overrides)  # type: ignore[arg-type]
