import csv
import importlib.util
import json
from pathlib import Path
import sys

import yaml
from PIL import Image, ImageDraw

from target_glyph_generation.p1_dataset import build_p1_extended_phase1_dataset
from target_glyph_generation.p1_review import create_p1_htj_mask_review


PROJECT_DIR = Path(__file__).parents[1]
NOTO_FONT = PROJECT_DIR / "data" / "fontdiffuser_open_dataset" / "fonts" / "noto_sans_sc_400.ttf"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_config(
    path: Path,
    characters_path: Path,
    samples_path: Path,
    render_plan_path: Path,
    coverage_summary_path: Path,
) -> None:
    payload = {
        "dataset_scope": "p1_extended",
        "scr": False,
        "canvas_size": 256,
        "characters_path": str(characters_path),
        "external_samples_path": str(samples_path),
        "open_font_render_plan_path": str(render_plan_path),
        "open_font_coverage_summary": str(coverage_summary_path),
        "content_font_path": str(NOTO_FONT),
        "open_font_paths": {"open_a": str(NOTO_FONT)},
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _save_external_glyph(path: Path, add_right_line: bool = False) -> None:
    image = Image.new("L", (64, 64), color=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 42, 48), fill=0)
    if add_right_line:
        draw.line((63, 0, 63, 63), fill=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def test_build_p1_dataset_masks_flagged_external_image_and_keeps_sparse_open_font_plan(tmp_path):
    assert NOTO_FONT.is_file()
    flagged = tmp_path / "flagged.png"
    unflagged = tmp_path / "unflagged.png"
    _save_external_glyph(flagged, add_right_line=True)
    _save_external_glyph(unflagged)
    characters_path = tmp_path / "characters.csv"
    _write_csv(
        characters_path,
        [
            {"character": "一", "split": "train", "external_style_coverage": "2"},
            {"character": "丁", "split": "validation", "external_style_coverage": "1"},
        ],
    )
    samples_path = tmp_path / "external_samples.csv"
    _write_csv(
        samples_path,
        [
            {
                "style_id": "htj",
                "character": "一",
                "character_split": "train",
                "target_path": str(flagged),
                "image_preprocess": "mask_isolated_right_border_line",
                "tier": "core",
                "paper_eligible": "True",
            },
            {
                "style_id": "lishu",
                "character": "丁",
                "character_split": "validation",
                "target_path": str(unflagged),
                "image_preprocess": "none",
                "tier": "extended",
                "paper_eligible": "True",
            },
        ],
    )
    render_plan_path = tmp_path / "open_font_render_plan.csv"
    _write_csv(
        render_plan_path,
        [
            {"style_id": "open_a", "character": "一", "character_split": "train"},
            {"style_id": "open_a", "character": "丁", "character_split": "validation"},
        ],
    )
    coverage_summary_path = tmp_path / "font_coverage_summary.csv"
    _write_csv(
        coverage_summary_path,
        [
            {
                "font_id": "open_a",
                "missing_count": "1",
            }
        ],
    )
    (tmp_path / "open_a_missing_characters.txt").write_text("丁\n", encoding="utf-8")
    config_path = tmp_path / "dataset.yaml"
    _write_config(
        config_path,
        characters_path,
        samples_path,
        render_plan_path,
        coverage_summary_path,
    )

    output_root = tmp_path / "dataset"
    summary = build_p1_extended_phase1_dataset(config_path, output_root)

    assert summary == {
        "dataset_scope": "p1_extended",
        "content_image_count": 2,
        "external_target_count": 2,
        "open_font_target_count": 1,
        "masked_external_count": 1,
        "target_image_count": 3,
        "scr": False,
    }
    flagged_target = output_root / "train" / "TargetImage" / "htj" / "htj+一.jpg"
    assert flagged_target.is_file()
    assert (output_root / "validation" / "TargetImage" / "lishu" / "lishu+丁.jpg").is_file()
    assert (output_root / "train" / "TargetImage" / "open_a" / "open_a+一.jpg").is_file()
    assert not (output_root / "validation" / "TargetImage" / "open_a" / "open_a+丁.jpg").exists()
    with Image.open(flagged_target) as image:
        assert image.mode == "RGB"
        assert image.size == (256, 256)
        assert image.convert("L").getbbox() is not None


def test_real_p1_phase1_config_uses_sparse_render_plan_and_scr_false():
    config_path = PROJECT_DIR / "configs" / "p1_extended_phase1_dataset.yaml"

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert payload["dataset_scope"] == "p1_extended"
    assert payload["scr"] is False
    assert payload["open_font_coverage_summary"].endswith("font_coverage_summary.csv")
    assert len(payload["open_font_paths"]) == 8


def test_p1_phase1_dataset_cli_forwards_config_and_output(monkeypatch, tmp_path: Path, capsys):
    script_path = PROJECT_DIR / "scripts" / "build_p1_extended_phase1_dataset.py"
    spec = importlib.util.spec_from_file_location("test_build_p1_phase1_dataset", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    def fake_build(config_path: Path, output_root: Path):
        captured["config_path"] = config_path
        captured["output_root"] = output_root
        return {"target_image_count": 3}

    monkeypatch.setattr(module, "build_p1_extended_phase1_dataset", fake_build)
    config_path = tmp_path / "dataset.yaml"
    output_root = tmp_path / "dataset"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_p1_extended_phase1_dataset.py",
            "--config",
            str(config_path),
            "--output-root",
            str(output_root),
        ],
    )

    module.main()

    assert captured == {"config_path": config_path, "output_root": output_root}
    assert json.loads(capsys.readouterr().out) == {"target_image_count": 3}


def test_create_p1_htj_mask_review_writes_deterministic_before_after_pages(tmp_path: Path):
    dataset_root = tmp_path / "dataset"
    raw_root = tmp_path / "raw"
    samples_path = dataset_root / "manifests" / "samples.csv"
    rows = []
    for index, character in enumerate(("甲", "乙", "丙"), start=1):
        source_path = raw_root / f"htj_{index}.png"
        _save_external_glyph(source_path, add_right_line=True)
        processed_path = dataset_root / "train" / "TargetImage" / "htj" / f"htj+{character}.jpg"
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            cleaned = image.copy()
            cleaned.paste(255, (63, 0, 64, 64))
            cleaned.convert("RGB").save(processed_path, format="JPEG")
        rows.append(
            {
                "source_kind": "external",
                "style_id": "htj",
                "character": character,
                "character_split": "train",
                "target_path": processed_path.relative_to(dataset_root).as_posix(),
                "source_path": str(source_path),
                "image_preprocess": "mask_isolated_right_border_line",
                "tier": "core",
                "paper_eligible": "True",
            }
        )
    _write_csv(samples_path, rows)

    review_dir = tmp_path / "review"
    summary = create_p1_htj_mask_review(samples_path, review_dir, sample_count=2, seed=7)

    assert summary == {"candidate_count": 3, "review_count": 2, "page_count": 1, "seed": 7}
    manifest_path = review_dir / "review_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert len(review_rows) == 2
    assert {row["character"] for row in review_rows}.issubset({"甲", "乙", "丙"})
    assert all(Path(row["source_path"]).is_file() for row in review_rows)
    assert all((dataset_root / row["processed_path"]).is_file() for row in review_rows)
    assert (review_dir / "review_pages" / "page_001.png").is_file()
    assert json.loads((review_dir / "review_summary.json").read_text(encoding="utf-8")) == summary
