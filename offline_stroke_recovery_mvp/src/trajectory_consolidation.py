"""Conservative post-ordering trajectory consolidation for local offline recovery."""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np


Point = tuple[float, float]
DEFAULT_MERGE_GAP_PX = 1.5
DEFAULT_DIRECTION_COS_THRESHOLD = 0.35
DEFAULT_SIMPLIFY_TOLERANCE_PX = 0.75
DEFAULT_RESAMPLE_STEP_PX = 1.0
DEFAULT_FOREGROUND_SNAP_RADIUS_PX = 4.0
DEFAULT_FOREGROUND_SNAP_STEP_PX = 0.5
DEFAULT_FOREGROUND_SNAP_SMOOTHING_WINDOW = 3
DEFAULT_FOREGROUND_SNAP_WIDTH_FACTOR = 1.75
DEFAULT_FOREGROUND_SNAP_WIDTH_MARGIN_PX = 1.5
DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MAX_DISTANCE_PX = 1.6
DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MIN_SUPPORT_RATIO = 0.75
DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MAX_TURN_COS = 0.9
DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MAX_DISTANCE_PX = 3.0
DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MIN_SUPPORT_RATIO = 0.95
DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MIN_AXIS_RATIO = 40.0
DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MAX_AXIS_RESIDUAL_PX = 0.2
DEFAULT_LOCAL_FOREGROUND_SNAP_FULL_DISTANCE_PX = 5.0
DEFAULT_LOCAL_FOREGROUND_SNAP_TAPER_DISTANCE_PX = 12.0
DEFAULT_LOCAL_FOREGROUND_SNAP_WEIGHT_SMOOTHING_WINDOW = 5
DEFAULT_INTERNAL_STITCH_GAP_PX = 3.5
DEFAULT_INTERNAL_STITCH_BRIDGED_GAP_PX = 6.0
DEFAULT_INTERNAL_STITCH_FOREGROUND_RATIO = 0.8
DEFAULT_INTERNAL_STITCH_DIRECTION_COS_MIN = 0.35
DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_LENGTH_PX = 10.0
DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_COMBINED_LENGTH_PX = 36.0
DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_GAP_PX = 4.5
DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_DIRECTION_COS = 0.93
DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_OPPOSITE_GAP_COS = 0.75
DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_FOREGROUND_RATIO = 0.55
DEFAULT_BRIDGED_MERGE_GAP_PX = 12.0
DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD = 0.94
DEFAULT_BRIDGED_MERGE_FOREGROUND_RATIO = 0.8
DEFAULT_ALIGNED_OVERLAP_GAP_PX = 2.5
DEFAULT_CORNER_MERGE_GAP_PX = 4.5
DEFAULT_CORNER_MERGE_DIRECTION_DOT_MAX = 0.35
DEFAULT_CORNER_MERGE_TAIL_GAP_COS_MIN = 0.35
DEFAULT_CORNER_MERGE_HEAD_GAP_COS_MAX = -0.6
DEFAULT_CORNER_ATTACHMENT_GAP_PX = 6.0
DEFAULT_CORNER_ATTACHMENT_FOREGROUND_RATIO = 0.55
DEFAULT_CORNER_ATTACHMENT_MATCHED_ENDPOINT_DIRECTION_DOT_MAX = 0.92
DEFAULT_CORNER_ATTACHMENT_MIXED_ENDPOINT_DIRECTION_DOT_MAX = 0.55
DEFAULT_CORNER_ATTACHMENT_CONNECTION_TOLERANCE_PX = 1.5
DEFAULT_CORNER_ATTACHMENT_SUPPORT_RADIUS_PX = 1.5
DEFAULT_CORNER_ATTACHMENT_SUPPORT_ADVANTAGE = 0.1
DEFAULT_LIGHT_REPAIR_EXACT_GAP_PX = 2.5
DEFAULT_LIGHT_REPAIR_BRIDGED_GAP_PX = 6.0
DEFAULT_LIGHT_REPAIR_EXACT_DIRECTION_COS_THRESHOLD = 0.94
DEFAULT_LIGHT_REPAIR_BRIDGED_DIRECTION_COS_THRESHOLD = 0.97
DEFAULT_LIGHT_REPAIR_FOREGROUND_RATIO = 0.8
DEFAULT_LIGHT_REPAIR_SHORT_SEGMENT_MAX_LENGTH_PX = 14.0
DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_POINT_COUNT = 12
DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_AXIS_RATIO = 10.0
DEFAULT_LIGHT_REPAIR_GEOMETRY_MAX_AXIS_RESIDUAL_PX = 0.55
DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_VERTICAL_TO_HORIZONTAL_RATIO = 1.5
DEFAULT_LIGHT_REPAIR_GEOMETRY_ENDPOINT_PRESERVE_COUNT = 4
DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_RADIUS_PX = 6.0
DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_MIN_ABS_PX = 0.75
DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_STD_MAX_PX = 0.45
DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_STD_RELAXED_MAX_PX = 0.6
DEFAULT_LIGHT_REPAIR_GEOMETRY_SIGN_FRACTION_MIN = 0.8
DEFAULT_LIGHT_REPAIR_GEOMETRY_SIGN_FRACTION_RELAXED_MIN = 0.85
DEFAULT_LIGHT_REPAIR_GEOMETRY_RELAXED_AXIS_RATIO = 25.0
DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_MIN_RUN_POINTS = 5
DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_ENDPOINT_GUARD_COUNT = 2
DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_TAPER_POINTS = 3
DEFAULT_LIGHT_REPAIR_GEOMETRY_CONNECTION_TOLERANCE_PX = 1.5
ENDPOINT_DIRECTION_SAMPLE_STEPS = 4


