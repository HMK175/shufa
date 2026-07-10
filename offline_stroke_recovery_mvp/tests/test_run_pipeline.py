from pathlib import Path
import sys
import re
import csv
import json

import pytest
from PIL import Image, ImageDraw


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from run_pipeline import build_output_dir, run_batch, run_single_image
import run_pipeline as pipeline


ALLOWED_AUDIT_STATUSES = {
    "promising",
    "risky_needs_manual_check",
    "failed",
}


def _make_simple_glyph(path: Path) -> None:
    image = Image.new("L", (32, 32), 255)
    draw = ImageDraw.Draw(image)
    draw.line((8, 16, 24, 16), fill=0, width=5)
    draw.line((16, 8, 16, 24), fill=0, width=5)
    image.save(path)


def _read_summary(sample_dir: Path) -> dict:
    return json.loads((sample_dir / "recovery_summary.json").read_text(encoding="utf-8"))


def _has_nonwhite_pixel(path: Path) -> bool:
    image = Image.open(path).convert("RGB")
    return any(channel_min < 255 for extrema in image.getextrema() for channel_min in extrema[:1])


def _report_rows_for(report: str, sample: str) -> list[str]:
    return [line for line in report.splitlines() if line.startswith(f"| {sample} |")]


def test_build_output_dir_uses_timestamped_batch_name(tmp_path: Path):
    out_dir = build_output_dir(tmp_path, prefix="batch")
    assert out_dir.parent == tmp_path
    assert re.fullmatch(r"batch_\d{8}_\d{6}_\d{6}", out_dir.name)


def test_run_single_image_writes_trial_outputs(tmp_path: Path):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    required_files = {
        "trial_ordered_trajectory.csv",
        "recovery_summary.json",
        "candidate_order.png",
        "raw_skeleton.png",
        "clean_skeleton.png",
        "segments.png",
        "final_trajectory.png",
        "input_image.png",
        "foreground_mask.png",
        "cropped_mask.png",
    }
    assert {path.name for path in sample_dir.iterdir()} >= required_files

    summary = _read_summary(sample_dir)
    assert summary["manual_audit_required"] is True
    assert summary["status"] == "ok"
    assert summary["audit_status"] in ALLOWED_AUDIT_STATUSES
    assert summary["audit_status"] in {"promising", "risky_needs_manual_check"}
    assert summary["image_path"] == str(image_path)
    assert summary["sample_dir"] == str(sample_dir)
    assert len(summary["bbox"]) == 4
    assert summary["raw_skeleton_pixel_count"] >= summary["clean_skeleton_pixel_count"] >= 0
    assert summary["segment_count"] >= 1
    assert summary["ordered_segment_count"] >= 1
    assert summary["component_count"] >= 1
    assert summary["endpoint_count"] >= 0
    assert summary["branch_point_count"] >= 0
    assert summary["trajectory_point_count"] >= 1
    assert "not real stroke order" in summary["boundary_note"]
    assert "not robot output" in summary["boundary_note"]

    with (sample_dir / "trial_ordered_trajectory.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert set(rows[0]) == {
        "y",
        "x",
        "stroke_like_id",
        "point_index",
        "is_break",
        "order_index",
        "source",
    }
    assert any(row["is_break"] == "false" for row in rows)


