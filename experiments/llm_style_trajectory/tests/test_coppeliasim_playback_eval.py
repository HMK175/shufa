import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
COPPELIA_DIR = ROOT / "experiments" / "llm_style_trajectory" / "coppeliasim"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(COPPELIA_DIR) not in sys.path:
    sys.path.insert(0, str(COPPELIA_DIR))

from evaluate_playback_batch import evaluate_batch
from run_demo import run_batch
from workspace_mapping import WorkspaceConfig, process_batch as map_workspace_batch
from workspace_resampling import ResamplingConfig, process_batch as resample_workspace_batch


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


def _write_task_csv(task_dir: Path) -> None:
    task_dir.mkdir(parents=True)
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
            "stroke_id": 1,
            "point_id": 2,
            "X_mm": 6,
            "Y_mm": 8,
            "Z_mm": 0,
            "speed_mm_s": 40,
            "pressure": 0.34,
            "width": 4,
            "pen_down": 1,
            "is_connector": 1,
            "segment_type": "connector",
        },
        {
            "segment_id": 3,
            "stroke_id": 2,
            "point_id": 3,
            "X_mm": 6,
            "Y_mm": 8,
            "Z_mm": 8,
            "speed_mm_s": 70,
            "pressure": 0,
            "width": 0,
            "pen_down": 0,
            "is_connector": 0,
            "segment_type": "pen_up_move",
        },
    ]
    with (task_dir / "robot_workspace_trajectory_resampled.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_batch_playback_dry_run_writes_summary_and_report(tmp_path):
    batch_dir = tmp_path / "batch"
    _write_task_csv(batch_dir / "u5c71_xingkai_case")

    result = evaluate_batch(batch_dir)

    summary_path = batch_dir / "coppeliasim_playback_summary.csv"
    report_path = batch_dir / "coppeliasim_playback_report.md"
    assert result["summary_csv"] == summary_path
    assert result["report_md"] == report_path
    assert summary_path.exists()
    assert report_path.exists()

    with summary_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["task_dir"] == "u5c71_xingkai_case"
    assert rows[0]["connector_count"] == "1"
    assert rows[0]["pen_up_move_count"] == "1"
    assert rows[0]["max_step_3d_mm"] == "8.0"
    assert rows[0]["max_xy_step_mm"] == "5.0"
    assert rows[0]["max_z_step_mm"] == "8.0"
    assert "CoppeliaSim playback dry-run" in report_path.read_text(encoding="utf-8")


def test_fixed_connection_ablation_playback_xy_steps_stay_within_segment_thresholds(tmp_path):
    result = run_batch(
        tasks=[
            "写一个不要连笔的行楷山",
            "写一个行楷风格的山",
            "写一个更连贯的行楷山",
        ],
        output_root=tmp_path,
        graphics_path=ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt",
        style_profiles_path=EXP_DIR / "configs" / "style_profiles.json",
        image_size=160,
    )
    batch_dir = Path(result["batch_dir"])
    map_workspace_batch(batch_dir, WorkspaceConfig(image_size=160))
    resample_workspace_batch(batch_dir, ResamplingConfig())
    evaluate_batch(batch_dir)

    with (batch_dir / "coppeliasim_playback_summary.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_pref = {row["connection_preference"]: row for row in rows}

    assert float(by_pref["none"]["max_z_step_mm"]) == 8.0
    assert float(by_pref["none"]["max_xy_step_mm"]) <= 5.0
    assert float(by_pref["weak"]["max_xy_step_mm"]) <= 2.5
    assert float(by_pref["normal"]["max_xy_step_mm"]) <= 2.5


def test_dry_run_writes_single_playback_result_json_and_markdown(tmp_path):
    task_dir = tmp_path / "u5c71_xingkai_case"
    _write_task_csv(task_dir)
    csv_path = task_dir / "robot_workspace_trajectory_resampled.csv"
    result_dir = tmp_path / "single_result"
    script = COPPELIA_DIR / "play_workspace_path.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--display-stride",
            "5",
            "--auto-stop",
            "--no-path-objects",
            "--result-out-dir",
            str(result_dir),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_summary = json.loads(completed.stdout)
    result_json = result_dir / "coppeliasim_playback_result.json"
    result_md = result_dir / "coppeliasim_playback_result.md"
    assert result_json.exists()
    assert result_md.exists()

    result = json.loads(result_json.read_text(encoding="utf-8"))
    assert stdout_summary["status"] == "dry_run"
    assert result["status"] == "dry_run"
    assert result["auto_stop"] is True
    assert result["simulation_stopped"] is False
    assert result["display_stride"] == 5
    assert result["path_objects_enabled"] is False
    assert result["dry_run"] is True
    assert result["max_step_3d_mm"] == 8.0
    assert result["max_xy_step_mm"] == 5.0
    assert result["max_z_step_mm"] == 8.0
    assert "pen-tip/sphere playback only" in result_md.read_text(encoding="utf-8")


def test_dry_run_defaults_result_files_to_csv_directory(tmp_path):
    task_dir = tmp_path / "u5c71_xingkai_case"
    _write_task_csv(task_dir)
    script = COPPELIA_DIR / "play_workspace_path.py"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(task_dir / "robot_workspace_trajectory_resampled.csv"),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (task_dir / "coppeliasim_playback_result.json").exists()
    assert (task_dir / "coppeliasim_playback_result.md").exists()