def consolidate_ordered_segments(
    ordered_segments: list[dict[str, Any]],
    *,
    merge_adjacent: bool = True,
    merge_gap_px: float = DEFAULT_MERGE_GAP_PX,
    direction_cos_threshold: float = DEFAULT_DIRECTION_COS_THRESHOLD,
    simplify_tolerance_px: float = DEFAULT_SIMPLIFY_TOLERANCE_PX,
    resample_step_px: float | None = DEFAULT_RESAMPLE_STEP_PX,
    foreground_mask: np.ndarray | None = None,
    foreground_snap_radius_px: float = DEFAULT_FOREGROUND_SNAP_RADIUS_PX,
    foreground_snap_blend: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    consolidated = [_copy_segment(segment) for segment in ordered_segments]
    merged_segment_count = 0

    if merge_adjacent:
        index = 0
        while index + 1 < len(consolidated):
            current = consolidated[index]
            following = consolidated[index + 1]
            merged = _try_merge_adjacent(
                current,
                following,
                merge_gap_px=merge_gap_px,
                direction_cos_threshold=direction_cos_threshold,
                foreground_mask=foreground_mask,
            )
            if merged is None:
                index += 1
                continue
            consolidated[index] = merged
            consolidated.pop(index + 1)
            merged_segment_count += 1

    simplified_point_delta = 0
    resampled_point_delta = 0
    snapped_point_count = 0
    refreshed: list[dict[str, Any]] = []
    snap_blend = min(max(float(foreground_snap_blend), 0.0), 1.0)
    for order_index, segment in enumerate(consolidated, start=1):
        updated = _copy_segment(segment)
        original_points = list(updated.get("points", ()))
        simplified_points = _rdp_simplify(original_points, simplify_tolerance_px)
        simplified_point_delta += max(0, len(original_points) - len(simplified_points))
        updated["points"] = simplified_points
        _refresh_geometry_metadata(updated)

        resampled_points = (
            _resample_polyline(updated["points"], step_px=resample_step_px)
            if resample_step_px is not None and resample_step_px > 0
            else list(updated["points"])
        )
        resampled_point_delta += max(0, len(resampled_points) - len(updated["points"]))
        updated["points"] = resampled_points
        if (
            foreground_mask is not None
            and foreground_snap_radius_px > 0
        ):
            local_snap_weights = _local_snap_weights_for_straight_prior_segment(
                updated,
                consolidated,
                segment_index=order_index - 1,
            )
            if local_snap_weights is not None or not _should_skip_foreground_snap(updated):
                snapped_points, moved_count = _snap_polyline_to_foreground_midline(
                    updated["points"],
                    foreground_mask,
                    radius_px=foreground_snap_radius_px,
                )
                if local_snap_weights is not None:
                    snapped_points, moved_count = _blend_polyline_points(
                        updated["points"],
                        snapped_points,
                        local_snap_weights,
                    )
                elif snap_blend < 1.0:
                    snapped_points, moved_count = _blend_polyline_points(
                        updated["points"],
                        snapped_points,
                        [snap_blend] * len(updated["points"]),
                    )
                updated["points"] = snapped_points
                snapped_point_count += moved_count
                if local_snap_weights is None:
                    post_snap_simplified = _rdp_simplify(updated["points"], simplify_tolerance_px)
                    simplified_point_delta += max(0, len(updated["points"]) - len(post_snap_simplified))
                    updated["points"] = post_snap_simplified
                    if resample_step_px is not None and resample_step_px > 0:
                        post_snap_resampled = _resample_polyline(updated["points"], step_px=resample_step_px)
                        resampled_point_delta += max(0, len(post_snap_resampled) - len(updated["points"]))
                        updated["points"] = post_snap_resampled
        updated["stroke_like_id"] = order_index
        updated["order_index"] = order_index
        _refresh_geometry_metadata(updated)
        refreshed.append(updated)

    refreshed = _stitch_small_internal_same_component_gaps(
        refreshed,
        max_gap_px=DEFAULT_INTERNAL_STITCH_GAP_PX,
        foreground_mask=foreground_mask,
    )
    refreshed, corner_attachment_count = _attach_supported_cross_component_corners(
        refreshed,
        foreground_mask=foreground_mask,
    )

    return refreshed, {
        "merged_segment_count": merged_segment_count,
        "simplified_point_delta": simplified_point_delta,
        "resampled_point_delta": resampled_point_delta,
        "snapped_point_count": snapped_point_count,
        "corner_attachment_count": corner_attachment_count,
    }


def light_repair_raw_segments(
    raw_segments: list[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None = None,
    exact_gap_px: float = DEFAULT_LIGHT_REPAIR_EXACT_GAP_PX,
    bridged_gap_px: float = DEFAULT_LIGHT_REPAIR_BRIDGED_GAP_PX,
    exact_direction_cos_threshold: float = DEFAULT_LIGHT_REPAIR_EXACT_DIRECTION_COS_THRESHOLD,
    bridged_direction_cos_threshold: float = DEFAULT_LIGHT_REPAIR_BRIDGED_DIRECTION_COS_THRESHOLD,
    foreground_ratio: float = DEFAULT_LIGHT_REPAIR_FOREGROUND_RATIO,
    short_segment_max_length_px: float = DEFAULT_LIGHT_REPAIR_SHORT_SEGMENT_MAX_LENGTH_PX,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    repaired = [_copy_segment(segment) for segment in raw_segments]
    merged_segment_count = 0

    while True:
        candidate = _find_light_repair_merge_candidate(
            repaired,
            foreground_mask=foreground_mask,
            exact_gap_px=exact_gap_px,
            bridged_gap_px=bridged_gap_px,
            exact_direction_cos_threshold=exact_direction_cos_threshold,
            bridged_direction_cos_threshold=bridged_direction_cos_threshold,
            foreground_ratio=foreground_ratio,
            short_segment_max_length_px=short_segment_max_length_px,
        )
        if candidate is None:
            break
        first_index, second_index, merged = candidate
        repaired[first_index] = merged
        repaired.pop(second_index)
        merged_segment_count += 1

    return repaired, {
        "light_repair_merged_segment_count": merged_segment_count,
    }


def light_repair_ordered_segments_geometry(
    ordered_segments: list[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    adjusted = [_copy_segment(segment) for segment in ordered_segments]
    if foreground_mask is None or not bool(np.asarray(foreground_mask, dtype=bool).any()):
        return adjusted, {"light_repair_geometry_adjusted_segment_count": 0}

    adjusted_segment_count = 0
    for segment_index, segment in enumerate(adjusted):
        updated_points = _light_repair_center_straight_segment(
            segment.get("points", ()),
            adjusted,
            segment_index=segment_index,
            foreground_mask=np.asarray(foreground_mask, dtype=bool),
        )
        if updated_points is None:
            continue
        original_points = [tuple(_as_point(point)) for point in segment.get("points", ())]
        original_start = original_points[0]
        original_end = original_points[-1]
        new_start = updated_points[0]
        new_end = updated_points[-1]
        segment["points"] = updated_points
        _refresh_geometry_metadata(segment)
        _propagate_light_repair_endpoint_move(
            adjusted,
            source_segment_index=segment_index,
            original_point=original_start,
            updated_point=new_start,
            tolerance_px=DEFAULT_LIGHT_REPAIR_GEOMETRY_CONNECTION_TOLERANCE_PX,
        )
        _propagate_light_repair_endpoint_move(
            adjusted,
            source_segment_index=segment_index,
            original_point=original_end,
            updated_point=new_end,
            tolerance_px=DEFAULT_LIGHT_REPAIR_GEOMETRY_CONNECTION_TOLERANCE_PX,
        )
        adjusted_segment_count += 1

    adjusted, corner_attachment_count = _attach_supported_cross_component_corners(
        adjusted,
        foreground_mask=np.asarray(foreground_mask, dtype=bool),
    )

    return adjusted, {
        "light_repair_geometry_adjusted_segment_count": adjusted_segment_count,
        "light_repair_geometry_corner_attachment_count": corner_attachment_count,
    }


def stitch_component_labeled_internal_gaps(
    segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None = None,
    max_gap_px: float = DEFAULT_INTERNAL_STITCH_GAP_PX,
) -> list[dict[str, Any]]:
    return _stitch_small_internal_same_component_gaps(
        segments,
        max_gap_px=max_gap_px,
        foreground_mask=foreground_mask,
    )


def merge_adjacent_short_fragments(
    segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None = None,
    max_short_length_px: float = DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_LENGTH_PX,
    max_combined_length_px: float = DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_COMBINED_LENGTH_PX,
) -> list[dict[str, Any]]:
    merged = [_copy_segment(segment) for segment in segments]
    if foreground_mask is None or len(merged) < 2:
        return merged

    index = 0
    while index + 1 < len(merged):
        current = merged[index]
        following = merged[index + 1]
        candidate = _try_merge_adjacent_short_fragment_pair(
            current,
            following,
            foreground_mask=foreground_mask,
            max_short_length_px=max_short_length_px,
            max_combined_length_px=max_combined_length_px,
        )
        if candidate is None:
            index += 1
            continue
        merged[index] = candidate
        merged.pop(index + 1)
    return merged


def merge_adjacent_component_labeled_short_fragments(
    segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None = None,
    max_short_length_px: float = DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_LENGTH_PX,
    max_combined_length_px: float = DEFAULT_ADJACENT_SHORT_FRAGMENT_MAX_COMBINED_LENGTH_PX,
) -> list[dict[str, Any]]:
    merged = [_copy_segment(segment) for segment in segments]
    if foreground_mask is None or len(merged) < 2:
        return merged

    index = 0
    while index + 1 < len(merged):
        current = merged[index]
        following = merged[index + 1]
        candidate = _try_merge_adjacent_component_labeled_short_fragment_pair(
            current,
            following,
            foreground_mask=np.asarray(foreground_mask, dtype=bool),
            max_short_length_px=max_short_length_px,
            max_combined_length_px=max_combined_length_px,
        )
        if candidate is None:
            index += 1
            continue
        merged[index] = candidate
        merged.pop(index + 1)
    return merged


def _try_merge_adjacent(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    merge_gap_px: float,
    direction_cos_threshold: float,
    foreground_mask: np.ndarray | None,
) -> dict[str, Any] | None:
    if current.get("component_id") != following.get("component_id"):
        return None

    current_points = list(current.get("points", ()))
    following_points = _orient_following_points_for_merge(current_points, following.get("points", ()))
    if len(current_points) < 2 or len(following_points) < 2:
        return None

    gap = _distance(current_points[-1], following_points[0])
    if gap > merge_gap_px:
        bridged = _try_merge_collinear_gap(
            current,
            following,
            current_points=current_points,
            following_points=following_points,
            gap=gap,
            foreground_mask=foreground_mask,
        )
        if bridged is None:
            return None
        return bridged
    if gap <= 1e-9:
        merged = _copy_segment(current)
        merged["points"] = current_points + following_points[1:]
        merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
            following.get("source_segment_ids", ())
        )
        render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
            current,
            following,
            current_points=current_points,
            following_points=following_points,
        )
        merged["render_subpaths"] = render_subpaths
        merged["render_subpath_source_ids"] = render_subpath_source_ids
        merged["source"] = "consolidated"
        _refresh_geometry_metadata(merged)
        return merged

    current_tail = _endpoint_direction(current_points, at_end=True)
    following_head = _endpoint_direction(following_points, at_end=False)
    if _dot(current_tail, following_head) < direction_cos_threshold:
        return None

    merged = _copy_segment(current)
    if gap <= 1e-9:
        merged_points = current_points + following_points[1:]
    else:
        merged_points = current_points + [following_points[0]] + following_points[1:]
    merged["points"] = merged_points
    merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
        following.get("source_segment_ids", ())
    )
    render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
        current,
        following,
        current_points=current_points,
        following_points=following_points,
    )
    merged["render_subpaths"] = render_subpaths
    merged["render_subpath_source_ids"] = render_subpath_source_ids
    merged["source"] = "consolidated"
    _refresh_geometry_metadata(merged)
    return merged


def _try_merge_adjacent_short_fragment_pair(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    foreground_mask: np.ndarray,
    max_short_length_px: float,
    max_combined_length_px: float,
) -> dict[str, Any] | None:
    current_source_ids = tuple(current.get("source_segment_ids", ()))
    following_source_ids = tuple(following.get("source_segment_ids", ()))
    if len(current_source_ids) != 1 or len(following_source_ids) != 1:
        return None

    current_length = float(current.get("length_px", 0.0) or 0.0)
    following_length = float(following.get("length_px", 0.0) or 0.0)
    if min(current_length, following_length) > float(max_short_length_px):
        return None
    if current_length + following_length > float(max_combined_length_px):
        return None

    candidate_points = [
        list(current.get("points", ())),
        list(reversed(current.get("points", ()))),
    ]
    following_variants = [
        list(following.get("points", ())),
        list(reversed(following.get("points", ()))),
    ]
    best_candidate: tuple[float, float, list[Point], list[Point], dict[str, Any]] | None = None
    for current_points in candidate_points:
        if len(current_points) < 2:
            continue
        for following_points in following_variants:
            if len(following_points) < 2:
                continue
            gap = _distance(current_points[-1], following_points[0])
            if gap > DEFAULT_CORNER_MERGE_GAP_PX:
                continue
            merged = _try_merge_collinear_gap(
                current,
                following,
                current_points=current_points,
                following_points=following_points,
                gap=gap,
                foreground_mask=foreground_mask,
            )
            if merged is None:
                merged = _try_merge_relaxed_short_overlap(
                    current,
                    following,
                    current_points=current_points,
                    following_points=following_points,
                    gap=gap,
                    foreground_mask=foreground_mask,
                )
            if merged is None:
                merged = _try_merge_relaxed_short_overlap(
                    current,
                    following,
                    current_points=current_points,
                    following_points=following_points,
                    gap=gap,
                    foreground_mask=foreground_mask,
                    max_gap_px=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_GAP_PX,
                    min_direction_cos=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_DIRECTION_COS,
                    min_opposite_gap_cos=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_OPPOSITE_GAP_COS,
                    foreground_ratio=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_FOREGROUND_RATIO,
                )
            if merged is None:
                continue
            tail = _endpoint_direction(current_points, at_end=True)
            head = _endpoint_direction(following_points, at_end=False)
            aligned_direction = _dot(tail, head)
            candidate_key = (
                float(gap),
                -float(aligned_direction),
                list(current_points),
                list(following_points),
                merged,
            )
            if best_candidate is None or candidate_key[:2] < best_candidate[:2]:
                best_candidate = candidate_key
    if best_candidate is None:
        return None

    _, _, best_current_points, best_following_points, merged = best_candidate

    shorter = current if current_length <= following_length else following
    if shorter.get("component_id") is not None:
        merged["component_id"] = shorter.get("component_id")
    merged["render_subpaths"] = _build_render_subpaths_for_short_fragment_merge(
        current_points=best_current_points,
        following_points=best_following_points,
    )
    merged["render_subpath_source_ids"] = [
        tuple(current_source_ids),
        tuple(following_source_ids),
    ]
    merged["source"] = "light_repair_adjacent_short_fragment"
    _refresh_geometry_metadata(merged)
    return merged


def _try_merge_adjacent_component_labeled_short_fragment_pair(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    foreground_mask: np.ndarray,
    max_short_length_px: float,
    max_combined_length_px: float,
) -> dict[str, Any] | None:
    if current.get("component_id") != following.get("component_id"):
        return None

    merged = _try_merge_adjacent_short_fragment_pair(
        current,
        following,
        foreground_mask=foreground_mask,
        max_short_length_px=max_short_length_px,
        max_combined_length_px=max_combined_length_px,
    )
    if merged is not None:
        if current.get("component_id") is not None:
            merged["component_id"] = current.get("component_id")
        return merged

    current_source_ids = tuple(current.get("source_segment_ids", ()))
    following_source_ids = tuple(following.get("source_segment_ids", ()))
    if len(current_source_ids) != 1 or len(following_source_ids) != 1:
        return None

    current_length = float(current.get("length_px", 0.0) or 0.0)
    following_length = float(following.get("length_px", 0.0) or 0.0)
    if min(current_length, following_length) > float(max_short_length_px):
        return None
    if current_length + following_length > float(max_combined_length_px):
        return None

    candidate_points = [
        list(current.get("points", ())),
        list(reversed(current.get("points", ()))),
    ]
    following_variants = [
        list(following.get("points", ())),
        list(reversed(following.get("points", ()))),
    ]
    best_candidate: tuple[float, float, dict[str, Any]] | None = None
    for current_points in candidate_points:
        if len(current_points) < 2:
            continue
        for following_points in following_variants:
            if len(following_points) < 2:
                continue
            gap = _distance(current_points[-1], following_points[0])
            candidate = _try_merge_relaxed_short_overlap(
                current,
                following,
                current_points=current_points,
                following_points=following_points,
                gap=gap,
                foreground_mask=foreground_mask,
                max_gap_px=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_GAP_PX,
                min_direction_cos=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_DIRECTION_COS,
                min_opposite_gap_cos=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_OPPOSITE_GAP_COS,
                foreground_ratio=DEFAULT_COMPONENT_LABELED_SHORT_FRAGMENT_RELAXED_FOREGROUND_RATIO,
            )
            if candidate is None:
                continue
            aligned_direction = _dot(
                _endpoint_direction(current_points, at_end=True),
                _endpoint_direction(following_points, at_end=False),
            )
            candidate_key = (float(gap), -float(aligned_direction), candidate)
            if best_candidate is None or candidate_key[:2] < best_candidate[:2]:
                best_candidate = candidate_key
    if best_candidate is None:
        return None

    _, _, merged = best_candidate
    if current.get("component_id") is not None:
        merged["component_id"] = current.get("component_id")
    merged["source"] = "component_labeled_short_fragment_merge"
    _refresh_geometry_metadata(merged)
    return merged


def _build_render_subpaths_for_short_fragment_merge(
    *,
    current_points: Sequence[Point],
    following_points: Sequence[Point],
) -> list[list[Point]]:
    first_subpath = [tuple(_as_point(point)) for point in current_points]
    second_subpath = [tuple(_as_point(point)) for point in following_points]
    if not first_subpath or not second_subpath:
        return [first_subpath, second_subpath]
    if first_subpath[-1] != second_subpath[0]:
        first_subpath = first_subpath + [second_subpath[0]]
        second_subpath = [first_subpath[-2]] + second_subpath
    return [first_subpath, second_subpath]


def _build_render_subpaths_for_generic_merge(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    current_points: Sequence[Point],
    following_points: Sequence[Point],
) -> tuple[list[list[Point]], list[tuple[Any, ...]]]:
    current_subpaths, current_source_ids = _oriented_render_subpaths_for_segment(
        current,
        oriented_points=current_points,
    )
    following_subpaths, following_source_ids = _oriented_render_subpaths_for_segment(
        following,
        oriented_points=following_points,
    )
    if current_subpaths and following_subpaths and current_subpaths[-1] and following_subpaths[0]:
        current_end = tuple(_as_point(current_subpaths[-1][-1]))
        following_start = tuple(_as_point(following_subpaths[0][0]))
        if current_end != following_start:
            current_subpaths[-1] = current_subpaths[-1] + [following_start]
            following_subpaths[0] = [current_end] + following_subpaths[0]
    return current_subpaths + following_subpaths, current_source_ids + following_source_ids


def _oriented_render_subpaths_for_segment(
    segment: dict[str, Any],
    *,
    oriented_points: Sequence[Point],
) -> tuple[list[list[Point]], list[tuple[Any, ...]]]:
    source_ids = tuple(segment.get("source_segment_ids", ()))
    point_list = [tuple(_as_point(point)) for point in oriented_points]
    render_subpaths = segment.get("render_subpaths", ())
    if not render_subpaths:
        return ([point_list] if point_list else []), ([source_ids] if point_list else [])

    subpaths = [
        [tuple(_as_point(point)) for point in subpath]
        for subpath in render_subpaths
    ]
    subpath_source_ids = [
        tuple(value)
        for value in segment.get("render_subpath_source_ids", ())
    ]
    if len(subpath_source_ids) != len(subpaths):
        subpath_source_ids = [source_ids for _ in subpaths]

    original_points = [tuple(_as_point(point)) for point in segment.get("points", ())]
    if _segment_points_are_reversed(original_points, point_list):
        subpaths = [list(reversed(subpath)) for subpath in reversed(subpaths)]
        subpath_source_ids = list(reversed(subpath_source_ids))
    return subpaths, subpath_source_ids


def _segment_points_are_reversed(
    original_points: Sequence[Point],
    oriented_points: Sequence[Point],
) -> bool:
    if len(original_points) < 2 or len(oriented_points) < 2:
        return False
    same_distance = _distance(original_points[0], oriented_points[0]) + _distance(
        original_points[-1],
        oriented_points[-1],
    )
    reversed_distance = _distance(original_points[0], oriented_points[-1]) + _distance(
        original_points[-1],
        oriented_points[0],
    )
    return reversed_distance + 1e-6 < same_distance


def _try_merge_relaxed_short_overlap(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    current_points: Sequence[Point],
    following_points: Sequence[Point],
    gap: float,
    foreground_mask: np.ndarray,
    max_gap_px: float = 3.5,
    min_direction_cos: float = 0.94,
    min_opposite_gap_cos: float = 0.9,
    foreground_ratio: float = 0.9,
) -> dict[str, Any] | None:
    if gap > float(max_gap_px):
        return None
    bridge_start = current_points[-1]
    bridge_end = following_points[0]
    if not _bridge_is_supported_by_foreground(
        bridge_start,
        bridge_end,
        foreground_mask,
        required_ratio=foreground_ratio,
    ):
        return None

    current_tail = _endpoint_direction(current_points, at_end=True)
    following_head = _endpoint_direction(following_points, at_end=False)
    aligned_direction = _dot(current_tail, following_head)
    gap_direction = _unit_direction(bridge_start, bridge_end)
    if gap_direction == (0.0, 0.0):
        return None
    tail_gap_alignment = _dot(current_tail, gap_direction)
    head_gap_alignment = _dot(following_head, gap_direction)
    if (
        aligned_direction < float(min_direction_cos)
        or tail_gap_alignment > -float(min_opposite_gap_cos)
        or head_gap_alignment > -float(min_opposite_gap_cos)
    ):
        return None

    merged = _copy_segment(current)
    merged["points"] = list(current_points) + [bridge_end] + list(following_points[1:])
    merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
        following.get("source_segment_ids", ())
    )
    render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
        current,
        following,
        current_points=current_points,
        following_points=following_points,
    )
    merged["render_subpaths"] = render_subpaths
    merged["render_subpath_source_ids"] = render_subpath_source_ids
    merged["source"] = "consolidated_short_overlap"
    _refresh_geometry_metadata(merged)
    return merged


