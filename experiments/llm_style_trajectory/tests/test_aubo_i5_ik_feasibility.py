import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aubo_i5_ik_feasibility import FeasibilityConfig, process_csv


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


def _rows():
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


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or FIELDS
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def test_feasibility_summary_report_and_points_are_generated_for_valid_targets(tmp_path):
    source_csv = tmp_path / "robot_target_poses.csv"
    _write_csv(source_csv, _rows())

    result = process_csv(source_csv, FeasibilityConfig())

    summary_path = Path(result["summary_json"])
    report_path = Path(result["report_md"])
    points_path = Path(result["points_csv"])
    assert summary_path.exists()
    assert report_path.exists()
    assert points_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["point_count"] == 3
    assert summary["source_csv"] == str(source_csv)
    assert summary["xy_range_m"] == {"x": [0.0, 0.003], "y": [0.0, 0.004]}
    assert summary["z_range_m"] == [0.0, 0.008]
    assert summary["radius_range_m"] == [0.0, 0.009434]
    assert summary["max_step_m"] == pytest_approx(0.008)
    assert summary["max_speed_m_s"] == pytest_approx(0.07)
    assert summary["time_monotonic"] is True
    assert summary["quaternion_normalized"] is True
    assert summary["has_nan_or_inf"] is False
    assert summary["required_fields_present"] is True
    assert summary["within_conservative_envelope"] is True
    assert summary["recommended_for_real_ik_check"] is True
    assert summary["warnings"] == []
    assert "not real IK" in report_path.read_text(encoding="utf-8")


def test_feasibility_flags_missing_required_fields(tmp_path):
    source_csv = tmp_path / "missing_fields.csv"
    fields = [field for field in FIELDS if field != "qz"]
    _write_csv(source_csv, _rows(), fields=fields)

    summary = process_csv(source_csv, FeasibilityConfig())["summary"]

    assert summary["required_fields_present"] is False
    assert summary["recommended_for_real_ik_check"] is False
    assert "qz" in summary["missing_fields"]
    assert any("required fields" in warning for warning in summary["warnings"])


def test_feasibility_flags_nan_inf_nonmonotonic_bad_quaternion_and_envelope(tmp_path):
    rows = _rows()
    rows[1]["t_s"] = -0.1
    rows[1]["X_m"] = 0.8
    rows[1]["speed_m_s"] = 0.2
    rows[1]["qw"] = 2
    rows[1]["qx"] = 0
    rows[2]["Y_m"] = "nan"
    source_csv = tmp_path / "bad_robot_target_poses.csv"
    _write_csv(source_csv, rows)

    summary = process_csv(source_csv, FeasibilityConfig(envelope_max_radius_m=0.2))["summary"]

    assert summary["recommended_for_real_ik_check"] is False
    assert summary["has_nan_or_inf"] is True
    assert summary["time_monotonic"] is False
    assert summary["quaternion_normalized"] is False
    assert summary["within_conservative_envelope"] is False
    assert summary["max_step_m"] > 0.015
    assert summary["max_speed_m_s"] > 0.10
    assert any("NaN or inf" in warning for warning in summary["warnings"])
    assert any("time" in warning for warning in summary["warnings"])
    assert any("quaternion" in warning for warning in summary["warnings"])
    assert any("envelope" in warning for warning in summary["warnings"])


def test_feasibility_module_does_not_import_aubo_sdk(tmp_path):
    source_csv = tmp_path / "robot_target_poses.csv"
    _write_csv(source_csv, _rows())
    sys.modules.pop("libpyauboi5", None)

    process_csv(source_csv, FeasibilityConfig())

    assert "libpyauboi5" not in sys.modules


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=1e-6)
