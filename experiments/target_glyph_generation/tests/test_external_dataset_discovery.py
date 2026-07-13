from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from target_glyph_generation.external_dataset_discovery import (
    ImageRecord,
    discover_calligrapher_images,
    discover_chinese_style_images,
    validate_calligrapher_audit_inventory,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")


def test_discover_chinese_style_keeps_same_number_as_independent_records(tmp_path: Path):
    _touch(tmp_path / "train" / "lishu" / "lishu_7.jpg")
    _touch(tmp_path / "train" / "xingkai" / "xingkai_7.jpg")

    records = discover_chinese_style_images(tmp_path)

    assert [(record.style_id, record.raw_index) for record in records] == [
        ("lishu", "7"),
        ("xingkai", "7"),
    ]
    assert [record.style_display_name for record in records] == ["隶书", "行楷"]
    assert len({record.key for record in records}) == 2
    assert records[0].key == ("chinese_style", "lishu", "train", "lishu_7.jpg")


def test_image_record_is_frozen():
    record = ImageRecord(
        dataset_id="example",
        style_id="style",
        style_display_name="Style",
        source_split="train",
        raw_filename="1.jpg",
        raw_index="1",
        image_path=Path("1.jpg"),
    )

    with pytest.raises(FrozenInstanceError):
        record.style_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "root",
    [
        pytest.param("missing", id="missing-root"),
        pytest.param("empty", id="no-valid-images"),
    ],
)
def test_discover_chinese_style_rejects_missing_root_or_no_valid_images(tmp_path: Path, root: str):
    dataset_root = tmp_path / root
    if root == "empty":
        dataset_root.mkdir()

    with pytest.raises(ValueError, match="ChineseStyle"):
        discover_chinese_style_images(dataset_root)


def test_discover_chinese_style_rejects_duplicate_records(tmp_path: Path, monkeypatch):
    _touch(tmp_path / "train" / "lishu" / "lishu_7.jpg")
    original_glob = Path.glob

    def duplicate_lishu_glob(path: Path, pattern: str):
        matches = list(original_glob(path, pattern))
        if path.name == "lishu" and pattern == "*.jpg":
            return [*matches, *matches]
        return matches

    monkeypatch.setattr(Path, "glob", duplicate_lishu_glob)

    with pytest.raises(ValueError, match="重复"):
        discover_chinese_style_images(tmp_path)


def test_discover_chinese_style_rejects_malformed_jpg_in_recognized_style_directory(
    tmp_path: Path,
):
    _touch(tmp_path / "train" / "lishu" / "lishu_7.jpg")
    _touch(tmp_path / "train" / "lishu" / "xingkai_7.jpg")

    with pytest.raises(ValueError, match="ChineseStyle 图像格式错误"):
        discover_chinese_style_images(tmp_path)


def test_discover_calligrapher_images_uses_writer_as_style_and_preserves_split(
    tmp_path: Path,
):
    _touch(tmp_path / "data" / "train" / "wxz" / "31.jpg")
    _touch(tmp_path / "data" / "test" / "yzq" / "31.jpg")
    sources = {
        "wxz": {"display_name": "王羲之", "expected_total": 6741},
        "yzq": {"display_name": "颜真卿", "expected_total": 6756},
    }

    records = discover_calligrapher_images(tmp_path / "data", sources)

    assert [(record.style_id, record.source_split, record.raw_index) for record in records] == [
        ("wxz", "train", "31"),
        ("yzq", "test", "31"),
    ]
    assert records[0].dataset_id == "calligrapher20"
    assert records[0].style_display_name == "王羲之"
    assert records[1].style_display_name == "颜真卿"


def test_discover_calligrapher_images_allows_same_split_writer_index_collisions(
    tmp_path: Path,
):
    _touch(tmp_path / "data" / "train" / "wxz" / "31.jpg")
    _touch(tmp_path / "data" / "train" / "yzq" / "31.jpg")
    sources = {
        "wxz": {"display_name": "王羲之", "expected_total": 6741},
        "yzq": {"display_name": "颜真卿", "expected_total": 6756},
    }

    records = discover_calligrapher_images(tmp_path / "data", sources)

    assert [(record.style_id, record.source_split, record.raw_index) for record in records] == [
        ("wxz", "train", "31"),
        ("yzq", "train", "31"),
    ]


def test_discover_calligrapher_images_rejects_unknown_writer_with_jpg(tmp_path: Path):
    _touch(tmp_path / "data" / "train" / "unknown" / "1.jpg")

    with pytest.raises(ValueError, match="未知书法家目录"):
        discover_calligrapher_images(
            tmp_path / "data",
            {"wxz": {"display_name": "王羲之", "expected_total": 6741}},
        )


def test_discover_calligrapher_images_rejects_malformed_file_in_configured_writer(
    tmp_path: Path,
):
    _touch(tmp_path / "data" / "train" / "wxz" / "not-a-number.jpg")

    with pytest.raises(ValueError, match="格式错误"):
        discover_calligrapher_images(
            tmp_path / "data",
            {"wxz": {"display_name": "王羲之", "expected_total": 6741}},
        )


def test_discover_calligrapher_images_rejects_missing_root_or_no_selected_images(tmp_path: Path):
    sources = {"wxz": {"display_name": "王羲之", "expected_total": 6741}}

    with pytest.raises(ValueError, match="书法家数据根目录"):
        discover_calligrapher_images(tmp_path / "missing", sources)

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    with pytest.raises(ValueError, match="没有发现"):
        discover_calligrapher_images(empty_root, sources)


def test_calligrapher8_sources_config_has_exact_expected_writers():
    path = Path(__file__).parents[1] / "configs" / "calligrapher8_sources.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload == {
        "sources": {
            "wxz": {"display_name": "王羲之", "expected_total": 6741},
            "yzq": {"display_name": "颜真卿", "expected_total": 6756},
            "lgq": {"display_name": "柳公权", "expected_total": 6763},
            "oyx": {"display_name": "欧阳询", "expected_total": 3510},
            "mf": {"display_name": "米芾", "expected_total": 6763},
            "sgt": {"display_name": "孙过庭", "expected_total": 6251},
            "yyr": {"display_name": "于右任", "expected_total": 6763},
            "shz": {"display_name": "宋徽宗", "expected_total": 6763},
        }
    }


def test_validate_calligrapher_audit_inventory_accepts_generator_records(tmp_path: Path):
    for source_split in ("train", "test"):
        (tmp_path / source_split / "wxz").mkdir(parents=True)
    records = (
        ImageRecord(
            dataset_id="calligrapher20",
            style_id="wxz",
            style_display_name="Wang Xizhi",
            source_split="train",
            raw_filename="1.jpg",
            raw_index="1",
            image_path=tmp_path / "train" / "wxz" / "1.jpg",
        ),
        ImageRecord(
            dataset_id="calligrapher20",
            style_id="wxz",
            style_display_name="Wang Xizhi",
            source_split="test",
            raw_filename="2.jpg",
            raw_index="2",
            image_path=tmp_path / "test" / "wxz" / "2.jpg",
        ),
    )

    validate_calligrapher_audit_inventory(
        tmp_path,
        (record for record in records),
        {"wxz": {"expected_total": 2}},
    )