def _find_light_repair_merge_candidate(
    segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None,
    exact_gap_px: float,
    bridged_gap_px: float,
    exact_direction_cos_threshold: float,
    bridged_direction_cos_threshold: float,
    foreground_ratio: float,
    short_segment_max_length_px: float,
) -> tuple[int, int, dict[str, Any]] | None:
    best_candidate: tuple[float, float, int, int, dict[str, Any]] | None = None
    for first_index in range(len(segments)):
        first = segments[first_index]
        for second_index in range(first_index + 1, len(segments)):
            second = segments[second_index]
            oriented = _try_light_repair_merge_pair(
                first,
                second,
                foreground_mask=foreground_mask,
                exact_gap_px=exact_gap_px,
                bridged_gap_px=bridged_gap_px,
                exact_direction_cos_threshold=exact_direction_cos_threshold,
                bridged_direction_cos_threshold=bridged_direction_cos_threshold,
                foreground_ratio=foreground_ratio,
                short_segment_max_length_px=short_segment_max_length_px,
            )
            if oriented is None:
                continue
            gap, aligned_direction, merged = oriented
            key = (float(gap), -float(aligned_direction), first_index, second_index)
            if best_candidate is None or key < best_candidate[:4]:
                best_candidate = (*key, merged)
    if best_candidate is None:
        return None
    _, _, first_index, second_index, merged = best_candidate
    return first_index, second_index, merged


