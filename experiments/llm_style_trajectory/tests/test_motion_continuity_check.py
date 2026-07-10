import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import motion_continuity_check
from motion_continuity_check import MotionThresholds, process_csv


TARGET_FIELDS = [
    "pose_id",
    "t_s",
    "X_m",
    "Y_m",
    "Z_m",
    "qw",
    "qx",
    "qy",
    "qz",
    "segment_type",
    "speed_m_s",
]


WORKSPACE_FIELDS = [
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


def _write_target_pose_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _target_rows() -> list[dict[str, object]]:
    return [
        {
            "pose_id": 0,
            "t_s": 0.0,
            "X_m": 0.0,
            "Y_m": 0.0,
            "Z_m": 0.0,
            "qw": 0.0,
            "qx": 1.0,
            "qy": 0.0,
            "qz": 0.0,
            "segment_type": "stroke",
            "speed_m_s": 0.025,
        },
        {
            "pose_id": 1,
            "t_s": 0.1,
            "X_m": 0.002,
            "Y_m": 0.0,
            "Z_m": 0.0,
            "qw": 0.0,
            "qx": 1.0,
            "qy": 0.0,
            "qz": 0.0,
            "segment_type": "stroke",
            "speed_m_s": 0.025,
        },
        {
            "pose_id": 2,
            "t_s": 0.2,
            "X_m": 0.004,
            "Y_m": 0.0,
            "Z_m": 0.0,
            "qw": 0.0,
            "qx": 1.0,
            "qy": 0.0,
            "qz": 0.0,
            "segment_type": "connector",
            "speed_m_s": 0.04,
        },
        {
            "pose_id": 3,
            "t_s": 0.3,
            "X_m": 0.006,
            "Y_m": 0.0,
            "Z_m": 0.0,
            "qw": 0.0,
            "qx": 1.0,
            "qy": 0.0,
            "qz": 0.0,
            "segment_type": "connector",
            "speed_m_s": 0.04,
        },
    ]


def test_normal_robot_target_poses_generates_summary_report_and_points(tmp_path):
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_target_pose_csv(csv_path, _target_rows())

    result = process_csv(csv_path)

    summary_path = Path(result["summary_json"])
    report_path = Path(result["report_md"])
    points_path = Path(result["points_csv"])
    assert summary_path.exists()
    assert report_path.exists()
    assert points_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["input_kind"] == "target_pose"
    assert summary["point_count"] == 4
    assert summary["time_monotonic"] is True
    assert summary["max_speed_m_s"] <= 0.1
    assert summary["quaternion_normalized"] is True
    assert summary["recommended_for_coppeliasim_playback"] is True
    assert summary["recommended_for_ik_dry_run"] is True
    assert summary["failure_reasons"] == []
    assert "not real robot dynamics" in report_path.read_text(encoding="utf-8")

    with points_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert "accel_m_s2" in rows[0]
    assert "jerk_m_s3" in rows[0]


def test_nonmonotonic_time_is_rejected(tmp_path):
    rows = _target_rows()
    rows[2]["t_s"] = 0.05
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_target_pose_csv(csv_path, rows)

    summary = process_csv(csv_path)["summary"]

    assert summary["time_monotonic"] is False
    assert summary["recommended_for_ik_dry_run"] is False
    assert any("dt <= 0" in reason or "time is not strictly increasing" in reason for reason in summary["failure_reasons"])


def test_speed_spike_or_speed_jump_is_rejected(tmp_path):
    rows = _target_rows()
    rows[2]["X_m"] = 0.2
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_target_pose_csv(csv_path, rows)

    summary = process_csv(csv_path)["summary"]

    assert summary["max_speed_m_s"] > 0.1
    assert summary["max_speed_jump_m_s"] > 0.05
    assert summary["recommended_for_ik_dry_run"] is False


def test_jerk_spike_is_rejected(tmp_path):
    rows = _target_rows()
    rows[2]["X_m"] = 0.03
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_target_pose_csv(csv_path, rows)

    result = process_csv(
        csv_path,
        thresholds=MotionThresholds(max_speed_m_s=1.0, max_accel_m_s2=10.0, max_jerk_m_s3=2.0),
    )
    summary = result["summary"]

    assert summary["max_jerk_m_s3"] > 2.0
    assert summary["jerk_peak_count"] > 0
    assert summary["recommended_for_ik_dry_run"] is False


def test_non_normalized_quaternion_is_warned_and_rejected(tmp_path):
    rows = _target_rows()
    rows[1]["qx"] = 2.0
    csv_path = tmp_path / "robot_target_poses.csv"
    _write_target_pose_csv(csv_path, rows)

    summary = process_csv(csv_path)["summary"]

    assert summary["quaternion_normalized"] is False
    assert summary["quaternion_norm_max"] > 1.0
    assert summary["recommended_for_ik_dry_run"] is False
    assert any("quaternion" in reason for reason in summary["failure_reasons"])


def test_workspace_csv_is_auto_detected_and_checked(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
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
            "X_mm": 2,
            "Y_mm": 0,
            "Z_mm": 0,
            "speed_mm_s": 25,
            "pressure": 1,
            "width": 9,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
        },
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=WORKSPACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = process_csv(csv_path, input_kind="auto")["summary"]

    assert summary["input_kind"] == "workspace"
    assert summary["required_fields_present"] is True
    assert summary["point_count"] == 2
    assert summary["time_monotonic"] is True
    assert summary["recommended_for_coppeliasim_playback"] is True


def test_motion_continuity_module_does_not_import_aubo_sdk():
    source = Path(motion_continuity_check.__file__).read_text(encoding="utf-8")

    assert "libpyauboi5" not in source
    assert "libpyauboi5" not in sys.modules
