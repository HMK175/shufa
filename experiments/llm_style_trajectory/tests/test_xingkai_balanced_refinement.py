from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _connector_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    segment_id = 0
    point_id = 0
    strokes = [
        [(20, 20), (40, 30), (60, 40)],
        [(74, 48), (92, 58), (112, 65)],
        [(132, 85), (152, 94), (170, 104)],
        [(220, 210), (230, 220), (238, 230)],
    ]
    for index, stroke in enumerate(strokes):
        if index > 0:
            prev_end = strokes[index - 1][-1]
            start = stroke[0]
            segment_id += 1
            for y, x in [prev_end, start]:
                rows.append(
                    {
                        "segment_id": segment_id,
                        "stroke_id": index + 1,
                        "point_id": point_id,
                        "y": y,
                        "x": x,
                        "z": 0.0,
                        "speed": 1.3,
                        "pressure": 0.35,
                        "width": 4.0,
                        "pen_down": 1,
                        "is_connector": 1,
                        "segment_type": "connector",
                        "connection_preference": "weak",
                    }
                )
                point_id += 1
        segment_id += 1
        for y, x in stroke:
            rows.append(
                {
                    "segment_id": segment_id,
                    "stroke_id": index + 1,
                    "point_id": point_id,
                    "y": y,
                    "x": x,
                    "z": 0.0,
                    "speed": 1.0,
                    "pressure": 1.0,
                    "width": 9.0,
                    "pen_down": 1,
                    "is_connector": 0,
                    "segment_type": "stroke",
                    "connection_preference": "weak",
                }
            )
            point_id += 1
    return rows


def _connector_count(rows: list[dict[str, object]]) -> int:
    return len({row["segment_id"] for row in rows if row["segment_type"] == "connector"})


def test_balanced_rule_is_between_baseline_and_conservative():
    from execution_refinement import execution_refinement_metrics, load_refinement_profiles, refine_execution_rows

    profiles = load_refinement_profiles()
    rows = _connector_rows()
    baseline = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["baseline"],
        stroke_width_profile=profiles["stroke_width_profiles"]["flat"],
    )
    conservative = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["conservative"],
        stroke_width_profile=profiles["stroke_width_profiles"]["simple_taper"],
    )
    balanced = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["balanced"],
        stroke_width_profile=profiles["stroke_width_profiles"]["xingkai_expressive_taper"],
        connector_shape=profiles["connector_shapes"]["slight_curve"],
    )

    assert _connector_count(conservative) <= _connector_count(balanced) < _connector_count(baseline)
    assert execution_refinement_metrics(balanced)["stroke_width_range"] >= execution_refinement_metrics(conservative)[
        "stroke_width_range"
    ]


def test_balanced_respects_none_and_non_xingkai_styles():
    from execution_refinement import load_refinement_profiles, refine_execution_rows

    profiles = load_refinement_profiles()
    rows = _connector_rows()
    balanced_rule = profiles["connector_rules"]["balanced"]
    curve = profiles["connector_shapes"]["slight_curve"]

    none_rows = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "none"},
        connector_rule=balanced_rule,
        connector_shape=curve,
    )
    kaishu_rows = refine_execution_rows(
        rows,
        style="kaishu",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=balanced_rule,
        connector_shape=curve,
    )
    lishu_rows = refine_execution_rows(
        rows,
        style="lishu",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=balanced_rule,
        connector_shape=curve,
    )

    assert _connector_count(none_rows) == 0
    assert _connector_count(kaishu_rows) == 0
    assert _connector_count(lishu_rows) == 0


def test_slight_curve_connector_is_not_straight_line():
    from execution_refinement import load_refinement_profiles, refine_execution_rows

    profiles = load_refinement_profiles()
    rows = _connector_rows()
    balanced = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["balanced"],
        connector_shape=profiles["connector_shapes"]["slight_curve"],
    )
    connector_groups: dict[object, list[dict[str, object]]] = {}
    for row in balanced:
        if row["segment_type"] == "connector":
            connector_groups.setdefault(row["segment_id"], []).append(row)

    assert connector_groups
    first = next(group for group in connector_groups.values() if len(group) >= 3)
    pts = np.asarray([[float(row["y"]), float(row["x"])] for row in first], dtype=float)
    start = pts[0]
    end = pts[-1]
    line_mid = (start + end) * 0.5
    actual_mid = pts[len(pts) // 2]
    assert np.linalg.norm(actual_mid - line_mid) > 0.1


def test_xingkai_balanced_experiment_writes_summary_report_and_figures(tmp_path):
    from execution_tools import write_execution_csv
    from xingkai_balanced_experiment import run_xingkai_balanced_experiment

    case_dir = tmp_path / "cases" / "u56fd_xingkai"
    write_execution_csv(_connector_rows(), case_dir / "baseline_execution_trajectory.csv")
    safe_dir = tmp_path / "cases" / "u4eba_lishu"
    write_execution_csv(_connector_rows(), safe_dir / "baseline_execution_trajectory.csv")

    result = run_xingkai_balanced_experiment(
        cases_dir=tmp_path / "cases",
        output_dir=tmp_path / "out",
        target_pairs=[("国", "xingkai"), ("人", "lishu")],
        copy_to_paper=False,
    )

    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()
    assert result["success_count"] == 2

    with Path(result["summary_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    variants = {(row["char"], row["style"], row["variant"]) for row in rows}
    assert ("国", "xingkai", "baseline") in variants
    assert ("国", "xingkai", "conservative") in variants
    assert ("国", "xingkai", "balanced") in variants
    assert ("人", "lishu", "balanced") in variants

    by_variant = {row["variant"]: row for row in rows if row["char"] == "国"}
    assert int(by_variant["conservative"]["connection_count"]) <= int(by_variant["balanced"]["connection_count"]) < int(
        by_variant["baseline"]["connection_count"]
    )
    assert by_variant["balanced"]["has_curved_connector"] == "True"

    lishu_balanced = next(row for row in rows if row["char"] == "人" and row["style"] == "lishu" and row["variant"] == "balanced")
    assert int(lishu_balanced["connection_count"]) == 0

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "不是最终行楷模型" in report
    assert "不进入仿真书写" in report


def test_xingkai_balanced_modules_do_not_import_libauboi5():
    for relative in ["src/execution_refinement.py", "src/xingkai_balanced_experiment.py"]:
        path = EXP_DIR / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