def _try_light_repair_merge_pair(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    foreground_mask: np.ndarray | None,
    exact_gap_px: float,
    bridged_gap_px: float,
    exact_direction_cos_threshold: float,
    bridged_direction_cos_threshold: float,
    foreground_ratio: float,
    short_segment_max_length_px: float,
) -> tuple[float, float, dict[str, Any]] | None:
    first_points = [tuple(_as_point(point)) for point in first.get("points", ())]
    second_points = [tuple(_as_point(point)) for point in second.get("points", ())]
    if len(first_points) < 2 or len(second_points) < 2:
        return None

    first_is_short = _polyline_length(first_points) <= short_segment_max_length_px
    second_is_short = _polyline_length(second_points) <= short_segment_max_length_px
    best_candidate: tuple[float, float, dict[str, Any]] | None = None
    for oriented_first in _candidate_point_orders(first_points):
        for oriented_second in _candidate_point_orders(second_points):
            gap = _distance(oriented_first[-1], oriented_second[0])
            first_tail = _endpoint_direction(oriented_first, at_end=True)
            second_head = _endpoint_direction(oriented_second, at_end=False)
            aligned_direction = _dot(first_tail, second_head)
            if gap <= exact_gap_px:
                if aligned_direction < exact_direction_cos_threshold:
                    continue
                if gap > 1e-9:
                    gap_direction = _unit_direction(oriented_first[-1], oriented_second[0])
                    if (
                        gap_direction == (0.0, 0.0)
                        or _dot(first_tail, gap_direction) < exact_direction_cos_threshold
                        or _dot(second_head, gap_direction) < exact_direction_cos_threshold
                    ):
                        continue
                    if (
                        foreground_mask is not None
                        and not _bridge_is_supported_by_foreground(
                            oriented_first[-1],
                            oriented_second[0],
                            foreground_mask,
                            required_ratio=foreground_ratio,
                        )
                    ):
                        continue
                merged = _merge_light_repair_pair(first, second, oriented_first, oriented_second)
            elif (
                gap <= bridged_gap_px
                and (first_is_short or second_is_short)
                and aligned_direction >= bridged_direction_cos_threshold
                and foreground_mask is not None
            ):
                gap_direction = _unit_direction(oriented_first[-1], oriented_second[0])
                if (
                    gap_direction == (0.0, 0.0)
                    or _dot(first_tail, gap_direction) < bridged_direction_cos_threshold
                    or _dot(second_head, gap_direction) < bridged_direction_cos_threshold
                    or not _bridge_is_supported_by_foreground(
                        oriented_first[-1],
                        oriented_second[0],
                        foreground_mask,
                        required_ratio=foreground_ratio,
                    )
                ):
                    continue
                merged = _merge_light_repair_pair(first, second, oriented_first, oriented_second)
            else:
                continue

            key = (float(gap), -float(aligned_direction))
            if best_candidate is None or key < (best_candidate[0], -best_candidate[1]):
                best_candidate = (float(gap), float(aligned_direction), merged)
    return best_candidate


def _candidate_point_orders(points: Sequence[Point]) -> list[list[Point]]:
    ordered = [list(points)]
    reversed_points = list(reversed(points))
    if reversed_points != ordered[0]:
        ordered.append(reversed_points)
    return ordered


def _merge_light_repair_pair(
    first: dict[str, Any],
    second: dict[str, Any],
    first_points: Sequence[Point],
    second_points: Sequence[Point],
) -> dict[str, Any]:
    merged = _copy_segment(first)
    if _distance(first_points[-1], second_points[0]) <= 1e-9:
        merged_points = list(first_points) + list(second_points[1:])
    else:
        merged_points = list(first_points) + [tuple(second_points[0])] + list(second_points[1:])
    merged["points"] = merged_points
    merged["component_id"] = int(min(first.get("component_id", 0) or 0, second.get("component_id", 0) or 0))
    merged["source_segment_ids"] = tuple(first.get("source_segment_ids", ())) + tuple(second.get("source_segment_ids", ()))
    render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
        first,
        second,
        current_points=first_points,
        following_points=second_points,
    )
    merged["render_subpaths"] = render_subpaths
    merged["render_subpath_source_ids"] = render_subpath_source_ids
    merged["source"] = "raw_light_repair"
    _refresh_geometry_metadata(merged)
    return merged


