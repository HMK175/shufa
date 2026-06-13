import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COPPELIA_DIR = ROOT / "experiments" / "llm_style_trajectory" / "coppeliasim"
if str(COPPELIA_DIR) not in sys.path:
    sys.path.insert(0, str(COPPELIA_DIR))

from play_workspace_path import build_arg_parser, dry_run_summary, load_workspace_path, mm_to_m


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


def _write_csv(path: Path) -> None:
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
            "X_mm": 10,
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
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 2,
            "X_mm": 10,
            "Y_mm": 0,
            "Z_mm": 8,
            "speed_mm_s": 70,
            "pressure": 0,
            "width": 0,
            "pen_down": 0,
            "is_connector": 0,
            "segment_type": "pen_up_move",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_mm_to_meter_mapping():
    assert mm_to_m(120) == 0.12
    assert mm_to_m(-30) == -0.03


def test_load_workspace_path_converts_points_to_meters(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)

    points = load_workspace_path(csv_path)

    assert len(points) == 3
    assert points[1]["position_m"] == (0.01, 0.0, 0.0)
    assert points[2]["position_m"] == (0.01, 0.0, 0.008)


def test_dry_run_summary_reports_counts_bounds_duration_and_max_step(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)

    summary = dry_run_summary(csv_path)

    assert summary["point_count"] == 3
    assert summary["segment_type_counts"] == {"pen_up_move": 1, "stroke": 2}
    assert summary["x_mm_range"] == [0.0, 10.0]
    assert summary["z_mm_range"] == [0.0, 8.0]
    assert summary["max_step_mm"] >= 10.0
    assert summary["max_step_3d_mm"] >= 10.0
    assert summary["max_xy_step_mm"] == 10.0
    assert summary["max_z_step_mm"] == 8.0
    assert summary["path_length_mm"] > 0
    assert summary["duration_estimate_s"] > 0


def test_low_load_playback_options_are_parseable():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--csv",
            "robot_workspace_trajectory_resampled.csv",
            "--display-stride",
            "5",
            "--no-path-objects",
            "--auto-stop",
        ]
    )

    assert args.display_stride == 5
    assert args.no_path_objects is True
    assert args.auto_stop is True


def test_display_stride_does_not_change_dry_run_point_count_or_path_length(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)

    direct = dry_run_summary(csv_path)
    script = COPPELIA_DIR / "play_workspace_path.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--dry-run",
            "--display-stride",
            "5",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    via_cli = json.loads(result.stdout)

    assert via_cli["point_count"] == direct["point_count"]
    assert via_cli["path_length_mm"] == direct["path_length_mm"]


def test_dry_run_max_xy_step_catches_inter_segment_jump(tmp_path):
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
            "X_mm": 1,
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
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 2,
            "X_mm": 41,
            "Y_mm": 0,
            "Z_mm": 0,
            "speed_mm_s": 40,
            "pressure": 0.34,
            "width": 4,
            "pen_down": 1,
            "is_connector": 1,
            "segment_type": "connector",
        },
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = dry_run_summary(csv_path)

    assert summary["max_xy_step_mm"] == 40.0
