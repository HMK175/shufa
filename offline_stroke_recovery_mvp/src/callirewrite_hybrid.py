"""Hybrid postprocessing for converted CalliRewrite outputs."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw

from exporters import write_summary_json, write_trial_csv
from makemeahanzi_prior import (
    build_kou_three_stroke_candidate,
    label_segments_by_makemeahanzi_components,
    regroup_ordered_segments_by_makemeahanzi,
)
from ordering import order_segments
from preprocess import ensure_foreground_is_true
from smoke_benchmark import create_smoke_benchmark_report, write_manual_audit_sheet
from stroke_primitives import (
    StrokePrimitiveLibrary,
    compose_hengzhe_primitive,
    normalize_stroke_primitive,
)
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
    merge_adjacent_component_labeled_short_fragments,
    merge_adjacent_short_fragments,
    stitch_component_labeled_internal_gaps,
)
from visualize import (
    PALETTE,
    _build_endpoint_cap_policies,
    _build_variable_width_profile,
    _estimate_point_brush_diameters_px,
    _sample_polyline_points,
    render_execution_image,
    write_execution_playback_contact_sheet,
    write_execution_render_png,
    write_order_png,
    write_trajectory_playback_contact_sheet,
    write_trajectory_png,
)


DEFAULT_SAMPLE_SET = ("kou", "shi", "xin", "yi", "yong", "zhong")
DEFAULT_MERGE_GAP_PX = 1.5
DEFAULT_DIRECTION_COS_THRESHOLD = 0.35
DEFAULT_SIMPLIFY_TOLERANCE_PX = 0.75
DEFAULT_RESAMPLE_STEP_PX = 1.0
HYBRID_CONTACT_PANELS = [
    ("input", "input_image.png"),
    ("source_overlay", "callirewrite_overlay.png"),
    ("review_trajectory", "review_recommended_trajectory.png"),
    ("raw_render", "raw_rendered_execution.png"),
    ("light_repair", "light_repair_rendered_execution.png"),
    ("local_render", "local_rendered_execution.png"),
    ("mmh_render", "makemeahanzi_rendered_execution.png"),
    ("component_mix", "component_mix_rendered_execution.png"),
    ("structure_primitive", "structure_primitive_rendered_execution.png"),
    ("fixed_width", "constant_width_render.png"),
    ("hybrid_overlay", "hybrid_overlay.png"),
    ("final_render", "rendered_execution.png"),
]
HYBRID_MAX_INTERNAL_JUMP_PX = 16.0
HYBRID_MAX_INTERNAL_MEAN_JUMP_PX = 8.0
HYBRID_MAX_AVOIDABLE_CROSS_COMPONENT_JUMP_PX = 4.0
DEFAULT_VISUAL_MARGIN_PX = 6
DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD = 0.65
DEFAULT_OVERLAY_SCALE = 6
DEFAULT_FOREGROUND_THRESHOLD = 200
DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX = 1.0
AUTO_LOCAL_INTERNAL_JUMP_OK_PX = 8.0
AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_OK_PX = 2.0
AUTO_LOCAL_INTERNAL_JUMP_RISKY_PX = 12.0
AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_RISKY_PX = 4.0
AUTO_PRIOR_SEVERE_FOLDBACK_COS = -0.5
AUTO_PRIOR_LOCAL_TURN_ADVANTAGE_COS = 0.5
AUTO_COMPONENT_LABEL_LOCAL_VISUAL_ADVANTAGE_MIN = 0.08
AUTO_LIGHT_REPAIR_RAW_INTERNAL_MIN_PX = 20.0
AUTO_LIGHT_REPAIR_VISUAL_GAIN_MIN = 0.05
AUTO_LIGHT_REPAIR_MIN_TURN_COS = 0.75
AUTO_LIGHT_REPAIR_MAX_RAW_TURN_DROP = 0.2
AUTO_LIGHT_REPAIR_MAX_INTERNAL_INCREASE_PX = 6.0
AUTO_LIGHT_REPAIR_MAX_COUNT_DROP = 1
AUTO_LIGHT_REPAIR_LOCAL_VISUAL_ADVANTAGE_MIN = 0.02
AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MIN_TURN_COS = -0.2
AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MAX_TURN_COS = 0.25
AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_VISUAL_GAIN_MIN = 0.12
AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MAX_INTERNAL_INCREASE_PX = 2.0
AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_VISUAL_GAIN_MIN = 0.15
AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MIN_TURN_COS = 0.45
AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MAX_RAW_TURN_DROP = 0.5
AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MAX_INTERNAL_INCREASE_PX = 2.0
AUTO_RAW_MIN_TURN_ADVANTAGE_COS = 0.25
AUTO_RAW_VISUAL_SIMILARITY_MAX_LOCAL_DROP = 0.03
AUTO_SIMPLE_EXACT_PRIOR_VISUAL_ADVANTAGE_MIN = 0.04
AUTO_SIMPLE_EXACT_PRIOR_TURN_ADVANTAGE_COS = 0.5
COMPONENT_MIX_LONG_FOLDBACK_MIN_LENGTH_PX = 70.0
COMPONENT_MIX_LONG_FOLDBACK_MAX_COS = -0.5
AUTO_COMPONENT_MIX_VISUAL_GAIN_MIN = 0.015
AUTO_COMPONENT_MIX_MAX_INTERNAL_INCREASE_PX = 1.0
AUTO_STRUCTURE_PRIMITIVE_MAX_VISUAL_DROP = 0.10
COMPONENT_MIX_REDUNDANT_LOCAL_SUBPATH_MAX_DISTANCE_PX = 3.0
COMPONENT_MIX_DETAIL_DOT_MAX_LENGTH_PX = 28.0
COMPONENT_MIX_DETAIL_DOT_ABOVE_PRIOR_MARGIN_PX = 3.0
LOCAL_COMPONENT_LABEL_MIN_SEGMENT_POINTS = 8
DEFAULT_RENDER_SUBPATH_BRIDGE_GAP_PX = 4.0
DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND = 0.35
DEFAULT_REVIEW_PANEL_HIGHLIGHT_OUTLINE = (214, 40, 40)
DEFAULT_REVIEW_PANEL_HIGHLIGHT_WIDTH = 3
DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_SHORT_LENGTH_PX = 12.0
DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_SHORT_TO_LONG_RATIO = 0.6
DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_GAP_PX = 1.5


def _select_axis_reference_segment(
    segments: Sequence[dict[str, Any]],
    *,
    axis: str,
    min_axis_ratio: float = 2.0,
) -> dict[str, Any] | None:
    axis_name = str(axis).lower()
    if axis_name not in {"horizontal", "vertical"}:
        raise ValueError(f"Unsupported reference axis: {axis}")

    candidates: list[tuple[float, dict[str, Any]]] = []
    for segment in segments:
        points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
        if len(points) < 2:
            continue
        start = np.asarray(points[0], dtype=float)
        end = np.asarray(points[-1], dtype=float)
        delta_y = abs(float(end[0] - start[0]))
        delta_x = abs(float(end[1] - start[1]))
        if axis_name == "horizontal" and delta_x < delta_y * float(min_axis_ratio):
            continue
        if axis_name == "vertical" and delta_y < delta_x * float(min_axis_ratio):
            continue
        candidates.append((_polyline_length(points), segment))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _build_reference_stroke_primitive_library(
    converted_dir: Path,
    input_dir: Path,
) -> tuple[StrokePrimitiveLibrary, dict[str, Any]]:
    library = StrokePrimitiveLibrary()
    missing: list[str] = []

    references = (
        ("heng", "yi", "horizontal"),
        ("shu", "shi", "vertical"),
    )
    for kind, sample, axis in references:
        sample_dir = Path(converted_dir) / sample
        input_path = Path(input_dir) / f"{sample}.png"
        try:
            segments, _ = load_callirewrite_segments(sample_dir)
        except FileNotFoundError:
            missing.append(kind)
            continue
        foreground_mask = _load_input_foreground_mask(input_path)
        selected = _select_axis_reference_segment(segments, axis=axis)
        if foreground_mask is None or selected is None:
            missing.append(kind)
            continue
        points = [tuple(_as_float_point(point)) for point in selected.get("points", ())]
        sampled_points = _sample_polyline_points(points, step_px=1.0)
        widths = _estimate_point_brush_diameters_px(sampled_points, foreground_mask)
        if len(sampled_points) < 2 or not widths:
            missing.append(kind)
            continue
        widths = _sanitize_reference_primitive_widths(widths)
        library.register(
            normalize_stroke_primitive(
                sampled_points,
                widths,
                kind=kind,
                start_role="free",
                end_role="free",
                source_sample=sample,
            )
        )

    heng = library.get("heng")
    shu = library.get("shu")
    if heng is not None and shu is not None:
        library.register(compose_hengzhe_primitive(heng, shu, corner_fraction=0.55))
    else:
        missing.append("hengzhe")

    return library, {
        "registered_primitive_kinds": list(library.kinds()),
        "missing_primitive_kinds": sorted(set(missing)),
    }


def _sanitize_reference_primitive_widths(
    widths: Sequence[float],
    *,
    min_relative_width: float = 0.7,
    max_relative_width: float = 1.35,
) -> list[float]:
    arr = np.asarray([max(float(value), 0.0) for value in widths], dtype=float)
    if arr.size == 0:
        return []
    positive = arr[arr > 1e-9]
    reference = float(np.median(positive)) if positive.size else 1.0
    smoothed = arr.copy()
    for index in range(int(arr.size)):
        start = max(0, index - 2)
        end = min(int(arr.size), index + 3)
        smoothed[index] = float(np.median(arr[start:end]))
    blended = 0.5 * arr + 0.5 * smoothed
    return np.clip(
        blended,
        reference * max(float(min_relative_width), 0.0),
        reference * max(float(max_relative_width), float(min_relative_width)),
    ).astype(float).tolist()


def _attach_primitive_width_profiles(
    segments: Sequence[dict[str, Any]],
    primitive_library: StrokePrimitiveLibrary,
    *,
    blend: float = 0.7,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attached: list[dict[str, Any]] = []
    applied_kinds: list[str] = []
    missing_kinds: list[str] = []
    for segment in segments:
        copied = _copy_segment(segment)
        kind = str(copied.get("primitive_kind", ""))
        primitive = primitive_library.get(kind) if kind else None
        if primitive is None:
            if kind:
                missing_kinds.append(kind)
            attached.append(copied)
            continue
        copied["primitive_relative_widths"] = tuple(float(value) for value in primitive.relative_widths)
        copied["primitive_width_blend"] = min(max(float(blend), 0.0), 1.0)
        copied["primitive_source_sample"] = primitive.source_sample
        applied_kinds.append(kind)
        attached.append(copied)
    return attached, {
        "primitive_transfer_applied": bool(applied_kinds),
        "primitive_transfer_segment_count": len(applied_kinds),
        "primitive_transfer_kinds": list(dict.fromkeys(applied_kinds)),
        "primitive_transfer_missing_kinds": sorted(set(missing_kinds)),
    }


def _register_gou_primitive_from_segments(
    segments: Sequence[dict[str, Any]],
    foreground_mask: np.ndarray | None,
    primitive_library: StrokePrimitiveLibrary,
    *,
    source_sample: str = "xin",
) -> dict[str, Any]:
    base_meta: dict[str, Any] = {
        "gou_primitive_registered": False,
        "gou_primitive_source_sample": "",
        "gou_primitive_pointed_end": False,
        "gou_primitive_last_relative_width": None,
    }
    if foreground_mask is None:
        return base_meta
    index = _single_long_foldback_segment_index(
        segments,
        min_length_px=COMPONENT_MIX_LONG_FOLDBACK_MIN_LENGTH_PX,
        max_turn_cos=COMPONENT_MIX_LONG_FOLDBACK_MAX_COS,
    )
    if index is None:
        return base_meta
    policies = _build_endpoint_cap_policies(segments)
    segment = segments[index]
    points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
    policy = policies[index]
    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=bool(policy["cap_start"]),
        cap_end=bool(policy["cap_end"]),
        source_segment_ids=segment.get("source_segment_ids", ()),
    )
    if profile is None:
        return base_meta
    sampled_points, diameters, _, _ = profile
    if len(sampled_points) < 2 or not diameters:
        return base_meta
    pointed_end = float(diameters[-1]) <= 1e-9
    if not pointed_end:
        return base_meta
    primitive = normalize_stroke_primitive(
        sampled_points,
        diameters,
        kind="gou",
        start_role="free" if bool(policy["cap_start"]) else "attached",
        end_role="pointed",
        source_sample=source_sample,
    )
    primitive_library.register(primitive)
    return {
        "gou_primitive_registered": True,
        "gou_primitive_source_sample": str(source_sample),
        "gou_primitive_pointed_end": primitive.end_role == "pointed",
        "gou_primitive_last_relative_width": float(primitive.relative_widths[-1]),
    }


def run_callirewrite_hybrid_probe(
    *,
    converted_dir: Path,
    input_dir: Path,
    output_dir: Path,
    samples: Sequence[str],
    merge_gap_px: float = DEFAULT_MERGE_GAP_PX,
    direction_cos_threshold: float = DEFAULT_DIRECTION_COS_THRESHOLD,
    simplify_tolerance_px: float = DEFAULT_SIMPLIFY_TOLERANCE_PX,
    resample_step_px: float | None = DEFAULT_RESAMPLE_STEP_PX,
    postprocess_mode: str = "local",
    makemeahanzi_graphics_path: Path | str | None = None,
    sample_char_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    converted_dir = Path(converted_dir)
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not converted_dir.exists():
        return {
            "status": "missing_converted_dir",
            "stage": "callirewrite_hybrid_probe",
            "converted_dir": str(converted_dir),
        }

    normalized_samples = [sample.strip() for sample in samples if str(sample).strip()]
    if not normalized_samples:
        normalized_samples = list(DEFAULT_SAMPLE_SET)

    missing_samples = [sample for sample in normalized_samples if not (converted_dir / sample).exists()]
    if missing_samples:
        return {
            "status": "missing_converted_samples",
            "stage": "callirewrite_hybrid_probe",
            "converted_dir": str(converted_dir),
            "missing_samples": missing_samples,
        }

    batch_dir = _build_output_dir(output_dir, prefix="callirewrite_hybrid_batch")
    batch_dir.mkdir(parents=True, exist_ok=True)
    primitive_library, primitive_library_meta = _build_reference_stroke_primitive_library(
        converted_dir,
        input_dir,
    )
    rows: list[dict[str, Any]] = []
    for sample in normalized_samples:
        sample_dir = _run_single_sample(
            converted_sample_dir=converted_dir / sample,
            sample=sample,
            input_image_path=input_dir / f"{sample}.png",
            batch_dir=batch_dir,
            merge_gap_px=merge_gap_px,
            direction_cos_threshold=direction_cos_threshold,
            simplify_tolerance_px=simplify_tolerance_px,
            resample_step_px=resample_step_px,
            postprocess_mode=postprocess_mode,
            makemeahanzi_graphics_path=makemeahanzi_graphics_path,
            sample_char_map=sample_char_map,
            primitive_library=primitive_library,
            primitive_library_meta=primitive_library_meta,
        )
        summary = json.loads((sample_dir / "recovery_summary.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "sample": sample,
                "status": summary.get("status", ""),
                "audit_status": summary.get("audit_status", ""),
                "ordered_segment_count": summary.get("ordered_segment_count", "n/a"),
                "consolidated_segment_count": summary.get("consolidated_segment_count", "n/a"),
                "merged_segment_count": summary.get("merged_segment_count", "n/a"),
                "max_pen_up_jump_px": summary.get("max_pen_up_jump_px", "n/a"),
                "sample_dir": str(sample_dir),
                "summary_path": str(sample_dir / "recovery_summary.json"),
                "trajectory_path": str(sample_dir / "trial_ordered_trajectory.csv"),
                "source_trajectory_image": str(sample_dir / "callirewrite_source_trajectory.png"),
                "final_trajectory_image": str(sample_dir / "final_trajectory.png"),
            }
        )

    manual_audit_sheet_path = write_manual_audit_sheet(batch_dir)
    contact_sheet_path = write_callirewrite_hybrid_contact_sheet(batch_dir)
    _write_hybrid_batch_report(
        batch_dir / "batch_report.md",
        rows,
        manual_audit_sheet_path=manual_audit_sheet_path,
        contact_sheet_path=contact_sheet_path,
    )

    benchmark = create_smoke_benchmark_report(batch_dir)
    report_path = batch_dir / "callirewrite_hybrid_probe_report.json"
    payload = {
        "status": "ok",
        "stage": "callirewrite_hybrid_probe",
        "converted_dir": str(converted_dir),
        "input_dir": str(input_dir),
        "batch_dir": str(batch_dir),
        "sample_count": len(normalized_samples),
        "samples": normalized_samples,
        "visual_audit_contact_sheet": str(contact_sheet_path),
        "manual_audit_sheet": str(manual_audit_sheet_path),
        "status_counts": benchmark["status_counts"],
        "audit_status_counts": benchmark["audit_status_counts"],
        "report_path": str(report_path),
        "boundary_note": (
            "External CalliRewrite coarse sequence plus local continuity-oriented postprocess "
            "for offline visual comparison only; not robot output."
        ),
    }
    write_summary_json(report_path, payload)
    return payload


def load_callirewrite_segments(sample_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sample_dir = Path(sample_dir)
    recovered_path = sample_dir / "callirewrite_recovered_strokes.json"
    if recovered_path.exists():
        payload = json.loads(recovered_path.read_text(encoding="utf-8"))
        segments = [_normalized_segment(segment, default_component_id=index + 1) for index, segment in enumerate(payload.get("segments", ()))]
        return segments, {
            "load_backend": "recovered_json",
            "external_source": str(payload.get("source", "")),
            "coordinate_frame": str(payload.get("coordinate_frame", "callirewrite_image_pixels")),
            "source_path": str(recovered_path),
        }

    trajectory_path = sample_dir / "trial_ordered_trajectory.csv"
    if trajectory_path.exists():
        return _load_segments_from_trial_csv(trajectory_path)

    raise FileNotFoundError(f"No CalliRewrite converted files found in {sample_dir}")


def write_callirewrite_hybrid_contact_sheet(
    batch_dir: Path,
    output_path: Path | None = None,
    *,
    panel_size: tuple[int, int] = (160, 160),
    padding: int = 12,
    sample_label_width: int = 260,
    header_height: int = 22,
    sample_height: int = 46,
) -> Path:
    batch_dir = Path(batch_dir)
    if output_path is None:
        output_path = batch_dir / "visual_audit_contact_sheet.png"
    output_path = Path(output_path)

    rows = _collect_batch_summary_rows(batch_dir)
    width = padding + sample_label_width + len(HYBRID_CONTACT_PANELS) * (panel_size[0] + padding)
    height = padding + header_height
    if rows:
        height += len(rows) * (sample_height + panel_size[1] + padding)
    else:
        height += sample_height + panel_size[1] + padding

    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((padding, padding), "sample", fill=(30, 30, 30))
    for index, (label, _) in enumerate(HYBRID_CONTACT_PANELS):
        x = padding + sample_label_width + index * (panel_size[0] + padding)
        draw.text((x, padding), label, fill=(30, 30, 30))

    if not rows:
        draw.text((padding, padding + header_height), "no samples", fill=(120, 120, 120))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path)
        return output_path

    for row_index, row in enumerate(rows):
        sample_dir = batch_dir / row["sample"]
        top = padding + header_height + row_index * (sample_height + panel_size[1] + padding)
        draw.text((padding, top), row["sample"], fill=(20, 20, 20))
        draw.text((padding, top + 10), row["audit_status"], fill=(120, 120, 120))
        draw.text((padding, top + 20), f"final:{row.get('selected_postprocess_mode', '')}", fill=(120, 120, 120))
        draw.text((padding, top + 30), f"review:{row.get('review_recommended_mode', '')}", fill=(120, 120, 120))
        panel_top = top + sample_height
        review_panel_filename = _review_panel_filename_for_mode(row.get("review_recommended_mode", ""))
        for panel_index, (_, filename) in enumerate(HYBRID_CONTACT_PANELS):
            left = padding + sample_label_width + panel_index * (panel_size[0] + padding)
            panel_image = _load_contact_panel(sample_dir / filename, panel_size)
            canvas.paste(panel_image, (left, panel_top))
            outline = DEFAULT_REVIEW_PANEL_HIGHLIGHT_OUTLINE if filename == review_panel_filename else (200, 200, 200)
            outline_width = DEFAULT_REVIEW_PANEL_HIGHLIGHT_WIDTH if filename == review_panel_filename else 1
            draw.rectangle(
                (left, panel_top, left + panel_size[0] - 1, panel_top + panel_size[1] - 1),
                outline=outline,
                width=outline_width,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def _run_single_sample(
    *,
    converted_sample_dir: Path,
    sample: str,
    input_image_path: Path,
    batch_dir: Path,
    merge_gap_px: float,
    direction_cos_threshold: float,
    simplify_tolerance_px: float,
    resample_step_px: float | None,
    postprocess_mode: str,
    makemeahanzi_graphics_path: Path | str | None,
    sample_char_map: dict[str, str] | None,
    primitive_library: StrokePrimitiveLibrary,
    primitive_library_meta: dict[str, Any],
) -> Path:
    sample_dir = batch_dir / sample
    sample_dir.mkdir(parents=True, exist_ok=True)

    raw_segments, meta = load_callirewrite_segments(converted_sample_dir)
    foreground_mask = _load_input_foreground_mask(input_image_path) if input_image_path.exists() else None
    light_repaired_raw_segments, light_repair_meta = light_repair_raw_segments(
        raw_segments,
        foreground_mask=foreground_mask,
    )
    raw_jump_metrics = _pen_up_jump_metrics(raw_segments)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    light_repaired_ordered_segments = order_segments(
        light_repaired_raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    light_repaired_ordered_segments, light_repair_geometry_meta = light_repair_ordered_segments_geometry(
        light_repaired_ordered_segments,
        foreground_mask=foreground_mask,
    )
    light_repaired_ordered_segments = _restore_render_subpaths_from_source_segments(
        light_repaired_ordered_segments,
        source_segments=ordered_segments,
    )
    local_prior_meta = _default_prior_meta(len(ordered_segments))
    local_consolidated = None
    local_consolidation_meta = None
    if postprocess_mode in {"local", "auto"}:
        local_consolidated, local_consolidation_meta = consolidate_ordered_segments(
            ordered_segments,
            merge_gap_px=merge_gap_px,
            direction_cos_threshold=direction_cos_threshold,
            simplify_tolerance_px=simplify_tolerance_px,
            resample_step_px=resample_step_px,
            foreground_mask=foreground_mask,
            foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
        )

    mmh_consolidated = None
    mmh_consolidation_meta = None
    mmh_prior_meta = _default_prior_meta(len(ordered_segments))
    if postprocess_mode in {"makemeahanzi_regroup", "auto"}:
        canvas_shape = tuple(int(value) for value in foreground_mask.shape) if foreground_mask is not None else (128, 128)
        mmh_grouped_segments, mmh_prior_meta = regroup_ordered_segments_by_makemeahanzi(
            ordered_segments,
            sample_name=sample,
            canvas_shape=canvas_shape,
            foreground_mask=foreground_mask,
            graphics_path=makemeahanzi_graphics_path if makemeahanzi_graphics_path is not None else Path("code/data/makemeahanzi/graphics.txt"),
            sample_char_map=sample_char_map,
        )
        mmh_consolidated, mmh_consolidation_meta = consolidate_ordered_segments(
            mmh_grouped_segments,
            merge_adjacent=False,
            merge_gap_px=merge_gap_px,
            direction_cos_threshold=direction_cos_threshold,
            simplify_tolerance_px=simplify_tolerance_px,
            resample_step_px=resample_step_px,
            foreground_mask=foreground_mask,
            foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
        )
        mmh_consolidated = _restore_render_subpaths_from_source_segments(
            mmh_consolidated,
            source_segments=ordered_segments,
        )

    local_candidate_segments = local_consolidated if local_consolidated is not None else []
    local_candidate_prior_meta = local_prior_meta
    if local_candidate_segments:
        local_candidate_segments, local_component_label_meta = _prepare_local_candidate_segments(
            local_candidate_segments,
            sample_name=sample,
            foreground_mask=foreground_mask,
            graphics_path=makemeahanzi_graphics_path if makemeahanzi_graphics_path is not None else Path("code/data/makemeahanzi/graphics.txt"),
            sample_char_map=sample_char_map,
        )
        if bool(local_component_label_meta.get("makemeahanzi_prior_available", False)):
            local_candidate_prior_meta = {
                **(dict(mmh_prior_meta) if bool(mmh_prior_meta.get("makemeahanzi_prior_available", False)) else local_prior_meta),
                **local_component_label_meta,
            }
        else:
            local_candidate_prior_meta = {**local_prior_meta, **local_component_label_meta}
        local_candidate_prior_meta["makemeahanzi_prior_applied"] = False

    structure_primitive_segments: list[dict[str, Any]] = []
    structure_meta: dict[str, Any] = {
        "structure_prior_applied": False,
        "structure_prior_reason": "not_applicable",
        "structure_target_stroke_count": 0,
        "structure_segment_count": 0,
        "structure_bridge_count": 0,
        "structure_max_bridge_gap_px": 0.0,
        "structure_overshoot_count": 0,
    }
    primitive_transfer_meta: dict[str, Any] = {
        "primitive_transfer_applied": False,
        "primitive_transfer_segment_count": 0,
        "primitive_transfer_kinds": [],
        "primitive_transfer_missing_kinds": [],
    }
    if sample == "kou" and local_candidate_segments:
        source_canvas_shape = (
            tuple(int(value) for value in foreground_mask.shape)
            if foreground_mask is not None
            else (128, 128)
        )
        structure_source_segments, _ = label_segments_by_makemeahanzi_components(
            light_repaired_ordered_segments,
            sample_name=sample,
            canvas_shape=source_canvas_shape,
            graphics_path=(
                makemeahanzi_graphics_path
                if makemeahanzi_graphics_path is not None
                else Path("code/data/makemeahanzi/graphics.txt")
            ),
            sample_char_map=sample_char_map,
        )
        structure_primitive_segments, structure_meta = build_kou_three_stroke_candidate(
            structure_source_segments,
            canvas_shape=source_canvas_shape,
            graphics_path=(
                makemeahanzi_graphics_path
                if makemeahanzi_graphics_path is not None
                else Path("code/data/makemeahanzi/graphics.txt")
            ),
            foreground_mask=foreground_mask,
        )
        if structure_primitive_segments:
            structure_primitive_segments, primitive_transfer_meta = _attach_primitive_width_profiles(
                structure_primitive_segments,
                primitive_library,
            )

    visual_crop_bbox, canvas_shape, trajectory_crop_bbox, input_foreground_bbox = _build_visual_crop_bbox(
        raw_segments,
        input_image_path if input_image_path.exists() else None,
        margin_px=DEFAULT_VISUAL_MARGIN_PX,
    )
    raw_visual_segments = _translate_segments(raw_segments, visual_crop_bbox)
    ordered_visual_segments = _translate_segments(ordered_segments, visual_crop_bbox)
    light_repaired_ordered_visual_segments = _translate_segments(light_repaired_ordered_segments, visual_crop_bbox)
    local_raw_compare_visual_segments = _translate_segments(local_consolidated or [], visual_crop_bbox)
    local_visual_segments = _translate_segments(local_candidate_segments, visual_crop_bbox)
    mmh_visual_segments = _translate_segments(mmh_consolidated or [], visual_crop_bbox)
    structure_primitive_visual_segments = _translate_segments(structure_primitive_segments, visual_crop_bbox)
    cropped_foreground_mask = (
        _crop_mask(foreground_mask, visual_crop_bbox)
        if foreground_mask is not None
        else None
    )

    raw_prior_meta = dict(mmh_prior_meta) if bool(mmh_prior_meta.get("makemeahanzi_prior_available", False)) else local_prior_meta
    raw_summary = _candidate_selection_summary(
        ordered_segments,
        raw_prior_meta,
        rendered_similarity_to_input=_execution_visual_similarity(
            ordered_visual_segments,
            canvas_shape=canvas_shape,
            foreground_mask=cropped_foreground_mask,
        ),
    )
    light_repair_summary = _candidate_selection_summary(
        light_repaired_ordered_segments,
        raw_prior_meta,
        rendered_similarity_to_input=_execution_visual_similarity(
            light_repaired_ordered_visual_segments,
            canvas_shape=canvas_shape,
            foreground_mask=cropped_foreground_mask,
        ),
    )
    local_raw_compare_summary = _candidate_selection_summary(
        local_consolidated or [],
        local_prior_meta,
        rendered_similarity_to_input=_execution_visual_similarity(
            local_raw_compare_visual_segments,
            canvas_shape=canvas_shape,
            foreground_mask=cropped_foreground_mask,
        ),
    )
    local_summary = _candidate_selection_summary(
        local_candidate_segments,
        local_candidate_prior_meta,
        rendered_similarity_to_input=_execution_visual_similarity(
            local_visual_segments,
            canvas_shape=canvas_shape,
            foreground_mask=cropped_foreground_mask,
        ),
    )
    prior_summary = _candidate_selection_summary(
        mmh_consolidated or [],
        mmh_prior_meta,
        rendered_similarity_to_input=_execution_visual_similarity(
            mmh_visual_segments,
            canvas_shape=canvas_shape,
            foreground_mask=cropped_foreground_mask,
        ),
    )
    component_mix_segments, component_mix_meta = _build_component_mix_candidate_segments(
        local_candidate_segments,
        mmh_consolidated or [],
        detail_source_segments=light_repaired_ordered_segments,
    )
    gou_primitive_meta = {
        "gou_primitive_registered": False,
        "gou_primitive_source_sample": "",
        "gou_primitive_pointed_end": False,
        "gou_primitive_last_relative_width": None,
    }
    if sample == "xin" and bool(component_mix_meta.get("component_mix_applied", False)):
        gou_primitive_meta = _register_gou_primitive_from_segments(
            component_mix_segments,
            foreground_mask,
            primitive_library,
            source_sample=sample,
        )
        primitive_library_meta = {
            **primitive_library_meta,
            "registered_primitive_kinds": list(primitive_library.kinds()),
            "missing_primitive_kinds": [
                kind
                for kind in primitive_library_meta.get("missing_primitive_kinds", [])
                if kind != "gou"
            ],
        }
    component_mix_visual_segments = _translate_segments(component_mix_segments, visual_crop_bbox)
    component_mix_summary = _candidate_selection_summary(
        component_mix_segments,
        local_candidate_prior_meta,
        rendered_similarity_to_input=(
            _execution_visual_similarity(
                component_mix_visual_segments,
                canvas_shape=canvas_shape,
                foreground_mask=cropped_foreground_mask,
            )
            if component_mix_segments
            else None
        ),
    )
    structure_prior_meta = {
        **local_candidate_prior_meta,
        "makemeahanzi_prior_available": bool(structure_meta.get("structure_prior_applied", False)),
        "makemeahanzi_prior_applied": bool(structure_meta.get("structure_prior_applied", False)),
        "makemeahanzi_target_stroke_count": int(structure_meta.get("structure_target_stroke_count", 0) or 0),
    }
    structure_primitive_summary = _candidate_selection_summary(
        structure_primitive_segments,
        structure_prior_meta,
        rendered_similarity_to_input=(
            _execution_visual_similarity(
                structure_primitive_visual_segments,
                canvas_shape=canvas_shape,
                foreground_mask=cropped_foreground_mask,
            )
            if structure_primitive_segments
            else None
        ),
    )

    if postprocess_mode == "local":
        selected_segments = local_candidate_segments
        consolidation_meta = local_consolidation_meta if local_consolidation_meta is not None else _regroup_consolidation_meta(local_prior_meta)
        prior_meta = local_candidate_prior_meta
        selected_postprocess_mode = "local"
        selection_reason = "manual_mode"
    elif postprocess_mode == "raw_light_repair":
        selected_segments = light_repaired_ordered_segments
        consolidation_meta = _light_repair_consolidation_meta(light_repair_meta, light_repair_geometry_meta)
        prior_meta = raw_prior_meta
        selected_postprocess_mode = "raw_light_repair"
        selection_reason = "manual_mode"
    elif postprocess_mode == "makemeahanzi_regroup":
        selected_segments = mmh_consolidated if mmh_consolidated is not None else []
        consolidation_meta = mmh_consolidation_meta if mmh_consolidation_meta is not None else _regroup_consolidation_meta(mmh_prior_meta)
        prior_meta = mmh_prior_meta
        selected_postprocess_mode = "makemeahanzi_regroup"
        selection_reason = "manual_mode"
    elif postprocess_mode == "auto":
        auto_local_summary = (
            local_summary
            if _should_use_component_labeled_local_candidate_for_auto(
                local_raw_compare_summary,
                local_summary,
                prior_summary,
            )
            else local_raw_compare_summary
        )
        selected_postprocess_mode, selection_reason = _choose_postprocess_candidate(
            auto_local_summary,
            prior_summary,
            raw_summary=raw_summary,
            raw_compare_local_summary=local_raw_compare_summary,
            light_repair_summary=light_repair_summary,
            component_mix_summary=component_mix_summary,
            component_mix_meta=component_mix_meta,
            structure_primitive_summary=structure_primitive_summary,
            structure_primitive_meta={**structure_meta, **primitive_transfer_meta},
        )
        if selected_postprocess_mode == "makemeahanzi_regroup":
            selected_segments = mmh_consolidated if mmh_consolidated is not None else []
            consolidation_meta = mmh_consolidation_meta if mmh_consolidation_meta is not None else _regroup_consolidation_meta(mmh_prior_meta)
            prior_meta = mmh_prior_meta
        elif selected_postprocess_mode == "component_mix":
            selected_segments = component_mix_segments
            consolidation_meta = local_consolidation_meta if local_consolidation_meta is not None else _regroup_consolidation_meta(local_prior_meta)
            prior_meta = dict(local_candidate_prior_meta)
        elif selected_postprocess_mode == "structure_primitive":
            selected_segments = structure_primitive_segments
            consolidation_meta = _regroup_consolidation_meta(structure_prior_meta)
            prior_meta = structure_prior_meta
        elif selected_postprocess_mode == "raw_light_repair":
            selected_segments = light_repaired_ordered_segments
            consolidation_meta = _light_repair_consolidation_meta(light_repair_meta, light_repair_geometry_meta)
            prior_meta = raw_prior_meta
            prior_meta["makemeahanzi_prior_applied"] = False
        elif selected_postprocess_mode == "raw":
            selected_segments = ordered_segments
            consolidation_meta = _raw_selection_consolidation_meta()
            prior_meta = raw_prior_meta
            prior_meta["makemeahanzi_prior_applied"] = False
        else:
            selected_segments = local_candidate_segments
            consolidation_meta = local_consolidation_meta if local_consolidation_meta is not None else _regroup_consolidation_meta(local_prior_meta)
            prior_meta = local_candidate_prior_meta
    else:
        raise ValueError(f"Unsupported postprocess_mode: {postprocess_mode}")

    selected_visual_segments = _translate_segments(selected_segments, visual_crop_bbox)
    blank_skeleton = np.zeros(canvas_shape, dtype=bool)
    review_recommended_mode = _recommended_review_mode(
        selected_postprocess_mode=selected_postprocess_mode,
        raw_summary=raw_summary,
        light_repair_summary=light_repair_summary,
        local_summary=local_summary,
        prior_summary=prior_summary,
        component_mix_summary=component_mix_summary,
        structure_primitive_summary=structure_primitive_summary,
    )
    review_recommended_segments = _segments_for_review_mode(
        review_recommended_mode,
        ordered_segments=ordered_segments,
        light_repaired_ordered_segments=light_repaired_ordered_segments,
        local_candidate_segments=local_candidate_segments,
        mmh_consolidated=mmh_consolidated,
        component_mix_segments=component_mix_segments,
        structure_primitive_segments=structure_primitive_segments,
        selected_segments=selected_segments,
    )
    review_recommended_visual_segments = _translate_segments(review_recommended_segments, visual_crop_bbox)

    cropped_input_image = None
    if input_image_path.exists():
        cropped_input_image = _crop_input_image(input_image_path, visual_crop_bbox)
        sample_dir.mkdir(parents=True, exist_ok=True)
        cropped_input_image.save(sample_dir / "input_image.png")

    if structure_primitive_visual_segments:
        write_trajectory_png(
            sample_dir / "structure_skeleton_trajectory.png",
            blank_skeleton,
            structure_primitive_visual_segments,
            show_pen_up_connectors=False,
        )
        _write_overlay_png(
            sample_dir / "structure_skeleton_overlay.png",
            cropped_input_image,
            structure_primitive_visual_segments,
            color_by_component=True,
        )
        write_trajectory_playback_contact_sheet(
            sample_dir / "structure_skeleton_playback_contact_sheet.png",
            blank_skeleton,
            structure_primitive_visual_segments,
        )

    write_order_png(sample_dir / "candidate_order.png", blank_skeleton, ordered_visual_segments)
    write_trajectory_png(
        sample_dir / "callirewrite_source_trajectory.png",
        blank_skeleton,
        raw_visual_segments,
        show_pen_up_connectors=False,
    )
    write_execution_render_png(
        sample_dir / "raw_rendered_execution.png",
        blank_skeleton,
        ordered_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_execution_render_png(
        sample_dir / "light_repair_rendered_execution.png",
        blank_skeleton,
        light_repaired_ordered_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_execution_render_png(
        sample_dir / "local_rendered_execution.png",
        blank_skeleton,
        local_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_execution_render_png(
        sample_dir / "makemeahanzi_rendered_execution.png",
        blank_skeleton,
        mmh_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    if component_mix_visual_segments:
        write_execution_render_png(
            sample_dir / "component_mix_rendered_execution.png",
            blank_skeleton,
            component_mix_visual_segments,
            scale=DEFAULT_OVERLAY_SCALE,
            foreground_mask=cropped_foreground_mask,
            edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
        )
    if structure_primitive_visual_segments:
        write_execution_render_png(
            sample_dir / "structure_primitive_rendered_execution.png",
            blank_skeleton,
            structure_primitive_visual_segments,
            scale=DEFAULT_OVERLAY_SCALE,
            foreground_mask=cropped_foreground_mask,
            edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
        )
    write_execution_render_png(
        sample_dir / "constant_width_render.png",
        blank_skeleton,
        selected_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        render_mode="fixed",
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_execution_render_png(
        sample_dir / "conservative_width_render.png",
        blank_skeleton,
        selected_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        render_mode="segment_constant",
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_trajectory_png(
        sample_dir / "review_recommended_trajectory.png",
        blank_skeleton,
        review_recommended_visual_segments,
        show_pen_up_connectors=False,
    )
    write_trajectory_png(
        sample_dir / "final_trajectory.png",
        blank_skeleton,
        selected_visual_segments,
        show_pen_up_connectors=False,
    )
    write_execution_render_png(
        sample_dir / "rendered_execution.png",
        blank_skeleton,
        selected_visual_segments,
        scale=DEFAULT_OVERLAY_SCALE,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    write_execution_playback_contact_sheet(
        sample_dir / "playback_contact_sheet.png",
        blank_skeleton,
        selected_visual_segments,
        foreground_mask=cropped_foreground_mask,
        edge_soften_radius_px=DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
    )
    _write_pen_up_debug_png(sample_dir / "callirewrite_pen_up.png", canvas_shape, raw_visual_segments)
    _write_pen_up_debug_png(
        sample_dir / "hybrid_pen_up.png",
        canvas_shape,
        selected_visual_segments,
        color_by_component=True,
    )
    _write_overlay_png(sample_dir / "callirewrite_overlay.png", cropped_input_image, raw_visual_segments)
    _write_overlay_png(
        sample_dir / "hybrid_overlay.png",
        cropped_input_image,
        selected_visual_segments,
        color_by_component=True,
    )
    trajectory_point_count = write_trial_csv(sample_dir / "trial_ordered_trajectory.csv", selected_segments)

    jump_metrics = _pen_up_jump_metrics(selected_segments)
    jump_breakdown = _pen_up_jump_breakdown(selected_segments)
    position_layer_source = _position_layer_source(selected_postprocess_mode)
    width_layer_source = "input_foreground_mask" if cropped_foreground_mask is not None else "fixed_default"
    if selected_postprocess_mode == "structure_primitive" and bool(primitive_transfer_meta.get("primitive_transfer_applied", False)):
        width_layer_source += "+stroke_primitive_profile"
    width_layer_render_mode = "variable" if cropped_foreground_mask is not None else "fixed"
    summary = {
        "sample": sample,
        "status": "ok",
        "source": "callirewrite_hybrid",
        "external_source": meta.get("external_source", ""),
        "load_backend": meta.get("load_backend", ""),
        "converted_sample_dir": str(converted_sample_dir),
        "sample_dir": str(sample_dir),
        "coordinate_frame": meta.get("coordinate_frame", "callirewrite_image_pixels"),
        "input_image_path": str(input_image_path) if input_image_path.exists() else "n/a",
        "raw_segment_count": len(raw_segments),
        "canvas_shape": [int(canvas_shape[0]), int(canvas_shape[1])],
        "visual_canvas_shape": [int(canvas_shape[0]), int(canvas_shape[1])],
        "visual_crop_bbox": [int(value) for value in visual_crop_bbox],
        "trajectory_crop_bbox": [int(value) for value in trajectory_crop_bbox],
        "input_foreground_bbox": [int(value) for value in input_foreground_bbox] if input_foreground_bbox is not None else None,
        "visual_crop_margin_px": DEFAULT_VISUAL_MARGIN_PX,
        "visual_crop_strategy": "union_input_foreground_and_trajectory",
        "position_layer_policy": "weak_foreground_snap",
        "position_layer_source": position_layer_source,
        "position_layer_foreground_snap_blend": DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
        "width_layer_source": width_layer_source,
        "width_layer_render_mode": width_layer_render_mode,
        "rendered_execution_uses_foreground_width": cropped_foreground_mask is not None,
        "rendered_execution_edge_soften_radius_px": DEFAULT_RENDERED_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
        "raw_rendered_execution_image": str(sample_dir / "raw_rendered_execution.png"),
        "light_repair_rendered_execution_image": str(sample_dir / "light_repair_rendered_execution.png"),
        "local_rendered_execution_image": str(sample_dir / "local_rendered_execution.png"),
        "makemeahanzi_rendered_execution_image": str(sample_dir / "makemeahanzi_rendered_execution.png"),
        "component_mix_rendered_execution_image": str(sample_dir / "component_mix_rendered_execution.png") if component_mix_segments else "n/a",
        "structure_primitive_rendered_execution_image": (
            str(sample_dir / "structure_primitive_rendered_execution.png")
            if structure_primitive_segments
            else "n/a"
        ),
        "structure_skeleton_trajectory_image": (
            str(sample_dir / "structure_skeleton_trajectory.png")
            if structure_primitive_segments
            else "n/a"
        ),
        "structure_skeleton_overlay_image": (
            str(sample_dir / "structure_skeleton_overlay.png")
            if structure_primitive_segments
            else "n/a"
        ),
        "structure_skeleton_playback_contact_sheet": (
            str(sample_dir / "structure_skeleton_playback_contact_sheet.png")
            if structure_primitive_segments
            else "n/a"
        ),
        "constant_width_render_image": str(sample_dir / "constant_width_render.png"),
        "conservative_width_render_image": str(sample_dir / "conservative_width_render.png"),
        "review_recommended_trajectory_image": str(sample_dir / "review_recommended_trajectory.png"),
        "rendered_execution_image": str(sample_dir / "rendered_execution.png"),
        "playback_contact_sheet": str(sample_dir / "playback_contact_sheet.png"),
        "postprocess_mode": postprocess_mode,
        "selected_postprocess_mode": selected_postprocess_mode,
        "postprocess_selection_reason": selection_reason,
        "review_recommended_mode": review_recommended_mode,
        "segment_count": len(ordered_segments),
        "ordered_segment_count": len(ordered_segments),
        "consolidated_segment_count": len(selected_segments),
        "component_count": len({segment.get("component_id") for segment in ordered_segments}),
        "trajectory_point_count": trajectory_point_count,
        "raw_visual_similarity_to_input": raw_summary.get("rendered_similarity_to_input"),
        "light_repair_visual_similarity_to_input": light_repair_summary.get("rendered_similarity_to_input"),
        "local_visual_similarity_to_input": local_summary.get("rendered_similarity_to_input"),
        "makemeahanzi_visual_similarity_to_input": prior_summary.get("rendered_similarity_to_input"),
        "component_mix_visual_similarity_to_input": component_mix_summary.get("rendered_similarity_to_input"),
        "structure_primitive_visual_similarity_to_input": structure_primitive_summary.get("rendered_similarity_to_input"),
        "component_mix_internal_max_pen_up_jump_px": component_mix_summary.get("internal_max_pen_up_jump_px"),
        "component_mix_avoidable_internal_max_jump_px": component_mix_summary.get("avoidable_internal_max_jump_px"),
        "component_mix_min_turn_cos": component_mix_summary.get("min_turn_cos"),
        **component_mix_meta,
        **structure_meta,
        **primitive_transfer_meta,
        **gou_primitive_meta,
        **primitive_library_meta,
        "registered_primitive_kinds": list(primitive_library.kinds()),
        **{f"raw_{key}": value for key, value in raw_jump_metrics.items()},
        **consolidation_meta,
        **jump_metrics,
        **jump_breakdown,
        **prior_meta,
        "ordered_source_segment_ids": [list(segment.get("source_segment_ids", ())) for segment in ordered_segments],
        "consolidated_source_segment_ids": [list(segment.get("source_segment_ids", ())) for segment in selected_segments],
        "manual_audit_required": True,
        "boundary_note": (
            "External CalliRewrite coarse sequence plus local continuity-oriented postprocess "
            "for offline visual comparison only; not robot output."
        ),
    }
    if not selected_segments or trajectory_point_count == 0:
        summary["status"] = "failed"
        summary["failure_reason"] = "no_consolidated_segments"
    else:
        summary["failure_reason"] = ""
    summary["audit_status"] = _hybrid_audit_status(summary)
    write_summary_json(sample_dir / "recovery_summary.json", summary)
    return sample_dir


def _default_prior_meta(grouped_segment_count: int) -> dict[str, Any]:
    return {
        "makemeahanzi_prior_available": False,
        "makemeahanzi_prior_applied": False,
        "makemeahanzi_component_labels_applied": False,
        "makemeahanzi_component_label_group_count": 0,
        "makemeahanzi_char": None,
        "makemeahanzi_target_stroke_count": 0,
        "makemeahanzi_grouped_segment_count": int(grouped_segment_count),
        "makemeahanzi_supported_bridge_count": 0,
        "makemeahanzi_rejected_bridge_count": 0,
        "makemeahanzi_skipped_contained_segment_count": 0,
        "makemeahanzi_merged_group_count": 0,
        "makemeahanzi_geometry_regularized_segment_count": 0,
        "makemeahanzi_local_blob_extended_segment_count": 0,
    }


def _regroup_consolidation_meta(prior_meta: dict[str, Any]) -> dict[str, int]:
    return {
        "merged_segment_count": int(prior_meta.get("makemeahanzi_merged_group_count", 0)),
        "simplified_point_delta": 0,
        "resampled_point_delta": 0,
        "snapped_point_count": 0,
    }


def _raw_selection_consolidation_meta() -> dict[str, int]:
    return {
        "merged_segment_count": 0,
        "simplified_point_delta": 0,
        "resampled_point_delta": 0,
        "snapped_point_count": 0,
    }


def _position_layer_source(selected_postprocess_mode: str) -> str:
    if selected_postprocess_mode == "raw":
        return "ordered_raw"
    if selected_postprocess_mode == "raw_light_repair":
        return "raw_light_repair"
    if selected_postprocess_mode == "makemeahanzi_regroup":
        return "makemeahanzi_regroup"
    if selected_postprocess_mode == "component_mix":
        return "component_mix"
    if selected_postprocess_mode == "structure_primitive":
        return "structure_primitive"
    return "local_candidate"


def _recommended_review_mode(
    *,
    selected_postprocess_mode: str,
    raw_summary: dict[str, Any],
    light_repair_summary: dict[str, Any],
    local_summary: dict[str, Any],
    prior_summary: dict[str, Any],
    component_mix_summary: dict[str, Any] | None = None,
    structure_primitive_summary: dict[str, Any] | None = None,
) -> str:
    if (
        selected_postprocess_mode == "structure_primitive"
        and structure_primitive_summary is not None
        and structure_primitive_summary.get("rendered_similarity_to_input") is not None
    ):
        return "structure_primitive"
    candidates = [
        ("raw", raw_summary.get("rendered_similarity_to_input")),
        ("raw_light_repair", light_repair_summary.get("rendered_similarity_to_input")),
        ("local", local_summary.get("rendered_similarity_to_input")),
        ("makemeahanzi_regroup", prior_summary.get("rendered_similarity_to_input")),
    ]
    if component_mix_summary is not None:
        candidates.append(("component_mix", component_mix_summary.get("rendered_similarity_to_input")))
    if structure_primitive_summary is not None:
        candidates.append(("structure_primitive", structure_primitive_summary.get("rendered_similarity_to_input")))
    valid_candidates = [
        (mode, float(score))
        for mode, score in candidates
        if score is not None
    ]
    if not valid_candidates:
        return str(selected_postprocess_mode)
    valid_candidates.sort(key=lambda item: item[1], reverse=True)
    return str(valid_candidates[0][0])


def _review_panel_filename_for_mode(review_mode: str) -> str | None:
    if review_mode == "raw":
        return "raw_rendered_execution.png"
    if review_mode == "raw_light_repair":
        return "light_repair_rendered_execution.png"
    if review_mode == "local":
        return "local_rendered_execution.png"
    if review_mode == "makemeahanzi_regroup":
        return "makemeahanzi_rendered_execution.png"
    if review_mode == "component_mix":
        return "component_mix_rendered_execution.png"
    if review_mode == "structure_primitive":
        return "structure_primitive_rendered_execution.png"
    return None


def _segments_for_review_mode(
    review_mode: str,
    *,
    ordered_segments: Sequence[dict[str, Any]],
    light_repaired_ordered_segments: Sequence[dict[str, Any]],
    local_candidate_segments: Sequence[dict[str, Any]],
    mmh_consolidated: Sequence[dict[str, Any]] | None,
    component_mix_segments: Sequence[dict[str, Any]] | None,
    structure_primitive_segments: Sequence[dict[str, Any]] | None,
    selected_segments: Sequence[dict[str, Any]],
) -> Sequence[dict[str, Any]]:
    if review_mode == "raw":
        return ordered_segments
    if review_mode == "raw_light_repair":
        return light_repaired_ordered_segments
    if review_mode == "local":
        return local_candidate_segments
    if review_mode == "makemeahanzi_regroup":
        return mmh_consolidated if mmh_consolidated is not None else []
    if review_mode == "component_mix":
        return component_mix_segments if component_mix_segments is not None else []
    if review_mode == "structure_primitive":
        return structure_primitive_segments if structure_primitive_segments is not None else []
    return selected_segments


def _light_repair_consolidation_meta(
    light_repair_meta: dict[str, Any],
    light_repair_geometry_meta: dict[str, Any],
) -> dict[str, int]:
    return {
        "merged_segment_count": int(light_repair_meta.get("light_repair_merged_segment_count", 0)),
        "simplified_point_delta": 0,
        "resampled_point_delta": 0,
        "snapped_point_count": 0,
        "light_repair_merged_segment_count": int(light_repair_meta.get("light_repair_merged_segment_count", 0)),
        "light_repair_geometry_adjusted_segment_count": int(
            light_repair_geometry_meta.get("light_repair_geometry_adjusted_segment_count", 0)
        ),
    }


def _candidate_selection_summary(
    consolidated: list[dict[str, Any]],
    prior_meta: dict[str, Any],
    *,
    rendered_similarity_to_input: float | None = None,
) -> dict[str, Any]:
    jump_breakdown = _pen_up_jump_breakdown(consolidated)
    return {
        "consolidated_segment_count": len(consolidated),
        "internal_max_pen_up_jump_px": float(jump_breakdown.get("internal_max_pen_up_jump_px", 0.0) or 0.0),
        "avoidable_internal_max_jump_px": jump_breakdown.get("avoidable_internal_max_jump_px"),
        "min_turn_cos": _min_turn_cos(consolidated),
        "rendered_similarity_to_input": rendered_similarity_to_input,
        "makemeahanzi_prior_available": bool(prior_meta.get("makemeahanzi_prior_available", False)),
        "makemeahanzi_target_stroke_count": int(prior_meta.get("makemeahanzi_target_stroke_count", 0) or 0),
    }


def _build_component_mix_candidate_segments(
    local_segments: Sequence[dict[str, Any]],
    prior_segments: Sequence[dict[str, Any]],
    *,
    detail_source_segments: Sequence[dict[str, Any]] | None = None,
    min_foldback_length_px: float = COMPONENT_MIX_LONG_FOLDBACK_MIN_LENGTH_PX,
    foldback_max_cos: float = COMPONENT_MIX_LONG_FOLDBACK_MAX_COS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    local_index = _single_long_foldback_segment_index(
        local_segments,
        min_length_px=min_foldback_length_px,
        max_turn_cos=foldback_max_cos,
    )
    prior_index = _single_long_foldback_segment_index(
        prior_segments,
        min_length_px=min_foldback_length_px,
        max_turn_cos=foldback_max_cos,
    )
    if local_index is None or prior_index is None:
        return [], {
            "component_mix_applied": False,
            "component_mix_reason": "missing_unique_long_foldback",
            "component_mix_segment_count": 0,
        }

    mixed: list[dict[str, Any]] = []
    pruned_local_subpath_count = 0
    detail_source_replaced_count = 0
    prior_replacement = prior_segments[prior_index]
    detail_source_by_ids = _component_mix_detail_source_by_ids(detail_source_segments or [])
    for index, segment in enumerate(local_segments):
        if index == local_index:
            mixed.append(_copy_segment_for_component_mix(prior_replacement, source_kind="prior"))
            continue
        copied = _copy_segment_for_component_mix(segment, source_kind="local")
        copied, pruned_count = _prune_component_mix_local_subpaths_near_prior_foldback(
            copied,
            prior_replacement,
        )
        pruned_local_subpath_count += pruned_count
        if copied is not None:
            copied, replaced = _maybe_replace_component_mix_detail_dot(
                copied,
                detail_source_by_ids,
                prior_replacement,
            )
            detail_source_replaced_count += int(replaced)
            mixed.append(copied)
    return mixed, {
        "component_mix_applied": True,
        "component_mix_reason": "prior_long_foldback_replaces_local_long_foldback",
        "component_mix_segment_count": len(mixed),
        "component_mix_pruned_local_subpath_count": pruned_local_subpath_count,
        "component_mix_detail_source_replaced_count": detail_source_replaced_count,
        "component_mix_local_replaced_source_ids": list(local_segments[local_index].get("source_segment_ids", ())),
        "component_mix_prior_source_ids": list(prior_segments[prior_index].get("source_segment_ids", ())),
    }


def _single_long_foldback_segment_index(
    segments: Sequence[dict[str, Any]],
    *,
    min_length_px: float,
    max_turn_cos: float,
) -> int | None:
    indices = [
        index
        for index, segment in enumerate(segments)
        if _is_long_foldback_segment(
            segment,
            min_length_px=min_length_px,
            max_turn_cos=max_turn_cos,
        )
    ]
    if len(indices) != 1:
        return None
    return indices[0]


def _is_long_foldback_segment(
    segment: dict[str, Any],
    *,
    min_length_px: float,
    max_turn_cos: float,
) -> bool:
    points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
    if _polyline_length(points) < float(min_length_px):
        return False
    return _segment_min_turn_cos(points) <= float(max_turn_cos)


def _segment_min_turn_cos(points: Sequence[tuple[float, float]]) -> float:
    arr = np.asarray(points, dtype=float)
    if len(arr) < 3:
        return 1.0
    vectors = np.diff(arr, axis=0)
    lengths = np.linalg.norm(vectors, axis=1)
    if len(vectors) < 2:
        return 1.0
    tangents = vectors / np.maximum(lengths[:, None], 1e-9)
    cosines = np.sum(tangents[:-1] * tangents[1:], axis=1)
    if len(cosines) == 0:
        return 1.0
    return float(np.min(cosines))


def _copy_segment_for_component_mix(segment: dict[str, Any], *, source_kind: str = "local") -> dict[str, Any]:
    copied = dict(segment)
    copied["points"] = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
    if "render_subpaths" in segment:
        copied["render_subpaths"] = [
            [tuple(_as_float_point(point)) for point in subpath]
            for subpath in segment.get("render_subpaths", ())
        ]
    if "render_subpath_source_ids" in segment:
        copied["render_subpath_source_ids"] = [
            tuple(group)
            for group in segment.get("render_subpath_source_ids", ())
        ]
    copied["component_mix_source"] = str(source_kind)
    return copied


def _component_mix_detail_source_by_ids(
    detail_source_segments: Sequence[dict[str, Any]],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    by_ids: dict[tuple[Any, ...], dict[str, Any]] = {}
    for segment in detail_source_segments:
        source_ids = tuple(segment.get("source_segment_ids", ()))
        if source_ids:
            by_ids[source_ids] = segment
    return by_ids


def _maybe_replace_component_mix_detail_dot(
    segment: dict[str, Any],
    detail_source_by_ids: dict[tuple[Any, ...], dict[str, Any]],
    prior_foldback_segment: dict[str, Any],
    *,
    max_length_px: float = COMPONENT_MIX_DETAIL_DOT_MAX_LENGTH_PX,
    above_margin_px: float = COMPONENT_MIX_DETAIL_DOT_ABOVE_PRIOR_MARGIN_PX,
) -> tuple[dict[str, Any], bool]:
    source_ids = tuple(segment.get("source_segment_ids", ()))
    if len(source_ids) != 1:
        return segment, False
    detail_source = detail_source_by_ids.get(source_ids)
    if detail_source is None:
        return segment, False
    if not _is_short_component_mix_detail_dot(segment, max_length_px=max_length_px):
        return segment, False
    if not _is_short_component_mix_detail_dot(detail_source, max_length_px=max_length_px):
        return segment, False
    if not _is_component_mix_segment_above_prior_foldback(
        segment,
        prior_foldback_segment,
        margin_px=above_margin_px,
    ):
        return segment, False
    if not _is_component_mix_segment_above_prior_foldback(
        detail_source,
        prior_foldback_segment,
        margin_px=above_margin_px,
    ):
        return segment, False
    replacement = _copy_segment_for_component_mix(detail_source, source_kind="detail")
    for key in ("segment_id", "component_id", "stroke_like_id", "order_index", "is_loop"):
        if key in segment:
            replacement[key] = segment[key]
    return replacement, True


def _is_short_component_mix_detail_dot(
    segment: dict[str, Any],
    *,
    max_length_px: float,
) -> bool:
    points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
    if len(points) < 2:
        return False
    return _polyline_length(points) <= float(max_length_px)


def _is_component_mix_segment_above_prior_foldback(
    segment: dict[str, Any],
    prior_foldback_segment: dict[str, Any],
    *,
    margin_px: float,
) -> bool:
    segment_bbox = _component_mix_segment_bbox(segment)
    prior_bbox = _component_mix_segment_bbox(prior_foldback_segment)
    if segment_bbox is None or prior_bbox is None:
        return False
    _, _, segment_max_y, _ = segment_bbox
    prior_min_y, _, _, _ = prior_bbox
    return float(segment_max_y) <= float(prior_min_y) - float(margin_px)


def _component_mix_segment_bbox(segment: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
    if not points:
        return None
    ys = [float(y) for y, _ in points]
    xs = [float(x) for _, x in points]
    return min(ys), min(xs), max(ys), max(xs)


def _prune_component_mix_local_subpaths_near_prior_foldback(
    segment: dict[str, Any],
    prior_foldback_segment: dict[str, Any],
    *,
    max_distance_px: float = COMPONENT_MIX_REDUNDANT_LOCAL_SUBPATH_MAX_DISTANCE_PX,
) -> tuple[dict[str, Any] | None, int]:
    render_subpaths = [
        [tuple(_as_float_point(point)) for point in subpath]
        for subpath in segment.get("render_subpaths", ())
    ]
    if len(render_subpaths) <= 1:
        return segment, 0

    prior_points = [tuple(_as_float_point(point)) for point in prior_foldback_segment.get("points", ())]
    if not prior_points:
        return segment, 0

    source_id_groups = [
        tuple(group)
        for group in segment.get("render_subpath_source_ids", ())
    ]
    if len(source_id_groups) != len(render_subpaths):
        source_ids = tuple(segment.get("source_segment_ids", ()))
        source_id_groups = [source_ids for _ in render_subpaths]

    kept_subpaths: list[list[tuple[float, float]]] = []
    kept_source_id_groups: list[tuple[Any, ...]] = []
    pruned_count = 0
    for subpath, source_ids in zip(render_subpaths, source_id_groups):
        if _min_point_cloud_distance(subpath, prior_points) <= float(max_distance_px):
            pruned_count += 1
            continue
        kept_subpaths.append(subpath)
        kept_source_id_groups.append(tuple(source_ids))

    if pruned_count == 0:
        return segment, 0
    if not kept_subpaths:
        return None, pruned_count

    copied = dict(segment)
    copied["render_subpaths"] = kept_subpaths
    copied["render_subpath_source_ids"] = kept_source_id_groups
    copied["source_segment_ids"] = tuple(
        source_id
        for source_ids in kept_source_id_groups
        for source_id in source_ids
    )
    copied["points"] = _flatten_render_subpaths(kept_subpaths)
    copied["start"] = copied["points"][0]
    copied["end"] = copied["points"][-1]
    copied["length_px"] = _polyline_length(copied["points"])
    return copied, pruned_count


def _min_point_cloud_distance(
    first: Sequence[tuple[float, float]],
    second: Sequence[tuple[float, float]],
) -> float:
    if not first or not second:
        return float("inf")
    first_arr = np.asarray(first, dtype=float)
    second_arr = np.asarray(second, dtype=float)
    distances = np.linalg.norm(first_arr[:, None, :] - second_arr[None, :, :], axis=2)
    return float(np.min(distances))


def _flatten_render_subpaths(
    render_subpaths: Sequence[Sequence[tuple[float, float]]],
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for subpath in render_subpaths:
        normalized = [tuple(_as_float_point(point)) for point in subpath]
        if not normalized:
            continue
        if points and np.allclose(points[-1], normalized[0]):
            points.extend(normalized[1:])
        else:
            points.extend(normalized)
    return points


def _as_float_point(point: Any) -> tuple[float, float]:
    y, x = point
    return float(y), float(x)


def _has_tiny_component_label_fragments(
    segments: Sequence[dict[str, Any]],
    *,
    min_segment_points: int,
) -> bool:
    if min_segment_points <= 1:
        return False
    return any(len(list(segment.get("points", ()))) < min_segment_points for segment in segments)


def _prepare_local_candidate_segments(
    segments: Sequence[dict[str, Any]],
    *,
    sample_name: str,
    foreground_mask: np.ndarray | None,
    graphics_path: Path | str,
    sample_char_map: dict[str, str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not segments:
        return [], _default_prior_meta(0)

    repaired_segments = merge_adjacent_short_fragments(
        segments,
        foreground_mask=foreground_mask,
    )
    render_subpath_map = {
        tuple(segment.get("source_segment_ids", ())): _render_subpath_meta_from_segment(segment)
        for segment in repaired_segments
    }
    canvas_shape = tuple(int(value) for value in foreground_mask.shape) if foreground_mask is not None else (128, 128)
    labelled_segments, component_label_meta = label_segments_by_makemeahanzi_components(
        repaired_segments,
        sample_name=sample_name,
        canvas_shape=canvas_shape,
        graphics_path=graphics_path,
        sample_char_map=sample_char_map,
    )
    if _has_tiny_component_label_fragments(
        labelled_segments,
        min_segment_points=LOCAL_COMPONENT_LABEL_MIN_SEGMENT_POINTS,
    ):
        labelled_segments, component_label_meta = label_segments_by_makemeahanzi_components(
            repaired_segments,
            sample_name=sample_name,
            canvas_shape=canvas_shape,
            graphics_path=graphics_path,
            sample_char_map=sample_char_map,
            split_geometry=False,
        )
    labelled_segments = _collapse_adjacent_identical_source_segments(labelled_segments)
    labelled_segments = _restore_render_subpaths_by_source_segment_ids(
        labelled_segments,
        render_subpath_map=render_subpath_map,
    )
    labelled_segments = merge_adjacent_component_labeled_short_fragments(
        labelled_segments,
        foreground_mask=foreground_mask,
    )
    labelled_segments = stitch_component_labeled_internal_gaps(
        labelled_segments,
        foreground_mask=foreground_mask,
    )
    return labelled_segments, component_label_meta


def _collapse_adjacent_identical_source_segments(
    segments: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    collapsed: list[dict[str, Any]] = []
    for segment in segments:
        copied = _copy_segment(segment)
        if not collapsed:
            collapsed.append(copied)
            continue
        previous = collapsed[-1]
        previous_source_ids = tuple(previous.get("source_segment_ids", ()))
        current_source_ids = tuple(copied.get("source_segment_ids", ()))
        if previous_source_ids != current_source_ids:
            collapsed.append(copied)
            continue

        previous_points = list(previous.get("points", ()))
        current_points = list(copied.get("points", ()))
        if not previous_points or not current_points:
            continue
        if np.linalg.norm(np.asarray(previous_points[-1], dtype=float) - np.asarray(current_points[-1], dtype=float)) < np.linalg.norm(
            np.asarray(previous_points[-1], dtype=float) - np.asarray(current_points[0], dtype=float)
        ):
            current_points = list(reversed(current_points))
        previous_component_id = previous.get("component_id")
        current_component_id = copied.get("component_id")
        if previous_component_id != current_component_id and not _should_collapse_cross_component_identical_source_segments(
            previous_points,
            current_points,
        ):
            collapsed.append(copied)
            continue
        stitched_points = previous_points + current_points[1:] if previous_points[-1] == current_points[0] else previous_points + current_points
        previous["points"] = stitched_points
        previous_render_subpaths = [
            [tuple((float(y), float(x))) for y, x in subpath]
            for subpath in previous.get("render_subpaths", ())
        ]
        current_render_subpaths = [
            [tuple((float(y), float(x))) for y, x in subpath]
            for subpath in copied.get("render_subpaths", ())
        ]
        if previous_render_subpaths or current_render_subpaths:
            previous["render_subpaths"] = previous_render_subpaths + current_render_subpaths
            previous["render_subpath_source_ids"] = list(previous.get("render_subpath_source_ids", ())) + list(
                copied.get("render_subpath_source_ids", ())
            )
        _normalized = _normalized_segment(
            previous,
            default_component_id=int(previous.get("component_id", copied.get("component_id", 1)) or 1),
        )
        collapsed[-1] = _normalized
    return collapsed


def _should_collapse_cross_component_identical_source_segments(
    previous_points: Sequence[tuple[float, float]],
    current_points: Sequence[tuple[float, float]],
) -> bool:
    if len(previous_points) < 2 or len(current_points) < 2:
        return False
    gap = _distance(tuple(previous_points[-1]), tuple(current_points[0]))
    if gap > DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_GAP_PX:
        return False
    previous_length = _polyline_length(previous_points)
    current_length = _polyline_length(current_points)
    shorter_length = min(previous_length, current_length)
    longer_length = max(previous_length, current_length)
    if shorter_length > DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_SHORT_LENGTH_PX:
        return False
    if longer_length <= 1e-6:
        return False
    return (shorter_length / longer_length) <= DEFAULT_IDENTICAL_SOURCE_CROSS_COMPONENT_COLLAPSE_MAX_SHORT_TO_LONG_RATIO


def _restore_render_subpaths_by_source_segment_ids(
    segments: Sequence[dict[str, Any]],
    *,
    render_subpath_map: dict[tuple[int, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    restored: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        copied = _normalized_segment(
            segment,
            default_component_id=int(segment.get("component_id", index + 1) or (index + 1)),
        )
        source_ids = tuple(copied.get("source_segment_ids", ()))
        render_meta = render_subpath_map.get(source_ids)
        if render_meta is None:
            render_meta = _compose_render_subpaths_for_source_ids(
                source_ids,
                render_subpath_map=render_subpath_map,
            )
        if render_meta is not None:
            if _segment_points_cover_render_meta_endpoints(copied.get("points", ()), render_meta):
                copied["render_subpaths"] = [
                    [tuple((float(y), float(x))) for y, x in subpath]
                    for subpath in render_meta.get("render_subpaths", ())
                ]
                copied["render_subpath_source_ids"] = [
                    tuple(source_ids)
                    for source_ids in render_meta.get("render_subpath_source_ids", ())
                ]
            else:
                copied["render_subpaths"] = [
                    [tuple((float(y), float(x))) for y, x in copied.get("points", ())]
                ]
                copied["render_subpath_source_ids"] = [source_ids]
        restored.append(copied)
    return restored


def _segment_points_cover_render_meta_endpoints(
    segment_points: Sequence[tuple[float, float]],
    render_meta: dict[str, Any],
    *,
    endpoint_tolerance_px: float = 6.0,
) -> bool:
    segment_points = [tuple((float(y), float(x))) for y, x in segment_points]
    if len(segment_points) < 2:
        return False
    render_subpaths = [
        [tuple((float(y), float(x))) for y, x in subpath]
        for subpath in render_meta.get("render_subpaths", ())
        if len(subpath) >= 2
    ]
    if not render_subpaths:
        return False

    render_start = render_subpaths[0][0]
    render_end = render_subpaths[-1][-1]
    segment_start = segment_points[0]
    segment_end = segment_points[-1]
    forward_match = (
        _distance(segment_start, render_start) <= endpoint_tolerance_px
        and _distance(segment_end, render_end) <= endpoint_tolerance_px
    )
    reverse_match = (
        _distance(segment_start, render_end) <= endpoint_tolerance_px
        and _distance(segment_end, render_start) <= endpoint_tolerance_px
    )
    return forward_match or reverse_match


def _render_subpath_meta_from_segment(segment: dict[str, Any]) -> dict[str, Any]:
    source_ids = tuple(segment.get("source_segment_ids", ()))
    render_subpaths = [
        [tuple((float(y), float(x))) for y, x in subpath]
        for subpath in segment.get("render_subpaths", ())
    ]
    render_subpath_source_ids = [
        tuple(source_ids_value)
        for source_ids_value in segment.get("render_subpath_source_ids", ())
    ]
    if render_subpaths:
        if len(render_subpath_source_ids) != len(render_subpaths):
            render_subpath_source_ids = [source_ids for _ in render_subpaths]
        return {
            "render_subpaths": render_subpaths,
            "render_subpath_source_ids": render_subpath_source_ids,
        }
    return {
        "render_subpaths": [
            [tuple((float(y), float(x))) for y, x in segment.get("points", ())]
        ],
        "render_subpath_source_ids": [source_ids],
    }


def _restore_render_subpaths_from_source_segments(
    segments: Sequence[dict[str, Any]],
    *,
    source_segments: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    render_subpath_map = {
        tuple(segment.get("source_segment_ids", ())): _render_subpath_meta_from_segment(segment)
        for segment in source_segments
        if tuple(segment.get("source_segment_ids", ()))
    }
    return _restore_render_subpaths_by_source_segment_ids(
        segments,
        render_subpath_map=render_subpath_map,
    )


def _compose_render_subpaths_for_source_ids(
    source_ids: Sequence[int],
    *,
    render_subpath_map: dict[tuple[int, ...], dict[str, Any]],
) -> dict[str, Any] | None:
    target_ids = tuple(int(value) for value in source_ids)
    if not target_ids:
        return None

    render_subpaths: list[list[tuple[float, float]]] = []
    render_subpath_source_ids: list[tuple[int, ...]] = []
    offset = 0
    while offset < len(target_ids):
        matched_ids: tuple[int, ...] | None = None
        matched_meta: dict[str, Any] | None = None
        for end in range(len(target_ids), offset, -1):
            candidate_ids = target_ids[offset:end]
            candidate_meta = render_subpath_map.get(candidate_ids)
            if candidate_meta is None:
                continue
            matched_ids = candidate_ids
            matched_meta = candidate_meta
            break
        if matched_ids is None or matched_meta is None:
            return None

        candidate_subpaths = [
            [tuple((float(y), float(x))) for y, x in subpath]
            for subpath in matched_meta.get("render_subpaths", ())
        ]
        candidate_source_ids = [
            tuple(int(value) for value in ids)
            for ids in matched_meta.get("render_subpath_source_ids", ())
        ]
        if len(candidate_source_ids) != len(candidate_subpaths):
            candidate_source_ids = [matched_ids for _ in candidate_subpaths]
        render_subpaths.extend(candidate_subpaths)
        render_subpath_source_ids.extend(candidate_source_ids)
        offset += len(matched_ids)

    if len(render_subpaths) <= 1:
        return None
    render_subpaths = _bridge_adjacent_render_subpaths_if_close(render_subpaths)
    return {
        "render_subpaths": render_subpaths,
        "render_subpath_source_ids": render_subpath_source_ids,
    }


def _bridge_adjacent_render_subpaths_if_close(
    render_subpaths: Sequence[Sequence[tuple[float, float]]],
    *,
    max_gap_px: float = DEFAULT_RENDER_SUBPATH_BRIDGE_GAP_PX,
) -> list[list[tuple[float, float]]]:
    bridged = [
        [tuple((float(y), float(x))) for y, x in subpath]
        for subpath in render_subpaths
    ]
    for previous, current in zip(bridged[:-1], bridged[1:]):
        if not previous or not current:
            continue
        previous_end = tuple(previous[-1])
        current_start = tuple(current[0])
        gap = float(np.linalg.norm(np.asarray(current_start, dtype=float) - np.asarray(previous_end, dtype=float)))
        if gap <= 1e-6 or gap > float(max_gap_px):
            continue
        previous.append(current_start)
    return bridged


def _should_use_component_labeled_local_candidate_for_auto(
    local_raw_compare_summary: dict[str, Any],
    local_component_label_summary: dict[str, Any],
    prior_summary: dict[str, Any],
) -> bool:
    raw_local_internal_max = float(local_raw_compare_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    raw_local_avoidable = local_raw_compare_summary.get("avoidable_internal_max_jump_px")
    raw_local_avoidable = float(raw_local_avoidable) if raw_local_avoidable is not None else 0.0
    labelled_internal_max = float(local_component_label_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    labelled_avoidable = local_component_label_summary.get("avoidable_internal_max_jump_px")
    labelled_avoidable = float(labelled_avoidable) if labelled_avoidable is not None else 0.0
    local_similarity = local_component_label_summary.get("rendered_similarity_to_input")
    prior_similarity = prior_summary.get("rendered_similarity_to_input")

    if (
        raw_local_internal_max <= AUTO_LOCAL_INTERNAL_JUMP_OK_PX
        and raw_local_avoidable <= AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_OK_PX
    ):
        return False
    if (
        labelled_internal_max > AUTO_LOCAL_INTERNAL_JUMP_OK_PX
        or labelled_avoidable > AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_OK_PX
    ):
        return False
    if local_similarity is None or prior_similarity is None:
        return False
    return float(local_similarity) >= float(prior_similarity) + AUTO_COMPONENT_LABEL_LOCAL_VISUAL_ADVANTAGE_MIN


def _choose_postprocess_candidate(
    local_summary: dict[str, Any],
    prior_summary: dict[str, Any],
    *,
    raw_summary: dict[str, Any] | None = None,
    raw_compare_local_summary: dict[str, Any] | None = None,
    light_repair_summary: dict[str, Any] | None = None,
    component_mix_summary: dict[str, Any] | None = None,
    component_mix_meta: dict[str, Any] | None = None,
    structure_primitive_summary: dict[str, Any] | None = None,
    structure_primitive_meta: dict[str, Any] | None = None,
) -> tuple[str, str]:
    baseline_mode, baseline_reason = _choose_processed_postprocess_candidate(local_summary, prior_summary)
    if structure_primitive_summary is not None and _should_promote_structure_primitive_candidate(
        structure_primitive_summary,
        structure_primitive_meta=structure_primitive_meta,
        comparison_summaries=(
            local_summary,
            prior_summary,
            raw_summary,
            light_repair_summary,
            component_mix_summary,
        ),
    ):
        return "structure_primitive", "three_stroke_structure_within_visual_tolerance"
    if baseline_reason == "prior_exact_simple_match_is_visually_cleaner":
        return baseline_mode, baseline_reason
    if light_repair_summary is not None and _should_keep_light_repair_against_local_candidate(
        local_summary,
        light_repair_summary,
    ):
        return "raw_light_repair", "light_repair_is_visually_cleaner_than_local"
    if (
        baseline_mode == "local"
        and raw_summary is not None
        and _should_keep_simple_exact_local_candidate(raw_summary, local_summary, prior_summary)
    ):
        return "local", "simple_exact_local_is_visually_cleaner_than_raw"
    if component_mix_summary is not None and _should_promote_component_mix_candidate(
        local_summary,
        prior_summary,
        component_mix_summary,
        component_mix_meta=component_mix_meta,
    ):
        return "component_mix", "component_mix_improves_long_foldback_without_extra_jump"

    processed_compare_summary = (
        prior_summary
        if baseline_mode == "makemeahanzi_regroup"
        else (raw_compare_local_summary if raw_compare_local_summary is not None and baseline_mode == "local_raw_compare" else local_summary)
    )
    if raw_summary is not None and _should_keep_raw_candidate(raw_summary, processed_compare_summary):
        if light_repair_summary is not None and _should_promote_raw_to_light_repair_candidate(
            raw_summary,
            light_repair_summary,
        ):
            return "raw_light_repair", "light_repair_improves_raw_without_local_distortion"
        return "raw", "raw_preserves_geometry_better_than_local"
    return baseline_mode, baseline_reason


def _should_promote_structure_primitive_candidate(
    structure_summary: dict[str, Any],
    *,
    structure_primitive_meta: dict[str, Any] | None,
    comparison_summaries: Sequence[dict[str, Any] | None],
    max_visual_drop: float = AUTO_STRUCTURE_PRIMITIVE_MAX_VISUAL_DROP,
) -> bool:
    if structure_primitive_meta is None:
        return False
    if not bool(structure_primitive_meta.get("structure_prior_applied", False)):
        return False
    if not bool(structure_primitive_meta.get("primitive_transfer_applied", False)):
        return False
    if structure_primitive_meta.get("kou_skeleton_regularization_applied") is not True:
        return False
    target_count = int(structure_primitive_meta.get("structure_target_stroke_count", 0) or 0)
    candidate_count = int(structure_summary.get("consolidated_segment_count", 0) or 0)
    if target_count <= 0 or candidate_count != target_count:
        return False
    candidate_similarity = structure_summary.get("rendered_similarity_to_input")
    if candidate_similarity is None:
        return False
    comparison_scores = [
        float(summary["rendered_similarity_to_input"])
        for summary in comparison_summaries
        if summary is not None and summary.get("rendered_similarity_to_input") is not None
    ]
    if not comparison_scores:
        return True
    return float(candidate_similarity) >= max(comparison_scores) - float(max_visual_drop)


def _should_promote_component_mix_candidate(
    local_summary: dict[str, Any],
    prior_summary: dict[str, Any],
    component_mix_summary: dict[str, Any],
    *,
    component_mix_meta: dict[str, Any] | None = None,
) -> bool:
    if component_mix_meta is None or not bool(component_mix_meta.get("component_mix_applied", False)):
        return False

    component_similarity = component_mix_summary.get("rendered_similarity_to_input")
    local_similarity = local_summary.get("rendered_similarity_to_input")
    if component_similarity is None or local_similarity is None:
        return False
    comparison_scores = [float(local_similarity)]
    prior_similarity = prior_summary.get("rendered_similarity_to_input")
    if prior_similarity is not None:
        comparison_scores.append(float(prior_similarity))
    if float(component_similarity) < max(comparison_scores) + AUTO_COMPONENT_MIX_VISUAL_GAIN_MIN:
        return False

    component_internal = _float_metric(component_mix_summary, "internal_max_pen_up_jump_px", default=float("inf"))
    local_internal = _float_metric(local_summary, "internal_max_pen_up_jump_px", default=0.0)
    if component_internal > local_internal + AUTO_COMPONENT_MIX_MAX_INTERNAL_INCREASE_PX:
        return False

    component_avoidable = component_mix_summary.get("avoidable_internal_max_jump_px")
    component_avoidable = float(component_avoidable) if component_avoidable is not None else 0.0
    local_avoidable = local_summary.get("avoidable_internal_max_jump_px")
    local_avoidable = float(local_avoidable) if local_avoidable is not None else 0.0
    return component_avoidable <= local_avoidable + AUTO_COMPONENT_MIX_MAX_INTERNAL_INCREASE_PX


def _choose_processed_postprocess_candidate(
    local_summary: dict[str, Any],
    prior_summary: dict[str, Any],
) -> tuple[str, str]:
    if not bool(prior_summary.get("makemeahanzi_prior_available", False)):
        return "local", "prior_unavailable"

    target_stroke_count = int(prior_summary.get("makemeahanzi_target_stroke_count", 0) or 0)
    if target_stroke_count <= 0:
        return "local", "missing_target_stroke_count"

    local_count = int(local_summary.get("consolidated_segment_count", 0) or 0)
    prior_count = int(prior_summary.get("consolidated_segment_count", 0) or 0)
    local_gap = abs(local_count - target_stroke_count)
    prior_gap = abs(prior_count - target_stroke_count)
    local_internal_max = float(local_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    local_avoidable_internal = local_summary.get("avoidable_internal_max_jump_px")
    local_avoidable_internal = float(local_avoidable_internal) if local_avoidable_internal is not None else 0.0
    local_min_turn_cos = _float_metric(local_summary, "min_turn_cos", default=1.0)
    prior_min_turn_cos = _float_metric(prior_summary, "min_turn_cos", default=1.0)
    local_similarity = local_summary.get("rendered_similarity_to_input")
    prior_similarity = prior_summary.get("rendered_similarity_to_input")

    if (
        target_stroke_count == 1
        and local_count == 1
        and prior_count == 1
        and local_similarity is not None
        and prior_similarity is not None
        and (float(prior_similarity) - float(local_similarity)) >= AUTO_SIMPLE_EXACT_PRIOR_VISUAL_ADVANTAGE_MIN
        and (prior_min_turn_cos - local_min_turn_cos) >= AUTO_SIMPLE_EXACT_PRIOR_TURN_ADVANTAGE_COS
    ):
        return "makemeahanzi_regroup", "prior_exact_simple_match_is_visually_cleaner"

    if (
        local_internal_max <= AUTO_LOCAL_INTERNAL_JUMP_OK_PX
        and local_avoidable_internal <= AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_OK_PX
    ):
        return "local", "local_already_continuous"

    if (
        prior_min_turn_cos <= AUTO_PRIOR_SEVERE_FOLDBACK_COS
        and (local_min_turn_cos - prior_min_turn_cos) >= AUTO_PRIOR_LOCAL_TURN_ADVANTAGE_COS
    ):
        return "local", "prior_introduces_severe_internal_foldback"

    if (
        prior_gap < local_gap
        and (
            local_internal_max > AUTO_LOCAL_INTERNAL_JUMP_RISKY_PX
            or local_avoidable_internal > AUTO_LOCAL_AVOIDABLE_INTERNAL_JUMP_RISKY_PX
        )
    ):
        return "makemeahanzi_regroup", "prior_reduces_oversegmentation_on_discontinuous_local"

    return "local", "local_kept_as_fallback"


def _should_keep_raw_candidate(
    raw_summary: dict[str, Any],
    local_summary: dict[str, Any],
) -> bool:
    raw_similarity = raw_summary.get("rendered_similarity_to_input")
    local_similarity = local_summary.get("rendered_similarity_to_input")
    if raw_similarity is None or local_similarity is None:
        return False

    raw_min_turn_cos = _float_metric(raw_summary, "min_turn_cos", default=1.0)
    local_min_turn_cos = _float_metric(local_summary, "min_turn_cos", default=1.0)
    raw_internal_max = float(raw_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    local_internal_max = float(local_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    return (
        (raw_min_turn_cos - local_min_turn_cos) >= AUTO_RAW_MIN_TURN_ADVANTAGE_COS
        and raw_internal_max <= local_internal_max
        and float(raw_similarity) >= float(local_similarity) - AUTO_RAW_VISUAL_SIMILARITY_MAX_LOCAL_DROP
    )


def _should_promote_raw_to_light_repair_candidate(
    raw_summary: dict[str, Any],
    light_repair_summary: dict[str, Any],
) -> bool:
    raw_similarity = raw_summary.get("rendered_similarity_to_input")
    light_similarity = light_repair_summary.get("rendered_similarity_to_input")
    if raw_similarity is None or light_similarity is None:
        return False

    raw_internal_max = float(raw_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    light_internal_max = float(light_repair_summary.get("internal_max_pen_up_jump_px", 0.0) or 0.0)
    raw_min_turn_cos = _float_metric(raw_summary, "min_turn_cos", default=1.0)
    light_min_turn_cos = _float_metric(light_repair_summary, "min_turn_cos", default=1.0)
    raw_count = int(raw_summary.get("consolidated_segment_count", 0) or 0)
    light_count = int(light_repair_summary.get("consolidated_segment_count", 0) or 0)
    continuity_case = (
        raw_internal_max >= AUTO_LIGHT_REPAIR_RAW_INTERNAL_MIN_PX
        and (float(light_similarity) - float(raw_similarity)) >= AUTO_LIGHT_REPAIR_VISUAL_GAIN_MIN
        and light_min_turn_cos >= AUTO_LIGHT_REPAIR_MIN_TURN_COS
        and (raw_min_turn_cos - light_min_turn_cos) <= AUTO_LIGHT_REPAIR_MAX_RAW_TURN_DROP
        and light_internal_max <= raw_internal_max + AUTO_LIGHT_REPAIR_MAX_INTERNAL_INCREASE_PX
        and 0 <= (raw_count - light_count) <= AUTO_LIGHT_REPAIR_MAX_COUNT_DROP
    )
    structured_corner_cleanup_case = (
        AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MIN_TURN_COS
        <= raw_min_turn_cos
        <= AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MAX_TURN_COS
        and AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MIN_TURN_COS
        <= light_min_turn_cos
        <= AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MAX_TURN_COS
        and (float(light_similarity) - float(raw_similarity)) >= AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_VISUAL_GAIN_MIN
        and light_internal_max <= raw_internal_max + AUTO_LIGHT_REPAIR_STRUCTURED_CORNER_MAX_INTERNAL_INCREASE_PX
        and 0 <= (raw_count - light_count) <= AUTO_LIGHT_REPAIR_MAX_COUNT_DROP
    )
    fragment_cleanup_case = (
        (float(light_similarity) - float(raw_similarity)) >= AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_VISUAL_GAIN_MIN
        and light_min_turn_cos >= AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MIN_TURN_COS
        and (raw_min_turn_cos - light_min_turn_cos) <= AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MAX_RAW_TURN_DROP
        and light_internal_max <= raw_internal_max + AUTO_LIGHT_REPAIR_FRAGMENT_CLEANUP_MAX_INTERNAL_INCREASE_PX
        and 0 <= (raw_count - light_count) <= AUTO_LIGHT_REPAIR_MAX_COUNT_DROP
    )
    return continuity_case or structured_corner_cleanup_case or fragment_cleanup_case


def _should_keep_light_repair_against_local_candidate(
    local_summary: dict[str, Any],
    light_repair_summary: dict[str, Any],
) -> bool:
    local_similarity = local_summary.get("rendered_similarity_to_input")
    light_similarity = light_repair_summary.get("rendered_similarity_to_input")
    if local_similarity is None or light_similarity is None:
        return False
    return float(light_similarity) >= float(local_similarity) + AUTO_LIGHT_REPAIR_LOCAL_VISUAL_ADVANTAGE_MIN


def _should_keep_simple_exact_local_candidate(
    raw_summary: dict[str, Any],
    local_summary: dict[str, Any],
    prior_summary: dict[str, Any],
) -> bool:
    if not bool(prior_summary.get("makemeahanzi_prior_available", False)):
        return False
    target_stroke_count = int(prior_summary.get("makemeahanzi_target_stroke_count", 0) or 0)
    local_count = int(local_summary.get("consolidated_segment_count", 0) or 0)
    raw_count = int(raw_summary.get("consolidated_segment_count", 0) or 0)
    if target_stroke_count != 1 or local_count != 1 or raw_count <= local_count:
        return False
    raw_similarity = raw_summary.get("rendered_similarity_to_input")
    local_similarity = local_summary.get("rendered_similarity_to_input")
    if raw_similarity is None or local_similarity is None:
        return False
    return float(local_similarity) > float(raw_similarity)


def _float_metric(summary: dict[str, Any], key: str, *, default: float) -> float:
    value = summary.get(key)
    if value is None:
        return float(default)
    return float(value)


def _execution_visual_similarity(
    ordered_segments: Sequence[dict[str, Any]],
    *,
    canvas_shape: tuple[int, int],
    foreground_mask: np.ndarray | None,
) -> float | None:
    if foreground_mask is None or not ordered_segments:
        return None
    target_mask = np.asarray(foreground_mask, dtype=bool)
    if target_mask.size == 0 or not np.any(target_mask):
        return None

    blank_skeleton = np.zeros(canvas_shape, dtype=bool)
    rendered = render_execution_image(
        blank_skeleton,
        ordered_segments,
        scale=1,
        foreground_mask=target_mask,
        edge_soften_radius_px=0.0,
    )
    rendered_mask = np.asarray(rendered.convert("L"), dtype=np.uint8) < DEFAULT_FOREGROUND_THRESHOLD
    intersection = int(np.logical_and(rendered_mask, target_mask).sum())
    union = int(np.logical_or(rendered_mask, target_mask).sum())
    if union <= 0:
        return None
    return float(intersection / union)


def _min_turn_cos(consolidated: Sequence[dict[str, Any]]) -> float:
    min_cos = 1.0
    for segment in consolidated:
        points = np.asarray(segment.get("points", ()), dtype=float)
        if len(points) < 3:
            continue
        vectors = np.diff(points, axis=0)
        lengths = np.linalg.norm(vectors, axis=1)
        if len(vectors) < 2:
            continue
        tangents = vectors / np.maximum(lengths[:, None], 1e-9)
        cosines = np.sum(tangents[:-1] * tangents[1:], axis=1)
        if len(cosines):
            min_cos = min(min_cos, float(np.min(cosines)))
    return float(min_cos)


def _collect_batch_summary_rows(batch_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sample_dir in sorted((path for path in Path(batch_dir).iterdir() if path.is_dir()), key=lambda path: path.name):
        summary_path = sample_dir / "recovery_summary.json"
        if not summary_path.exists():
            rows.append(
                {
                    "sample": sample_dir.name,
                    "audit_status": "failed",
                    "selected_postprocess_mode": "",
                    "review_recommended_mode": "",
                }
            )
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "sample": str(summary.get("sample", sample_dir.name)),
                "audit_status": str(summary.get("audit_status", "")),
                "selected_postprocess_mode": str(summary.get("selected_postprocess_mode", "")),
                "review_recommended_mode": str(summary.get("review_recommended_mode", "")),
            }
        )
    return rows


def _write_hybrid_batch_report(
    path: Path,
    rows: Sequence[dict[str, Any]],
    *,
    manual_audit_sheet_path: Path,
    contact_sheet_path: Path,
) -> None:
    rows = list(rows)
    lines = [
        "# CalliRewrite Hybrid Batch Report",
        "",
        "## Samples processed",
        "",
        f"Total samples processed: {len(rows)}",
        "",
        "## Continuity Summary",
        "",
        "| sample | status | audit_status | ordered segments | consolidated segments | merged | max pen-up jump px |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {sample} | {status} | {audit_status} | {ordered} | {consolidated} | {merged} | {jump} |".format(
                sample=_md_cell(row.get("sample", "")),
                status=_md_cell(row.get("status", "")),
                audit_status=_md_cell(row.get("audit_status", "")),
                ordered=_report_value(row.get("ordered_segment_count", "n/a")),
                consolidated=_report_value(row.get("consolidated_segment_count", "n/a")),
                merged=_report_value(row.get("merged_segment_count", "n/a")),
                jump=_format_number_or_na(row.get("max_pen_up_jump_px", "n/a")),
            )
        )
    lines.extend(
        [
            "",
            "## Output File Locations",
            "",
            "| sample | sample directory | summary | trajectory | source image | final image |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| {sample} | {sample_dir} | {summary} | {trajectory} | {source_image} | {final_image} |".format(
                sample=_md_cell(row.get("sample", "")),
                sample_dir=_md_cell(row.get("sample_dir", "n/a")),
                summary=_md_cell(row.get("summary_path", "n/a")),
                trajectory=_md_cell(row.get("trajectory_path", "n/a")),
                source_image=_md_cell(row.get("source_trajectory_image", "n/a")),
                final_image=_md_cell(row.get("final_trajectory_image", "n/a")),
            )
        )
    lines.extend(
        [
            "",
            "## Manual Audit",
            "",
            f"- Manual audit sheet: `{manual_audit_sheet_path}`",
            f"- Visual audit contact sheet: `{contact_sheet_path}`",
            "",
            "Manual visual inspection is required before making any quality claim.",
            "",
            "Boundary note: external CalliRewrite coarse sequence plus local postprocess for offline comparison only; not robot output.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_visual_crop_bbox(
    segments: Sequence[dict[str, Any]],
    input_image_path: Path | None,
    *,
    margin_px: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int], tuple[int, int, int, int], tuple[int, int, int, int] | None]:
    if input_image_path is not None and input_image_path.exists():
        with Image.open(input_image_path) as image:
            image_height = int(image.height)
            image_width = int(image.width)
    else:
        image_height = None
        image_width = None

    points = [
        (float(y), float(x))
        for segment in segments
        for y, x in segment.get("points", ())
    ]
    if not points:
        if image_height is not None and image_width is not None:
            bbox = (0, 0, image_height, image_width)
            return bbox, (image_height, image_width), bbox, bbox
        bbox = (0, 0, 1, 1)
        return bbox, (1, 1), bbox, None

    min_y = math.floor(min(y for y, _ in points)) - int(margin_px)
    min_x = math.floor(min(x for _, x in points)) - int(margin_px)
    max_y = math.ceil(max(y for y, _ in points)) + int(margin_px) + 1
    max_x = math.ceil(max(x for _, x in points)) + int(margin_px) + 1

    if image_height is not None and image_width is not None:
        min_y = max(0, min_y)
        min_x = max(0, min_x)
        max_y = min(image_height, max_y)
        max_x = min(image_width, max_x)
    else:
        min_y = max(0, min_y)
        min_x = max(0, min_x)

    if max_y <= min_y:
        max_y = min_y + 1
    if max_x <= min_x:
        max_x = min_x + 1
    trajectory_bbox = (min_y, min_x, max_y, max_x)

    input_foreground_bbox = _foreground_bbox_for_image(input_image_path, pad=margin_px) if input_image_path is not None else None
    visual_bbox = _union_bbox(trajectory_bbox, input_foreground_bbox, image_height=image_height, image_width=image_width)
    return visual_bbox, (visual_bbox[2] - visual_bbox[0], visual_bbox[3] - visual_bbox[1]), trajectory_bbox, input_foreground_bbox


def _translate_segments(
    segments: Sequence[dict[str, Any]],
    crop_bbox: tuple[int, int, int, int],
) -> list[dict[str, Any]]:
    top, left, _, _ = crop_bbox
    translated: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        shifted_points = [
            (float(y) - float(top), float(x) - float(left))
            for y, x in segment.get("points", ())
        ]
        shifted_render_subpaths = [
            [
                (float(y) - float(top), float(x) - float(left))
                for y, x in subpath
            ]
            for subpath in segment.get("render_subpaths", ())
        ]
        translated.append(
            _normalized_segment(
                {
                    **segment,
                    "points": shifted_points,
                    "render_subpaths": shifted_render_subpaths,
                },
                default_component_id=int(segment.get("component_id", index + 1)),
            )
        )
    return translated


def _crop_input_image(
    input_image_path: Path,
    crop_bbox: tuple[int, int, int, int],
) -> Image.Image:
    top, left, bottom, right = crop_bbox
    with Image.open(input_image_path) as image:
        return image.crop((left, top, right, bottom)).convert("L")


def _crop_mask(
    mask: np.ndarray,
    crop_bbox: tuple[int, int, int, int],
) -> np.ndarray:
    top, left, bottom, right = crop_bbox
    return np.asarray(mask[top:bottom, left:right], dtype=bool)


def _foreground_bbox_for_image(
    input_image_path: Path | None,
    *,
    pad: int,
    threshold: int = DEFAULT_FOREGROUND_THRESHOLD,
) -> tuple[int, int, int, int] | None:
    if input_image_path is None or not Path(input_image_path).exists():
        return None
    with Image.open(input_image_path) as image:
        arr = np.asarray(image.convert("L"))
    mask = ensure_foreground_is_true(arr, threshold=threshold)
    if not bool(mask.any()):
        return None
    ys, xs = np.nonzero(mask)
    y0 = max(int(ys.min()) - int(pad), 0)
    x0 = max(int(xs.min()) - int(pad), 0)
    y1 = min(int(ys.max()) + int(pad) + 1, mask.shape[0])
    x1 = min(int(xs.max()) + int(pad) + 1, mask.shape[1])
    return (y0, x0, y1, x1)


def _load_input_foreground_mask(
    input_image_path: Path,
    *,
    threshold: int = DEFAULT_FOREGROUND_THRESHOLD,
) -> np.ndarray | None:
    if not Path(input_image_path).exists():
        return None
    with Image.open(input_image_path) as image:
        arr = np.asarray(image.convert("L"))
    mask = ensure_foreground_is_true(arr, threshold=threshold)
    return mask if bool(mask.any()) else None


def _union_bbox(
    trajectory_bbox: tuple[int, int, int, int],
    input_foreground_bbox: tuple[int, int, int, int] | None,
    *,
    image_height: int | None,
    image_width: int | None,
) -> tuple[int, int, int, int]:
    if input_foreground_bbox is None:
        return trajectory_bbox
    y0 = min(int(trajectory_bbox[0]), int(input_foreground_bbox[0]))
    x0 = min(int(trajectory_bbox[1]), int(input_foreground_bbox[1]))
    y1 = max(int(trajectory_bbox[2]), int(input_foreground_bbox[2]))
    x1 = max(int(trajectory_bbox[3]), int(input_foreground_bbox[3]))
    if image_height is not None:
        y0 = max(0, y0)
        y1 = min(image_height, y1)
    if image_width is not None:
        x0 = max(0, x0)
        x1 = min(image_width, x1)
    if y1 <= y0:
        y1 = y0 + 1
    if x1 <= x0:
        x1 = x0 + 1
    return (y0, x0, y1, x1)


def _write_overlay_png(
    output_path: Path,
    cropped_input_image: Image.Image | None,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = DEFAULT_OVERLAY_SCALE,
    color_by_component: bool = False,
) -> None:
    canvas = _overlay_base(cropped_input_image, ordered_segments, scale=scale)
    draw = ImageDraw.Draw(canvas)
    for index, segment in enumerate(ordered_segments):
        color = _segment_color(segment, index=index, color_by_component=color_by_component)
        _draw_overlay_polyline(draw, segment.get("points", ()), scale, color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _write_pen_up_debug_png(
    output_path: Path,
    canvas_shape: tuple[int, int],
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = DEFAULT_OVERLAY_SCALE,
    color_by_component: bool = False,
) -> None:
    height, width = canvas_shape
    canvas = Image.new("RGB", (max(width * scale, 1), max(height * scale, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    previous_end = None
    for index, segment in enumerate(ordered_segments):
        points = list(segment.get("points", ()))
        color = _segment_color(segment, index=index, color_by_component=color_by_component)
        if previous_end is not None and points:
            _draw_dashed_line(draw, _scaled_xy(previous_end, scale), _scaled_xy(points[0], scale), (150, 150, 150), scale)
        if points:
            _draw_endpoint_marker(draw, points[0], scale, color)
            _draw_endpoint_marker(draw, points[-1], scale, color)
            previous_end = points[-1]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _segment_color(
    segment: dict[str, Any],
    *,
    index: int,
    color_by_component: bool,
) -> tuple[int, int, int]:
    if color_by_component:
        component_id = int(segment.get("component_id", 0) or 0)
        if component_id > 0:
            return PALETTE[(component_id - 1) % len(PALETTE)]
    return PALETTE[index % len(PALETTE)]


def _overlay_base(
    cropped_input_image: Image.Image | None,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int,
) -> Image.Image:
    if cropped_input_image is not None:
        width = max(cropped_input_image.width * scale, 1)
        height = max(cropped_input_image.height * scale, 1)
        return cropped_input_image.convert("RGB").resize((width, height), resample=Image.Resampling.NEAREST)

    max_y = 1
    max_x = 1
    for segment in ordered_segments:
        for y, x in segment.get("points", ()):
            max_y = max(max_y, int(math.ceil(float(y))) + 1)
            max_x = max(max_x, int(math.ceil(float(x))) + 1)
    return Image.new("RGB", (max_x * scale, max_y * scale), (255, 255, 255))


def _draw_overlay_polyline(
    draw: ImageDraw.ImageDraw,
    points: Sequence[Any],
    scale: int,
    color: tuple[int, int, int],
) -> None:
    scaled_points = [_scaled_xy(point, scale) for point in points]
    if len(scaled_points) == 1:
        x, y = scaled_points[0]
        radius = max(scale // 2, 2)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        return
    if len(scaled_points) <= 1:
        return
    outline_width = max(scale, 3)
    line_width = max(scale - 1, 2)
    draw.line(scaled_points, fill=(255, 255, 255), width=outline_width, joint="curve")
    draw.line(scaled_points, fill=color, width=line_width, joint="curve")


def _draw_endpoint_marker(
    draw: ImageDraw.ImageDraw,
    point: Any,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    x, y = _scaled_xy(point, scale)
    radius = max(scale // 3, 2)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(255, 255, 255))


def _scaled_xy(point: Any, scale: int) -> tuple[int, int]:
    y, x = point
    return (int(round(float(x) * scale + scale / 2.0)), int(round(float(y) * scale + scale / 2.0)))


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
    scale: int,
    *,
    dash_px: int = 10,
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    distance = float((dx * dx + dy * dy) ** 0.5)
    if distance <= 0:
        return
    steps = max(int(distance // dash_px), 1)
    for step in range(0, steps, 2):
        a = step / steps
        b = min((step + 1) / steps, 1.0)
        draw.line(
            (
                int(round(x0 + dx * a)),
                int(round(y0 + dy * a)),
                int(round(x0 + dx * b)),
                int(round(y0 + dy * b)),
            ),
            fill=color,
            width=max(scale // 3, 1),
        )


def _load_segments_from_trial_csv(trajectory_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current_points: list[tuple[float, float]] = []
    current_source_ids: tuple[int, ...] = ()
    with Path(trajectory_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("is_break") == "true":
                if current_points:
                    segments.append(
                        _normalized_segment(
                            {
                                "segment_id": len(segments) + 1,
                                "source_segment_ids": current_source_ids or (len(segments) + 1,),
                                "points": current_points,
                                "component_id": 1,
                            },
                            default_component_id=1,
                        )
                    )
                current_points = []
                current_source_ids = ()
                continue
            if not row.get("y") or not row.get("x"):
                continue
            current_points.append((float(row["y"]), float(row["x"])))
            current_source_ids = _parse_source_ids(row.get("source", ""))
    if current_points:
        segments.append(
            _normalized_segment(
                {
                    "segment_id": len(segments) + 1,
                    "source_segment_ids": current_source_ids or (len(segments) + 1,),
                    "points": current_points,
                    "component_id": 1,
                },
                default_component_id=1,
            )
        )
    return segments, {
        "load_backend": "trial_csv",
        "external_source": "callirewrite_trial_csv",
        "coordinate_frame": "callirewrite_image_pixels",
        "source_path": str(trajectory_path),
    }


def _normalized_segment(segment: dict[str, Any], *, default_component_id: int) -> dict[str, Any]:
    points = [tuple((float(y), float(x))) for y, x in segment.get("points", ())]
    source_segment_ids = tuple(int(value) for value in segment.get("source_segment_ids", ()) if value is not None)
    normalized = {
        "segment_id": int(segment.get("segment_id", default_component_id)),
        "source_segment_ids": source_segment_ids or (int(segment.get("segment_id", default_component_id)),),
        "points": points,
        "pixel_count": len(points),
        "length_px": _polyline_length(points),
        "start": points[0] if points else (0.0, 0.0),
        "end": points[-1] if points else (0.0, 0.0),
        "component_id": int(segment.get("component_id", default_component_id)),
        "is_loop": bool(segment.get("is_loop", False)),
        "order_index": int(segment.get("order_index", default_component_id)),
        "stroke_like_id": int(segment.get("stroke_like_id", default_component_id)),
    }
    if segment.get("render_subpaths"):
        normalized["render_subpaths"] = [
            [tuple((float(y), float(x))) for y, x in subpath]
            for subpath in segment.get("render_subpaths", ())
        ]
    if segment.get("render_subpath_source_ids"):
        normalized["render_subpath_source_ids"] = [
            tuple(int(value) for value in source_ids if value is not None)
            for source_ids in segment.get("render_subpath_source_ids", ())
        ]
    if segment.get("primitive_kind"):
        normalized["primitive_kind"] = str(segment.get("primitive_kind"))
    if segment.get("primitive_relative_widths"):
        normalized["primitive_relative_widths"] = tuple(
            float(value) for value in segment.get("primitive_relative_widths", ())
        )
    if "primitive_width_blend" in segment:
        normalized["primitive_width_blend"] = float(segment.get("primitive_width_blend", 0.7))
    for key in ("primitive_start_role", "primitive_end_role", "primitive_source_sample"):
        if key in segment:
            normalized[key] = str(segment.get(key, ""))
    for key in ("pointed_start", "pointed_end", "structure_prior_applied"):
        if key in segment:
            normalized[key] = bool(segment.get(key, False))
    return normalized


def _hybrid_audit_status(summary: dict[str, Any]) -> str:
    if (
        summary.get("status") == "failed"
        or int(summary.get("ordered_segment_count", 0)) == 0
        or int(summary.get("consolidated_segment_count", 0)) == 0
        or int(summary.get("trajectory_point_count", 0)) == 0
    ):
        return "failed"

    internal_jump_count = int(summary.get("internal_pen_up_jump_count", summary.get("pen_up_jump_count", 0)))
    internal_max_jump = float(summary.get("internal_max_pen_up_jump_px", summary.get("max_pen_up_jump_px", 0.0)))
    internal_mean_jump = float(summary.get("internal_mean_pen_up_jump_px", summary.get("mean_pen_up_jump_px", 0.0)))
    avoidable_cross_component_max_jump = summary.get("avoidable_cross_component_max_jump_px")
    avoidable_cross_component_risky = (
        summary.get("makemeahanzi_prior_applied") is not True
        and summary.get("makemeahanzi_component_labels_applied") is not True
        and summary.get("selected_postprocess_mode") != "makemeahanzi_regroup"
        and summary.get("cross_component_best_is_exact") is True
        and avoidable_cross_component_max_jump is not None
        and float(avoidable_cross_component_max_jump) > HYBRID_MAX_AVOIDABLE_CROSS_COMPONENT_JUMP_PX
    )
    if (
        internal_max_jump > HYBRID_MAX_INTERNAL_JUMP_PX
        or (internal_jump_count > 1 and internal_mean_jump > HYBRID_MAX_INTERNAL_MEAN_JUMP_PX)
        or avoidable_cross_component_risky
    ):
        return "risky_needs_manual_check"
    return "promising"


def _pen_up_jump_metrics(ordered_segments: list[dict[str, Any]]) -> dict[str, float | int]:
    jumps: list[float] = []
    previous_end = None
    for segment in ordered_segments:
        points = list(segment.get("points", ()))
        if previous_end is not None and points:
            jumps.append(_distance(previous_end, points[0]))
        if points:
            previous_end = points[-1]
    if not jumps:
        return {
            "pen_up_jump_count": 0,
            "max_pen_up_jump_px": 0.0,
            "mean_pen_up_jump_px": 0.0,
        }
    return {
        "pen_up_jump_count": len(jumps),
        "max_pen_up_jump_px": max(jumps),
        "mean_pen_up_jump_px": sum(jumps) / len(jumps),
    }


def _pen_up_jump_breakdown(ordered_segments: list[dict[str, Any]]) -> dict[str, float | int | bool | None]:
    cross_component_jumps: list[float] = []
    internal_jumps: list[float] = []
    component_groups = _component_groups(ordered_segments)

    previous_end = None
    previous_component_id = None
    for segment in ordered_segments:
        points = list(segment.get("points", ()))
        component_id = segment.get("component_id")
        if previous_end is not None and points:
            jump = _distance(previous_end, points[0])
            if component_id == previous_component_id:
                internal_jumps.append(jump)
            else:
                cross_component_jumps.append(jump)
        if points:
            previous_end = points[-1]
            previous_component_id = component_id

    metrics: dict[str, float | int | bool | None] = {}
    metrics.update(_jump_metrics_for_prefix("cross_component", cross_component_jumps))
    metrics.update(_jump_metrics_for_prefix("internal", internal_jumps))

    cross_best_jumps, cross_best_is_exact = _best_cross_component_jumps(component_groups)
    metrics["cross_component_best_is_exact"] = cross_best_is_exact
    metrics.update(_best_jump_metrics_for_prefix("cross_component", cross_component_jumps, cross_best_jumps, cross_best_is_exact))

    internal_best_jumps, internal_best_is_exact = _best_internal_jumps(component_groups)
    metrics["internal_best_is_exact"] = internal_best_is_exact
    metrics.update(_best_jump_metrics_for_prefix("internal", internal_jumps, internal_best_jumps, internal_best_is_exact))
    return metrics


def _component_groups(ordered_segments: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for segment in ordered_segments:
        component_id = segment.get("component_id")
        copied = _copy_segment(segment)
        if groups and groups[-1][0].get("component_id") == component_id:
            groups[-1].append(copied)
        else:
            groups.append([copied])
    return groups


def _jump_metrics_for_prefix(prefix: str, jumps: list[float]) -> dict[str, float | int]:
    if not jumps:
        return {
            f"{prefix}_pen_up_jump_count": 0,
            f"{prefix}_max_pen_up_jump_px": 0.0,
            f"{prefix}_mean_pen_up_jump_px": 0.0,
        }
    return {
        f"{prefix}_pen_up_jump_count": len(jumps),
        f"{prefix}_max_pen_up_jump_px": max(jumps),
        f"{prefix}_mean_pen_up_jump_px": sum(jumps) / len(jumps),
    }


def _best_jump_metrics_for_prefix(
    prefix: str,
    actual_jumps: list[float],
    best_jumps: list[float] | None,
    best_is_exact: bool,
) -> dict[str, float | None]:
    if not best_is_exact or best_jumps is None:
        return {
            f"{prefix}_best_max_pen_up_jump_px": None,
            f"{prefix}_best_mean_pen_up_jump_px": None,
            f"avoidable_{prefix}_max_jump_px": None,
            f"avoidable_{prefix}_mean_jump_px": None,
        }

    actual_max = max(actual_jumps) if actual_jumps else 0.0
    actual_mean = (sum(actual_jumps) / len(actual_jumps)) if actual_jumps else 0.0
    best_max = max(best_jumps) if best_jumps else 0.0
    best_mean = (sum(best_jumps) / len(best_jumps)) if best_jumps else 0.0
    return {
        f"{prefix}_best_max_pen_up_jump_px": best_max,
        f"{prefix}_best_mean_pen_up_jump_px": best_mean,
        f"avoidable_{prefix}_max_jump_px": max(0.0, actual_max - best_max),
        f"avoidable_{prefix}_mean_jump_px": max(0.0, actual_mean - best_mean),
    }


def _best_cross_component_jumps(component_groups: list[list[dict[str, Any]]]) -> tuple[list[float] | None, bool]:
    if len(component_groups) <= 1:
        return [], True
    if len(component_groups) > 6:
        return None, False

    best_key = None
    best_jumps = None
    for order in _permutations(range(len(component_groups))):
        for flip_flags in _bit_product(len(component_groups)):
            arranged_groups: list[list[dict[str, Any]]] = []
            for position, group_index in enumerate(order):
                group = component_groups[group_index]
                arranged_groups.append(_reversed_group(group) if flip_flags[position] else _copy_group(group))
            jumps = _group_transition_jumps(arranged_groups)
            key = (max(jumps) if jumps else 0.0, sum(jumps), order, flip_flags)
            if best_key is None or key < best_key:
                best_key = key
                best_jumps = jumps
    return best_jumps, True


def _best_internal_jumps(component_groups: list[list[dict[str, Any]]]) -> tuple[list[float] | None, bool]:
    best_jumps: list[float] = []
    for group in component_groups:
        component_best, is_exact = _best_group_internal_jumps(group)
        if not is_exact or component_best is None:
            return None, False
        best_jumps.extend(component_best)
    return best_jumps, True


def _best_group_internal_jumps(group: list[dict[str, Any]]) -> tuple[list[float] | None, bool]:
    if len(group) <= 1:
        return [], True
    if len(group) > 6:
        return None, False

    best_key = None
    best_jumps = None
    for order in _permutations(range(len(group))):
        for flip_flags in _bit_product(len(group)):
            arranged: list[dict[str, Any]] = []
            for position, segment_index in enumerate(order):
                segment = group[segment_index]
                arranged.append(_reversed_segment(segment) if flip_flags[position] else _copy_segment(segment))
            jumps = _segment_transition_jumps(arranged)
            key = (max(jumps) if jumps else 0.0, sum(jumps), order, flip_flags)
            if best_key is None or key < best_key:
                best_key = key
                best_jumps = jumps
    return best_jumps, True


def _group_transition_jumps(groups: list[list[dict[str, Any]]]) -> list[float]:
    jumps: list[float] = []
    previous_end = _group_end(groups[0]) if groups else None
    for group in groups[1:]:
        start = _group_start(group)
        if previous_end is not None and start is not None:
            jumps.append(_distance(previous_end, start))
        previous_end = _group_end(group)
    return jumps


def _segment_transition_jumps(segments: list[dict[str, Any]]) -> list[float]:
    jumps: list[float] = []
    previous_end = None
    for segment in segments:
        points = list(segment.get("points", ()))
        if previous_end is not None and points:
            jumps.append(_distance(previous_end, points[0]))
        if points:
            previous_end = points[-1]
    return jumps


def _copy_group(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_copy_segment(segment) for segment in group]


def _reversed_group(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_reversed_segment(segment) for segment in reversed(group)]


def _copy_segment(segment: dict[str, Any]) -> dict[str, Any]:
    copied = dict(segment)
    copied["points"] = [tuple(point) for point in copied.get("points", ())]
    copied["source_segment_ids"] = tuple(copied.get("source_segment_ids", ()))
    return copied


def _reversed_segment(segment: dict[str, Any]) -> dict[str, Any]:
    reversed_segment = _copy_segment(segment)
    reversed_segment["points"] = list(reversed(reversed_segment.get("points", ())))
    return reversed_segment


def _group_start(group: list[dict[str, Any]]) -> tuple[float, float] | None:
    for segment in group:
        points = list(segment.get("points", ()))
        if points:
            return tuple(points[0])
    return None


def _group_end(group: list[dict[str, Any]]) -> tuple[float, float] | None:
    for segment in reversed(group):
        points = list(segment.get("points", ()))
        if points:
            return tuple(points[-1])
    return None


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    dy = float(first[0]) - float(second[0])
    dx = float(first[1]) - float(second[1])
    return float((dy * dy + dx * dx) ** 0.5)


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    return sum(_distance(start, end) for start, end in zip(points[:-1], points[1:]))


def _parse_source_ids(value: str) -> tuple[int, ...]:
    if not value or not value.startswith("segment:"):
        return ()
    tokens = value.split(":", 1)[1].split("+")
    ids: list[int] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except ValueError:
            continue
    return tuple(ids)


def _permutations(values: Iterable[int]) -> Iterable[tuple[int, ...]]:
    values = tuple(values)
    if len(values) <= 1:
        yield values
        return
    for index, value in enumerate(values):
        rest = values[:index] + values[index + 1 :]
        for tail in _permutations(rest):
            yield (value,) + tail


def _bit_product(length: int) -> Iterable[tuple[int, ...]]:
    if length <= 0:
        yield ()
        return
    total = 1 << length
    for mask in range(total):
        yield tuple((mask >> index) & 1 for index in range(length))


def _build_output_dir(base_dir: Path, prefix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return Path(base_dir) / f"{prefix}_{stamp}"


def _load_contact_panel(path: Path, panel_size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", panel_size, (248, 248, 248))
    draw = ImageDraw.Draw(panel)
    if not path.exists():
        draw.rectangle((0, 0, panel_size[0] - 1, panel_size[1] - 1), outline=(210, 210, 210))
        draw.text((8, 8), "missing", fill=(140, 140, 140))
        return panel
    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        draw.rectangle((0, 0, panel_size[0] - 1, panel_size[1] - 1), outline=(210, 210, 210))
        draw.text((8, 8), "invalid", fill=(140, 140, 140))
        return panel

    image.thumbnail((panel_size[0] - 8, panel_size[1] - 8))
    offset_x = (panel_size[0] - image.width) // 2
    offset_y = (panel_size[1] - image.height) // 2
    panel.paste(image, (offset_x, offset_y))
    return panel


def _format_number_or_na(value: Any) -> str:
    if value in {"", None, "n/a"}:
        return "n/a"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _report_value(value: Any) -> Any:
    if value in {"", None}:
        return "n/a"
    return value


def _md_cell(value: Any) -> str:
    return (
        str(value)
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
        .replace("|", "\\|")
    )
