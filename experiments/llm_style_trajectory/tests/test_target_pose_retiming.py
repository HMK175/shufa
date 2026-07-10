import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import target_pose_retiming
from target_pose_retiming import RetimingConfig, process_csv


FIELDS = [
    "pose_id",
    "t_s",
    "X_m",
    "Y_m",
    "Z_m",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "qw",
    "qx",
    "qy",
    "qz",
    "pen_down",
    "segment_type",
    "speed_m_s",
    "source_X_mm",
    "source_Y_mm",
    "source_Z_mm",
]


def _row(pose_id: int, t_s: float, x_m: float, segment_type: str = "stroke") -> dict[str, object]:
    return {
        "pose_id": pose_id,
        "t_s": t_s,
        "X_m": x_m,
        "Y_m": 0.0,
        "Z_m": 0.0,
        "roll_deg": 180.0,
        "pitch_deg": 0.0,
        "yaw_deg": 0.0,
        "qw": 0.0,
        "qx": 1.0,
        "qy": 0.0,
        "qz": 0.0,
        "pen_down": 1,
        "segment_type": segment_type,
        "speed_m_s": 0.025,
        "source_X_mm": x_m * 1000.0,
        "source_Y_mm": 0.0,
        "source_Z_mm": 0.0,
    }


def _write_pose_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_process_csv_writes_smoothed_outputs_and_after_motion_check(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    rows = [_row(0, 0.0, 0.0), _row(1, 0.0, 0.0), _row(2, 0.0, 0.002), _row(3, 0.01, 0.004)]
    _write_pose_csv(csv_path, rows)

    result = process_csv(csv_path)

    assert Path(result["smoothed_csv"]).exists()
    assert Path(result["summary_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["after_motion_summary_json"]).exists()
    assert Path(result["after_motion_report_md"]).exists()
    assert Path(result["after_motion_points_csv"]).exists()
    assert result["summary"]["removed_duplicate_count"] == 1
    assert result["summary"]["retimed_point_count"] == 3
    assert result["after_motion_summary"]["dt_nonpositive_count"] == 0
    assert result["after_motion_summary"]["recommended_for_coppeliasim_playback"] is True
    assert result["after_motion_summary"]["recommended_for_ik_dry_run"] is True


def test_output_time_is_strictly_increasing(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_pose_csv(csv_path, [_row(0, 0.0, 0.0), _row(1, 0.0, 0.002), _row(2, 0.0, 0.004)])

    result = process_csv(csv_path)
    smoothed_rows = _read_rows(Path(result["smoothed_csv"]))
    times = [float(row["t_s"]) for row in smoothed_rows]

    assert all(b > a for a, b in zip(times, times[1:]))
    assert result["after_motion_summary"]["dt_nonpositive_count"] == 0


def test_same_time_different_position_is_retained_and_retimed(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_pose_csv(csv_path, [_row(0, 0.0, 0.0), _row(1, 0.0, 0.002), _row(2, 0.0, 0.004)])

    result = process_csv(csv_path)
    smoothed_rows = _read_rows(Path(result["smoothed_csv"]))

    assert len(smoothed_rows) == 3
    assert result["summary"]["removed_duplicate_count"] == 0
    assert [float(row["X_m"]) for row in smoothed_rows] == [0.0, 0.002, 0.004]


def test_geometry_path_length_is_preserved_except_duplicate_points(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_pose_csv(csv_path, [_row(0, 0.0, 0.0), _row(1, 0.0, 0.0), _row(2, 0.0, 0.003)])

    result = process_csv(csv_path)
    summary = result["summary"]

    assert summary["geometry_path_length_before_m"] == pytest_approx(0.003)
    assert summary["geometry_path_length_after_m"] == pytest_approx(0.003)
    assert abs(summary["path_length_delta_m"]) < 1e-12


def test_iterative_time_scaling_reduces_accel_and_jerk_under_thresholds(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    rows = [
        _row(0, 0.0, 0.0),
        _row(1, 0.001, 0.003),
        _row(2, 0.002, 0.006),
        _row(3, 0.003, 0.009),
    ]
    _write_pose_csv(csv_path, rows)

    result = process_csv(
        csv_path,
        config=RetimingConfig(stroke_speed_m_s=0.08, max_iterations=8, time_scale_step=1.25),
    )
    after = result["after_motion_summary"]

    assert result["summary"]["iterations_used"] >= 1
    assert after["max_accel_m_s2"] <= 0.5
    assert after["max_jerk_m_s3"] <= 5.0
    assert after["recommended_for_ik_dry_run"] is True


def test_target_pose_retiming_module_does_not_import_aubo_sdk():
    source = Path(target_pose_retiming.__file__).read_text(encoding="utf-8")

    assert "libpyauboi5" not in source
    assert "libpyauboi5" not in sys.modules


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=1e-9)
