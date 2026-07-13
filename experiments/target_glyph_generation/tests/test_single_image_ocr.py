import csv
import json
import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from target_glyph_generation.external_dataset_discovery import ImageRecord
from target_glyph_generation.single_image_ocr import (
    LabelRecord,
    apply_manual_overrides,
    build_label_records,
    create_review_pages,
    dataset_fingerprint,
    select_review_sample,
    write_audit_outputs,
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
    dataset_id: str = "calligrapher20",
    style_id: str = "wxz",
    manual_character: str | None = None,
    ocr_score: float = 0.99,
    flags: tuple[str, ...] = (),
) -> LabelRecord:
    return LabelRecord(
        image=_image_record(path, dataset_id=dataset_id, style_id=style_id),
        ocr_text=ocr_text,
        ocr_score=ocr_score,
        manual_character=manual_character,
        character=character,
        review_state=review_state,
        flags=flags,
    )


def _write_jpeg(path: Path, color: tuple[int, int, int] = (240, 240, 240)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path, format="JPEG")
    return path


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
    assert labels[0].ocr_score == 0.90
    assert labels[0].flags == ()
    assert labels[1].review_state == "provisional"
    assert labels[1].ocr_score == 0.899
    assert labels[1].flags == ("low_confidence",)


@pytest.mark.parametrize("score", [-0.1, 1.1, math.nan, math.inf, -math.inf])
def test_build_label_records_normalizes_out_of_range_scores_to_low_confidence(
    tmp_path: Path, score: float
):
    label = build_label_records([_image_record(tmp_path / "1.jpg")], [("山", score)])[0]

    assert label.ocr_score == 0.0
    assert label.character == "山"
    assert label.review_state == "provisional"
    assert label.flags == ("low_confidence",)


def test_build_label_records_rejects_prediction_count_mismatch(tmp_path: Path):
    with pytest.raises(ValueError, match="length"):
        build_label_records([_image_record(tmp_path / "1.jpg")], [])


@pytest.mark.parametrize(
    "prediction",
    ["木0", b"m0", {"text": "木", "score": 0.99}, ("木",), ("木", 0.99, "extra")],
)
def test_build_label_records_rejects_malformed_prediction_containers(
    tmp_path: Path, prediction: object
):
    label = build_label_records([_image_record(tmp_path / "1.jpg")], [prediction])[0]  # type: ignore[list-item]

    assert label.ocr_text is None
    assert label.ocr_score == 0.0
    assert label.character is None
    assert label.review_state == "required_review"
    assert label.flags == ("invalid_prediction",)


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


def test_select_review_sample_caps_repeated_label_instance_by_input_position(tmp_path: Path):
    label = _label_record(tmp_path / "1.jpg")

    sample = select_review_sample([label, label], per_style=1, seed=42)

    assert sample == [label]


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


def test_apply_manual_overrides_marks_same_style_final_character_collisions_for_review(
    tmp_path: Path,
):
    existing = _label_record(tmp_path / "existing.jpg", ocr_text="山", character="山")
    corrected = _label_record(
        tmp_path / "corrected.jpg", ocr_text="山水", character=None, review_state="required_review"
    )

    labels = apply_manual_overrides(
        [existing, corrected],
        {corrected.key: {"manual_character": "山", "decision": "accept"}},
    )

    assert [label.character for label in labels] == ["山", "山"]
    assert [label.review_state for label in labels] == ["required_review", "required_review"]
    assert all("duplicate_character" in label.flags for label in labels)


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


