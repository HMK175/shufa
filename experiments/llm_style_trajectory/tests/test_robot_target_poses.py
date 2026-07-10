import csv
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from robot_target_poses import TargetPoseConfig, process_csv, rpy_to_quaternion


FIELDS = [
    "segment_id",
    "stroke_id",
    "point_id",
    "X_mm",
    "Y_mm",
    "Z_mm",
    "speed_mm_s",
    "pressure",
    "width",
    "pen_down",
    "is_connector",
    "segment_type",
]


def _write_workspace_csv(path: Path) -> None:
    rows = [
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 0,
            "X_mm": 0,
            "Y_mm": 0,
            "Z_mm": 0,
            "speed_mm_s": 25,
            "pressure": 1,
            "width": 9,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
        },
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 1,
            "X_mm": 3,
            "Y_mm": 4,
            "Z_mm": 0,
            "speed_mm_s": 25,
            "pressure": 1,
            "width": 9,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
        },
        {
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 2,
            "X_mm": 3,
            "Y_mm": 4,
            "Z_mm": 8,
            "speed_mm_s": 70,
            "pressure": 0,
            "width": 0,
            "pen_down": 0,
            "is_connector": 0,
            "segment_type": "pen_up_move",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_rpy_to_quaternion_is_normalized_for_default_pen_down_pose():
    q = rpy_to_quaternion(roll_deg=180, pitch_deg=0, yaw_deg=0)

    norm = math.sqrt(sum(value * value for value in q))
    assert norm == pytest_approx(1.0)
    assert q[0] == pytest_approx(0.0)
    assert abs(q[1]) == pytest_approx(1.0)
    assert q[2] == pytest_approx(0.0)
    assert q[3] == pytest_approx(0.0)


def test_process_csv_converts_mm_to_m_time_speed_and_pose_outputs(tmp_path):
    source_csv = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_workspace_csv(source_csv)

    result = process_csv(source_csv, TargetPoseConfig(origin_x_m=0.1, origin_y_m=-0.2, origin_z_m=0.3))

    out_csv = Path(result["target_pose_csv"])
    out_report = Path(result["report_md"])
    out_summary = Path(result["summary_json"])
    assert out_csv.exists()
    assert out_report.exists()
    assert out_summary.exists()

    with out_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    assert rows[0]["pose_id"] == "0"
    assert float(rows[0]["X_m"]) == pytest_approx(0.1)
    assert float(rows[1]["X_m"]) == pytest_approx(0.103)
    assert float(rows[1]["Y_m"]) == pytest_approx(-0.196)
    assert float(rows[2]["Z_m"]) == pytest_approx(0.308)
    assert float(rows[1]["speed_m_s"]) == pytest_approx(0.025)
    assert rows[2]["pen_down"] == "0"
    assert rows[2]["segment_type"] == "pen_up_move"
    assert float(rows[0]["roll_deg"]) == pytest_approx(180.0)
    assert float(rows[0]["pitch_deg"]) == pytest_approx(0.0)
    assert float(rows[0]["yaw_deg"]) == pytest_approx(0.0)

    times = [float(row["t_s"]) for row in rows]
    assert times == sorted(times)
    assert times[0] == pytest_approx(0.0)
    assert times[1] > times[0]
    assert times[2] > times[1]

    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    assert summary["point_count"] == 3
    assert summary["duration_s"] == pytest_approx(times[-1])
    assert summary["path_length_m"] == pytest_approx(0.013)
    assert summary["max_step_m"] == pytest_approx(0.008)
    assert summary["max_speed_m_s"] == pytest_approx(0.07)
    assert summary["segment_counts"] == {"pen_up_move": 1, "stroke": 2}
    assert summary["recommended_for_ik_dry_run"] is True
    assert summary["warnings"] == []
    assert "target pose only" in out_report.read_text(encoding="utf-8")


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=1e-6)
