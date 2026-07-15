import csv
from pathlib import Path

from PIL import Image, ImageDraw

from target_glyph_generation.p0_review import write_p0_review_pack


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _save_glyph(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", (256, 256), color=255)
    ImageDraw.Draw(image).rectangle((64, 64, 192, 192), fill=0)
    image.save(path)


def test_write_p0_review_pack_uses_priority_counts_and_covers_character_splits(tmp_path: Path):
    dataset_root = tmp_path / "p0"
    styles = [
        {"style_id": "lishu", "style_split": "train", "source_kind": "external", "dataset_id": "chinese_style", "license_status": "unverified"},
        {"style_id": "lgq", "style_split": "train", "source_kind": "external", "dataset_id": "calligrapher20", "license_status": "CC-BY-SA-4.0"},
        {"style_id": "open_style", "style_split": "test", "source_kind": "open_font", "dataset_id": "open_font", "license_status": "OFL-1.1"},
    ]
    _write_csv(
        dataset_root / "manifests" / "styles.csv",
        ["style_id", "style_split", "source_kind", "dataset_id", "license_status"],
        styles,
    )
    characters = [
        ("一", "train"),
        ("二", "train"),
        ("三", "train"),
        ("四", "validation"),
        ("五", "test"),
    ]
    samples = []
    for style in styles:
        for character, character_split in characters:
            target_path = Path("rendered") / "TargetImage" / style["style_id"] / f"{style['style_id']}+{character}.png"
            _save_glyph(dataset_root / target_path)
            samples.append(
                {
                    "style_id": style["style_id"],
                    "style_split": style["style_split"],
                    "source_kind": style["source_kind"],
                    "source_dataset": style["dataset_id"],
                    "character": character,
                    "character_split": character_split,
                    "content_path": f"rendered/ContentImage/{character}.png",
                    "target_path": target_path.as_posix(),
                    "source_path": f"D:/source/{style['style_id']}/{character}.png",
                    "source_split": "train",
                    "license_status": style["license_status"],
                }
            )
    _write_csv(
        dataset_root / "manifests" / "samples.csv",
        [
            "style_id", "style_split", "source_kind", "source_dataset", "character", "character_split",
            "content_path", "target_path", "source_path", "source_split", "license_status",
        ],
        samples,
    )

    output_dir = tmp_path / "review"
    summary = write_p0_review_pack(
        dataset_root=dataset_root,
        output_dir=output_dir,
        priority_style_ids={"lgq"},
        external_samples_per_style=2,
        priority_samples_per_style=3,
        open_font_samples_per_style=1,
        seed=7,
    )

    assert summary == {
        "review_count": 6,
        "page_count": 1,
        "per_style_counts": {"lgq": 3, "lishu": 2, "open_style": 1},
    }
    queue_path = output_dir / "review_queue.csv"
    assert queue_path.read_bytes().startswith(b"\xef\xbb\xbf")
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert {row["review_reason"] for row in review_rows if row["style_id"] == "lgq"} == {
        "ocr_label_and_preprocessing"
    }
    assert {row["review_label"] for row in review_rows if row["style_id"] == "lgq"} == {
        "核对 OCR+预处理"
    }
    assert {row["character_split"] for row in review_rows if row["style_id"] == "lgq"} == {
        "train", "validation", "test"
    }
    assert {row["review_reason"] for row in review_rows if row["style_id"] == "lishu"} == {
        "external_preprocessing"
    }
    assert {row["review_reason"] for row in review_rows if row["style_id"] == "open_style"} == {
        "open_font_render"
    }
    assert {row["review_label"] for row in review_rows if row["style_id"] == "open_style"} == {
        "核对字体渲染"
    }
    assert (output_dir / "review_pages" / "review_page_001.png").is_file()
