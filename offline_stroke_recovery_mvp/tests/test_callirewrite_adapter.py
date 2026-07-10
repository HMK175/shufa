from pathlib import Path
import csv
import json
import sys

import numpy as np
import pytest


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_adapter import (
    build_callirewrite_test_command,
    convert_callirewrite_npz_to_outputs,
    inspect_callirewrite_checkout,
    write_callirewrite_feasibility_report,
)


def test_inspect_callirewrite_checkout_reports_missing_repo(tmp_path: Path):
    checkout_dir = tmp_path / "CalliRewrite"

    status = inspect_callirewrite_checkout(checkout_dir)

    assert status["ready"] is False
    assert status["status"] == "missing_checkout"
    assert status["checkout_dir"] == str(checkout_dir)
    assert status["repo_url"] == "https://github.com/LoYuXr/CalliRewrite"
    assert "checkout_dir" in status["missing"]
    assert "seq_extract" in status["stages"]


def test_inspect_callirewrite_checkout_reports_missing_weights(tmp_path: Path):
    checkout_dir = tmp_path / "CalliRewrite"
    seq_dir = checkout_dir / "seq_extract"
    seq_dir.mkdir(parents=True)
    (seq_dir / "test.py").write_text("print('test')\n", encoding="utf-8")
    (seq_dir / "environment.yml").write_text("name: CalliRewrite\n", encoding="utf-8")

    status = inspect_callirewrite_checkout(checkout_dir, model_name="new_train_phase_2")

    assert status["ready"] is False
    assert status["status"] == "missing_checkpoints"
    assert "seq_extract/outputs/snapshot/new_train_phase_2" in status["missing"]
    assert "optional_missing: seq_extract/outputs/snapshot/pretrain_perceptual_model" in status["warnings"]
    assert status["stages"]["seq_extract"]["test_py"] == str(seq_dir / "test.py")
    assert status["stages"]["seq_extract"]["environment_yml"] == str(seq_dir / "environment.yml")


def test_build_callirewrite_test_command_uses_seq_extract_entrypoint(tmp_path: Path):
    checkout_dir = tmp_path / "CalliRewrite"
    input_dir = tmp_path / "inputs"

    command = build_callirewrite_test_command(
        checkout_dir,
        input_dir,
        model_name="new_train_phase_2",
    )

    assert command["cwd"] == str(checkout_dir / "seq_extract")
    assert command["argv"] == [
        "python",
        "./test.py",
        "--input",
        str(input_dir),
        "--model",
        "new_train_phase_2",
    ]
    assert command["expected_seq_data_dir"] == str(
        checkout_dir / "seq_extract" / "outputs" / "sampling" / "inputs__new_train_phase_2" / "seq_data"
    )
    assert "python ./test.py --input" in command["powershell"]