def test_write_audit_outputs_exports_labels_reviews_candidates_and_summary(tmp_path: Path):
    wxz_one = _write_jpeg(tmp_path / "images" / "wxz-1.jpg")
    wxz_two = _write_jpeg(tmp_path / "images" / "wxz-2.jpg", (220, 220, 220))
    wxz_three = _write_jpeg(tmp_path / "images" / "wxz-3.jpg", (200, 200, 200))
    wxz_four = _write_jpeg(tmp_path / "images" / "wxz-4.jpg", (180, 180, 180))
    mf_one = _write_jpeg(tmp_path / "images" / "mf-1.jpg", (160, 160, 160))
    mf_two = _write_jpeg(tmp_path / "images" / "mf-2.jpg", (140, 140, 140))
    labels = [
        _label_record(wxz_one, character="山", flags=("low_confidence",)),
        _label_record(wxz_two, character="水", review_state="sample_checked"),
        _label_record(wxz_three, character="永", review_state="required_review"),
        _label_record(wxz_four, character="书", review_state="rejected"),
        _label_record(
            mf_one,
            character="永",
            style_id="mf",
            manual_character="永",
            review_state="manual_override",
        ),
        _label_record(mf_two, character="字", style_id="mf"),
    ]
    fingerprint = dataset_fingerprint([label.image for label in labels])
    output_dir = tmp_path / "audit"

    summary = write_audit_outputs(
        labels,
        output_dir,
        allowed_characters={"山", "水", "永", "书"},
        model_name="PaddleOCR-v4",
        dataset_fingerprint=fingerprint,
        review_per_style=1,
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "ocr_labels.csv",
        "required_review.csv",
        "review_sample.csv",
        "manual_overrides.csv",
        "target_glyph_candidates.csv",
        "ocr_audit_summary.json",
    }
    with (output_dir / "ocr_labels.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 6
    with (output_dir / "required_review.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 1
    with (output_dir / "review_sample.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2
    with (output_dir / "target_glyph_candidates.csv").open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    assert len(candidates) == 3
    assert {row["character"] for row in candidates} == {"山", "水", "永"}
    assert {row["review_state"] for row in candidates} == {
        "provisional",
        "sample_checked",
        "manual_override",
    }
    assert all(row["character"] in {"山", "水", "永", "书"} for row in candidates)
    assert json.loads((output_dir / "ocr_audit_summary.json").read_text(encoding="utf-8")) == summary
    assert summary["model_name"] == "PaddleOCR-v4"
    assert summary["dataset_fingerprint"] == fingerprint
    assert summary["label_count"] == 6
    assert summary["required_review_count"] == 1
    assert summary["review_sample_count"] == 2
    assert summary["join_candidate_count"] == 3
    assert summary["unique_candidate_character_count"] == 3
    assert summary["per_style_counts"] == [
        {
            "dataset_id": "calligrapher20",
            "style_id": "mf",
            "label_count": 2,
            "required_review_count": 0,
            "review_sample_count": 1,
            "join_candidate_count": 1,
        },
        {
            "dataset_id": "calligrapher20",
            "style_id": "wxz",
            "label_count": 4,
            "required_review_count": 1,
            "review_sample_count": 1,
            "join_candidate_count": 2,
        },
    ]


def test_write_audit_outputs_preserves_existing_manual_override_entries(tmp_path: Path):
    image_path = _write_jpeg(tmp_path / "source.jpg")
    label = _label_record(image_path)
    output_dir = tmp_path / "audit"
    output_dir.mkdir()
    manual_overrides = output_dir / "manual_overrides.csv"
    existing_contents = (
        "dataset_id,style_id,source_split,raw_filename,manual_character,decision\n"
        "calligrapher20,wxz,train,source.jpg,永,accept\n"
    )
    manual_overrides.write_text(existing_contents, encoding="utf-8")

    write_audit_outputs(
        [label],
        output_dir,
        allowed_characters={"山"},
        model_name="PaddleOCR-v4",
        dataset_fingerprint=dataset_fingerprint([label.image]),
    )

    assert manual_overrides.read_text(encoding="utf-8") == existing_contents


@pytest.mark.parametrize("invalid_fingerprint", ["", "   ", None, 123])
def test_write_audit_outputs_accepts_nonempty_fingerprint_and_rejects_blank_or_nonstring_values(
    tmp_path: Path, invalid_fingerprint: object
):
    image_path = _write_jpeg(tmp_path / "source.jpg")
    label = _label_record(image_path)

    summary = write_audit_outputs(
        [label],
        tmp_path / "accepted",
        allowed_characters={"山"},
        model_name="PaddleOCR-v4",
        dataset_fingerprint="test-fingerprint",
    )

    assert summary["dataset_fingerprint"] == "test-fingerprint"
    with pytest.raises(ValueError, match="dataset_fingerprint"):
        write_audit_outputs(
            [label],
            tmp_path / "rejected",
            allowed_characters={"山"},
            model_name="PaddleOCR-v4",
            dataset_fingerprint=invalid_fingerprint,  # type: ignore[arg-type]
        )


def test_dataset_fingerprint_is_order_stable_and_detects_source_file_size_changes(tmp_path: Path):
    first_path = _write_jpeg(tmp_path / "first.jpg")
    second_path = _write_jpeg(tmp_path / "second.jpg", (10, 20, 30))
    first = _image_record(first_path)
    second = _image_record(second_path)

    fingerprint = dataset_fingerprint([first, second])

    assert dataset_fingerprint([second, first]) == fingerprint
    same_metadata_first = ImageRecord(
        dataset_id="calligrapher20",
        style_id="wxz",
        style_display_name="wxz",
        source_split="train",
        raw_filename="same.jpg",
        raw_index="same",
        image_path=first_path,
    )
    same_metadata_second = ImageRecord(
        dataset_id="calligrapher20",
        style_id="wxz",
        style_display_name="wxz",
        source_split="train",
        raw_filename="same.jpg",
        raw_index="same",
        image_path=second_path,
    )
    assert dataset_fingerprint([same_metadata_first, same_metadata_second]) == dataset_fingerprint(
        [same_metadata_second, same_metadata_first]
    )
    with first_path.open("ab") as handle:
        handle.write(b"extra-byte")
    assert dataset_fingerprint([first, second]) != fingerprint
    with pytest.raises(FileNotFoundError, match="source image"):
        dataset_fingerprint([_image_record(tmp_path / "missing.jpg")])


def test_create_review_pages_paginates_images_and_rejects_invalid_page_size(tmp_path: Path):
    labels = [
        _label_record(
            _write_jpeg(tmp_path / "images" / f"{index}.jpg", (index, index, index)),
            character="山" if index % 2 == 0 else "水",
            style_id="wxz" if index % 2 == 0 else "mf",
        )
        for index in range(26)
    ]

    pages = create_review_pages(labels, tmp_path / "review-pages", page_size=25)

    assert [path.name for path in pages] == ["review_page_001.png", "review_page_002.png"]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pages)
    assert all(Image.open(path).verify() is None for path in pages)
    first_dataset_page = create_review_pages(
        [_label_record(labels[0].image.image_path, dataset_id="dataset-one")],
        tmp_path / "dataset-one",
    )[0]
    second_dataset_page = create_review_pages(
        [_label_record(labels[0].image.image_path, dataset_id="dataset-two")],
        tmp_path / "dataset-two",
    )[0]
    with Image.open(first_dataset_page) as first_dataset_image:
        first_pixels = first_dataset_image.convert("RGB")
    with Image.open(second_dataset_page) as second_dataset_image:
        second_pixels = second_dataset_image.convert("RGB")
    assert ImageChops.difference(first_pixels, second_pixels).getbbox() is not None


@pytest.mark.parametrize("page_size", [0, 26])
def test_create_review_pages_rejects_page_sizes_outside_one_to_twenty_five(
    tmp_path: Path, page_size: int
):
    with pytest.raises(ValueError, match="page_size"):
        create_review_pages([], tmp_path / "invalid-pages", page_size=page_size)
