from datetime import datetime
import json
from itertools import permutations, product
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from cleanup import prune_short_spurs, remove_small_components
from exporters import write_batch_report, write_summary_json, write_trial_csv
from graph_extract import extract_segments
from ordering import order_segments
from preprocess import crop_to_foreground, ensure_foreground_is_true
from skeleton import ridge_skeleton, skeleton_backend_name, skeleton_backend_warning
from smoke_benchmark import write_manual_audit_sheet
from trajectory_consolidation import consolidate_ordered_segments
from visualize import (
    write_mask_png,
    write_order_png,
    write_segments_png,
    write_skeleton_png,
    write_trajectory_png,
)


FIRST_PASS_AUDIT_MAX_BRANCH_POINTS = 4
FIRST_PASS_AUDIT_MAX_ENDPOINTS = 9
FIRST_PASS_AUDIT_MAX_PEN_UP_JUMP_PX = 16.0
FIRST_PASS_AUDIT_MAX_MEAN_PEN_UP_JUMP_PX = 8.0
FIRST_PASS_AUDIT_MAX_AVOIDABLE_CROSS_COMPONENT_JUMP_PX = 4.0
AUDIT_MAX_EXACT_GROUP_SEGMENTS = 6
AUDIT_MAX_EXACT_COMPONENT_GROUPS = 6


def build_output_dir(base_dir: Path, prefix: str = "batch") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return base_dir / f"{prefix}_{stamp}"


