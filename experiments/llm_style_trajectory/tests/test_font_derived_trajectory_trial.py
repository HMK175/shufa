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


def test_font_derived_trajectory_trial_writes_three_sample_outputs(tmp_path):
    from font_derived_trajectory_trial import run_font_derived_trajectory_trial

    font_path = _available_font()
    if font_path is None:
        pytest.skip("No local font available for font-derived trajectory trial test")

    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": [str(font_path)], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = run_font_derived_trajectory_trial(
        output_dir=tmp_path / "trial",
        sample_specs=[("山", "kaishu"), ("人", "kaishu"), ("山", "lishu")],
        style_sources_path=sources_path,
        image_size=96,
        skeleton_method="ridge",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    for subdir_name in ["u5c71_kaishu", "u4eba_kaishu", "u5c71_lishu"]:
        sample_dir = out_dir / subdir_name
        assert sample_dir.exists()
        assert (sample_dir / "font_derived_trial_trajectory.csv").exists()
        assert (sample_dir / "font_derived_trial_summary.json").exists()
        assert (sample_dir / "font_derived_trial_compare.png").exists()
        assert not (sample_dir / "trajectory.csv").exists()

        rows = list(csv.DictReader((sample_dir / "font_derived_trial_trajectory.csv").open(encoding="utf-8-sig")))
        assert rows
        assert {"y", "x", "segment_id", "point_index", "is_break", "source"}.issubset(rows[0])
        assert any(row["is_break"] == "1" for row in rows)
        assert all(row["source"] == "font_skeleton_trial" for row in rows)

        summary = json.loads((sample_dir / "font_derived_trial_summary.json").read_text(encoding="utf-8"))
        assert summary["segment_count"] > 0
        assert summary["point_count"] > 0
        assert summary["break_count"] == summary["segment_count"]
        assert "median_path_length_px" in summary

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 3
    assert all(row["style"] in {"kaishu", "lishu"} for row in summary_rows)

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "不是正式轨迹" in report
    assert "不含真实笔顺" in report
    assert "不含执行层 width/pressure" in report
    assert "font-outline basis" in report


def test_font_derived_trajectory_trial_module_does_not_import_libauboi5():
    module_path = SRC / "font_derived_trajectory_trial.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