def _light_repair_center_straight_segment(
    points: Sequence[Point],
    segments: Sequence[dict[str, Any]],
    *,
    segment_index: int,
    foreground_mask: np.ndarray,
) -> list[Point] | None:
    point_list = [tuple(_as_point(point)) for point in points]
    if len(point_list) < DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_POINT_COUNT:
        return None
    axis_ratio = _principal_axis_ratio(point_list)
    if axis_ratio < DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_AXIS_RATIO:
        return None
    if _principal_axis_residual(point_list) > DEFAULT_LIGHT_REPAIR_GEOMETRY_MAX_AXIS_RESIDUAL_PX:
        return None

    total_dy = abs(float(point_list[-1][0]) - float(point_list[0][0]))
    total_dx = abs(float(point_list[-1][1]) - float(point_list[0][1]))
    dominant_span = max(total_dy, total_dx)
    minor_span = min(total_dy, total_dx)
    is_horizontal = total_dx > total_dy * DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_VERTICAL_TO_HORIZONTAL_RATIO
    if dominant_span <= 1e-6 or dominant_span < max(
        minor_span * DEFAULT_LIGHT_REPAIR_GEOMETRY_MIN_VERTICAL_TO_HORIZONTAL_RATIO,
        1e-6,
    ):
        return None
    if _light_repair_endpoint_connection_count(
        segments,
        segment_index=segment_index,
        point=point_list[0],
        tolerance_px=DEFAULT_LIGHT_REPAIR_GEOMETRY_CONNECTION_TOLERANCE_PX,
    ) <= 0 and _light_repair_endpoint_connection_count(
        segments,
        segment_index=segment_index,
        point=point_list[-1],
        tolerance_px=DEFAULT_LIGHT_REPAIR_GEOMETRY_CONNECTION_TOLERANCE_PX,
    ) <= 0:
        return None

    offsets: list[float | None] = []
    normals: list[Point | None] = []
    for index, point in enumerate(point_list):
        tangent = _local_tangent(point_list, index)
        norm = math.hypot(float(tangent[0]), float(tangent[1]))
        if norm <= 1e-9:
            offsets.append(None)
            normals.append(None)
            continue
        normal = (-float(tangent[1]) / norm, float(tangent[0]) / norm)
        normals.append(normal)
        sampled_offsets = _foreground_offsets_along_normal(
            point,
            normal,
            foreground_mask,
            radius_px=DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_RADIUS_PX,
            sample_step_px=DEFAULT_FOREGROUND_SNAP_STEP_PX,
        )
        if not sampled_offsets:
            offsets.append(None)
            continue
        run = _select_local_offset_run(sampled_offsets, step_px=DEFAULT_FOREGROUND_SNAP_STEP_PX)
        offsets.append(None if not run else float(0.5 * (run[0] + run[-1])))

    preserve = min(
        max(DEFAULT_LIGHT_REPAIR_GEOMETRY_ENDPOINT_PRESERVE_COUNT, 0),
        max(len(point_list) // 3, 0),
    )
    body_offsets = [offset for offset in offsets[preserve : len(offsets) - preserve] if offset is not None]
    if len(body_offsets) < max(len(point_list) // 3, 4):
        return _light_repair_center_partial_horizontal_run(
            point_list,
            offsets,
            normals,
            axis_ratio=axis_ratio,
            is_horizontal=is_horizontal,
        )

    median_offset = float(np.median(np.asarray(body_offsets, dtype=float)))
    if abs(median_offset) < DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_MIN_ABS_PX:
        return _light_repair_center_partial_horizontal_run(
            point_list,
            offsets,
            normals,
            axis_ratio=axis_ratio,
            is_horizontal=is_horizontal,
        )
    body_std = float(np.std(np.asarray(body_offsets, dtype=float)))
    sign = 1.0 if median_offset >= 0.0 else -1.0
    aligned_fraction = sum(1 for offset in body_offsets if sign * float(offset) >= 0.25) / float(len(body_offsets))
    if aligned_fraction < DEFAULT_LIGHT_REPAIR_GEOMETRY_SIGN_FRACTION_MIN:
        return _light_repair_center_partial_horizontal_run(
            point_list,
            offsets,
            normals,
            axis_ratio=axis_ratio,
            is_horizontal=is_horizontal,
        )
    if body_std > DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_STD_MAX_PX:
        if (
            body_std > DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_STD_RELAXED_MAX_PX
            or aligned_fraction < DEFAULT_LIGHT_REPAIR_GEOMETRY_SIGN_FRACTION_RELAXED_MIN
            or axis_ratio < DEFAULT_LIGHT_REPAIR_GEOMETRY_RELAXED_AXIS_RATIO
        ):
            return _light_repair_center_partial_horizontal_run(
                point_list,
                offsets,
                normals,
                axis_ratio=axis_ratio,
                is_horizontal=is_horizontal,
            )

    corrected: list[Point] = []
    for point, normal in zip(point_list, normals):
        if normal is None:
            corrected.append(point)
            continue
        corrected.append(
            (
                float(point[0]) + float(normal[0]) * median_offset,
                float(point[1]) + float(normal[1]) * median_offset,
            )
        )
    return corrected


def _light_repair_center_partial_horizontal_run(
    point_list: Sequence[Point],
    offsets: Sequence[float | None],
    normals: Sequence[Point | None],
    *,
    axis_ratio: float,
    is_horizontal: bool,
) -> list[Point] | None:
    if not is_horizontal or axis_ratio < DEFAULT_LIGHT_REPAIR_GEOMETRY_RELAXED_AXIS_RATIO:
        return None

    guard = min(
        max(DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_ENDPOINT_GUARD_COUNT, 0),
        max(len(point_list) // 4, 0),
    )
    if len(point_list) - 2 * guard < DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_MIN_RUN_POINTS:
        return None

    best_run: tuple[int, int, float, float] | None = None
    for sign in (1.0, -1.0):
        index = guard
        limit = len(point_list) - guard
        while index < limit:
            offset = offsets[index]
            normal = normals[index]
            if offset is None or normal is None or sign * float(offset) < DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_MIN_ABS_PX:
                index += 1
                continue

            start = index
            values: list[float] = []
            while index < limit:
                offset = offsets[index]
                normal = normals[index]
                if offset is None or normal is None or sign * float(offset) < DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_MIN_ABS_PX:
                    break
                values.append(float(offset))
                index += 1
            end = index - 1

            if len(values) < DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_MIN_RUN_POINTS:
                continue
            median_offset = float(np.median(np.asarray(values, dtype=float)))
            if abs(median_offset) < DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_MIN_ABS_PX:
                continue
            offset_std = float(np.std(np.asarray(values, dtype=float)))
            if offset_std > DEFAULT_LIGHT_REPAIR_GEOMETRY_OFFSET_STD_RELAXED_MAX_PX:
                continue

            run_score = (
                len(values),
                abs(median_offset),
                -offset_std,
            )
            best_score = (
                0,
                0.0,
                -float("inf"),
            )
            if best_run is not None:
                best_score = (
                    best_run[1] - best_run[0] + 1,
                    abs(best_run[2]),
                    -best_run[3],
                )
            if run_score > best_score:
                best_run = (start, end, median_offset, offset_std)

    if best_run is None:
        return None

    start, end, median_offset, _offset_std = best_run
    taper_points = max(DEFAULT_LIGHT_REPAIR_GEOMETRY_PARTIAL_TAPER_POINTS, 0)
    corrected: list[Point] = []
    for index, (point, normal) in enumerate(zip(point_list, normals)):
        if normal is None or index < start or index > end:
            corrected.append(tuple(_as_point(point)))
            continue
        if taper_points <= 0:
            weight = 1.0
        else:
            edge_distance = min(index - start, end - index)
            weight = min(1.0, float(edge_distance + 1) / float(taper_points + 1))
        corrected.append(
            (
                float(point[0]) + float(normal[0]) * median_offset * weight,
                float(point[1]) + float(normal[1]) * median_offset * weight,
            )
        )
    return corrected


def _light_repair_endpoint_connection_count(
    segments: Sequence[dict[str, Any]],
    *,
    segment_index: int,
    point: Point,
    tolerance_px: float,
) -> int:
    count = 0
    for index, segment in enumerate(segments):
        if index == segment_index:
            continue
        points = [tuple(_as_point(value)) for value in segment.get("points", ())]
        if not points:
            continue
        if _distance(points[0], point) <= tolerance_px or _distance(points[-1], point) <= tolerance_px:
            count += 1
    return count


def _propagate_light_repair_endpoint_move(
    segments: Sequence[dict[str, Any]],
    *,
    source_segment_index: int,
    original_point: Point,
    updated_point: Point,
    tolerance_px: float,
) -> None:
    for index, segment in enumerate(segments):
        if index == source_segment_index:
            continue
        points = [tuple(_as_point(point)) for point in segment.get("points", ())]
        if not points:
            continue
        changed = False
        if _distance(points[0], original_point) <= tolerance_px:
            points[0] = tuple(updated_point)
            changed = True
        if _distance(points[-1], original_point) <= tolerance_px:
            points[-1] = tuple(updated_point)
            changed = True
        if changed:
            segment["points"] = points
            _refresh_geometry_metadata(segment)


def _try_merge_collinear_gap(
    current: dict[str, Any],
    following: dict[str, Any],
    *,
    current_points: Sequence[Point] | None = None,
    following_points: Sequence[Point] | None = None,
    gap: float,
    foreground_mask: np.ndarray | None,
) -> dict[str, Any] | None:
    if foreground_mask is None or gap > DEFAULT_BRIDGED_MERGE_GAP_PX:
        return None

    current_points = list(current_points if current_points is not None else current.get("points", ()))
    following_points = list(
        following_points
        if following_points is not None
        else _orient_following_points_for_merge(current_points, following.get("points", ()))
    )
    if len(current_points) < 2 or len(following_points) < 2:
        return None

    current_tail = _endpoint_direction(current_points, at_end=True)
    following_head = _endpoint_direction(following_points, at_end=False)
    aligned_direction = _dot(current_tail, following_head)

    bridge_start = current_points[-1]
    bridge_end = following_points[0]
    gap_direction = _unit_direction(bridge_start, bridge_end)
    if gap_direction == (0.0, 0.0):
        return None
    if not _bridge_is_supported_by_foreground(
        bridge_start,
        bridge_end,
        foreground_mask,
        required_ratio=DEFAULT_BRIDGED_MERGE_FOREGROUND_RATIO,
    ):
        return None

    tail_gap_alignment = _dot(current_tail, gap_direction)
    head_gap_alignment = _dot(following_head, gap_direction)
    if (
        aligned_direction >= DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
        and tail_gap_alignment >= DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
        and head_gap_alignment >= DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
    ):
        merged = _copy_segment(current)
        merged["points"] = current_points + [bridge_end] + following_points[1:]
        merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
            following.get("source_segment_ids", ())
        )
        render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
            current,
            following,
            current_points=current_points,
            following_points=following_points,
        )
        merged["render_subpaths"] = render_subpaths
        merged["render_subpath_source_ids"] = render_subpath_source_ids
        merged["source"] = "consolidated_bridged"
        _refresh_geometry_metadata(merged)
        return merged

    if (
        aligned_direction >= DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
        and gap <= DEFAULT_ALIGNED_OVERLAP_GAP_PX
        and tail_gap_alignment <= -DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
        and head_gap_alignment <= -DEFAULT_BRIDGED_MERGE_DIRECTION_COS_THRESHOLD
    ):
        merged = _copy_segment(current)
        merged["points"] = current_points + following_points[1:]
        merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
            following.get("source_segment_ids", ())
        )
        render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
            current,
            following,
            current_points=current_points,
            following_points=following_points,
        )
        merged["render_subpaths"] = render_subpaths
        merged["render_subpath_source_ids"] = render_subpath_source_ids
        merged["source"] = "consolidated_overlap"
        _refresh_geometry_metadata(merged)
        return merged

    if (
        gap <= DEFAULT_CORNER_MERGE_GAP_PX
        and abs(aligned_direction) <= DEFAULT_CORNER_MERGE_DIRECTION_DOT_MAX
        and tail_gap_alignment >= DEFAULT_CORNER_MERGE_TAIL_GAP_COS_MIN
        and head_gap_alignment <= DEFAULT_CORNER_MERGE_HEAD_GAP_COS_MAX
    ):
        merged = _copy_segment(current)
        merged["points"] = current_points + [bridge_end] + following_points[1:]
        merged["source_segment_ids"] = tuple(current.get("source_segment_ids", ())) + tuple(
            following.get("source_segment_ids", ())
        )
        render_subpaths, render_subpath_source_ids = _build_render_subpaths_for_generic_merge(
            current,
            following,
            current_points=current_points,
            following_points=following_points,
        )
        merged["render_subpaths"] = render_subpaths
        merged["render_subpath_source_ids"] = render_subpath_source_ids
        merged["source"] = "consolidated_corner"
        _refresh_geometry_metadata(merged)
        return merged

    return None


