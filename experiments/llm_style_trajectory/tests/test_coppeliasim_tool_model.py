import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COPPELIA_DIR = ROOT / "experiments" / "llm_style_trajectory" / "coppeliasim"
if str(COPPELIA_DIR) not in sys.path:
    sys.path.insert(0, str(COPPELIA_DIR))

import play_workspace_path
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


def _write_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 0,
            "X_mm": -5,
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
            "X_mm": 5,
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
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_tool_model_arguments_are_parseable():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--tool-model",
            "simple-pen",
            "--show-tool-frame",
            "--tool-length-mm",
            "120",
            "--tool-radius-mm",
            "4",
            "--tcp-offset-mm",
            "2",
            "--base-frame-origin-mm",
            "1,2,3",
        ]
    )

    assert args.tool_model == "simple-pen"
    assert args.show_tool_frame is True
    assert args.tool_length_mm == 120
    assert args.tool_radius_mm == 4
    assert args.tcp_offset_mm == 2
    assert args.base_frame_origin_mm == [1.0, 2.0, 3.0]


def test_dry_run_simple_pen_writes_tool_model_result(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)
    script = COPPELIA_DIR / "play_workspace_path.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--tool-model",
            "simple-pen",
            "--show-tool-frame",
            "--tool-length-mm",
            "120",
            "--tool-radius-mm",
            "4",
            "--tcp-offset-mm",
            "0",
            "--base-frame-origin-mm",
            "0,0,0",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_result = json.loads(completed.stdout)
    result_json = csv_path.parent / "coppeliasim_tool_model_result.json"
    result_md = csv_path.parent / "coppeliasim_tool_model_result.md"
    assert result_json.exists()
    assert result_md.exists()

    result = json.loads(result_json.read_text(encoding="utf-8"))
    assert stdout_result["tool_model"] == "simple-pen"
    assert result["tool_model"] == "simple-pen"
    assert result["tool_length_mm"] == 120.0
    assert result["tool_radius_mm"] == 4.0
    assert result["tcp_offset_mm"] == 0.0
    assert result["base_frame_origin_mm"] == [0.0, 0.0, 0.0]
    assert result["show_tool_frame"] is True
    assert result["recommended_for_coordinate_calibration"] is True
    assert "coordinate_frames" in result
    assert "tcp_convention" in result
    assert "simple pen/tool visual sanity check" in result["scope"]
    assert "simple pen/tool visual sanity check" in result_md.read_text(encoding="utf-8")


def test_tool_model_none_keeps_existing_result_name(tmp_path):
    csv_path = tmp_path / "robot_workspace_trajectory_resampled.csv"
    _write_csv(csv_path)
    script = COPPELIA_DIR / "play_workspace_path.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--csv",
            str(csv_path),
            "--tool-model",
            "none",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["tool_model"] == "none"
    assert result["path_objects_enabled"] is True
    assert (csv_path.parent / "coppeliasim_playback_result.json").exists()
    assert not (csv_path.parent / "coppeliasim_tool_model_result.json").exists()


def test_tool_model_module_does_not_import_aubo_sdk():
    source = Path(play_workspace_path.__file__).read_text(encoding="utf-8")

    assert "libpyauboi5" not in source
    assert "libpyauboi5" not in sys.modules