def run_single_image(
    image_path: Path,
    output_dir: Path,
    *,
    threshold: int = 200,
    crop_pad: int = 2,
    min_component_pixels: int = 3,
    spur_max_length: int = 1,
    min_segment_pixels: int = 2,
    ordering_endpoint_merge_distance: float = 0.0,
    ordering_direction_cos_threshold: float = 0.65,
) -> Path:
    image_path = Path(image_path)
    sample_dir = _sample_output_dir(Path(output_dir), image_path.stem)
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample = sample_dir.name

    boundary_note = (
        "Offline recovery debug output only: candidate ordering is not real stroke order "
        "and this is not robot output."
    )
    try:
        image = Image.open(image_path).convert("L")
    except (OSError, ValueError) as exc:
        write_summary_json(
            sample_dir / "recovery_summary.json",
            {
                "sample": sample,
                "status": "failed",
                "failure_reason": "image_read_error",
                "error_message": str(exc),
                "image_path": str(image_path),
                "sample_dir": str(sample_dir),
                "audit_status": "failed",
                "manual_audit_required": True,
                "boundary_note": boundary_note,
            },
        )
        return sample_dir

    image.save(sample_dir / "input_image.png")
    mask = ensure_foreground_is_true(np.asarray(image), threshold=threshold)
    write_mask_png(sample_dir / "foreground_mask.png", mask)
    foreground_pixel_count = int(mask.sum())
    original_image_size = [int(image.width), int(image.height)]
    if foreground_pixel_count == 0:
        write_summary_json(
            sample_dir / "recovery_summary.json",
            {
                "sample": sample,
                "status": "failed",
                "failure_reason": "no_foreground_pixels",
                "foreground_pixel_count": foreground_pixel_count,
                "threshold": threshold,
                "image_path": str(image_path),
                "sample_dir": str(sample_dir),
                "original_image_size": original_image_size,
                "audit_status": "failed",
                "manual_audit_required": True,
                "boundary_note": boundary_note,
            },
        )
        return sample_dir

    cropped_mask, bbox = crop_to_foreground(mask, pad=crop_pad)
    write_mask_png(sample_dir / "cropped_mask.png", cropped_mask)

    skeleton_backend = skeleton_backend_name()
    raw_skeleton = ridge_skeleton(cropped_mask)
    component_cleaned, _ = remove_small_components(raw_skeleton, min_component_pixels=min_component_pixels)
    clean_skeleton, _ = prune_short_spurs(component_cleaned, max_length=spur_max_length)

    graph = extract_segments(clean_skeleton, min_segment_pixels=min_segment_pixels)
    ordered = order_segments(
        graph["segments"],
        endpoint_merge_distance=ordering_endpoint_merge_distance,
        direction_cos_threshold=ordering_direction_cos_threshold,
    )
    consolidated, consolidation_meta = consolidate_ordered_segments(ordered)
    trajectory_point_count = write_trial_csv(sample_dir / "trial_ordered_trajectory.csv", consolidated)
    jump_metrics = _pen_up_jump_metrics(consolidated)
    jump_breakdown = _pen_up_jump_breakdown(consolidated)
    shared_interior_intersection_count = _shared_interior_intersection_count(consolidated)

    summary = {
        "sample": sample,
        "status": "ok",
        "image_path": str(image_path),
        "sample_dir": str(sample_dir),
        "bbox": list(bbox),
        "coordinate_frame": "crop_local",
        "origin_offset_y": int(bbox[0]),
        "origin_offset_x": int(bbox[1]),
        "original_image_size": original_image_size,
        "foreground_pixel_count": foreground_pixel_count,
        "threshold": threshold,
        "skeleton_backend": skeleton_backend,
        "skeleton_backend_warning": skeleton_backend_warning(skeleton_backend),
        "raw_skeleton_pixel_count": int(raw_skeleton.sum()),
        "clean_skeleton_pixel_count": int(clean_skeleton.sum()),
        "segment_count": int(graph["segment_count"]),
        "ordered_segment_count": len(ordered),
        "consolidated_segment_count": len(consolidated),
        "component_count": int(graph["component_count"]),
        "endpoint_count": int(graph["endpoint_count"]),
        "branch_point_count": int(graph["branch_point_count"]),
        "trajectory_point_count": trajectory_point_count,
        "ordering_endpoint_merge_distance": float(ordering_endpoint_merge_distance),
        "ordering_direction_cos_threshold": float(ordering_direction_cos_threshold),
        "shared_interior_intersection_count": shared_interior_intersection_count,
        **consolidation_meta,
        **jump_metrics,
        **jump_breakdown,
        "manual_audit_required": True,
        "boundary_note": boundary_note,
    }
    if len(consolidated) == 0 or trajectory_point_count == 0:
        summary["status"] = "failed"
        summary["failure_reason"] = "no_ordered_segments"
    summary["audit_status"] = _audit_status(summary)
    write_summary_json(sample_dir / "recovery_summary.json", summary)

    write_skeleton_png(sample_dir / "raw_skeleton.png", raw_skeleton)
    write_skeleton_png(sample_dir / "clean_skeleton.png", clean_skeleton)
    write_segments_png(sample_dir / "segments.png", clean_skeleton, graph["segments"])
    write_order_png(sample_dir / "candidate_order.png", clean_skeleton, ordered)
    write_trajectory_png(sample_dir / "final_trajectory.png", clean_skeleton, consolidated)

    return sample_dir


def run_batch(
    image_paths: Sequence[Path],
    output_dir: Path,
    *,
    threshold: int = 200,
    crop_pad: int = 2,
    min_component_pixels: int = 3,
    spur_max_length: int = 1,
    min_segment_pixels: int = 2,
    ordering_endpoint_merge_distance: float = 0.0,
    ordering_direction_cos_threshold: float = 0.65,
) -> Path:
    batch_dir = build_output_dir(Path(output_dir), prefix="offline_recovery_batch")
    batch_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for image_path in image_paths:
        sample_dir = run_single_image(
            Path(image_path),
            batch_dir,
            threshold=threshold,
            crop_pad=crop_pad,
            min_component_pixels=min_component_pixels,
            spur_max_length=spur_max_length,
            min_segment_pixels=min_segment_pixels,
            ordering_endpoint_merge_distance=ordering_endpoint_merge_distance,
            ordering_direction_cos_threshold=ordering_direction_cos_threshold,
        )
        summary = json.loads((sample_dir / "recovery_summary.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "sample": summary.get("sample", sample_dir.name),
                "status": summary.get("status", ""),
                "failure_reason": summary.get("failure_reason", "n/a"),
                "audit_status": summary.get("audit_status", ""),
                "component_count": summary.get("component_count", "n/a"),
                "branch_point_count": summary.get("branch_point_count", "n/a"),
                "skeleton_backend": summary.get("skeleton_backend", "n/a"),
                "max_pen_up_jump_px": summary.get("max_pen_up_jump_px", "n/a"),
                "trajectory_point_count": summary.get("trajectory_point_count", "n/a"),
                "sample_dir": str(sample_dir),
                "summary_path": _existing_artifact_path(sample_dir / "recovery_summary.json"),
                "trajectory_path": _existing_artifact_path(sample_dir / "trial_ordered_trajectory.csv"),
                "final_trajectory_image": _existing_artifact_path(sample_dir / "final_trajectory.png"),
            }
        )
    manual_audit_sheet_path = write_manual_audit_sheet(batch_dir)
    write_batch_report(
        batch_dir / "batch_report.md",
        rows,
        manual_audit_sheet_path=manual_audit_sheet_path,
    )
    return batch_dir


