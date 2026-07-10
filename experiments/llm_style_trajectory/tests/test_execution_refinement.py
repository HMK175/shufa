from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _stroke_segment(segment_id: int, stroke_id: int, points: list[tuple[float, float]]) -> list[dict]:
    return [
        {
            "segment_id": segment_id,
            "stroke_id": stroke_id,
            "point_id": idx,
            "y": y,
            "x": x,
            "z": 0.0,
            "speed": 1.0,
            "pressure": 1.0,
            "width": 10.0,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
            "connection_preference": "weak",
        }
        for idx, (y, x) in enumerate(points)
    ]


def _connector_segment(segment_id: int, stroke_id: int, start: tuple[float, float], end: tuple[float, float]) -> list[dict]:
    return [
        {
            "segment_id": segment_id,
            "stroke_id": stroke_id,
            "point_id": idx,
            "y": point[0],
            "x": point[1],
            "z": 0.0,
            "speed": 1.3,
            "pressure": 0.35,
            "width": 4.0,
            "pen_down": 1,
            "is_connector": 1,
            "segment_type": "connector",
            "connection_preference": "weak",
        }
        for idx, point in enumerate([start, end])
    ]


def _rows_with_two_connectors() -> list[dict]:
    first = _stroke_segment(1, 1, [(10, 10), (20, 20), (30, 30)])
    second = _stroke_segment(3, 2, [(34, 34), (44, 44), (54, 54)])
    third = _stroke_segment(5, 3, [(180, 180), (180, 210), (180, 240)])
    return (
        first
        + _connector_segment(2, 2, (30, 30), (34, 34))
        + second
        + _connector_segment(4, 3, (54, 54), (180, 180))
        + third
    )


def _count_connectors(rows: list[dict]) -> int:
    return len({row["segment_id"] for row in rows if row["segment_type"] == "connector"})


def test_baseline_connector_rule_keeps_existing_connectors():
    from execution_refinement import refine_execution_rows

    rows = _rows_with_two_connectors()
    refined = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule={"mode": "all_adjacent"},
        stroke_width_profile={"mode": "constant"},
    )

    assert _count_connectors(refined) == _count_connectors(rows)
    assert all(float(row["width"]) == 10.0 for row in refined if row["segment_type"] == "stroke")


def test_conservative_connector_rule_reduces_long_or_sharp_connectors():
    from execution_refinement import refine_execution_rows

    rows = _rows_with_two_connectors()
    refined = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule={
            "mode": "distance_angle_gate",
            "max_connector_distance_abs": 30.0,
            "max_connector_distance_ratio": 1.0,
            "max_turn_angle_deg": 140.0,
            "min_stroke_endpoint_distance": 1.0,
            "connect_every_n": 1,
        },
        stroke_width_profile={"mode": "constant"},
    )

    assert _count_connectors(refined) < _count_connectors(rows)
    converted = [row for row in refined if row["segment_id"] == 4]
    assert converted
    assert all(row["segment_type"] == "pen_up_move" for row in converted)
    assert all(int(row["pen_down"]) == 0 for row in converted)
    assert all(float(row["pressure"]) == 0.0 for row in converted)
    assert all(float(row["width"]) == 0.0 for row in converted)


def test_kaishu_lishu_and_none_do_not_keep_interstroke_connectors():
    from execution_refinement import refine_execution_rows

    rows = _rows_with_two_connectors()
    rule = {"mode": "distance_angle_gate", "max_connector_distance_abs": 999.0}

    for style, preference in [("kaishu", "weak"), ("lishu", "normal"), ("xingkai", "none")]:
        refined = refine_execution_rows(
            rows,
            style=style,
            style_modifiers={"connection_preference": preference},
            connector_rule=rule,
            stroke_width_profile={"mode": "constant"},
        )
        assert _count_connectors(refined) == 0
        assert any(row["segment_type"] == "pen_up_move" for row in refined)


def test_simple_taper_changes_stroke_width_and_pressure_only():
    from execution_refinement import refine_execution_rows

    rows = _rows_with_two_connectors()
    refined = refine_execution_rows(
        rows,
        style="xingkai",
        style_modifiers={"connection_preference": "weak"},
        connector_rule={"mode": "all_adjacent"},
        stroke_width_profile={
            "mode": "sinusoidal_taper",
            "start_width_scale": 0.8,
            "mid_width_scale": 1.2,
            "end_width_scale": 0.85,
            "start_pressure_scale": 0.8,
            "mid_pressure_scale": 1.0,
            "end_pressure_scale": 0.9,
        },
    )

    stroke_widths = [float(row["width"]) for row in refined if row["segment_type"] == "stroke"]
    stroke_pressures = [float(row["pressure"]) for row in refined if row["segment_type"] == "stroke"]
    connector_widths = [float(row["width"]) for row in refined if row["segment_type"] == "connector"]
    connector_pressures = [float(row["pressure"]) for row in refined if row["segment_type"] == "connector"]

    assert max(stroke_widths) - min(stroke_widths) > 0.0
    assert max(stroke_pressures) - min(stroke_pressures) > 0.0
    assert connector_widths and set(connector_widths) == {4.0}
    assert connector_pressures and set(connector_pressures) == {0.35}


def test_build_execution_trajectory_accepts_refinement_options():
    from execution_tools import build_execution_trajectory

    raw_strokes = [
        np.asarray([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0]], dtype=float),
        np.asarray([[34.0, 34.0], [44.0, 44.0], [54.0, 54.0]], dtype=float),
        np.asarray([[180.0, 180.0], [180.0, 210.0], [180.0, 240.0]], dtype=float),
    ]
    style_params = {
        "resample_step": 100.0,
        "smoothness": 0.0,
        "corner_rounding": 0.0,
        "horizontal_scale": 1.0,
        "vertical_scale": 1.0,
        "speed_scale": 1.0,
        "pen_up_height": 8.0,
        "allow_interstroke_connections": True,
        "connection_strength": 0.2,
    }

    baseline = build_execution_trajectory(
        raw_strokes,
        style_params,
        {"base_width": 10.0},
        {"connection_preference": "weak"},
        image_size=256,
    )
    refined = build_execution_trajectory(
        raw_strokes,
        style_params,
        {"base_width": 10.0},
        {"connection_preference": "weak"},
        image_size=256,
        style="xingkai",
        connector_rule={"mode": "distance_angle_gate", "max_connector_distance_abs": 30.0},
        stroke_width_profile={"mode": "sinusoidal_taper"},
    )

    assert _count_connectors(refined) < _count_connectors(baseline)
    widths = [float(row["width"]) for row in refined if row["segment_type"] == "stroke"]
    assert max(widths) - min(widths) > 0.0


def test_execution_refinement_module_does_not_import_libauboi5():
    module_path = SRC / "execution_refinement.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
