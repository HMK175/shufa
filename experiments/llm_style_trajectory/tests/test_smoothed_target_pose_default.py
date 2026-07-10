import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aubo_i5_command_adapter import AdapterConfig, process_csv as process_command_csv
from aubo_i5_ik_feasibility import FeasibilityConfig, process_csv as process_feasibility_csv
from target_pose_defaults import select_default_target_pose_csv


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


def _rows(count: int = 2) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx in range(count):
        rows.append(
            {
                "pose_id": idx,
                "t_s": idx * 0.1,
                "X_m": idx * 0.001,
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
                "speed_m_s": 0.01,
                "source_X_mm": idx,
                "source_Y_mm": 0,
                "source_Z_mm": 0,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_retiming_metadata(task_dir: Path) -> None:
    (task_dir / "target_pose_retiming_summary.json").write_text(
        json.dumps({"retiming_success": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (task_dir / "motion_continuity_after_retiming_summary.json").write_text(
        json.dumps({"recommended_for_ik_dry_run": True}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_default_target_pose_selection_prefers_smoothed_and_falls_back_to_raw(tmp_path):
    raw = tmp_path / "robot_target_poses.csv"
    smoothed = tmp_path / "robot_target_poses_smoothed.csv"
    _write_csv(raw, _rows(3))
    _write_csv(smoothed, _rows(2))

    assert select_default_target_pose_csv(tmp_path) == smoothed

    smoothed.unlink()

    assert select_default_target_pose_csv(tmp_path) == raw


def test_explicit_raw_command_adapter_input_is_not_replaced_by_smoothed(tmp_path):
    raw = tmp_path / "robot_target_poses.csv"
    smoothed = tmp_path / "robot_target_poses_smoothed.csv"
    _write_csv(raw, _rows(3))
    _write_csv(smoothed, _rows(2))

    result = process_command_csv(raw, AdapterConfig())

    assert result["source_csv"] == str(raw)
    assert Path(result["command_plan_csv"]).name == "aubo_i5_command_plan.csv"
    safety = json.loads(Path(result["safety_check_json"]).read_text(encoding="utf-8"))
    assert safety["point_count"] == 3
    assert safety["source_target_pose_csv"] == str(raw)
    assert safety["source_target_pose_kind"] == "raw"


def test_smoothed_command_adapter_uses_smoothed_output_names_and_metadata(tmp_path):
    smoothed = tmp_path / "robot_target_poses_smoothed.csv"
    _write_csv(smoothed, _rows(2))
    _write_retiming_metadata(tmp_path)

    result = process_command_csv(smoothed, AdapterConfig())

    assert Path(result["command_plan_csv"]).name == "aubo_i5_command_plan_smoothed.csv"
    assert Path(result["safety_check_json"]).name == "aubo_i5_safety_check_smoothed.json"
    assert Path(result["command_plan_md"]).name == "aubo_i5_command_plan_smoothed.md"
    safety = json.loads(Path(result["safety_check_json"]).read_text(encoding="utf-8"))
    assert safety["point_count"] == 2
    assert safety["command_count"] == 4
    assert safety["source_target_pose_kind"] == "smoothed"
    assert safety["source_retiming_summary"].endswith("target_pose_retiming_summary.json")
    assert safety["source_motion_continuity_after_retiming"].endswith(
        "motion_continuity_after_retiming_summary.json"
    )
    assert safety["recommended_for_sdk_dry_run"] is True


def test_smoothed_ik_feasibility_uses_smoothed_output_names_and_recommends_dry_run(tmp_path):
    smoothed = tmp_path / "robot_target_poses_smoothed.csv"
    _write_csv(smoothed, _rows(2))
    _write_retiming_metadata(tmp_path)

    result = process_feasibility_csv(smoothed, FeasibilityConfig())

    assert Path(result["summary_json"]).name == "aubo_i5_ik_feasibility_smoothed_summary.json"
    assert Path(result["report_md"]).name == "aubo_i5_ik_feasibility_smoothed_report.md"
    assert Path(result["points_csv"]).name == "aubo_i5_ik_feasibility_smoothed_points.csv"
    summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
    assert summary["point_count"] == 2
    assert summary["source_target_pose_csv"] == str(smoothed)
    assert summary["source_target_pose_kind"] == "smoothed"
    assert summary["source_retiming_summary"].endswith("target_pose_retiming_summary.json")
    assert summary["recommended_for_real_ik_check"] is True


def test_smoothed_default_flow_does_not_import_aubo_sdk(tmp_path):
    smoothed = tmp_path / "robot_target_poses_smoothed.csv"
    _write_csv(smoothed, _rows(2))
    sys.modules.pop("libpyauboi5", None)

    process_command_csv(smoothed, AdapterConfig())
    process_feasibility_csv(smoothed, FeasibilityConfig())

    assert "libpyauboi5" not in sys.modules