def _sample_output_dir(output_dir: Path, stem: str) -> Path:
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem).strip("_")
    if not safe_stem:
        safe_stem = "sample"
    candidate = output_dir / safe_stem
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = output_dir / f"{safe_stem}_{index}"
        if not numbered.exists():
            return numbered
        index += 1


def _existing_artifact_path(path: Path) -> str:
    if path.exists():
        return str(path)
    return "n/a"


def _pen_up_jump_metrics(ordered_segments: list[dict]) -> dict[str, float | int]:
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


def _pen_up_jump_breakdown(ordered_segments: list[dict]) -> dict[str, float | int | bool | None]:
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


def _component_groups(ordered_segments: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
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


def _best_cross_component_jumps(component_groups: list[list[dict]]) -> tuple[list[float] | None, bool]:
    if len(component_groups) <= 1:
        return [], True
    if len(component_groups) > AUDIT_MAX_EXACT_COMPONENT_GROUPS:
        return None, False

    best_key = None
    best_jumps = None
    for order in permutations(range(len(component_groups))):
        for flip_flags in product((0, 1), repeat=len(component_groups)):
            arranged_groups: list[list[dict]] = []
            for position, group_index in enumerate(order):
                group = component_groups[group_index]
                arranged_groups.append(_reversed_group(group) if flip_flags[position] else _copy_group(group))
            jumps = _group_transition_jumps(arranged_groups)
            key = (
                max(jumps) if jumps else 0.0,
                sum(jumps),
                order,
                flip_flags,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_jumps = jumps
    return best_jumps, True


def _best_internal_jumps(component_groups: list[list[dict]]) -> tuple[list[float] | None, bool]:
    best_jumps: list[float] = []
    for group in component_groups:
        component_best, is_exact = _best_group_internal_jumps(group)
        if not is_exact or component_best is None:
            return None, False
        best_jumps.extend(component_best)
    return best_jumps, True


def _best_group_internal_jumps(group: list[dict]) -> tuple[list[float] | None, bool]:
    if len(group) <= 1:
        return [], True
    if len(group) > AUDIT_MAX_EXACT_GROUP_SEGMENTS:
        return None, False

    best_key = None
    best_jumps = None
    for order in permutations(range(len(group))):
        for flip_flags in product((0, 1), repeat=len(group)):
            arranged: list[dict] = []
            for position, segment_index in enumerate(order):
                segment = group[segment_index]
                arranged.append(_reversed_segment(segment) if flip_flags[position] else _copy_segment(segment))
            jumps = _segment_transition_jumps(arranged)
            key = (
                max(jumps) if jumps else 0.0,
                sum(jumps),
                order,
                flip_flags,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_jumps = jumps
    return best_jumps, True


def _group_transition_jumps(groups: list[list[dict]]) -> list[float]:
    jumps: list[float] = []
    previous_end = _group_end(groups[0]) if groups else None
    for group in groups[1:]:
        start = _group_start(group)
        if previous_end is not None and start is not None:
            jumps.append(_distance(previous_end, start))
        previous_end = _group_end(group)
    return jumps


def _segment_transition_jumps(segments: list[dict]) -> list[float]:
    jumps: list[float] = []
    previous_end = None
    for segment in segments:
        points = list(segment.get("points", ()))
        if previous_end is not None and points:
            jumps.append(_distance(previous_end, points[0]))
        if points:
            previous_end = points[-1]
    return jumps


def _copy_group(group: list[dict]) -> list[dict]:
    return [_copy_segment(segment) for segment in group]


def _reversed_group(group: list[dict]) -> list[dict]:
    return [_reversed_segment(segment) for segment in reversed(group)]


def _copy_segment(segment: dict) -> dict:
    copied = dict(segment)
    copied["points"] = [tuple(point) for point in copied.get("points", ())]
    return copied


def _reversed_segment(segment: dict) -> dict:
    reversed_segment = _copy_segment(segment)
    reversed_segment["points"] = list(reversed(reversed_segment.get("points", ())))
    return reversed_segment


def _group_start(group: list[dict]) -> tuple[float, float] | None:
    for segment in group:
        points = list(segment.get("points", ()))
        if points:
            return tuple(points[0])
    return None


def _group_end(group: list[dict]) -> tuple[float, float] | None:
    for segment in reversed(group):
        points = list(segment.get("points", ()))
        if points:
            return tuple(points[-1])
    return None


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    dy = float(first[0]) - float(second[0])
    dx = float(first[1]) - float(second[1])
    return float((dy * dy + dx * dx) ** 0.5)


def _shared_interior_intersection_count(ordered_segments: list[dict]) -> int:
    interior_sets: list[set[tuple[float, float]]] = []
    for segment in ordered_segments:
        points = [tuple(point) for point in segment.get("points", ())]
        interior_sets.append(set(points[1:-1]))

    count = 0
    for index, first in enumerate(interior_sets):
        if not first:
            continue
        for second in interior_sets[index + 1 :]:
            if first.intersection(second):
                count += 1
    return count


def _audit_status(summary: dict) -> str:
    if (
        summary.get("status") == "failed"
        or int(summary.get("segment_count", 0)) == 0
        or int(summary.get("ordered_segment_count", 0)) == 0
        or int(summary.get("trajectory_point_count", 0)) == 0
    ):
        return "failed"

    structural_crossing_break = (
        int(summary.get("component_count", 0)) == 1
        and int(summary.get("ordered_segment_count", 0)) == 2
        and int(summary.get("shared_interior_intersection_count", 0)) > 0
    )

    internal_jump_count = int(summary.get("internal_pen_up_jump_count", summary.get("pen_up_jump_count", 0)))
    internal_max_jump = float(summary.get("internal_max_pen_up_jump_px", summary.get("max_pen_up_jump_px", 0.0)))
    internal_mean_jump = float(summary.get("internal_mean_pen_up_jump_px", summary.get("mean_pen_up_jump_px", 0.0)))
    avoidable_cross_component_max_jump = summary.get("avoidable_cross_component_max_jump_px")
    avoidable_cross_component_risky = (
        summary.get("cross_component_best_is_exact") is True
        and avoidable_cross_component_max_jump is not None
        and float(avoidable_cross_component_max_jump) > FIRST_PASS_AUDIT_MAX_AVOIDABLE_CROSS_COMPONENT_JUMP_PX
    )

    if (
        int(summary.get("branch_point_count", 0)) > FIRST_PASS_AUDIT_MAX_BRANCH_POINTS
        or int(summary.get("endpoint_count", 0)) > FIRST_PASS_AUDIT_MAX_ENDPOINTS
        or (
            not structural_crossing_break
            and (
                internal_max_jump > FIRST_PASS_AUDIT_MAX_PEN_UP_JUMP_PX
                or (
                    internal_jump_count > 1
                    and internal_mean_jump > FIRST_PASS_AUDIT_MAX_MEAN_PEN_UP_JUMP_PX
                )
                or avoidable_cross_component_risky
            )
        )
    ):
        return "risky_needs_manual_check"

    return "promising"
