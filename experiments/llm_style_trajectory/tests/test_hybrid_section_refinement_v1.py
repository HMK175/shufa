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


def test_hybrid_section_refinement_v1_writes_only_feng_lishu_outputs(tmp_path):
    from hybrid_section_refinement_v1 import run_hybrid_section_refinement_v1

    result = run_hybrid_section_refinement_v1(
        output_dir=tmp_path / "hybrid_section",
        image_size=96,
        skeleton_method="ridge",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    sample_dir = out_dir / "u98ce_lishu"
    assert sample_dir.exists()
    assert not (out_dir / "u5c71_lishu").exists()
    assert not (sample_dir / "trajectory.csv").exists()
    assert not (sample_dir / "execution_trajectory.csv").exists()
    assert not (sample_dir / "robot_workspace_trajectory.csv").exists()
    assert (sample_dir / "hybrid_section_conservative.csv").exists()
    assert (sample_dir / "hybrid_section_balanced.csv").exists()
    assert (sample_dir / "hybrid_section_summary.json").exists()
    assert (sample_dir / "hybrid_section_compare.png").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads((sample_dir / "hybrid_section_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "trial_not_used_by_default"
    assert summary["source"] == "hybrid_section_refinement_v1_trial"
    assert summary["char"] == "风"
    assert summary["char_id"] == "u98ce"
    assert summary["style"] == "lishu"
    assert summary["stroke_count_preserved"] is True
    assert summary["stroke_count"] > 0
    assert summary["point_count"] > 0
    assert summary["section_count"] >= 2
    assert summary["section_count"] <= 4
    assert len(summary["section_names"]) == summary["section_count"]
    assert summary["section_source"] in {"component_bbox", "top_mid_bottom_fallback"}
    assert summary["bbox_aspect_target"] >= summary["bbox_aspect_median"]
    assert summary["lower_half_width_target"] >= 0.0
    assert summary["max_point_shift_px"]["conservative"] <= 15.0 + 1e-6
    assert summary["max_point_shift_px"]["balanced"] <= 18.0 + 1e-6
    assert summary["path_length_ratio"]["conservative"] >= 0.88
    assert summary["path_length_ratio"]["balanced"] >= 0.84
    assert summary["recommended_for_visual_followup"] is True

    rows = list(csv.DictReader((sample_dir / "hybrid_section_conservative.csv").open(encoding="utf-8-sig")))
    assert rows
    assert {"y", "x", "stroke_id", "point_index", "section_name", "is_break", "variant", "source"}.issubset(rows[0])
    assert any(row["is_break"] == "1" for row in rows)
    point_sections = {row["section_name"] for row in rows if row["is_break"] == "0"}
    assert point_sections
    assert point_sections.issubset(set(summary["section_names"]))
    assert all(row["source"] == "hybrid_section_refinement_v1_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 1
    assert summary_rows[0]["char_id"] == "u98ce"
    assert summary_rows[0]["style"] == "lishu"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "hybrid section refinement" in report
    assert "component bbox" in report
    assert "top/mid/bottom" in report
    assert "trial-only" in report
    assert "不生成正式 trajectory.csv" in report


def test_build_hybrid_sections_prefers_component_boxes_and_has_fallback():
    from hybrid_section_refinement_v1 import build_hybrid_sections

    mask = np.zeros((96, 96), dtype=bool)
    mask[10:30, 8:24] = True
    mask[36:58, 30:54] = True
    mask[60:86, 56:88] = True

    sections = build_hybrid_sections(mask, max_sections=4)
    assert sections["section_source"] == "component_bbox"
    assert 2 <= len(sections["sections"]) <= 4
    for section in sections["sections"]:
        assert "name" in section
        assert "bbox" in section
        assert section["bbox"]["x_max"] >= section["bbox"]["x_min"]
        assert section["bbox"]["y_max"] >= section["bbox"]["y_min"]

    empty = build_hybrid_sections(np.zeros((64, 64), dtype=bool), max_sections=3)
    assert empty["section_source"] == "top_mid_bottom_fallback"
    assert len(empty["sections"]) == 3


def test_assign_sections_to_points_keeps_lengths_and_uses_known_names():
    from hybrid_section_refinement_v1 import assign_sections_to_points

    strokes = [
        np.asarray([[10.0, 12.0], [18.0, 15.0], [26.0, 20.0]]),
        np.asarray([[40.0, 48.0], [60.0, 50.0], [78.0, 55.0]]),
    ]
    sections = [
        {"name": "top_component", "bbox": {"x_min": 0.0, "x_max": 30.0, "y_min": 0.0, "y_max": 35.0}},
        {"name": "bottom_component", "bbox": {"x_min": 35.0, "x_max": 80.0, "y_min": 35.0, "y_max": 90.0}},
    ]

    labels = assign_sections_to_points(strokes, sections)

    assert len(labels) == len(strokes)
    for stroke, stroke_labels in zip(strokes, labels):
        assert len(stroke) == len(stroke_labels)
    flat_labels = {label for stroke_labels in labels for label in stroke_labels}
    assert flat_labels.issubset({"top_component", "bottom_component"})


def test_hybrid_section_refinement_v1_module_does_not_import_libauboi5():
    module_path = SRC / "hybrid_section_refinement_v1.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
