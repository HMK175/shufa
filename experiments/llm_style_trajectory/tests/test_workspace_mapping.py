import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from workspace_mapping import (
    WorkspaceConfig,
    map_execution_rows,
    process_batch,
    validate_workspace_rows,
)


EXECUTION_FIELDS = [
    "segment_id",
    "stroke_id",
    "point_id",
    "y",
    "x",
    "z",
    "speed",
    "pressure",
    "width",
    "pen_down",
    "is_connector",
    "segment_type",
    "connection_preference",
]


def _write_execution_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXECUTION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in EXECUTION_FIELDS})


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 0,
            "y": 128,
            "x": 128,
            "z": 0,
            "speed": 1.0,
            "pressure": 1.0,
            "width": 8.0,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
            "connection_preference": "none",
        },
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 1,
            "y": 0,
            "x": 0,
            "z": 0,
            "speed": 1.0,
            "pressure": 1.0,
            "width": 8.0,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
            "connection_preference": "none",
        },
        {
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 2,
            "y": 256,
            "x": 256,
            "z": 8,
            "speed": 1.6,
            "pressure": 0,
            "width": 0,
            "pen_down": 0,
            "is_connector": 0,
            "segment_type": "pen_up_move",
            "connection_preference": "none",
        },
    ]


def test_image_center_maps_to_workspace_origin():
    rows = map_execution_rows([_sample_rows()[0]], WorkspaceConfig())

    assert rows[0]["X_mm"] == 0
    assert rows[0]["Y_mm"] == 0


def test_image_corners_map_with_expected_direction():
    rows = map_execution_rows(_sample_rows()[1:], WorkspaceConfig())

    assert rows[0]["X_mm"] == -60
    assert rows[0]["Y_mm"] == 60
    assert rows[1]["X_mm"] == 60
    assert rows[1]["Y_mm"] == -60


def test_z_mapping_respects_pen_state_and_segment_type():
    rows = map_execution_rows(_sample_rows(), WorkspaceConfig(pen_up_height_mm=8))

    assert rows[0]["Z_mm"] == 0
    assert rows[0]["speed_mm_s"] == 30
    assert rows[2]["Z_mm"] == 8
    assert rows[2]["pen_down"] == 0


def test_out_of_bounds_validation_detects_invalid_xy():
    mapped = map_execution_rows(
        [
            {
                **_sample_rows()[0],
                "x": 300,
                "y": 128,
            }
        ],
        WorkspaceConfig(),
    )

    report = validate_workspace_rows(mapped, WorkspaceConfig())
    assert report["out_of_bounds"] is True


def test_batch_processing_writes_workspace_outputs(tmp_path):
    task_dir = tmp_path / "u5c71_xingkai_test"
    _write_execution_csv(task_dir / "execution_trajectory.csv", _sample_rows())

    result = process_batch(tmp_path, WorkspaceConfig())

    assert (task_dir / "robot_workspace_trajectory.csv").exists()
    assert (task_dir / "workspace_validation_report.md").exists()
    assert (task_dir / "workspace_path_preview.png").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert "u5c71" in result["ablation_images"]
