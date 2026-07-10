import csv
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aubo_i5_command_adapter import AdapterConfig, process_csv


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


def _write_target_poses(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _valid_rows() -> list[dict[str, object]]:
    return [
        {
            "pose_id": 0,
            "t_s": 0.0,
            "X_m": 0.0,
            "Y_m": 0.0,
            "Z_m": 0.0,
            "roll_deg": 180,
            "pitch_deg": 0,
            "yaw_deg": 0,
            "qw": 0,
            "qx": 1,
            "qy": 0,
            "qz": 0,
            "pen_down": 1,
            "segment_type": "stroke",
            "speed_m_s": 0.025,
            "source_X_mm": 0,
            "source_Y_mm": 0,
            "source_Z_mm": 0,
        },
        {
            "pose_id": 1,
            "t_s": 0.2,
            "X_m": 0.003,
            "Y_m": 0.004,
            "Z_m": 0.0,
            "roll_deg": 180,
            "pitch_deg": 0,
            "yaw_deg": 0,
            "qw": 0,
            "qx": 1,
            "qy": 0,
            "qz": 0,
            "pen_down": 1,
            "segment_type": "connector",
            "speed_m_s": 0.04,
            "source_X_mm": 3,
            "source_Y_mm": 4,
            "source_Z_mm": 0,
        },
        {
            "pose_id": 2,
            "t_s": 0.4,
            "X_m": 0.003,
            "Y_m": 0.004,
            "Z_m": 0.008,
            "roll_deg": 180,
            "pitch_deg": 0,
            "yaw_deg": 0,
            "qw": 0,
            "qx": 1,
            "qy": 0,
            "qz": 0,
            "pen_down": 0,
            "segment_type": "pen_up_move",
            "speed_m_s": 0.07,
            "source_X_mm": 3,
            "source_Y_mm": 4,
            "source_Z_mm": 8,
        },
    ]


def test_process_csv_writes_offline_command_plan_and_safety_files(tmp_path):
    source_csv = tmp_path / "robot_target_poses.csv"
    _write_target_poses(source_csv, _valid_rows())

    result = process_csv(source_csv, AdapterConfig())

    plan_csv = Path(result["command_plan_csv"])
    safety_json = Path(result["safety_check_json"])
    report_md = Path(result["command_plan_md"])
    assert plan_csv.exists()
    assert safety_json.exists()
    assert report_md.exists()

    with plan_csv.open(newline="", encoding="utf-8") as f:
        commands = list(csv.DictReader(f))

    assert [row["command_type"] for row in commands] == [
        "move_joint_approach",
        "move_line",
        "move_line",
        "move_line",
        "move_line_retract",
    ]
    assert all(row["dry_run_only"] == "true" for row in commands)
    assert all("future:" in row["sdk_hint"] for row in commands)
    report_text = report_md.read_text(encoding="utf-8").lower()
    assert "does not connect" in report_text
    assert "no real robot control" in report_text
    assert "pen-up segment" in commands[3]["notes"]

    safety = json.loads(safety_json.read_text(encoding="utf-8"))
    assert safety["point_count"] == 3
    assert safety["command_count"] == 5
    assert safety["max_step_m"] == pytest_approx(0.008)
    assert safety["max_speed_m_s"] == pytest_approx(0.07)
    assert safety["quaternion_normalized"] is True
    assert safety["time_monotonic"] is True
    assert safety["has_nan_or_inf"] is False
    assert safety["recommended_for_sdk_dry_run"] is True
    assert safety["warnings"] == []
    assert "dry-run command plan only" in safety["scope"]


def test_safety_check_flags_bad_target_pose_rows(tmp_path):
    rows = _valid_rows()
    rows[1]["t_s"] = -0.1
    rows[1]["X_m"] = 0.1
    rows[1]["speed_m_s"] = 0.2
    rows[1]["qw"] = 2.0
    rows[1]["qx"] = 0.0
    rows[2]["Y_m"] = "nan"
    source_csv = tmp_path / "bad_robot_target_poses.csv"
    _write_target_poses(source_csv, rows)

    result = process_csv(source_csv, AdapterConfig())
    safety = json.loads(Path(result["safety_check_json"]).read_text(encoding="utf-8"))

    assert safety["recommended_for_sdk_dry_run"] is False
    assert safety["has_nan_or_inf"] is True
    assert safety["time_monotonic"] is False
    assert safety["quaternion_normalized"] is False
    assert safety["max_speed_m_s"] > 0.10
    assert safety["max_step_m"] > 0.015
    assert any("NaN or inf" in warning for warning in safety["warnings"])
    assert any("time" in warning for warning in safety["warnings"])
    assert any("quaternion" in warning for warning in safety["warnings"])
    assert any("speed" in warning for warning in safety["warnings"])
    assert any("step" in warning for warning in safety["warnings"])


def test_adapter_module_does_not_import_aubo_sdk(tmp_path):
    source_csv = tmp_path / "robot_target_poses.csv"
    _write_target_poses(source_csv, _valid_rows())
    sys.modules.pop("libpyauboi5", None)

    process_csv(source_csv, AdapterConfig())

    assert "libpyauboi5" not in sys.modules


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=1e-6)
