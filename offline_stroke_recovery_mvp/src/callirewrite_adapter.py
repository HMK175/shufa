"""Adapter helpers for evaluating CalliRewrite as an external baseline.

This module does not vendor or execute CalliRewrite. It checks an external
checkout, writes a reproducibility report, and converts CalliRewrite sequence
``.npz`` outputs into the local trial trajectory format when such outputs are
available.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from exporters import write_summary_json, write_trial_csv


CALLIREWRITE_REPO_URL = "https://github.com/LoYuXr/CalliRewrite"
DEFAULT_MODEL_NAME = "new_train_phase_2"
DEFAULT_SEQ_EXTRACT_DIR = "seq_extract"
DEFAULT_BEZIER_SAMPLES = 16
DEFAULT_RASTER_SIZE = 128.0
DEFAULT_MIN_WINDOW_SIZE = 32.0


def inspect_callirewrite_checkout(
    checkout_dir: Path,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, Any]:
    """Inspect whether an external CalliRewrite checkout is runnable enough."""

    checkout_dir = Path(checkout_dir)
    seq_dir = checkout_dir / DEFAULT_SEQ_EXTRACT_DIR
    test_py = seq_dir / "test.py"
    environment_yml = seq_dir / "environment.yml"
    model_dir = seq_dir / "outputs" / "snapshot" / model_name
    perceptual_model_dir = seq_dir / "outputs" / "snapshot" / "pretrain_perceptual_model"

    missing: list[str] = []
    warnings: list[str] = []
    if not checkout_dir.exists():
        missing.append("checkout_dir")
        status = "missing_checkout"
    elif not seq_dir.exists():
        missing.append(DEFAULT_SEQ_EXTRACT_DIR)
        status = "missing_seq_extract"
    else:
        if not test_py.exists():
            missing.append("seq_extract/test.py")
        if not environment_yml.exists():
            missing.append("seq_extract/environment.yml")
        if not model_dir.exists():
            missing.append(f"seq_extract/outputs/snapshot/{model_name}")
        if not perceptual_model_dir.exists():
            warnings.append("optional_missing: seq_extract/outputs/snapshot/pretrain_perceptual_model")

        if missing:
            status = "missing_checkpoints" if any("snapshot" in item for item in missing) else "missing_entrypoint"
        else:
            status = "ready"

    return {
        "ready": status == "ready",
        "status": status,
        "repo_url": CALLIREWRITE_REPO_URL,
        "checkout_dir": str(checkout_dir),
        "model_name": model_name,
        "missing": missing,
        "warnings": warnings,
        "stages": {
            "seq_extract": {
                "path": str(seq_dir),
                "test_py": str(test_py),
                "environment_yml": str(environment_yml),
                "model_dir": str(model_dir),
                "perceptual_model_dir": str(perceptual_model_dir),
            }
        },
    }


def build_callirewrite_test_command(
    checkout_dir: Path,
    input_dir: Path,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, Any]:
    """Return the CalliRewrite seq_extract command without executing it."""

    checkout_dir = Path(checkout_dir)
    input_dir = Path(input_dir)
    argv = [
        "python",
        "./test.py",
        "--input",
        str(input_dir),
        "--model",
        model_name,
    ]
    expected_seq_data_dir = (
        checkout_dir
        / DEFAULT_SEQ_EXTRACT_DIR
        / "outputs"
        / "sampling"
        / f"{input_dir.name}__{model_name}"
        / "seq_data"
    )
    return {
        "cwd": str(checkout_dir / DEFAULT_SEQ_EXTRACT_DIR),
        "argv": argv,
        "powershell": " ".join(_quote_arg(arg) for arg in argv),
        "expected_seq_data_dir": str(expected_seq_data_dir),
        "note": "Run inside a CalliRewrite seq_extract environment; this adapter does not execute external code.",
    }


def convert_callirewrite_npz_to_outputs(
    npz_path: Path,
    output_dir: Path,
    *,
    bezier_samples: int = DEFAULT_BEZIER_SAMPLES,
    raster_size: float = DEFAULT_RASTER_SIZE,
    min_window_size: float = DEFAULT_MIN_WINDOW_SIZE,
) -> Path:
    """Convert one CalliRewrite sequence ``.npz`` file into local outputs."""

    npz_path = Path(npz_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    segments, stats = _segments_from_npz(
        npz_path,
        bezier_samples=bezier_samples,
        raster_size=raster_size,
        min_window_size=min_window_size,
    )
    trajectory_point_count = write_trial_csv(output_dir / "trial_ordered_trajectory.csv", segments)
    recovered = {
        "source": "callirewrite_npz",
        "npz_path": str(npz_path),
        "coordinate_frame": "callirewrite_image_pixels",
        "segments": [_json_segment(segment) for segment in segments],
        "boundary_note": (
            "External CalliRewrite coarse sequence converted for offline comparison only; "
            "not connected to robot execution."
        ),
    }
    write_summary_json(output_dir / "callirewrite_recovered_strokes.json", recovered)

    summary = {
        "status": "ok" if segments else "failed",
        "source": "callirewrite_npz",
        "npz_path": str(npz_path),
        "sample": npz_path.stem,
        "drawing_primitive_count": stats["drawing_primitive_count"],
        "pen_up_primitive_count": stats["pen_up_primitive_count"],
        "segment_count": len(segments),
        "trajectory_point_count": trajectory_point_count,
        "manual_audit_required": True,
        "failure_reason": "" if segments else "no_drawing_primitives",
        "boundary_note": (
            "External CalliRewrite coarse sequence converted for offline comparison only; "
            "not connected to robot execution."
        ),
    }
    write_summary_json(output_dir / "callirewrite_summary.json", summary)
    return output_dir / "callirewrite_summary.json"


def write_callirewrite_feasibility_report(
    checkout_dir: Path,
    input_dir: Path,
    output_dir: Path,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Path:
    """Write a reproducibility report for the external CalliRewrite baseline."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inspection = inspect_callirewrite_checkout(checkout_dir, model_name=model_name)
    command = build_callirewrite_test_command(checkout_dir, input_dir, model_name=model_name)
    decision = "go_attempt_seq_extract" if inspection["ready"] else "no_go_until_external_checkout_is_ready"
    payload = {
        "inspection": inspection,
        "command": command,
        "recommended_decision": decision,
        "scope": (
            "seq_extract coarse sequence only; no RL fine-tuning, calibration, "
            "CoppeliaSim, AUBO, SDK, or robot execution."
        ),
    }
    write_summary_json(output_dir / "callirewrite_feasibility.json", payload)

    missing = ", ".join(inspection["missing"]) if inspection["missing"] else "none"
    warnings = ", ".join(inspection["warnings"]) if inspection["warnings"] else "none"
    lines = [
        "# CalliRewrite Feasibility Report",
        "",
        "## Scope",
        "",
        "This report checks CalliRewrite as an external coarse-sequence baseline. It is not connected to robot execution.",
        "",
        "## Checkout",
        "",
        f"- Repository: {CALLIREWRITE_REPO_URL}",
        f"- Checkout directory: {inspection['checkout_dir']}",
        f"- Status: {inspection['status']}",
        f"- Missing: {missing}",
        f"- Warnings: {warnings}",
        "",
        "## Suggested seq_extract command",
        "",
        f"- Working directory: `{command['cwd']}`",
        f"- Command: `{command['powershell']}`",
        f"- Expected `.npz` output directory: `{command['expected_seq_data_dir']}`",
        "",
        "## Decision",
        "",
        f"`{decision}`",
        "",
        "## Boundary",
        "",
        "Use only `seq_extract` outputs for offline visual comparison. Do not run RL fine-tuning, calibration, CoppeliaSim, AUBO, SDK, or real robot commands in this thread.",
        "",
    ]
    (output_dir / "callirewrite_feasibility_report.md").write_text("\n".join(lines), encoding="utf-8")
    return output_dir / "callirewrite_feasibility_report.md"