def _orient_following_points_for_merge(
    current_points: Sequence[Point],
    following_points: Sequence[Point],
) -> list[Point]:
    current = [tuple(_as_point(point)) for point in current_points]
    following = [tuple(_as_point(point)) for point in following_points]
    if len(current) < 2 or len(following) < 2:
        return following

    current_end = current[-1]
    current_tail = _endpoint_direction(current, at_end=True)
    candidates = [following]
    reversed_following = list(reversed(following))
    if reversed_following != following:
        candidates.append(reversed_following)

    best_candidate = candidates[0]
    best_key: tuple[float, float, float, float] | None = None
    for candidate in candidates:
        gap = _distance(current_end, candidate[0])
        head = _endpoint_direction(candidate, at_end=False)
        key = (
            gap,
            -_dot(current_tail, head),
            float(candidate[0][0]),
            float(candidate[0][1]),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_candidate = candidate
    return best_candidate


def _rdp_simplify(points: Sequence[Point], tolerance: float) -> list[Point]:
    if len(points) <= 2 or tolerance <= 0:
        return list(points)

    first = points[0]
    last = points[-1]
    max_distance = -1.0
    split_index = -1
    for index in range(1, len(points) - 1):
        distance = _point_line_distance(points[index], first, last)
        if distance > max_distance:
            max_distance = distance
            split_index = index

    if max_distance <= tolerance:
        return [first, last]

    left = _rdp_simplify(points[: split_index + 1], tolerance)
    right = _rdp_simplify(points[split_index:], tolerance)
    return left[:-1] + right


def _resample_polyline(points: Sequence[Point], *, step_px: float | None) -> list[Point]:
    if step_px is None or step_px <= 0 or len(points) <= 1:
        return list(points)

    cumulative = [0.0]
    for start, end in zip(points[:-1], points[1:]):
        cumulative.append(cumulative[-1] + _distance(start, end))

    total_length = cumulative[-1]
    if total_length <= 1e-9:
        return [points[0], points[-1]] if len(points) > 1 else list(points)

    targets = [0.0]
    position = step_px
    while position < total_length:
        targets.append(position)
        position += step_px
    if targets[-1] != total_length:
        targets.append(total_length)

    resampled: list[Point] = []
    segment_index = 0
    for target in targets:
        while segment_index + 1 < len(cumulative) and cumulative[segment_index + 1] < target:
            segment_index += 1
        if segment_index + 1 >= len(cumulative):
            resampled.append(points[-1])
            continue
        start = points[segment_index]
        end = points[segment_index + 1]
        start_distance = cumulative[segment_index]
        end_distance = cumulative[segment_index + 1]
        span = end_distance - start_distance
        if span <= 1e-9:
            resampled.append(end)
            continue
        ratio = (target - start_distance) / span
        y = float(start[0]) + (float(end[0]) - float(start[0])) * ratio
        x = float(start[1]) + (float(end[1]) - float(start[1])) * ratio
        resampled.append((y, x))
    return resampled


def _point_line_distance(point: Point, start: Point, end: Point) -> float:
    dy = float(end[0]) - float(start[0])
    dx = float(end[1]) - float(start[1])
    denom = dy * dy + dx * dx
    if denom <= 1e-12:
        return _distance(point, start)
    t = ((float(point[0]) - float(start[0])) * dy + (float(point[1]) - float(start[1])) * dx) / denom
    proj_y = float(start[0]) + dy * t
    proj_x = float(start[1]) + dx * t
    return math.hypot(float(point[0]) - proj_y, float(point[1]) - proj_x)


def _snap_polyline_to_foreground_midline(
    points: Sequence[Point],
    foreground_mask: np.ndarray,
    *,
    radius_px: float,
    sample_step_px: float = DEFAULT_FOREGROUND_SNAP_STEP_PX,
) -> tuple[list[Point], int]:
    if len(points) <= 1:
        return list(points), 0

    mask = np.asarray(foreground_mask, dtype=bool)
    if mask.ndim != 2 or not bool(mask.any()):
        return list(points), 0

    normals: list[Point | None] = []
    target_offsets: list[float | None] = []
    run_widths: list[float | None] = []
    for index, point in enumerate(points):
        tangent = _local_tangent(points, index)
        norm = math.hypot(float(tangent[0]), float(tangent[1]))
        if norm <= 1e-9:
            normals.append(None)
            target_offsets.append(None)
            run_widths.append(None)
            continue
        normal = (-float(tangent[1]) / norm, float(tangent[0]) / norm)
        normals.append(normal)
        sampled_offsets = _foreground_offsets_along_normal(
            point,
            normal,
            mask,
            radius_px=radius_px,
            sample_step_px=sample_step_px,
        )
        if not sampled_offsets:
            target_offsets.append(None)
            run_widths.append(None)
            continue
        selected_run = _select_local_offset_run(sampled_offsets, step_px=sample_step_px)
        if not selected_run:
            target_offsets.append(None)
            run_widths.append(None)
            continue
        target_offsets.append(0.5 * (selected_run[0] + selected_run[-1]))
        run_widths.append(float(selected_run[-1] - selected_run[0]))

    filtered_offsets = _filter_ambiguous_snap_offsets(
        target_offsets,
        run_widths,
        width_factor=DEFAULT_FOREGROUND_SNAP_WIDTH_FACTOR,
        extra_margin_px=DEFAULT_FOREGROUND_SNAP_WIDTH_MARGIN_PX,
    )
    interpolated_offsets = _interpolate_optional_offsets(filtered_offsets)
    smoothed_offsets = _smooth_optional_offsets(interpolated_offsets, window=DEFAULT_FOREGROUND_SNAP_SMOOTHING_WINDOW)
    snapped: list[Point] = []
    moved_count = 0
    for point, normal, target_offset in zip(points, normals, smoothed_offsets):
        if normal is None or target_offset is None:
            snapped.append(point)
            continue
        shifted = (float(point[0]) + normal[0] * target_offset, float(point[1]) + normal[1] * target_offset)
        snapped.append(shifted)
        if _distance(point, shifted) > 1e-6:
            moved_count += 1
    return snapped, moved_count


def _should_skip_foreground_snap(
    segment: dict[str, Any],
    *,
    max_prior_distance_px: float = DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MAX_DISTANCE_PX,
    min_support_ratio: float = DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MIN_SUPPORT_RATIO,
    max_turn_cos: float = DEFAULT_PRIOR_ALIGNED_SNAP_SKIP_MAX_TURN_COS,
) -> bool:
    source_ids = tuple(segment.get("source_segment_ids", ()))
    if len(source_ids) <= 1:
        return False
    points = segment.get("points", ())
    prior_distance = segment.get("makemeahanzi_prior_subpath_mean_distance_px")
    support_ratio = segment.get("makemeahanzi_foreground_support_ratio_r1")
    if prior_distance is None or support_ratio is None:
        return False

    if (
        float(prior_distance) <= float(max_prior_distance_px)
        and float(support_ratio) >= float(min_support_ratio)
        and _min_polyline_turn_cos(points) <= float(max_turn_cos)
    ):
        return True
    return _is_straight_prior_aligned_segment(segment)


def _is_straight_prior_aligned_segment(
    segment: dict[str, Any],
    *,
    max_prior_distance_px: float = DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MAX_DISTANCE_PX,
    min_support_ratio: float = DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MIN_SUPPORT_RATIO,
    min_axis_ratio: float = DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MIN_AXIS_RATIO,
    max_axis_residual_px: float = DEFAULT_PRIOR_STRAIGHT_SNAP_SKIP_MAX_AXIS_RESIDUAL_PX,
) -> bool:
    source_ids = tuple(segment.get("source_segment_ids", ()))
    if len(source_ids) <= 1:
        return False
    points = np.asarray(segment.get("points", ()), dtype=float)
    if len(points) < 2:
        return False
    prior_distance = segment.get("makemeahanzi_prior_subpath_mean_distance_px")
    support_ratio = segment.get("makemeahanzi_foreground_support_ratio_r1")
    if prior_distance is None or support_ratio is None:
        return False
    return (
        float(prior_distance) <= float(max_prior_distance_px)
        and float(support_ratio) >= float(min_support_ratio)
        and _principal_axis_ratio(points) >= float(min_axis_ratio)
        and _principal_axis_residual(points) <= float(max_axis_residual_px)
    )


def _local_snap_weights_for_straight_prior_segment(
    segment: dict[str, Any],
    all_segments: Sequence[dict[str, Any]],
    *,
    segment_index: int,
    full_distance_px: float = DEFAULT_LOCAL_FOREGROUND_SNAP_FULL_DISTANCE_PX,
    taper_distance_px: float = DEFAULT_LOCAL_FOREGROUND_SNAP_TAPER_DISTANCE_PX,
    smoothing_window: int = DEFAULT_LOCAL_FOREGROUND_SNAP_WEIGHT_SMOOTHING_WINDOW,
) -> list[float] | None:
    points = np.asarray(segment.get("points", ()), dtype=float)
    if not _is_straight_prior_aligned_segment(segment):
        return None

    foreign_points = [
        np.asarray(other.get("points", ()), dtype=float)
        for index, other in enumerate(all_segments)
        if index != segment_index and len(other.get("points", ())) > 0
    ]
    if not foreign_points:
        return None
    foreign = np.vstack(foreign_points)
    distances = np.sqrt(((points[:, None, :] - foreign[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    weights = np.clip(
        (float(taper_distance_px) - distances) / max(float(taper_distance_px) - float(full_distance_px), 1e-6),
        0.0,
        1.0,
    )
    weights[distances <= float(full_distance_px)] = 1.0
    smoothed = _smooth_scalar_values(weights.tolist(), window=smoothing_window)
    if max(smoothed, default=0.0) <= 1e-3:
        return None
    return smoothed


def _min_polyline_turn_cos(points: Sequence[Point]) -> float:
    pts = [tuple(_as_point(point)) for point in points]
    min_cos = 1.0
    for previous, current, following in zip(pts[:-2], pts[1:-1], pts[2:]):
        first = (float(current[0]) - float(previous[0]), float(current[1]) - float(previous[1]))
        second = (float(following[0]) - float(current[0]), float(following[1]) - float(current[1]))
        first_norm = math.hypot(first[0], first[1])
        second_norm = math.hypot(second[0], second[1])
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = (first[0] * second[0] + first[1] * second[1]) / (first_norm * second_norm)
        min_cos = min(min_cos, float(cosine))
    return float(min_cos)


def _principal_axis_residual(points: Sequence[Point]) -> float:
    pts = np.asarray([_as_point(point) for point in points], dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    return float(np.mean(np.abs(centered @ vh[-1])))


def _principal_axis_ratio(points: Sequence[Point]) -> float:
    pts = np.asarray([_as_point(point) for point in points], dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    if len(singular_values) == 0:
        return 0.0
    return float(singular_values[0] / max(float(singular_values[-1]), 1e-6))


def _blend_polyline_points(
    original_points: Sequence[Point],
    snapped_points: Sequence[Point],
    weights: Sequence[float],
) -> tuple[list[Point], int]:
    blended: list[Point] = []
    moved_count = 0
    for original, snapped, weight in zip(original_points, snapped_points, weights):
        clipped_weight = min(max(float(weight), 0.0), 1.0)
        point = (
            float(original[0]) * (1.0 - clipped_weight) + float(snapped[0]) * clipped_weight,
            float(original[1]) * (1.0 - clipped_weight) + float(snapped[1]) * clipped_weight,
        )
        blended.append(point)
        if _distance(original, point) > 1e-6:
            moved_count += 1
    return blended, moved_count


def _smooth_scalar_values(values: Sequence[float], *, window: int) -> list[float]:
    if window <= 1:
        return [float(value) for value in values]
    radius = max(window // 2, 0)
    smoothed: list[float] = []
    for index in range(len(values)):
        weighted_sum = 0.0
        total_weight = 0.0
        for neighbor in range(max(0, index - radius), min(len(values), index + radius + 1)):
            weight = float(radius + 1 - abs(neighbor - index))
            weighted_sum += float(values[neighbor]) * weight
            total_weight += weight
        smoothed.append(weighted_sum / total_weight if total_weight > 0 else float(values[index]))
    return smoothed


def _foreground_offsets_along_normal(
    point: Point,
    normal: Point,
    foreground_mask: np.ndarray,
    *,
    radius_px: float,
    sample_step_px: float,
) -> list[float]:
    height, width = foreground_mask.shape
    offsets: list[float] = []
    steps = int(math.floor(radius_px / sample_step_px))
    for step_index in range(-steps, steps + 1):
        offset = step_index * sample_step_px
        y = float(point[0]) + float(normal[0]) * offset
        x = float(point[1]) + float(normal[1]) * offset
        iy = int(round(y))
        ix = int(round(x))
        if 0 <= iy < height and 0 <= ix < width and bool(foreground_mask[iy, ix]):
            offsets.append(offset)
    return offsets


def _bridge_is_supported_by_foreground(
    start: Point,
    end: Point,
    foreground_mask: np.ndarray,
    *,
    required_ratio: float,
) -> bool:
    samples = _sample_line_points(start, end)
    if not samples:
        return False
    height, width = foreground_mask.shape
    supported = 0
    for y, x in samples:
        iy = int(round(y))
        ix = int(round(x))
        if 0 <= iy < height and 0 <= ix < width and bool(foreground_mask[iy, ix]):
            supported += 1
    return (supported / float(len(samples))) >= required_ratio


def _sample_line_points(start: Point, end: Point) -> list[Point]:
    distance = _distance(start, end)
    if distance <= 1e-9:
        return [start]
    steps = max(int(math.ceil(distance)), 1)
    points: list[Point] = []
    for step in range(steps + 1):
        ratio = step / float(steps)
        y = float(start[0]) + (float(end[0]) - float(start[0])) * ratio
        x = float(start[1]) + (float(end[1]) - float(start[1])) * ratio
        points.append((y, x))
    return points


def _attach_supported_cross_component_corners(
    segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray | None,
    max_gap_px: float = DEFAULT_CORNER_ATTACHMENT_GAP_PX,
    foreground_ratio: float = DEFAULT_CORNER_ATTACHMENT_FOREGROUND_RATIO,
) -> tuple[list[dict[str, Any]], int]:
    attached = [_copy_segment(segment) for segment in segments]
    if (
        foreground_mask is None
        or max_gap_px <= 0
        or len(attached) < 2
        or not bool(np.asarray(foreground_mask, dtype=bool).any())
    ):
        return attached, 0

    mask = np.asarray(foreground_mask, dtype=bool)
    candidates: list[dict[str, Any]] = []
    for first_index, first in enumerate(attached):
        first_points = [tuple(_as_point(point)) for point in first.get("points", ())]
        if len(first_points) < 2:
            continue
        for second_index in range(first_index + 1, len(attached)):
            second = attached[second_index]
            if first.get("component_id") == second.get("component_id"):
                continue
            second_points = [tuple(_as_point(point)) for point in second.get("points", ())]
            if len(second_points) < 2:
                continue
            candidates.extend(
                _corner_attachment_candidates_for_pair(
                    first_index,
                    first_points,
                    second_index,
                    second_points,
                    foreground_mask=mask,
                    max_gap_px=max_gap_px,
                    foreground_ratio=foreground_ratio,
                )
            )

    candidates.sort(
        key=lambda candidate: (
            float(candidate["gap_px"]),
            float(candidate["direction_dot"]),
            -float(min(candidate["support_a"], candidate["support_b"])),
            int(candidate["first_index"]),
            int(candidate["second_index"]),
        )
    )

    used_endpoints: set[tuple[int, str]] = set()
    attachment_count = 0
    for candidate in candidates:
        first_key = (int(candidate["first_index"]), str(candidate["first_endpoint"]))
        second_key = (int(candidate["second_index"]), str(candidate["second_endpoint"]))
        if first_key in used_endpoints or second_key in used_endpoints:
            continue
        shared_point = _select_corner_attachment_point(
            candidate["first_point"],
            candidate["second_point"],
            support_a=float(candidate["support_a"]),
            support_b=float(candidate["support_b"]),
            foreground_mask=mask,
        )
        _set_segment_endpoint(
            attached[int(candidate["first_index"])],
            endpoint=str(candidate["first_endpoint"]),
            point=shared_point,
        )
        _set_segment_endpoint(
            attached[int(candidate["second_index"])],
            endpoint=str(candidate["second_endpoint"]),
            point=shared_point,
        )
        _propagate_light_repair_endpoint_move(
            attached,
            source_segment_index=int(candidate["first_index"]),
            original_point=candidate["first_point"],
            updated_point=shared_point,
            tolerance_px=DEFAULT_CORNER_ATTACHMENT_CONNECTION_TOLERANCE_PX,
        )
        _propagate_light_repair_endpoint_move(
            attached,
            source_segment_index=int(candidate["second_index"]),
            original_point=candidate["second_point"],
            updated_point=shared_point,
            tolerance_px=DEFAULT_CORNER_ATTACHMENT_CONNECTION_TOLERANCE_PX,
        )
        used_endpoints.add(first_key)
        used_endpoints.add(second_key)
        attachment_count += 1

    return attached, attachment_count


def _corner_attachment_candidates_for_pair(
    first_index: int,
    first_points: Sequence[Point],
    second_index: int,
    second_points: Sequence[Point],
    *,
    foreground_mask: np.ndarray,
    max_gap_px: float,
    foreground_ratio: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    endpoint_specs = (("start", 0), ("end", -1))
    for first_endpoint, first_point_index in endpoint_specs:
        first_point = tuple(_as_point(first_points[first_point_index]))
        first_tangent = _local_tangent(first_points, 0 if first_endpoint == "start" else len(first_points) - 1)
        for second_endpoint, second_point_index in endpoint_specs:
            second_point = tuple(_as_point(second_points[second_point_index]))
            gap = _distance(first_point, second_point)
            if gap <= 1e-9 or gap > max_gap_px:
                continue
            if not _bridge_is_supported_by_foreground(
                first_point,
                second_point,
                foreground_mask,
                required_ratio=foreground_ratio,
            ):
                continue
            second_tangent = _local_tangent(second_points, 0 if second_endpoint == "start" else len(second_points) - 1)
            direction_dot = abs(_dot(first_tangent, second_tangent))
            direction_dot_limit = (
                DEFAULT_CORNER_ATTACHMENT_MATCHED_ENDPOINT_DIRECTION_DOT_MAX
                if first_endpoint == second_endpoint
                else DEFAULT_CORNER_ATTACHMENT_MIXED_ENDPOINT_DIRECTION_DOT_MAX
            )
            if direction_dot > direction_dot_limit:
                continue
            candidates.append(
                {
                    "first_index": first_index,
                    "first_endpoint": first_endpoint,
                    "first_point": first_point,
                    "second_index": second_index,
                    "second_endpoint": second_endpoint,
                    "second_point": second_point,
                    "gap_px": gap,
                    "direction_dot": direction_dot,
                    "support_a": _foreground_support_ratio_in_radius(
                        first_point,
                        foreground_mask,
                        radius_px=DEFAULT_CORNER_ATTACHMENT_SUPPORT_RADIUS_PX,
                    ),
                    "support_b": _foreground_support_ratio_in_radius(
                        second_point,
                        foreground_mask,
                        radius_px=DEFAULT_CORNER_ATTACHMENT_SUPPORT_RADIUS_PX,
                    ),
                }
            )
    return candidates


def _select_corner_attachment_point(
    first_point: Point,
    second_point: Point,
    *,
    support_a: float,
    support_b: float,
    foreground_mask: np.ndarray,
) -> Point:
    if support_a >= support_b + DEFAULT_CORNER_ATTACHMENT_SUPPORT_ADVANTAGE:
        return tuple(first_point)
    if support_b >= support_a + DEFAULT_CORNER_ATTACHMENT_SUPPORT_ADVANTAGE:
        return tuple(second_point)
    midpoint = (
        (float(first_point[0]) + float(second_point[0])) / 2.0,
        (float(first_point[1]) + float(second_point[1])) / 2.0,
    )
    if _point_is_foreground(midpoint, foreground_mask):
        return midpoint
    return tuple(first_point if support_a >= support_b else second_point)


def _set_segment_endpoint(
    segment: dict[str, Any],
    *,
    endpoint: str,
    point: Point,
) -> None:
    points = [tuple(_as_point(value)) for value in segment.get("points", ())]
    if not points:
        return
    if endpoint == "start":
        points[0] = tuple(point)
    else:
        points[-1] = tuple(point)
    segment["points"] = points
    _refresh_geometry_metadata(segment)


def _foreground_support_ratio_in_radius(
    point: Point,
    foreground_mask: np.ndarray,
    *,
    radius_px: float,
) -> float:
    if radius_px <= 0:
        return 1.0 if _point_is_foreground(point, foreground_mask) else 0.0
    height, width = foreground_mask.shape
    py = float(point[0])
    px = float(point[1])
    radius = int(math.ceil(radius_px))
    total = 0
    supported = 0
    for iy in range(max(0, int(math.floor(py)) - radius), min(height, int(math.ceil(py)) + radius + 1)):
        for ix in range(max(0, int(math.floor(px)) - radius), min(width, int(math.ceil(px)) + radius + 1)):
            if ((float(iy) - py) ** 2 + (float(ix) - px) ** 2) > (radius_px ** 2 + 1e-6):
                continue
            total += 1
            if bool(foreground_mask[iy, ix]):
                supported += 1
    return float(supported) / float(total) if total > 0 else 0.0


def _point_is_foreground(point: Point, foreground_mask: np.ndarray) -> bool:
    iy = int(round(float(point[0])))
    ix = int(round(float(point[1])))
    height, width = foreground_mask.shape
    return 0 <= iy < height and 0 <= ix < width and bool(foreground_mask[iy, ix])


def _select_local_offset_run(offsets: Sequence[float], *, step_px: float) -> list[float]:
    if not offsets:
        return []

    runs: list[list[float]] = [[float(offsets[0])]]
    for offset in offsets[1:]:
        if float(offset) - runs[-1][-1] <= step_px * 1.5:
            runs[-1].append(float(offset))
        else:
            runs.append([float(offset)])

    containing_zero = [run for run in runs if run[0] - 1e-9 <= 0.0 <= run[-1] + 1e-9]
    if containing_zero:
        return max(containing_zero, key=len)
    return min(runs, key=lambda run: min(abs(run[0]), abs(run[-1]), abs(0.5 * (run[0] + run[-1]))))


def _filter_ambiguous_snap_offsets(
    offsets: Sequence[float | None],
    run_widths: Sequence[float | None],
    *,
    width_factor: float,
    extra_margin_px: float,
) -> list[float | None]:
    valid_widths = [float(width) for width in run_widths if width is not None]
    if not valid_widths:
        return list(offsets)
    reference_width = float(np.median(np.asarray(valid_widths, dtype=float)))
    max_allowed_width = max(reference_width * width_factor, reference_width + extra_margin_px)

    filtered: list[float | None] = []
    for offset, width in zip(offsets, run_widths):
        if offset is None or width is None:
            filtered.append(None)
            continue
        filtered.append(None if float(width) > max_allowed_width else float(offset))
    return filtered


def _interpolate_optional_offsets(offsets: Sequence[float | None]) -> list[float | None]:
    if not offsets:
        return []
    filled = list(offsets)
    valid_indices = [index for index, value in enumerate(filled) if value is not None]
    if not valid_indices:
        return filled

    first_valid = valid_indices[0]
    for index in range(0, first_valid):
        filled[index] = filled[first_valid]

    last_valid = valid_indices[-1]
    for index in range(last_valid + 1, len(filled)):
        filled[index] = filled[last_valid]

    previous_valid = first_valid
    for current_valid in valid_indices[1:]:
        gap = current_valid - previous_valid
        if gap > 1:
            start_value = float(filled[previous_valid])
            end_value = float(filled[current_valid])
            for step in range(1, gap):
                ratio = step / float(gap)
                filled[previous_valid + step] = start_value + (end_value - start_value) * ratio
        previous_valid = current_valid
    return filled


def _smooth_optional_offsets(offsets: Sequence[float | None], *, window: int) -> list[float | None]:
    if window <= 1:
        return list(offsets)
    radius = max(window // 2, 0)
    smoothed: list[float | None] = []
    for index, value in enumerate(offsets):
        if value is None:
            smoothed.append(None)
            continue
        weighted_sum = 0.0
        total_weight = 0.0
        for neighbor in range(max(0, index - radius), min(len(offsets), index + radius + 1)):
            neighbor_value = offsets[neighbor]
            if neighbor_value is None:
                continue
            weight = float(radius + 1 - abs(neighbor - index))
            weighted_sum += float(neighbor_value) * weight
            total_weight += weight
        smoothed.append(weighted_sum / total_weight if total_weight > 0 else value)
    return smoothed


def _stitch_small_internal_same_component_gaps(
    segments: Sequence[dict[str, Any]],
    *,
    max_gap_px: float,
    foreground_mask: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    stitched = [_copy_segment(segment) for segment in segments]
    if max_gap_px <= 0:
        return stitched
    component_ids = {segment.get("component_id") for segment in stitched}
    if len(component_ids) <= 1:
        return stitched

    for previous, current in zip(stitched[:-1], stitched[1:]):
        previous_points = list(previous.get("points", ()))
        current_points = list(current.get("points", ()))
        if (
            not previous_points
            or not current_points
            or previous.get("component_id") != current.get("component_id")
        ):
            continue
        gap = _distance(previous_points[-1], current_points[0])
        if gap > max_gap_px:
            if (
                foreground_mask is None
                or gap > DEFAULT_INTERNAL_STITCH_BRIDGED_GAP_PX
                or not _bridge_is_supported_by_foreground(
                    previous_points[-1],
                    current_points[0],
                    foreground_mask,
                    required_ratio=DEFAULT_INTERNAL_STITCH_FOREGROUND_RATIO,
                )
            ):
                continue
            gap_direction = _unit_direction(previous_points[-1], current_points[0])
            if gap_direction == (0.0, 0.0):
                continue
            previous_tail = _local_tangent(previous_points, len(previous_points) - 1)
            current_head = _local_tangent(current_points, 0)
            if (
                _dot(previous_tail, gap_direction) < DEFAULT_INTERNAL_STITCH_DIRECTION_COS_MIN
                or _dot(current_head, gap_direction) < DEFAULT_INTERNAL_STITCH_DIRECTION_COS_MIN
            ):
                continue
        current_points[0] = tuple(previous_points[-1])
        current["points"] = current_points
        _refresh_geometry_metadata(current)
    return stitched


def _local_tangent(points: Sequence[Point], index: int) -> Point:
    if len(points) <= 1:
        return (0.0, 0.0)
    current = points[index]
    previous = points[index - 1] if index > 0 else current
    following = points[index + 1] if index + 1 < len(points) else current
    dy = float(following[0]) - float(previous[0])
    dx = float(following[1]) - float(previous[1])
    norm = math.hypot(dy, dx)
    if norm <= 1e-12:
        return (0.0, 0.0)
    return (dy / norm, dx / norm)


def _unit_direction(start: Point, end: Point) -> Point:
    dy = float(end[0] - start[0])
    dx = float(end[1] - start[1])
    norm = math.hypot(dy, dx)
    if norm <= 1e-12:
        return (0.0, 0.0)
    return (dy / norm, dx / norm)


def _refresh_geometry_metadata(segment: dict[str, Any]) -> None:
    points = [tuple(_as_point(point)) for point in segment.get("points", ())]
    segment["points"] = points
    segment["length_px"] = _polyline_length(points)
    segment["pixel_count"] = len(points)
    if points:
        segment["start"] = points[0]
        segment["end"] = points[-1]


def _copy_segment(segment: dict[str, Any]) -> dict[str, Any]:
    copied = dict(segment)
    copied["source_segment_ids"] = tuple(copied.get("source_segment_ids", ()))
    copied["points"] = [tuple(_as_point(point)) for point in copied.get("points", ())]
    if "render_subpaths" in copied:
        copied["render_subpaths"] = [
            [tuple(_as_point(point)) for point in subpath]
            for subpath in copied.get("render_subpaths", ())
        ]
    if "render_subpath_source_ids" in copied:
        copied["render_subpath_source_ids"] = [
            tuple(source_ids)
            for source_ids in copied.get("render_subpath_source_ids", ())
        ]
    _refresh_geometry_metadata(copied)
    return copied


def _endpoint_direction(points: Sequence[Point], *, at_end: bool) -> Point:
    if len(points) < 2:
        return (0.0, 0.0)
    if at_end:
        end = points[-1]
        start = points[max(0, len(points) - 1 - ENDPOINT_DIRECTION_SAMPLE_STEPS)]
    else:
        start = points[0]
        end = points[min(len(points) - 1, ENDPOINT_DIRECTION_SAMPLE_STEPS)]
    dy = float(end[0] - start[0])
    dx = float(end[1] - start[1])
    norm = math.hypot(dy, dx)
    if norm <= 1e-12:
        return (0.0, 0.0)
    return (dy / norm, dx / norm)


def _as_point(point: Iterable[Any]) -> Point:
    y, x = point
    return (float(y), float(x))


def _polyline_length(points: Sequence[Point]) -> float:
    return sum(_distance(start, end) for start, end in zip(points[:-1], points[1:]))


def _distance(first: Point, second: Point) -> float:
    return math.hypot(float(first[0] - second[0]), float(first[1] - second[1]))


def _dot(first: Point, second: Point) -> float:
    return float(first[0] * second[0] + first[1] * second[1])
