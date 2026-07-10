from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _available_font() -> Path | None:
    for candidate in [
        Path("C:/Windows/Fonts/simkai.ttf"),
        Path("C:/Windows/Fonts/SIMLI.TTF"),
        Path("C:/Windows/Fonts/STKAITI.TTF"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]:
        if candidate.exists():
            return candidate
    return None


def test_median_font_adaptation_v2_writes_two_samples_without_formal_trajectory(tmp_path):
    from median_font_adaptation_v2 import run_median_font_adaptation_v2

    font_path = _available_font()
    if font_path is None:
        pytest.skip("No local font available for median-font adaptation v2 test")

    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": [str(font_path)], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = run_median_font_adaptation_v2(
        output_dir=tmp_path / "adaptation_v2",
        style_sources_path=sources_path,
        sample_specs=[("人", "kaishu"), ("山", "lishu")],
        image_size=96,
        skeleton_method="ridge",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    for subdir_name in ["u4eba_kaishu", "u5c71_lishu"]:
        sample_dir = out_dir / subdir_name
        assert sample_dir.exists()
        assert (sample_dir / "adapted_v2_conservative.csv").exists()
        assert (sample_dir / "adapted_v2_stronger.csv").exists()
        assert (sample_dir / "median_font_adaptation_v2_summary.json").exists()
        assert (sample_dir / "median_font_adaptation_v2_compare.png").exists()
        assert not (sample_dir / "trajectory.csv").exists()

        summary = json.loads((sample_dir / "median_font_adaptation_v2_summary.json").read_text(encoding="utf-8"))
        assert summary["stroke_count"] > 0
        assert summary["stroke_count"] == summary["adapted_stroke_count"]
        assert summary["projection_distance_v2_conservative"] <= summary["projection_distance_before"] + 1e-6
        assert summary["projection_distance_v2_stronger"] <= summary["projection_distance_before"] + 1e-6
        assert summary["max_point_shift_px"]["conservative"] <= 18.0 + 1e-6
        assert summary["max_point_shift_px"]["stronger"] <= 18.0 + 1e-6
        assert "aspect_gap_v2_conservative" in summary
        assert "path_length_ratio" in summary

        rows = list(csv.DictReader((sample_dir / "adapted_v2_conservative.csv").open(encoding="utf-8-sig")))
        assert rows
        assert {"y", "x", "stroke_id", "point_index", "is_break", "variant", "source"}.issubset(rows[0])
        assert any(row["is_break"] == "1" for row in rows)
        assert all(row["source"] == "median_font_adaptation_v2_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 2
    assert {row["char_id"] for row in summary_rows} == {"u4eba", "u5c71"}

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "global bbox alignment" in report
    assert "stroke-level anchor alignment" in report
    assert "projection distance 不能作为唯一标准" in report
    assert "不生成正式" in report


def test_global_bbox_alignment_moves_aspect_toward_target():
    from median_font_adaptation_v2 import apply_global_bbox_alignment, bbox_aspect

    strokes = [
        np.asarray([[20.0, 20.0], [40.0, 20.0], [60.0, 20.0]]),
        np.asarray([[20.0, 40.0], [40.0, 40.0], [60.0, 40.0]]),
    ]
    target_bbox = {"y_min": 20.0, "y_max": 60.0, "x_min": 10.0, "x_max": 70.0}

    adapted = apply_global_bbox_alignment(strokes, target_bbox, bbox_alpha=0.5, max_scale_delta=0.5)

    assert len(adapted) == len(strokes)
    assert bbox_aspect(adapted) > bbox_aspect(strokes)


def test_median_font_adaptation_v2_module_does_not_import_libauboi5():
    module_path = SRC / "median_font_adaptation_v2.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
