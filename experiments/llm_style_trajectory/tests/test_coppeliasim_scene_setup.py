import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COPPELIA_DIR = ROOT / "experiments" / "llm_style_trajectory" / "coppeliasim"
if str(COPPELIA_DIR) not in sys.path:
    sys.path.insert(0, str(COPPELIA_DIR))

from play_workspace_path import build_arg_parser


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


def _write_csv(path: Path, *, x_extent: float = 10.0, z_max: float = 8.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 0,
            "X_mm": -x_extent,
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
            "X_mm": x_extent,
            "Y_mm": 0,
            "Z_mm": z_max,
            "speed_mm_s": 25,
            "pressure": 1,
            "width": 9,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_scene_setup_arguments_are_parseable():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--scene-setup",
            "standard",
            "--clear-previous-scene",
            "--paper-size-mm",
            "120",
            "--pen-tip-radius-mm",
            "1.5",
            "--show-axes",
            "--show-boundary",
        ]
    )

    assert args.scene_setup == "standard"
    assert args.clear_previous_scene is True
    assert args.paper_size_mm == 120
    assert args.pen_tip_radius_mm == 1.5
    assert args.show_axes is True
    assert args.show_boundary is True


def test_dry_run_result_contains_standard_scene_report(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)
    script = COPPELIA_DIR / "play_workspace_path.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--scene-setup",
            "standard",
            "--paper-size-mm",
            "120",
            "--pen-tip-radius-mm",
            "1.5",
            "--show-axes",
            "--show-boundary",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["scene_setup"] == "standard"
    assert result["paper_size_mm"] == 120.0
    assert result["pen_tip_radius_mm"] == 1.5
    assert result["axes_enabled"] is True
    assert result["boundary_enabled"] is True
    assert result["coordinate_mapping"] == {
        "X_m": "X_mm / 1000",
        "Y_m": "Y_mm / 1000",
        "Z_m": "Z_mm / 1000",
    }
    assert result["workspace_bounds"]["xy_within_bounds"] is True
    assert result["workspace_bounds"]["z_within_bounds"] is True
    assert result["recommended_playback"] is True
    assert "standard pen-tip scene only, no robot arm IK" in result["scope"]


def test_dry_run_scene_bounds_warn_when_paper_is_too_small(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path, x_extent=10.0)
    script = COPPELIA_DIR / "play_workspace_path.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--paper-size-mm",
            "12",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["out_of_workspace_bounds"] is True
    assert result["workspace_bounds"]["xy_within_bounds"] is False
    assert result["recommended_playback"] is False
    assert result["scene_warnings"]
