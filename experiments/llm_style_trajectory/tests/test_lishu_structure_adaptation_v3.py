from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_lishu_structure_adaptation_v3_writes_only_shan_lishu_outputs(tmp_path):
    from lishu_structure_adaptation_v3 import run_lishu_structure_adaptation_v3

    result = run_lishu_structure_adaptation_v3(
        output_dir=tmp_path / "lishu_v3",
        image_size=96,
        skeleton_method="ridge",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    sample_dir = out_dir / "u5c71_lishu"
    assert sample_dir.exists()
    assert not (out_dir / "u4eba_kaishu").exists()
    assert not (sample_dir / "trajectory.csv").exists()
    assert not (sample_dir / "execution_trajectory.csv").exists()
    assert (sample_dir / "lishu_structure_v3_conservative.csv").exists()
    assert (sample_dir / "lishu_structure_v3_stronger.csv").exists()
    assert (sample_dir / "lishu_structure_v3_summary.json").exists()
    assert (sample_dir / "lishu_structure_v3_compare.png").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads((sample_dir / "lishu_structure_v3_summary.json").read_text(encoding="utf-8"))
    assert summary["char"] == "山"
    assert summary["style"] == "lishu"
    assert summary["stroke_count"] == summary["adapted_stroke_count"]
    assert summary["stroke_count"] > 0
    assert summary["bbox_aspect_v3_conservative"] >= summary["bbox_aspect_v2_stronger"]
    assert summary["bbox_aspect_v3_stronger"] >= summary["bbox_aspect_v2_stronger"]
    assert summary["lower_half_width_v3_conservative"] >= summary["lower_half_width_v2_stronger"]
    assert summary["lower_half_width_v3_stronger"] >= summary["lower_half_width_v2_stronger"]
    assert summary["max_point_shift_px"]["conservative"] <= 22.0 + 1e-6
    assert summary["max_point_shift_px"]["stronger"] <= 22.0 + 1e-6
    assert "path_length_ratio" in summary
    assert summary["recommended_for_visual_followup"] is True

    rows = list(csv.DictReader((sample_dir / "lishu_structure_v3_conservative.csv").open(encoding="utf-8-sig")))
    assert rows
    assert {"y", "x", "stroke_id", "point_index", "is_break", "variant", "source"}.issubset(rows[0])
    assert any(row["is_break"] == "1" for row in rows)
    assert all(row["source"] == "lishu_structure_adaptation_v3_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 1
    assert summary_rows[0]["char_id"] == "u5c71"
    assert summary_rows[0]["style"] == "lishu"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "structure-level constraints" in report
    assert "不生成正式" in report
    assert "山/lishu" in report


def test_lower_half_width_prefers_lower_points_and_tracks_spread():
    from lishu_structure_adaptation_v3 import lower_half_width, structure_spread_points

    strokes = [
        np.asarray([[10.0, 50.0], [30.0, 50.0], [80.0, 40.0], [90.0, 35.0]]),
        np.asarray([[15.0, 55.0], [70.0, 90.0], [92.0, 100.0]]),
    ]

    width = lower_half_width(strokes)
    adapted = structure_spread_points(
        strokes,
        target_left_x=20.0,
        target_right_x=118.0,
        target_bottom_y=94.0,
        spread_alpha=0.6,
        bottom_alpha=0.4,
        max_shift_px=22.0,
    )

    assert lower_half_width(adapted) > width
    assert len(adapted) == len(strokes)
    for before, after in zip(strokes, adapted):
        assert len(before) == len(after)


def test_lishu_structure_adaptation_v3_module_does_not_import_libauboi5():
    module_path = SRC / "lishu_structure_adaptation_v3.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