def test_run_single_image_writes_failure_summary_for_blank_input(tmp_path: Path):
    image_path = tmp_path / "blank.png"
    Image.new("L", (16, 16), 255).save(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs", threshold=100)

    summary = _read_summary(sample_dir)
    assert summary["status"] == "failed"
    assert summary["audit_status"] == "failed"
    assert summary["failure_reason"] == "no_foreground_pixels"
    assert summary["foreground_pixel_count"] == 0
    assert summary["threshold"] == 100
    assert summary["image_path"] == str(image_path)
    assert summary["sample_dir"] == str(sample_dir)
    assert summary["manual_audit_required"] is True
    assert "not real stroke order" in summary["boundary_note"]
    assert "not robot output" in summary["boundary_note"]
    assert (sample_dir / "input_image.png").exists()
    assert (sample_dir / "foreground_mask.png").exists()


def test_run_single_image_marks_foreground_without_ordered_segments_failed(tmp_path: Path):
    image_path = tmp_path / "single_pixel.png"
    image = Image.new("L", (16, 16), 255)
    image.putpixel((8, 8), 0)
    image.save(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    summary = _read_summary(sample_dir)
    assert summary["status"] == "failed"
    assert summary["audit_status"] == "failed"
    assert summary["failure_reason"] == "no_ordered_segments"
    assert summary["foreground_pixel_count"] > 0
    assert summary["segment_count"] == 0
    assert summary["ordered_segment_count"] == 0
    assert summary["trajectory_point_count"] == 0
    assert summary["manual_audit_required"] is True
    assert "not real stroke order" in summary["boundary_note"]
    assert "not robot output" in summary["boundary_note"]


def test_run_single_image_summary_includes_coordinate_frame_and_pen_up_metrics(tmp_path: Path):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    summary = _read_summary(sample_dir)
    assert summary["coordinate_frame"] == "crop_local"
    assert summary["origin_offset_y"] == summary["bbox"][0]
    assert summary["origin_offset_x"] == summary["bbox"][1]
    assert summary["original_image_size"] == [32, 32]
    assert summary["foreground_pixel_count"] > 0
    assert summary["threshold"] == 200
    assert summary["pen_up_jump_count"] >= 0
    assert summary["max_pen_up_jump_px"] >= 0.0
    assert summary["mean_pen_up_jump_px"] >= 0.0
    assert summary["cross_component_pen_up_jump_count"] >= 0
    assert summary["cross_component_max_pen_up_jump_px"] >= 0.0
    assert summary["internal_pen_up_jump_count"] >= 0
    assert summary["internal_max_pen_up_jump_px"] >= 0.0
    assert summary["cross_component_best_is_exact"] in {True, False}
    assert summary["internal_best_is_exact"] in {True, False}
    assert summary["consolidated_segment_count"] >= 1
    assert summary["merged_segment_count"] >= 0
    assert summary["simplified_point_delta"] >= 0
    assert summary["resampled_point_delta"] >= 0


def test_run_single_image_summary_includes_skeleton_backend_metadata(tmp_path: Path):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    summary = _read_summary(sample_dir)
    assert summary["skeleton_backend"] in {"skimage_skeletonize", "numpy_midpoint_fallback"}
    assert "skeleton_backend_warning" in summary


def test_run_single_image_summary_flags_numpy_fallback_backend(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    monkeypatch.setattr(pipeline, "skeleton_backend_name", lambda: "numpy_midpoint_fallback")

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    summary = _read_summary(sample_dir)
    assert summary["skeleton_backend"] == "numpy_midpoint_fallback"
    assert "scikit-image" in summary["skeleton_backend_warning"]


def test_run_single_image_passes_ordering_merge_options_to_order_segments(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)
    calls: list[dict[str, float]] = []
    original = pipeline.order_segments

    def fake_order_segments(segments, *, endpoint_merge_distance=0.0, direction_cos_threshold=0.65):
        calls.append(
            {
                "endpoint_merge_distance": float(endpoint_merge_distance),
                "direction_cos_threshold": float(direction_cos_threshold),
            }
        )
        return original(
            segments,
            endpoint_merge_distance=endpoint_merge_distance,
            direction_cos_threshold=direction_cos_threshold,
        )

    monkeypatch.setattr(pipeline, "order_segments", fake_order_segments)

    run_single_image(
        image_path,
        tmp_path / "outputs",
        ordering_endpoint_merge_distance=1.25,
        ordering_direction_cos_threshold=0.9,
    )

    assert calls == [
        {
            "endpoint_merge_distance": 1.25,
            "direction_cos_threshold": 0.9,
        }
    ]


def test_run_single_image_uses_consolidated_segments_for_final_trajectory(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)
    call_sizes: list[int] = []

    def fake_consolidate_ordered_segments(ordered_segments, **kwargs):
        first = dict(ordered_segments[0])
        first["points"] = list(first["points"])
        return [first], {
            "merged_segment_count": max(0, len(ordered_segments) - 1),
            "simplified_point_delta": 0,
            "resampled_point_delta": 0,
        }

    def fake_write_trajectory_png(path, skeleton, ordered_segments, *, scale=8):
        call_sizes.append(len(ordered_segments))
        return None

    monkeypatch.setattr(pipeline, "consolidate_ordered_segments", fake_consolidate_ordered_segments, raising=False)
    monkeypatch.setattr(pipeline, "write_trajectory_png", fake_write_trajectory_png)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    summary = _read_summary(sample_dir)
    assert summary["consolidated_segment_count"] == 1
    assert call_sizes == [1]


def test_run_batch_writes_manual_audit_report_with_outputs(tmp_path: Path):
    simple_path = tmp_path / "simple_glyph.png"
    blank_path = tmp_path / "blank_sample.png"
    _make_simple_glyph(simple_path)
    Image.new("L", (16, 16), 255).save(blank_path)

    batch_dir = run_batch([simple_path, blank_path], tmp_path / "batch_outputs")

    report_path = batch_dir / "batch_report.md"
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Samples processed" in report
    assert "Topology / Audit Summary" in report
    assert "Output File Locations" in report
    assert "failure_reason" in report
    assert "skeleton backend" in report
    assert "visual inspection is required" in report
    assert "not real stroke order" in report
    assert "not robot output" in report
    assert "simple_glyph" in report
    assert "blank_sample" in report
    assert "failed" in report
    assert "no_foreground_pixels" in report
    assert "recovery_summary.json" in report
    assert "trial_ordered_trajectory.csv" in report

    blank_rows = _report_rows_for(report, "blank_sample")
    assert len(blank_rows) == 2
    blank_topology_row, blank_output_row = blank_rows
    assert "no_foreground_pixels" in blank_topology_row
    assert "n/a" in blank_topology_row
    assert "n/a" in blank_output_row
    assert "blank_sample\\trial_ordered_trajectory.csv" not in blank_output_row
    assert "blank_sample/trial_ordered_trajectory.csv" not in blank_output_row
    assert "blank_sample\\final_trajectory.png" not in blank_output_row
    assert "blank_sample/final_trajectory.png" not in blank_output_row


def test_run_batch_forwards_ordering_merge_options(tmp_path: Path, monkeypatch):
    simple_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(simple_path)
    calls: list[dict[str, float]] = []
    original = pipeline.run_single_image

    def fake_run_single_image(*args, **kwargs):
        calls.append(
            {
                "ordering_endpoint_merge_distance": float(kwargs["ordering_endpoint_merge_distance"]),
                "ordering_direction_cos_threshold": float(kwargs["ordering_direction_cos_threshold"]),
            }
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "run_single_image", fake_run_single_image)

    run_batch(
        [simple_path],
        tmp_path / "batch_outputs",
        ordering_endpoint_merge_distance=1.0,
        ordering_direction_cos_threshold=0.7,
    )

    assert calls == [
        {
            "ordering_endpoint_merge_distance": 1.0,
            "ordering_direction_cos_threshold": 0.7,
        }
    ]


def test_run_batch_keeps_going_when_one_input_image_is_missing(tmp_path: Path):
    missing_path = tmp_path / "missing_input.png"
    simple_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(simple_path)

    batch_dir = run_batch([missing_path, simple_path], tmp_path / "batch_outputs")

    missing_summary = _read_summary(batch_dir / "missing_input")
    assert missing_summary["sample"] == "missing_input"
    assert missing_summary["status"] == "failed"
    assert missing_summary["audit_status"] == "failed"
    assert missing_summary["failure_reason"] == "image_read_error"
    assert missing_summary["image_path"] == str(missing_path)
    assert "No such file" in missing_summary["error_message"] or "cannot find" in missing_summary["error_message"]

    simple_summary = _read_summary(batch_dir / "simple_glyph")
    assert simple_summary["status"] == "ok"

    report = (batch_dir / "batch_report.md").read_text(encoding="utf-8")
    assert "missing_input" in report
    assert "image_read_error" in report

    with (batch_dir / "manual_audit_sheet.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    missing_row = next(row for row in rows if row["sample"] == "missing_input")
    assert missing_row["status"] == "failed"
    assert missing_row["failure_reason"] == "image_read_error"
    assert missing_row["candidate_order_image"] == "n/a"
    assert missing_row["final_trajectory_image"] == "n/a"


def test_first_pass_audit_policy_marks_risky_topology_directly():
    summary = {
        "status": "ok",
        "segment_count": 1,
        "ordered_segment_count": 1,
        "trajectory_point_count": 5,
        "component_count": 1,
        "branch_point_count": pipeline.FIRST_PASS_AUDIT_MAX_BRANCH_POINTS + 1,
        "endpoint_count": 2,
        "max_pen_up_jump_px": 0.0,
        "mean_pen_up_jump_px": 0.0,
    }

    assert pipeline._audit_status(summary) == "risky_needs_manual_check"


def test_first_pass_audit_allows_single_component_crossing_break_with_shared_interior_point():
    summary = {
        "status": "ok",
        "segment_count": 4,
        "ordered_segment_count": 2,
        "trajectory_point_count": 149,
        "component_count": 1,
        "branch_point_count": 2,
        "endpoint_count": 5,
        "max_pen_up_jump_px": 44.1,
        "mean_pen_up_jump_px": 44.1,
        "shared_interior_intersection_count": 1,
    }

    assert pipeline._audit_status(summary) == "promising"


def test_pen_up_jump_breakdown_separates_cross_component_and_internal_jumps():
    ordered = [
        {"component_id": 1, "points": [(0, 0), (0, 1)]},
        {"component_id": 2, "points": [(0, 20), (0, 21)]},
        {"component_id": 3, "points": [(0, 10), (0, 11)]},
    ]

    metrics = pipeline._pen_up_jump_breakdown(ordered)

    assert metrics["cross_component_pen_up_jump_count"] == 2
    assert metrics["cross_component_max_pen_up_jump_px"] == pytest.approx(19.0)
    assert metrics["cross_component_mean_pen_up_jump_px"] == pytest.approx(15.0)
    assert metrics["internal_pen_up_jump_count"] == 0
    assert metrics["internal_max_pen_up_jump_px"] == pytest.approx(0.0)
    assert metrics["cross_component_best_is_exact"] is True
    assert metrics["cross_component_best_max_pen_up_jump_px"] == pytest.approx(9.0)
    assert metrics["avoidable_cross_component_max_jump_px"] == pytest.approx(10.0)
    assert metrics["internal_best_is_exact"] is True
    assert metrics["avoidable_internal_max_jump_px"] == pytest.approx(0.0)


def test_first_pass_audit_allows_structural_multi_component_separation_with_small_internal_jump():
    summary = {
        "status": "ok",
        "segment_count": 6,
        "ordered_segment_count": 5,
        "trajectory_point_count": 140,
        "component_count": 4,
        "branch_point_count": 1,
        "endpoint_count": 9,
        "max_pen_up_jump_px": 23.7,
        "mean_pen_up_jump_px": 17.1,
        "cross_component_pen_up_jump_count": 3,
        "cross_component_max_pen_up_jump_px": 23.7,
        "cross_component_mean_pen_up_jump_px": 19.8,
        "cross_component_best_is_exact": True,
        "cross_component_best_max_pen_up_jump_px": 23.7,
        "cross_component_best_mean_pen_up_jump_px": 19.8,
        "avoidable_cross_component_max_jump_px": 0.0,
        "internal_pen_up_jump_count": 1,
        "internal_max_pen_up_jump_px": 9.1,
        "internal_mean_pen_up_jump_px": 9.1,
        "internal_best_is_exact": True,
        "internal_best_max_pen_up_jump_px": 9.1,
        "internal_best_mean_pen_up_jump_px": 9.1,
        "avoidable_internal_max_jump_px": 0.0,
        "avoidable_internal_mean_jump_px": 0.0,
    }

    assert pipeline._audit_status(summary) == "promising"


def test_first_pass_audit_keeps_risky_when_internal_fragmentation_is_large():
    summary = {
        "status": "ok",
        "segment_count": 7,
        "ordered_segment_count": 5,
        "trajectory_point_count": 216,
        "component_count": 3,
        "branch_point_count": 3,
        "endpoint_count": 8,
        "max_pen_up_jump_px": 52.2,
        "mean_pen_up_jump_px": 33.2,
        "cross_component_pen_up_jump_count": 2,
        "cross_component_max_pen_up_jump_px": 52.2,
        "cross_component_mean_pen_up_jump_px": 37.6,
        "cross_component_best_is_exact": True,
        "cross_component_best_max_pen_up_jump_px": 51.9,
        "cross_component_best_mean_pen_up_jump_px": 37.5,
        "avoidable_cross_component_max_jump_px": 0.3,
        "internal_pen_up_jump_count": 2,
        "internal_max_pen_up_jump_px": 31.4,
        "internal_mean_pen_up_jump_px": 28.7,
        "internal_best_is_exact": True,
        "internal_best_max_pen_up_jump_px": 31.4,
        "internal_best_mean_pen_up_jump_px": 28.7,
        "avoidable_internal_max_jump_px": 0.0,
        "avoidable_internal_mean_jump_px": 0.0,
    }

    assert pipeline._audit_status(summary) == "risky_needs_manual_check"


def test_first_pass_audit_marks_risky_when_cross_component_jump_is_avoidable():
    summary = {
        "status": "ok",
        "segment_count": 3,
        "ordered_segment_count": 3,
        "trajectory_point_count": 60,
        "component_count": 3,
        "branch_point_count": 0,
        "endpoint_count": 6,
        "max_pen_up_jump_px": 19.0,
        "mean_pen_up_jump_px": 15.0,
        "cross_component_pen_up_jump_count": 2,
        "cross_component_max_pen_up_jump_px": 19.0,
        "cross_component_mean_pen_up_jump_px": 15.0,
        "cross_component_best_is_exact": True,
        "cross_component_best_max_pen_up_jump_px": 9.0,
        "cross_component_best_mean_pen_up_jump_px": 9.0,
        "avoidable_cross_component_max_jump_px": 10.0,
        "internal_pen_up_jump_count": 0,
        "internal_max_pen_up_jump_px": 0.0,
        "internal_mean_pen_up_jump_px": 0.0,
        "internal_best_is_exact": True,
        "internal_best_max_pen_up_jump_px": 0.0,
        "internal_best_mean_pen_up_jump_px": 0.0,
        "avoidable_internal_max_jump_px": 0.0,
        "avoidable_internal_mean_jump_px": 0.0,
    }

    assert pipeline._audit_status(summary) == "risky_needs_manual_check"


def test_shared_interior_intersection_count_ignores_endpoint_only_contacts():
    ordered = [
        {"points": [(0, 0), (0, 1), (0, 2)]},
        {"points": [(0, 2), (1, 2), (2, 2)]},
    ]

    assert pipeline._shared_interior_intersection_count(ordered) == 0


def test_shared_interior_intersection_count_detects_crossing_point():
    ordered = [
        {"points": [(0, 1), (1, 1), (2, 1), (3, 1)]},
        {"points": [(1, 0), (1, 1), (1, 2), (1, 3)]},
    ]

    assert pipeline._shared_interior_intersection_count(ordered) == 1


def test_run_single_image_debug_pngs_are_nonblank(tmp_path: Path):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")

    for filename in [
        "candidate_order.png",
        "final_trajectory.png",
        "input_image.png",
        "foreground_mask.png",
        "cropped_mask.png",
    ]:
        path = sample_dir / filename
        assert path.stat().st_size > 0
        assert _has_nonwhite_pixel(path)