def test_convert_callirewrite_npz_to_outputs_writes_unified_json_and_csv(tmp_path: Path):
    npz_path = tmp_path / "sample_seq.npz"
    np.savez(
        npz_path,
        strokes_data=np.array(
            [
                [0.0, 0.0, 0.0, 0.4, 0.0, 0.2, 1.0],
                [1.0, 0.0, 0.0, 0.0, 0.4, 0.2, 1.0],
                [0.0, 0.0, 0.0, -0.4, 0.0, 0.2, 1.0],
            ],
            dtype=np.float32,
        ),
        init_cursors=np.array([[0.5, 0.5]], dtype=np.float32),
        image_size=np.array(100, dtype=np.int32),
        round_length=np.array([3], dtype=np.int32),
        init_width=np.array(0.2, dtype=np.float32),
    )

    output_dir = tmp_path / "outputs"
    summary_path = convert_callirewrite_npz_to_outputs(npz_path, output_dir)

    assert summary_path == output_dir / "callirewrite_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["source"] == "callirewrite_npz"
    assert summary["drawing_primitive_count"] == 2
    assert summary["pen_up_primitive_count"] == 1
    assert summary["trajectory_point_count"] > 0

    recovered = json.loads((output_dir / "callirewrite_recovered_strokes.json").read_text(encoding="utf-8"))
    assert recovered["source"] == "callirewrite_npz"
    assert len(recovered["segments"]) == 2
    assert recovered["segments"][0]["points"]
    assert recovered["segments"][0]["source_segment_ids"] == [1]
    assert recovered["segments"][1]["source_segment_ids"] == [3]

    with (output_dir / "trial_ordered_trajectory.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert any(row["is_break"] == "true" for row in rows)
    assert any(row["source"] == "segment:1" for row in rows)
    assert any(row["source"] == "segment:3" for row in rows)


def test_convert_callirewrite_npz_uses_full_image_window_like_upstream_visualizer(tmp_path: Path):
    npz_path = tmp_path / "window_scale_seq.npz"
    np.savez(
        npz_path,
        strokes_data=np.array(
            [
                [0.0, 0.0, 0.0, 0.0, 0.5, 0.2, 1.0],
            ],
            dtype=np.float32,
        ),
        init_cursors=np.array([[0.5, 0.5]], dtype=np.float32),
        image_size=np.array(64, dtype=np.int32),
        round_length=np.array([1], dtype=np.int32),
        init_width=np.array(0.2, dtype=np.float32),
    )

    output_dir = tmp_path / "outputs"
    convert_callirewrite_npz_to_outputs(npz_path, output_dir)

    recovered = json.loads((output_dir / "callirewrite_recovered_strokes.json").read_text(encoding="utf-8"))
    points = recovered["segments"][0]["points"]

    assert points[0][0] == pytest.approx(32.0)
    assert points[0][1] == pytest.approx(32.0)
    assert points[-1][0] == pytest.approx(32.0)
    assert points[-1][1] == pytest.approx(48.0)


def test_convert_callirewrite_npz_maps_callirewrite_axis_convention_into_internal_yx(tmp_path: Path):
    npz_path = tmp_path / "axis_semantics_seq.npz"
    np.savez(
        npz_path,
        strokes_data=np.array(
            [
                [0.0, 0.0, 0.0, 0.0, 0.5, 0.2, 1.0],
            ],
            dtype=np.float32,
        ),
        init_cursors=np.array([[0.25, 0.5]], dtype=np.float32),
        image_size=np.array(64, dtype=np.int32),
        round_length=np.array([1], dtype=np.int32),
        init_width=np.array(0.2, dtype=np.float32),
    )

    output_dir = tmp_path / "outputs"
    convert_callirewrite_npz_to_outputs(npz_path, output_dir)

    recovered = json.loads((output_dir / "callirewrite_recovered_strokes.json").read_text(encoding="utf-8"))
    points = recovered["segments"][0]["points"]

    assert points[0][0] == pytest.approx(32.0)
    assert points[0][1] == pytest.approx(16.0)
    assert points[-1][0] == pytest.approx(32.0)
    assert points[-1][1] == pytest.approx(32.0)


def test_write_callirewrite_feasibility_report_records_no_go_when_repo_missing(tmp_path: Path):
    checkout_dir = tmp_path / "CalliRewrite"
    input_dir = tmp_path / "inputs"
    report_dir = tmp_path / "report"

    report_path = write_callirewrite_feasibility_report(
        checkout_dir,
        input_dir,
        report_dir,
        model_name="new_train_phase_2",
    )

    assert report_path == report_dir / "callirewrite_feasibility_report.md"
    report = report_path.read_text(encoding="utf-8")
    assert "CalliRewrite Feasibility Report" in report
    assert "missing_checkout" in report
    assert "not connected to robot execution" in report

    payload = json.loads((report_dir / "callirewrite_feasibility.json").read_text(encoding="utf-8"))
    assert payload["inspection"]["status"] == "missing_checkout"
    assert payload["recommended_decision"] == "no_go_until_external_checkout_is_ready"
