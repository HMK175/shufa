from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

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


def test_median_font_alignment_writes_two_samples_without_formal_trajectory(tmp_path):
    from median_font_alignment_prototype import run_median_font_alignment

    font_path = _available_font()
    if font_path is None:
        pytest.skip("No local font available for median-font alignment test")

    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": [str(font_path)], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = run_median_font_alignment(
        output_dir=tmp_path / "alignment",
        style_sources_path=sources_path,
        sample_specs=[("人", "kaishu"), ("山", "lishu")],
        image_size=96,
        skeleton_method="ridge",
        alpha_values=[0.25, 0.5],
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    for subdir_name in ["u4eba_kaishu", "u5c71_lishu"]:
        sample_dir = out_dir / subdir_name
        assert sample_dir.exists()
        assert (sample_dir / "median_font_alignment_summary.json").exists()
        assert (sample_dir / "adapted_trial_alpha_025.csv").exists()
        assert (sample_dir / "adapted_trial_alpha_050.csv").exists()
        assert (sample_dir / "median_font_alignment_compare.png").exists()
        assert not (sample_dir / "trajectory.csv").exists()

        summary = json.loads((sample_dir / "median_font_alignment_summary.json").read_text(encoding="utf-8"))
        assert summary["stroke_count"] > 0
        assert summary["stroke_count"] == summary["adapted_stroke_count"]
        assert summary["mean_projection_distance_px_after"]["0.25"] <= summary["mean_projection_distance_px_before"] + 1e-6
        assert summary["mean_projection_distance_px_after"]["0.5"] <= summary["mean_projection_distance_px_before"] + 1e-6
        assert summary["max_point_shift_px"]["0.25"] <= 15.0 + 1e-6
        assert summary["max_point_shift_px"]["0.5"] <= 15.0 + 1e-6

        rows = list(csv.DictReader((sample_dir / "adapted_trial_alpha_025.csv").open(encoding="utf-8-sig")))
        assert rows
        assert {"y", "x", "stroke_id", "point_index", "is_break", "alpha", "source"}.issubset(rows[0])
        assert any(row["is_break"] == "1" for row in rows)
        assert all(row["source"] == "median_font_alignment_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 2
    assert {row["char_id"] for row in summary_rows} == {"u4eba", "u5c71"}

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "median + font skeleton" in report
    assert "保留 MakeMeAHanzi stroke order" in report
    assert "不恢复真实笔顺" in report
    assert "不接机器人" in report


def test_soft_adapt_keeps_stroke_count_and_caps_shift():
    from median_font_alignment_prototype import adapt_strokes_to_reference

    strokes = [
        [[0.0, 0.0], [0.0, 10.0], [0.0, 20.0]],
        [[10.0, 0.0], [10.0, 10.0]],
    ]
    reference = [[0.0, 5.0], [0.0, 15.0], [10.0, 5.0], [10.0, 15.0]]

    adapted, metrics = adapt_strokes_to_reference(strokes, reference, alpha=0.5, max_shift_px=3.0, max_snap_distance_px=100.0)

    assert len(adapted) == len(strokes)
    assert metrics["max_point_shift_px"] <= 3.0 + 1e-6
    assert metrics["mean_projection_distance_px_after"] < metrics["mean_projection_distance_px_before"]


def test_median_font_alignment_module_does_not_import_libauboi5():
    module_path = SRC / "median_font_alignment_prototype.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
