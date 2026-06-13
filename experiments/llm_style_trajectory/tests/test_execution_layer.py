import csv
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution_tools import build_execution_trajectory
from run_demo import run_batch


GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
PROFILES = EXP_DIR / "configs" / "style_profiles.json"


def _run_connection_batch(tmp_path):
    return run_batch(
        tasks=[
            "写一个不要连笔的行楷山",
            "写一个行楷风格的山",
            "写一个更连贯的行楷山",
        ],
        output_root=tmp_path,
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
        image_size=160,
    )


def _read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_execution_trajectory_csv_fields_and_old_csv_are_preserved(tmp_path):
    result = _run_connection_batch(tmp_path)
    first = result["results"][0]

    old_rows = _read_csv(first["trajectory_csv"])
    assert list(old_rows[0].keys()) == ["y", "x"]
    assert any(row["y"].lower() == "nan" and row["x"].lower() == "nan" for row in old_rows)

    exec_rows = _read_csv(first["execution_trajectory_csv"])
    expected_fields = {
        "stroke_id",
        "point_id",
        "y",
        "x",
        "z",
        "speed",
        "pressure",
        "width",
        "pen_down",
        "is_connector",
        "segment_type",
    }
    assert expected_fields.issubset(exec_rows[0].keys())


def test_pen_up_move_rows_have_lifted_pen_state(tmp_path):
    result = _run_connection_batch(tmp_path)
    none_result = result["results"][0]
    exec_rows = _read_csv(none_result["execution_trajectory_csv"])
    pen_up_rows = [row for row in exec_rows if row["segment_type"] == "pen_up_move"]

    assert pen_up_rows
    assert all(row["pen_down"] == "0" for row in pen_up_rows)
    assert all(float(row["pressure"]) == 0 for row in pen_up_rows)
    assert all(float(row["width"]) == 0 for row in pen_up_rows)
    assert all(float(row["z"]) > 0 for row in pen_up_rows)


def test_weak_connector_pressure_and_width_are_below_normal(tmp_path):
    result = _run_connection_batch(tmp_path)
    rows = _read_csv(result["modifier_summary_csv"])
    by_pref = {row["connection_preference"]: row for row in rows}

    assert float(by_pref["none"]["connector_draw_length"]) == 0
    assert float(by_pref["none"]["pen_up_move_length"]) > 0
    assert float(by_pref["weak"]["connector_draw_length"]) > 0
    assert float(by_pref["normal"]["connector_draw_length"]) > 0
    assert float(by_pref["weak"]["connector_mean_pressure"]) < float(by_pref["normal"]["connector_mean_pressure"])
    assert float(by_pref["weak"]["connector_mean_width"]) < float(by_pref["normal"]["connector_mean_width"])
    assert float(by_pref["weak"]["mean_pressure"]) < float(by_pref["normal"]["mean_pressure"])


def test_connector_geometry_reaches_next_stroke_start():
    raw_strokes = [
        np.asarray([[10.0, 10.0], [20.0, 10.0]], dtype=float),
        np.asarray([[40.0, 50.0], [60.0, 50.0]], dtype=float),
    ]
    style_params = {
        "resample_step": 100.0,
        "smoothness": 0.0,
        "corner_rounding": 0.0,
        "horizontal_scale": 1.0,
        "vertical_scale": 1.0,
        "speed_scale": 1.0,
        "pen_up_height": 4.0,
        "allow_interstroke_connections": True,
        "connection_strength": 0.2,
    }
    rows = build_execution_trajectory(
        raw_strokes,
        style_params,
        {"base_width": 9.0},
        {"connection_preference": "weak"},
        image_size=80,
    )

    connector_rows = [row for row in rows if row["segment_type"] == "connector"]
    second_stroke_rows = [row for row in rows if row["segment_type"] == "stroke" and row["stroke_id"] == 2]
    assert connector_rows
    assert second_stroke_rows
    assert np.allclose(
        [connector_rows[-1]["y"], connector_rows[-1]["x"]],
        [second_stroke_rows[0]["y"], second_stroke_rows[0]["x"]],
    )


def test_execution_ablation_compare_image_is_generated(tmp_path):
    result = _run_connection_batch(tmp_path)

    compare_path = Path(result["execution_compare_images"]["山"])
    assert compare_path.exists()
    assert compare_path.name == "execution_ablation_u5c71.png"
