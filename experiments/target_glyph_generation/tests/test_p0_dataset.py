import csv
import importlib.util
import json
from pathlib import Path
import sys

import yaml
from PIL import Image, ImageDraw

from target_glyph_generation.p0_dataset import build_p0_dataset


CHARACTERS = ["一", "二", "三"]
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(filename: str):
    spec = importlib.util.spec_from_file_location(f"test_{filename.replace('.', '_')}", SCRIPTS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _save_glyph(path: Path, size: tuple[int, int], color_mode: str = "RGB") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new(color_mode, size, color="white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4), fill="black")
    image.save(path)


def _write_candidate_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset_id",
                "style_id",
                "character",
                "source_split",
                "target_path",
                "raw_filename",
                "review_state",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_config(path: Path) -> None:
    payload = {
        "canvas_size": 256,
        "selection_seed": 7,
        "split_seed": 11,
        "character_count": 3,
        "character_splits": {"train": 1, "validation": 1, "test": 1},
        "dataset_tier": "exploratory",
        "external_styles": [
            {"dataset_id": "chinese_style", "style_id": "lishu", "license_status": "unverified"},
            {"dataset_id": "chinese_style", "style_id": "xingkai", "license_status": "unverified"},
            {"dataset_id": "calligrapher20", "style_id": "lgq", "license_status": "CC-BY-SA-4.0"},
            {"dataset_id": "calligrapher20", "style_id": "yzq", "license_status": "CC-BY-SA-4.0"},
        ],
        "open_style_ids": ["open_style"],
        "style_splits": {
            "train": ["lishu", "xingkai", "lgq"],
            "validation": ["yzq"],
            "test": ["open_style"],
        },
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_build_p0_dataset_normalizes_external_images_and_writes_disjoint_manifests(tmp_path: Path):
    chinese_rows = []
    calligrapher_rows = []
    for dataset_id, style_id, rows in (
        ("chinese_style", "lishu", chinese_rows),
        ("chinese_style", "xingkai", chinese_rows),
        ("calligrapher20", "lgq", calligrapher_rows),
        ("calligrapher20", "yzq", calligrapher_rows),
    ):
        for character in CHARACTERS:
            image_path = tmp_path / "source" / dataset_id / style_id / f"{character}.jpg"
            _save_glyph(image_path, (64, 64) if dataset_id == "calligrapher20" else (256, 256))
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "style_id": style_id,
                    "character": character,
                    "source_split": "train",
                    "target_path": str(image_path),
                    "raw_filename": image_path.name,
                    "review_state": "final",
                }
            )

    chinese_manifest = tmp_path / "chinese_manifest.csv"
    calligrapher_manifest = tmp_path / "calligrapher_manifest.csv"
    _write_candidate_manifest(chinese_manifest, chinese_rows)
    _write_candidate_manifest(calligrapher_manifest, calligrapher_rows)

    open_root = tmp_path / "open"
    for character in CHARACTERS:
        _save_glyph(open_root / "rendered" / "ContentImage" / f"{character}.png", (256, 256), "L")
        _save_glyph(
            open_root / "rendered" / "TargetImage" / "open_style" / f"open_style+{character}.png",
            (256, 256),
            "L",
        )

    config_path = tmp_path / "dataset_p0.yaml"
    _write_config(config_path)
    output_root = tmp_path / "p0"

    summary = build_p0_dataset(
        config_path=config_path,
        chinese_manifest_path=chinese_manifest,
        calligrapher_manifest_path=calligrapher_manifest,
        open_dataset_root=open_root,
        output_root=output_root,
    )

    assert summary == {
        "character_count": 3,
        "style_count": 5,
        "target_image_count": 15,
        "dataset_tier": "exploratory",
        "paper_ready": False,
    }
    with (output_root / "manifests" / "characters.csv").open(encoding="utf-8", newline="") as handle:
        character_rows = list(csv.DictReader(handle))
    assert {row["split"] for row in character_rows} == {"train", "validation", "test"}
    assert len({row["character"] for row in character_rows}) == 3

    with (output_root / "manifests" / "samples.csv").open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle))
    assert len(samples) == 15
    assert {row["style_split"] for row in samples} == {"train", "validation", "test"}
    assert {row["character_split"] for row in samples} == {"train", "validation", "test"}
    external_sample = next(row for row in samples if row["style_id"] == "lgq")
    with Image.open(output_root / external_sample["target_path"]) as image:
        assert image.mode == "L"
        assert image.size == (256, 256)
        assert image.getbbox() is not None


def test_build_p0_dataset_rejects_when_external_styles_do_not_share_enough_characters(tmp_path: Path):
    config_path = tmp_path / "dataset_p0.yaml"
    _write_config(config_path)
    rows = []
    for dataset_id, style_id, character in (
        ("chinese_style", "lishu", "一"),
        ("chinese_style", "xingkai", "一"),
        ("calligrapher20", "lgq", "一"),
        ("calligrapher20", "yzq", "二"),
    ):
        image_path = tmp_path / "source" / style_id / f"{character}.jpg"
        _save_glyph(image_path, (64, 64))
        rows.append(
            {
                "dataset_id": dataset_id,
                "style_id": style_id,
                "character": character,
                "source_split": "train",
                "target_path": str(image_path),
                "raw_filename": image_path.name,
                "review_state": "final",
            }
        )
    chinese_manifest = tmp_path / "chinese_manifest.csv"
    calligrapher_manifest = tmp_path / "calligrapher_manifest.csv"
    _write_candidate_manifest(chinese_manifest, [row for row in rows if row["dataset_id"] == "chinese_style"])
    _write_candidate_manifest(calligrapher_manifest, [row for row in rows if row["dataset_id"] == "calligrapher20"])

    try:
        build_p0_dataset(
            config_path=config_path,
            chinese_manifest_path=chinese_manifest,
            calligrapher_manifest_path=calligrapher_manifest,
            open_dataset_root=tmp_path / "open",
            output_root=tmp_path / "p0",
        )
    except ValueError as error:
        assert "公共字符" in str(error)
    else:
        raise AssertionError("expected insufficient shared characters to be rejected")


def test_prepare_p0_dataset_cli_forwards_all_dataset_paths(monkeypatch, tmp_path: Path, capsys):
    module = _load_script("prepare_p0_dataset.py")
    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return {"character_count": 800}

    monkeypatch.setattr(module, "build_p0_dataset", fake_build)
    arguments = {
        "config_path": tmp_path / "config.yaml",
        "chinese_manifest_path": tmp_path / "chinese.csv",
        "calligrapher_manifest_path": tmp_path / "calligrapher.csv",
        "open_dataset_root": tmp_path / "open",
        "output_root": tmp_path / "output",
    }
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_p0_dataset.py",
            "--config",
            str(arguments["config_path"]),
            "--chinese-manifest",
            str(arguments["chinese_manifest_path"]),
            "--calligrapher-manifest",
            str(arguments["calligrapher_manifest_path"]),
            "--open-dataset-root",
            str(arguments["open_dataset_root"]),
            "--output-root",
            str(arguments["output_root"]),
        ],
    )

    module.main()

    assert captured == arguments
    assert json.loads(capsys.readouterr().out) == {"character_count": 800}