def _segments_from_npz(
    npz_path: Path,
    *,
    bezier_samples: int,
    raster_size: float,
    min_window_size: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    data = np.load(npz_path, allow_pickle=True)
    strokes_data = np.asarray(data["strokes_data"], dtype=float)
    if strokes_data.ndim != 2 or strokes_data.shape[1] < 7:
        raise ValueError("strokes_data must be a 2D array with at least 7 columns")

    image_size = float(np.asarray(data.get("image_size", 128)).reshape(-1)[0])
    init_width = float(np.asarray(data.get("init_width", image_size * 0.02)).reshape(-1)[0])
    init_cursors = np.asarray(data.get("init_cursors", [[0.5, 0.5]]), dtype=float)
    round_lengths = np.asarray(data.get("round_length", [len(strokes_data)]), dtype=int).reshape(-1)
    segments: list[dict[str, Any]] = []
    primitive_index = 0
    pen_up_count = 0
    drawing_count = 0
    for round_index, round_length in enumerate(round_lengths):
        cursor = _initial_cursor(init_cursors, round_index, image_size)
        prev_scaling = 1.0
        prev_window_size = float(raster_size)
        width = init_width
        for _ in range(int(round_length)):
            if primitive_index >= len(strokes_data):
                break
            primitive_index += 1
            row = strokes_data[primitive_index - 1]
            flag = float(row[0])
            window_size = _clamp(prev_scaling * prev_window_size, min_window_size, image_size)
            points = _primitive_points(cursor, row, window_size, bezier_samples)
            if flag < 0.5:
                drawing_count += 1
                segments.append(
                    {
                        "segment_id": primitive_index,
                        "source_segment_ids": (primitive_index,),
                        "points": points,
                        "pixel_count": len(points),
                        "length_px": _polyline_length(points),
                        "start": points[0],
                        "end": points[-1],
                        "component_id": round_index + 1,
                        "is_loop": False,
                    }
                )
            else:
                pen_up_count += 1
            cursor = _advance_cursor(cursor, row, window_size, image_size)

            next_width = float(row[5])
            next_scaling = float(row[6])
            next_window_size = _clamp(next_scaling * window_size, min_window_size, image_size)
            width = max(1e-6, abs(next_width) * window_size / max(1e-6, next_window_size))
            prev_scaling = abs(next_scaling)
            prev_window_size = window_size

    return segments, {
        "drawing_primitive_count": drawing_count,
        "pen_up_primitive_count": pen_up_count,
    }


def _initial_cursor(init_cursors: np.ndarray, round_index: int, image_size: float) -> tuple[float, float]:
    cursor = init_cursors[min(round_index, len(init_cursors) - 1)]
    x = float(cursor[0]) * image_size
    y = float(cursor[1]) * image_size
    return (x, y)


def _primitive_points(
    cursor_xy: tuple[float, float],
    row: Sequence[float],
    window_size: float,
    bezier_samples: int,
) -> list[tuple[float, float]]:
    _, x1_param, y1_param, *_ = [float(value) for value in row[:7]]
    start_x, start_y = cursor_xy
    end_x, end_y = _stroke_endpoint(cursor_xy, row, window_size)
    control_x = start_x + (end_x - start_x) * y1_param
    control_y = start_y + (end_y - start_y) * x1_param

    points: list[tuple[float, float]] = []
    for index in range(max(2, int(bezier_samples))):
        t = index / float(max(1, bezier_samples - 1))
        one_minus = 1.0 - t
        x = one_minus * one_minus * start_x + 2.0 * one_minus * t * control_x + t * t * end_x
        y = one_minus * one_minus * start_y + 2.0 * one_minus * t * control_y + t * t * end_y
        points.append((y, x))
    return points


def _stroke_endpoint(
    cursor_xy: tuple[float, float],
    row: Sequence[float],
    window_size: float,
) -> tuple[float, float]:
    _, _, _, x2_param, y2_param, *_ = [float(value) for value in row[:7]]
    cursor_x, cursor_y = cursor_xy
    return (
        cursor_x + y2_param * window_size / 2.0,
        cursor_y + x2_param * window_size / 2.0,
    )


def _advance_cursor(
    cursor_xy: tuple[float, float],
    row: Sequence[float],
    window_size: float,
    image_size: float,
) -> tuple[float, float]:
    next_x, next_y = _stroke_endpoint(cursor_xy, row, window_size)
    return (
        _clamp(next_x, 0.0, image_size - 1.0),
        _clamp(next_y, 0.0, image_size - 1.0),
    )


def _json_segment(segment: dict[str, Any]) -> dict[str, Any]:
    return {
        **segment,
        "source_segment_ids": list(segment.get("source_segment_ids", ())),
        "points": [[float(y), float(x)] for y, x in segment.get("points", ())],
        "start": [float(value) for value in segment.get("start", (0.0, 0.0))],
        "end": [float(value) for value in segment.get("end", (0.0, 0.0))],
    }


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    return sum(
        math.hypot(float(y1 - y0), float(x1 - x0))
        for (y0, x0), (y1, x1) in zip(points[:-1], points[1:])
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(float(value), float(lower)), float(upper))


def _quote_arg(arg: str) -> str:
    if not arg or any(char.isspace() for char in arg):
        return "'" + arg.replace("'", "''") + "'"
    return arg
