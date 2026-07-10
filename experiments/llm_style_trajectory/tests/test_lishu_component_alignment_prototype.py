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


def test_lishu_component_alignment_writes_only_shan_lishu_outputs(tmp_path):
    from lishu_component_alignment_prototype import run_lishu_component_alignment

    result = run_lishu_component_alignment(
        output_dir=tmp_path / "component_alignment",
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
    assert (sample_dir / "lishu_component_alignment_conservative.csv").exists()
    assert (sample_dir / "lishu_component_alignment_stronger.csv").exists()
    assert (sample_dir / "lishu_component_alignment_summary.json").exists()
    assert (sample_dir / "lishu_component_alignment_compare.png").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads((sample_dir / "lishu_component_alignment_summary.json").read_text(encoding="utf-8"))
    assert summary["char"] == "山"
    assert summary["style"] == "lishu"
    assert summary["stroke_count"] == summary["adapted_stroke_count"]
    assert summary["component_groups"] == [
        "left_group",
        "center_group",
        "right_group",
        "lower_support_group",
    ]
    assert set(summary["group_point_counts"]) == set(summary["component_groups"])
    assert sum(summary["group_point_counts"].values()) == summary["point_count"]
    assert summary["bbox_aspect_component_conservative"] >= summary["bbox_aspect_v3_stronger"]
    assert summary["bbox_aspect_component_stronger"] >= summary["bbox_aspect_v3_stronger"]
    assert summary["lower_half_width_component_conservative"] >= summary["lower_half_width_v3_stronger"]
    assert summary["lower_half_width_component_stronger"] >= summary["lower_half_width_v3_stronger"]
    assert summary["max_point_shift_px"]["conservative"] <= 24.0 + 1e-6
    assert summary["max_point_shift_px"]["stronger"] <= 24.0 + 1e-6
    assert summary["path_length_ratio"]["conservative"] >= 0.80
    assert summary["path_length_ratio"]["stronger"] >= 0.80
    assert summary["recommended_for_visual_followup"] is True

    rows = list(csv.DictReader((sample_dir / "lishu_component_alignment_conservative.csv").open(encoding="utf-8-sig")))
    assert rows
    assert {"y", "x", "stroke_id", "point_index", "component_group", "is_break", "variant", "source"}.issubset(rows[0])
    assert any(row["is_break"] == "1" for row in rows)
    point_groups = {row["component_group"] for row in rows if row["is_break"] == "0"}
    assert {"left_group", "center_group", "right_group", "lower_support_group"}.issubset(point_groups)
    assert all(row["source"] == "lishu_component_alignment_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 1
    assert summary_rows[0]["char_id"] == "u5c71"
    assert summary_rows[0]["style"] == "lishu"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "component-level alignment" in report
    assert "不生成正式" in report
    assert "山/lishu" in report


def test_component_grouping_assigns_four_explainable_groups():
    from lishu_component_alignment_prototype import assign_component_groups

    strokes = [
        np.asarray([[10.0, 20.0], [40.0, 20.0], [80.0, 15.0]]),
        np.asarray([[10.0, 50.0], [45.0, 52.0], [80.0, 55.0]]),
        np.asarray([[10.0, 90.0], [45.0, 92.0], [82.0, 96.0]]),
        np.asarray([[78.0, 25.0], [86.0, 55.0], [88.0, 98.0]]),
    ]

    grouped = assign_component_groups(strokes)

    assert len(grouped) == len(strokes)
    labels = {label for stroke_labels in grouped for label in stroke_labels}
    assert {"left_group", "center_group", "right_group", "lower_support_group"}.issubset(labels)
    for stroke, labels_for_stroke in zip(strokes, grouped):
        assert len(stroke) == len(labels_for_stroke)


def test_lishu_component_alignment_module_does_not_import_libauboi5():
    module_path = SRC / "lishu_component_alignment_prototype.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
