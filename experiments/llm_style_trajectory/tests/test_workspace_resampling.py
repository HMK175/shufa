import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from workspace_resampling import (
    ResamplingConfig,
    process_batch,
    resample_workspace_rows,
    resampling_metrics,
)


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
    "y",
    "x",
]


def _row(segment_id, segment_type, x, y, z, *, pressure=1.0, width=8.0, pen_down=1, is_connector=0):
    return {
        "segment_id": segment_id,
        "stroke_id": segment_id,
        "point_id": 0,
        "X_mm": x,
        "Y_mm": y,
        "Z_mm": z,
        "speed_mm_s": 30,
        "pressure": pressure,
        "width": width,
        "pen_down": pen_down,
        "is_connector": is_connector,
        "segment_type": segment_type,
        "y": 0,
        "x": 0,
    }


def _segment_rows(segment_type, distance, *, pressure=1.0, width=8.0, pen_down=1, is_connector=0):
    return [
        _row(1, segment_type, 0, 0, 0, pressure=pressure, width=width, pen_down=pen_down, is_connector=is_connector),
        _row(1, segment_type, distance, 0, 0, pressure=pressure, width=width, pen_down=pen_down, is_connector=is_connector),
    ]


def _write_workspace_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=WORKSPACE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in WORKSPACE_FIELDS})


def test_long_stroke_segment_is_resampled_to_two_mm_or_less():
    rows = resample_workspace_rows(_segment_rows("stroke", 10), ResamplingConfig())
    metrics = resampling_metrics(_segment_rows("stroke", 10), rows, ResamplingConfig())

    assert metrics["segment_max_steps"]["stroke"] <= 2.0
    assert len(rows) > 2
    assert {float(row["speed_mm_s"]) for row in rows} == {25.0}


def test_connector_segment_is_resampled_and_keeps_connector_state():
    original = _segment_rows("connector", 10, pressure=0.34, width=4.0, is_connector=1)
    rows = resample_workspace_rows(original, ResamplingConfig())
    metrics = resampling_metrics(original, rows, ResamplingConfig())

    assert metrics["segment_max_steps"]["connector"] <= 2.5
    assert all(int(row["is_connector"]) == 1 for row in rows)
    assert {float(row["speed_mm_s"]) for row in rows} == {40.0}


def test_pen_up_move_is_resampled_and_keeps_lifted_pen_state():
    original = _segment_rows("pen_up_move", 13, pressure=0, width=0, pen_down=0)
    rows = resample_workspace_rows(original, ResamplingConfig())
    metrics = resampling_metrics(original, rows, ResamplingConfig())

    assert metrics["segment_max_steps"]["pen_up_move"] <= 5.0
    assert all(int(row["pen_down"]) == 0 for row in rows)
    assert all(float(row["pressure"]) == 0 for row in rows)
    assert all(float(row["width"]) == 0 for row in rows)
    assert {float(row["speed_mm_s"]) for row in rows} == {70.0}


def test_estimated_duration_is_positive():
    rows = resample_workspace_rows(_segment_rows("stroke", 10), ResamplingConfig())
    metrics = resampling_metrics(_segment_rows("stroke", 10), rows, ResamplingConfig())

    assert metrics["estimated_duration_s"] > 0


def test_batch_processing_writes_resampled_outputs(tmp_path):
    task_dir = tmp_path / "u5c71_xingkai_test"
    _write_workspace_csv(task_dir / "robot_workspace_trajectory.csv", _segment_rows("stroke", 10))

    result = process_batch(tmp_path, ResamplingConfig())

    assert (task_dir / "robot_workspace_trajectory_resampled.csv").exists()
    assert (task_dir / "workspace_resampling_report.md").exists()
    assert (task_dir / "workspace_resampled_preview.png").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert "u5c71" in result["ablation_images"]
