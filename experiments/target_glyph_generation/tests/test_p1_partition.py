import csv
import importlib.util
import json
from pathlib import Path
import sys

import yaml

from target_glyph_generation.p1_partition import build_p1_extended_partition


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_config(
    path: Path, core_path: Path, extended_path: Path, artifact_actions_path: Path | None = None
) -> None:
    payload = {
        "dataset_scope": "p1_extended",
        "paper_use_basis": "user_confirmed_unverified_source",
        "seed": 17,
        "ratios": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "core_candidates_path": str(core_path),
        "extended_candidates_path": str(extended_path),
        "open_font_style_ids": ["open_1", "open_2"],
    }
    if artifact_actions_path is not None:
        payload["artifact_actions_path"] = str(artifact_actions_path)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_partition_assigns_each_character_once_and_preserves_extended_boundary(tmp_path: Path):
    image_path = tmp_path / "glyph.png"
    image_path.write_bytes(b"image")
    characters = list("一丁丙乙甲己庚辛壬癸")
    core_rows = []
    extended_rows = []
    for index, character in enumerate(characters):
        core_rows.append(
            {
                "tier": "core",
                "dataset_id": "calligrapher20",
                "style_id": "writer_a",
                "style_display_name": "书法家甲",
                "character": character,
                "source_split": "train",
                "raw_filename": f"core_{index}.jpg",
                "target_path": str(image_path),
                "review_state": "provisional",
                "ocr_score": "0.99",
                "selection_rule": "test",
                "audit_source": "test.csv",
                "paper_eligible": "True",
            }
        )
        extended_rows.append(
            {
                "tier": "extended",
                "dataset_id": "chinese_style",
                "style_id": "lishu",
                "style_display_name": "隶书",
                "character": character,
                "source_split": "train",
                "raw_filename": f"extended_{index}.jpg",
                "target_path": str(image_path),
                "review_state": "final",
                "ocr_score": "",
                "selection_rule": "all_finalized_rows",
                "audit_source": "test.csv",
                "paper_eligible": "True",
                "paper_use_basis": "user_confirmed_unverified_source",
            }
        )
    core_path = tmp_path / "core.csv"
    extended_path = tmp_path / "extended.csv"
    _write_csv(core_path, core_rows)
    _write_csv(extended_path, extended_rows)
    artifact_actions_path = tmp_path / "artifact_actions.csv"
    _write_csv(
        artifact_actions_path,
        [
            {
                "style_id": "writer_a",
                "source_split": "train",
                "raw_filename": "core_0.jpg",
                "image_preprocess": "mask_isolated_right_border_line",
            }
        ],
    )
    config_path = tmp_path / "partition.yaml"
    _write_config(config_path, core_path, extended_path, artifact_actions_path)

    output_dir = tmp_path / "output"
    summary = build_p1_extended_partition(config_path, output_dir)

    assert summary == {
        "dataset_scope": "p1_extended",
        "character_count": 10,
        "external_sample_count": 20,
        "external_style_count": 2,
        "open_font_style_count": 2,
        "open_font_render_plan_count": 20,
        "paper_ready": True,
    }
    with (output_dir / "characters.csv").open(encoding="utf-8", newline="") as handle:
        character_rows = list(csv.DictReader(handle))
    assert {row["split"] for row in character_rows} == {"train", "validation", "test"}
    with (output_dir / "external_samples.csv").open(encoding="utf-8", newline="") as handle:
        sample_rows = list(csv.DictReader(handle))
    splits_by_character = {}
    for row in sample_rows:
        splits_by_character.setdefault(row["character"], set()).add(row["character_split"])
    assert all(len(splits) == 1 for splits in splits_by_character.values())
    assert {row["paper_eligible"] for row in sample_rows if row["tier"] == "extended"} == {"True"}
    assert next(row for row in sample_rows if row["raw_filename"] == "core_0.jpg")["image_preprocess"] == "mask_isolated_right_border_line"
    assert {row["image_preprocess"] for row in sample_rows if row["raw_filename"] != "core_0.jpg"} == {"none"}
    with (output_dir / "open_font_render_plan.csv").open(encoding="utf-8", newline="") as handle:
        open_font_rows = list(csv.DictReader(handle))
    assert len(open_font_rows) == 20
    assert {row["character_split"] for row in open_font_rows} == {"train", "validation", "test"}
    assert json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))["paper_ready"] is True


def test_real_partition_config_declares_p1_extended_scope_and_80_10_10_ratio():
    config_path = Path(__file__).parents[1] / "configs" / "p1_extended_partition.yaml"

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert payload["dataset_scope"] == "p1_extended"
    assert payload["seed"] == 20260716
    assert payload["ratios"] == {"train": 0.8, "validation": 0.1, "test": 0.1}
    assert len(payload["open_font_style_ids"]) == 8


def test_p1_extended_partition_cli_forwards_config_and_output(monkeypatch, tmp_path: Path, capsys):
    script_path = Path(__file__).parents[1] / "scripts" / "build_p1_extended_partition.py"
    spec = importlib.util.spec_from_file_location("test_build_p1_extended_partition", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    def fake_build(config_path: Path, output_dir: Path):
        captured["config_path"] = config_path
        captured["output_dir"] = output_dir
        return {"character_count": 7399}

    monkeypatch.setattr(module, "build_p1_extended_partition", fake_build)
    config_path = tmp_path / "partition.yaml"
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_p1_extended_partition.py", "--config", str(config_path), "--output-dir", str(output_dir)],
    )

    module.main()

    assert captured == {"config_path": config_path, "output_dir": output_dir}
    assert json.loads(capsys.readouterr().out) == {"character_count": 7399}
