import csv
import importlib.util
import json
from pathlib import Path
import sys

import yaml

from target_glyph_generation.p1_style_pool import build_style_pool


def _write_csv(path: Path, rows: list[dict[str, str]], encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_config(path: Path, core_source: Path, extended_source: Path) -> None:
    core_styles = [
        {
            "style_id": "writer_a",
            "display_name": "书法家甲",
            "source_kind": "calligrapher",
            "dataset_id": "calligrapher20",
            "license_status": "CC-BY-SA-4.0",
            "paper_eligible": True,
            "candidate_source": {
                "path": str(core_source),
                "path_column": "image_path",
                "filters": {
                    "allowed_review_states": ["provisional", "manual_override"],
                    "minimum_ocr_score": 0.90,
                },
            },
        }
    ]
    core_styles.extend(
        {
            "style_id": f"open_{index}",
            "display_name": f"开源字体{index}",
            "source_kind": "open_font",
            "dataset_id": "open_font",
            "license_status": "OFL-1.1",
            "paper_eligible": True,
        }
        for index in range(1, 17)
    )
    payload = {
        "core_styles": core_styles,
        "extended_styles": [
            {
                "style_id": "lishu",
                "display_name": "隶书",
                "source_kind": "external_glyph",
                "dataset_id": "chinese_style",
                "license_status": "unverified",
                "paper_eligible": True,
                "paper_use_basis": "user_confirmed_unverified_source",
                "candidate_source": {"path": str(extended_source), "path_column": "target_path"},
            },
            {
                "style_id": "xingkai",
                "display_name": "行楷",
                "source_kind": "external_glyph",
                "dataset_id": "chinese_style",
                "license_status": "unverified",
                "paper_eligible": True,
                "paper_use_basis": "user_confirmed_unverified_source",
                "candidate_source": {"path": str(extended_source), "path_column": "target_path"},
            },
        ],
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_build_style_pool_filters_candidates_and_writes_tiered_manifests(tmp_path: Path):
    core_image = tmp_path / "images" / "core.png"
    lishu_image = tmp_path / "images" / "lishu.png"
    xingkai_image = tmp_path / "images" / "xingkai.png"
    for image_path in (core_image, lishu_image, xingkai_image):
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"image")

    core_source = tmp_path / "core.csv"
    _write_csv(
        core_source,
        [
            {
                "dataset_id": "calligrapher20",
                "style_id": "writer_a",
                "style_display_name": "书法家甲",
                "source_split": "train",
                "raw_filename": "0001.jpg",
                "image_path": str(core_image),
                "character": "一",
                "review_state": "provisional",
                "ocr_score": "0.99",
            },
            {
                "dataset_id": "calligrapher20",
                "style_id": "writer_a",
                "style_display_name": "书法家甲",
                "source_split": "train",
                "raw_filename": "0002.jpg",
                "image_path": str(core_image),
                "character": "丁",
                "review_state": "provisional",
                "ocr_score": "0.50",
            },
            {
                "dataset_id": "calligrapher20",
                "style_id": "writer_a",
                "style_display_name": "书法家甲",
                "source_split": "test",
                "raw_filename": "0003.jpg",
                "image_path": str(core_image),
                "character": "丙",
                "review_state": "manual_override",
                "ocr_score": "0.99",
            },
        ],
        encoding="utf-8-sig",
    )
    extended_source = tmp_path / "extended.csv"
    _write_csv(
        extended_source,
        [
            {
                "dataset_id": "chinese_style",
                "style_id": "lishu",
                "source_split": "train",
                "raw_filename": "lishu_1.jpg",
                "target_path": str(lishu_image),
                "character": "一",
                "review_state": "final",
            },
            {
                "dataset_id": "chinese_style",
                "style_id": "xingkai",
                "source_split": "test",
                "raw_filename": "xingkai_1.jpg",
                "target_path": str(xingkai_image),
                "character": "丁",
                "review_state": "final",
            },
        ],
    )
    config_path = tmp_path / "pool.yaml"
    _write_config(config_path, core_source, extended_source)

    output_dir = tmp_path / "output"
    summary = build_style_pool(config_path, output_dir)

    assert summary == {
        "core_style_count": 17,
        "extended_style_count": 2,
        "core_calligrapher_candidate_count": 2,
        "extended_candidate_count": 2,
        "paper_core_ready": True,
    }
    with (output_dir / "core_calligrapher_candidates.csv").open(encoding="utf-8", newline="") as handle:
        core_rows = list(csv.DictReader(handle))
    assert {(row["style_id"], row["character"], row["tier"]) for row in core_rows} == {
        ("writer_a", "一", "core"),
        ("writer_a", "丙", "core"),
    }
    with (output_dir / "extended_chinese_style_candidates.csv").open(encoding="utf-8", newline="") as handle:
        extended_rows = list(csv.DictReader(handle))
    assert {row["style_id"] for row in extended_rows} == {"lishu", "xingkai"}
    assert {row["paper_eligible"] for row in extended_rows} == {"True"}
    with (output_dir / "style_pool.csv").open(encoding="utf-8", newline="") as handle:
        style_rows = list(csv.DictReader(handle))
    chinese_style_rows = [row for row in style_rows if row["tier"] == "extended"]
    assert {row["license_status"] for row in chinese_style_rows} == {"unverified"}
    assert {row["paper_use_basis"] for row in chinese_style_rows} == {
        "user_confirmed_unverified_source"
    }
    summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary_payload["paper_core_ready"] is True


def test_build_style_pool_rejects_missing_external_image(tmp_path: Path):
    core_source = tmp_path / "core.csv"
    _write_csv(
        core_source,
        [
            {
                "dataset_id": "calligrapher20",
                "style_id": "writer_a",
                "style_display_name": "书法家甲",
                "source_split": "train",
                "raw_filename": "0001.jpg",
                "image_path": str(tmp_path / "missing.png"),
                "character": "一",
                "review_state": "provisional",
                "ocr_score": "0.99",
            }
        ],
    )
    extended_source = tmp_path / "extended.csv"
    lishu_image = tmp_path / "lishu.png"
    xingkai_image = tmp_path / "xingkai.png"
    lishu_image.write_bytes(b"image")
    xingkai_image.write_bytes(b"image")
    _write_csv(
        extended_source,
        [
            {"dataset_id": "chinese_style", "style_id": "lishu", "source_split": "train", "raw_filename": "1.jpg", "target_path": str(lishu_image), "character": "一", "review_state": "final"},
            {"dataset_id": "chinese_style", "style_id": "xingkai", "source_split": "train", "raw_filename": "2.jpg", "target_path": str(xingkai_image), "character": "丁", "review_state": "final"},
        ],
    )
    config_path = tmp_path / "pool.yaml"
    _write_config(config_path, core_source, extended_source)

    try:
        build_style_pool(config_path, tmp_path / "output")
    except ValueError as error:
        assert "不存在" in str(error)
    else:
        raise AssertionError("expected a missing source image to be rejected")


def test_real_p1_config_has_17_core_and_2_extended_styles():
    config_path = Path(__file__).parents[1] / "configs" / "p1_style_pool.yaml"

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert len(payload["core_styles"]) == 17
    assert {style["style_id"] for style in payload["extended_styles"]} == {"lishu", "xingkai"}
    assert all(style["license_status"] != "unverified" for style in payload["core_styles"])
    assert all(style["paper_eligible"] is True for style in payload["extended_styles"])
    assert all(
        style["paper_use_basis"] == "user_confirmed_unverified_source"
        for style in payload["extended_styles"]
    )


def test_build_p1_style_pool_cli_forwards_config_and_output(monkeypatch, tmp_path: Path, capsys):
    script_path = Path(__file__).parents[1] / "scripts" / "build_p1_style_pool.py"
    spec = importlib.util.spec_from_file_location("test_build_p1_style_pool", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    def fake_build(config_path: Path, output_dir: Path):
        captured["config_path"] = config_path
        captured["output_dir"] = output_dir
        return {"core_style_count": 17}

    monkeypatch.setattr(module, "build_style_pool", fake_build)
    config_path = tmp_path / "pool.yaml"
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_p1_style_pool.py", "--config", str(config_path), "--output-dir", str(output_dir)],
    )

    module.main()

    assert captured == {"config_path": config_path, "output_dir": output_dir}
    assert json.loads(capsys.readouterr().out) == {"core_style_count": 17}
