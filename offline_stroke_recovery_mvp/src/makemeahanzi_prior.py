"""Light MakeMeAHanzi structural priors for offline stroke regrouping."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np


DEFAULT_GRAPHICS_PATH = Path("code") / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_SAMPLE_CHAR_ALIASES = {
    "kou": "口",
    "shi": "十",
    "xin": "心",
    "yi": "一",
    "yong": "永",
    "zhong": "中",
}
DEFAULT_SUPPORT_THRESHOLD = 0.6
DEFAULT_OVERLAP_TOLERANCE_PX = 2.0
DEFAULT_ALIGNMENT_PENALTY_WEIGHT = 8.0
DEFAULT_POINT_ALIGNMENT_PENALTY_WEIGHT = 4.0
DEFAULT_OVERLAP_APPEND_MAX_GAP_PX = 6.0
DEFAULT_OVERLAP_APPEND_DIRECTION_COS_MIN = -0.3
DEFAULT_SHARP_LEAD_IN_DIRECTION_COS_MAX = 0.7
DEFAULT_SHARP_LEAD_IN_LENGTH_RATIO_MAX = 0.55
DEFAULT_SHARP_LEAD_IN_MAX_LENGTH_PX = 28.0
DEFAULT_SHARP_LEAD_IN_MIN_MAIN_LENGTH_PX = 20.0
DEFAULT_GEOMETRY_REGULARIZATION_BLEND = 0.82
DEFAULT_GEOMETRY_REGULARIZATION_MAX_DISTANCE_PX = 9.0
DEFAULT_GEOMETRY_REGULARIZATION_MIN_SUPPORT_RATIO = 0.5
DEFAULT_GEOMETRY_REGULARIZATION_MIN_CHANGED_NORM = 0.15
DEFAULT_GEOMETRY_REGULARIZATION_MIN_PATH_RATIO = 1.04
DEFAULT_GEOMETRY_REGULARIZATION_MIN_PATH_RATIO_FOR_MERGED = 1.01
DEFAULT_GEOMETRY_REGULARIZATION_SUPPORT_RADIUS_PX = 4
DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_LENGTH_PX = 12.0
DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_ARC_FRACTION = 0.08
DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_ALIGNMENT = 0.8
DEFAULT_LOCAL_BLOB_EXTENSION_MAX_PATH_LENGTH_PX = 10.0
DEFAULT_LOCAL_BLOB_EXTENSION_MIN_POINT_COUNT = 4
DEFAULT_LOCAL_BLOB_EXTENSION_MIN_COMPONENT_PIXELS = 24
DEFAULT_LOCAL_BLOB_EXTENSION_MAX_COMPONENT_PIXELS = 220
DEFAULT_LOCAL_BLOB_EXTENSION_MAX_MINOR_SPAN_PX = 10.0
DEFAULT_LOCAL_BLOB_EXTENSION_MIN_BLOB_ASPECT_RATIO = 1.8
DEFAULT_LOCAL_BLOB_EXTENSION_MIN_ALIGNMENT = 0.92
DEFAULT_LOCAL_BLOB_EXTENSION_MAX_COVERAGE_RATIO = 0.4
DEFAULT_LOCAL_BLOB_EXTENSION_TARGET_COVERAGE_RATIO = 0.56
DEFAULT_LOCAL_BLOB_EXTENSION_MAX_EXPANSION_RATIO = 1.9
DEFAULT_LOCAL_BLOB_EXTENSION_TRIM_FRACTION = 0.08
DEFAULT_LOCAL_BLOB_EXTENSION_SUPPORT_RADIUS_PX = 2
DEFAULT_LOCAL_BLOB_EXTENSION_MIN_SUPPORT_RATIO = 0.9
ENDPOINT_DIRECTION_SAMPLE_STEPS = 4
DEFAULT_MIN_PRIOR_RUN_POINTS = 3


@dataclass
class GlyphKnowledge:
    char: str
    medians: list[np.ndarray]

    @property
    def stroke_count(self) -> int:
        return len(self.medians)


class MakeMeAHanziKnowledge:
    def __init__(self, graphics_path: Path | str):
        self.graphics_path = Path(graphics_path)
        if not self.graphics_path.exists():
            raise FileNotFoundError(f"makemeahanzi graphics.txt not found: {self.graphics_path}")

    def get_glyph(self, char: str) -> GlyphKnowledge:
        for line in self.graphics_path.open(encoding="utf-8"):
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("character") != char:
                continue
            medians = [np.asarray(points, dtype=float) for points in item.get("medians", [])]
            medians = [points for points in medians if points.ndim == 2 and points.shape[1] == 2 and len(points) > 0]
            return GlyphKnowledge(char=char, medians=medians)
        raise KeyError(f"Character not found in makemeahanzi graphics: {char}")


def resolve_sample_char(sample_name: str, sample_char_map: dict[str, str] | None = None) -> str | None:
    sample = str(sample_name).strip()
    if not sample:
        return None
    if sample_char_map and sample in sample_char_map:
        return str(sample_char_map[sample])
    if len(sample) == 1:
        return sample
    return DEFAULT_SAMPLE_CHAR_ALIASES.get(sample)


def normalize_medians_to_canvas(
    medians_xy: Sequence[np.ndarray],
    *,
    canvas_shape: tuple[int, int],
    margin_ratio: float = 0.08,
) -> list[np.ndarray]:
    xs: list[float] = []
    ys: list[float] = []
    for stroke in medians_xy:
        if len(stroke):
            xs.extend(stroke[:, 0].tolist())
            ys.extend(stroke[:, 1].tolist())
    if not xs or not ys:
        return []

    height, width = canvas_shape
    image_size = float(min(height, width))
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, 1.0)
    margin = image_size * float(margin_ratio)
    scale = (image_size - 2.0 * margin) / span
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    out: list[np.ndarray] = []
    for stroke in medians_xy:
        pts = np.asarray(stroke, dtype=float)
        mapped = np.empty_like(pts, dtype=float)
        mapped[:, 0] = float(height) / 2.0 - (pts[:, 1] - cy) * scale
        mapped[:, 1] = (pts[:, 0] - cx) * scale + float(width) / 2.0
        out.append(mapped)
    return out


def regroup_ordered_segments_by_makemeahanzi(
    ordered_segments: Sequence[dict[str, Any]],
    *,
    sample_name: str,
    canvas_shape: tuple[int, int],
    foreground_mask: np.ndarray | None,
    graphics_path: Path | str = DEFAULT_GRAPHICS_PATH,
    sample_char_map: dict[str, str] | None = None,
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD,
    overlap_tolerance_px: float = DEFAULT_OVERLAP_TOLERANCE_PX,
    alignment_penalty_weight: float = DEFAULT_ALIGNMENT_PENALTY_WEIGHT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    char = resolve_sample_char(sample_name, sample_char_map=sample_char_map)
    base_meta: dict[str, Any] = {
        "makemeahanzi_prior_available": False,
        "makemeahanzi_prior_applied": False,
        "makemeahanzi_char": char,
        "makemeahanzi_target_stroke_count": 0,
        "makemeahanzi_grouped_segment_count": len(ordered_segments),
        "makemeahanzi_supported_bridge_count": 0,
        "makemeahanzi_rejected_bridge_count": 0,
        "makemeahanzi_skipped_contained_segment_count": 0,
        "makemeahanzi_merged_group_count": 0,
        "makemeahanzi_geometry_regularized_segment_count": 0,
        "makemeahanzi_local_blob_extended_segment_count": 0,
    }
    copied = [_copy_segment(segment) for segment in ordered_segments]
    if char is None:
        return copied, base_meta

    try:
        prior_strokes = normalize_medians_to_canvas(
            MakeMeAHanziKnowledge(graphics_path).get_glyph(char).medians,
            canvas_shape=canvas_shape,
        )
    except (FileNotFoundError, KeyError):
        return copied, base_meta
    if not prior_strokes:
        return copied, base_meta

    regrouped, regroup_meta = regroup_ordered_segments_by_prior_strokes(
        copied,
        prior_strokes,
        foreground_mask=foreground_mask,
        support_threshold=support_threshold,
        overlap_tolerance_px=overlap_tolerance_px,
        alignment_penalty_weight=alignment_penalty_weight,
    )
    return regrouped, {
        **base_meta,
        "makemeahanzi_prior_available": True,
        "makemeahanzi_prior_applied": True,
        "makemeahanzi_char": char,
        "makemeahanzi_target_stroke_count": len(prior_strokes),
        "makemeahanzi_grouped_segment_count": len(regrouped),
        "makemeahanzi_supported_bridge_count": regroup_meta["supported_bridge_count"],
        "makemeahanzi_rejected_bridge_count": regroup_meta["rejected_bridge_count"],
        "makemeahanzi_skipped_contained_segment_count": regroup_meta["skipped_contained_segment_count"],
        "makemeahanzi_merged_group_count": regroup_meta["merged_group_count"],
        "makemeahanzi_geometry_regularized_segment_count": regroup_meta["geometry_regularized_segment_count"],
        "makemeahanzi_local_blob_extended_segment_count": regroup_meta["local_blob_extended_segment_count"],
    }


def label_segments_by_makemeahanzi_components(
    segments: Sequence[dict[str, Any]],
    *,
    sample_name: str,
    canvas_shape: tuple[int, int],
    graphics_path: Path | str = DEFAULT_GRAPHICS_PATH,
    sample_char_map: dict[str, str] | None = None,
    alignment_penalty_weight: float = DEFAULT_ALIGNMENT_PENALTY_WEIGHT,
    split_geometry: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    char = resolve_sample_char(sample_name, sample_char_map=sample_char_map)
    base_meta: dict[str, Any] = {
        "makemeahanzi_prior_available": False,
        "makemeahanzi_prior_applied": False,
        "makemeahanzi_component_labels_applied": False,
        "makemeahanzi_component_label_group_count": 0,
        "makemeahanzi_char": char,
        "makemeahanzi_target_stroke_count": 0,
    }
    copied = [_copy_segment(segment) for segment in segments]
    if char is None:
        return copied, base_meta

    try:
        prior_strokes = normalize_medians_to_canvas(
            MakeMeAHanziKnowledge(graphics_path).get_glyph(char).medians,
            canvas_shape=canvas_shape,
        )
    except (FileNotFoundError, KeyError):
        return copied, base_meta
    if not prior_strokes:
        return copied, base_meta

    if split_geometry:
        labelled_segments = _split_segments_by_prior_runs(
            copied,
            prior_strokes,
            alignment_penalty_weight=alignment_penalty_weight,
        )
    else:
        labelled_segments = _label_segments_by_dominant_prior_component(
            copied,
            prior_strokes,
            alignment_penalty_weight=alignment_penalty_weight,
        )
    assigned_ids: set[int] = set()
    for segment in labelled_segments:
        stroke_index = int(segment.get("component_id", 0) or 0)
        if stroke_index > 0:
            assigned_ids.add(stroke_index)
    return labelled_segments, {
        **base_meta,
        "makemeahanzi_prior_available": True,
        "makemeahanzi_component_labels_applied": True,
        "makemeahanzi_component_label_group_count": len(assigned_ids),
        "makemeahanzi_char": char,
        "makemeahanzi_target_stroke_count": len(prior_strokes),
    }


def _copy_member_as_float_or_object(member: Any) -> tuple[np.ndarray, bool]:
    try:
        return np.asarray(member, dtype=float).copy(), True
    except (TypeError, ValueError):
        return np.asarray(member, dtype=object).copy(), False


def _stable_downward_suffix_index(
    points: np.ndarray,
    *,
    stable_run_points: int = 6,
    max_upward_reversal_px: float = 0.5,
    max_lateral_reversal_px: float = 0.5,
) -> int | None:
    try:
        pts = np.asarray(points, dtype=float)
        run_points_value = float(stable_run_points)
        upward_limit = float(max_upward_reversal_px)
        lateral_limit = float(max_lateral_reversal_px)
    except (TypeError, ValueError, OverflowError):
        return None
    if pts.ndim != 2 or pts.shape[1] != 2 or not bool(np.isfinite(pts).all()):
        return None
    if not all(np.isfinite(value) for value in (run_points_value, upward_limit, lateral_limit)):
        return None
    if upward_limit < 0.0 or lateral_limit < 0.0:
        return None

    run_points = max(int(run_points_value), 3)
    if len(pts) < run_points:
        return None
    for index in range(0, len(pts) - run_points + 1):
        window = pts[index:index + run_points]
        deltas = np.diff(window, axis=0)
        downward = float(np.maximum(deltas[:, 0], 0.0).sum())
        upward = float(np.maximum(-deltas[:, 0], 0.0).sum())
        lateral = float(np.abs(deltas[:, 1]).sum())
        expected_lateral_sign = float(np.sign(pts[-1, 1] - pts[index, 1]))
        opposite_lateral = lateral if expected_lateral_sign == 0.0 else float(
            np.maximum(-expected_lateral_sign * deltas[:, 1], 0.0).sum()
        )
        if downward < 2.0 or downward < lateral * 1.25:
            continue
        if upward > upward_limit:
            continue
        if opposite_lateral > lateral_limit:
            continue
        return index
    return None


def trim_overlapping_hengzhe_corner_members(
    horizontal_member: np.ndarray,
    vertical_member: np.ndarray,
    *,
    max_bridge_gap_px: float = 10.0,
    stable_run_points: int = 6,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    horizontal, horizontal_is_numeric = _copy_member_as_float_or_object(horizontal_member)
    vertical, vertical_is_numeric = _copy_member_as_float_or_object(vertical_member)
    meta: dict[str, Any] = {
        "trim_applied": False,
        "trim_reason": "invalid_members",
        "trimmed_point_count": 0,
        "bridge_gap_px": math.inf,
    }
    if (
        not horizontal_is_numeric
        or not vertical_is_numeric
        or horizontal.ndim != 2
        or horizontal.shape[1] != 2
        or len(horizontal) < 2
        or vertical.ndim != 2
        or vertical.shape[1] != 2
        or len(vertical) < 2
        or not bool(np.isfinite(horizontal).all())
        or not bool(np.isfinite(vertical).all())
    ):
        return horizontal, vertical, meta
    try:
        bridge_limit = float(max_bridge_gap_px)
    except (TypeError, ValueError, OverflowError):
        meta["trim_reason"] = "invalid_parameters"
        return horizontal, vertical, meta
    if not np.isfinite(bridge_limit) or bridge_limit < 0.0:
        meta["trim_reason"] = "invalid_parameters"
        return horizontal, vertical, meta

    meta["trim_reason"] = "stable_downward_suffix_not_found"
    meta["bridge_gap_px"] = None
    suffix_index = _stable_downward_suffix_index(vertical, stable_run_points=stable_run_points)
    if suffix_index is None:
        return horizontal, vertical, meta

    bridge_gap = float(np.linalg.norm(vertical[suffix_index] - horizontal[-1]))
    meta["bridge_gap_px"] = bridge_gap
    if bridge_gap > bridge_limit:
        meta["trim_reason"] = "trimmed_bridge_gap_exceeds_limit"
        return horizontal, vertical, meta

    trimmed_vertical = vertical[suffix_index:].copy()
    meta.update(
        {
            "trim_applied": suffix_index > 0,
            "trim_reason": "stable_downward_suffix",
            "trimmed_point_count": suffix_index,
        }
    )
    return horizontal, trimmed_vertical, meta


def smooth_polyline_leg_bounded(
    points: np.ndarray,
    *,
    fixed_indices: Sequence[int],
    smoothing_strength: float = 4.0,
) -> np.ndarray:
    """Minimize resampled fidelity plus second-difference energy for one leg.

    Valid fixed indices are exact anchors to the original points. Points must be
    finite float Nx2 and strength must be finite; malformed fixed entries are ignored.
    """

    try:
        pts = np.asarray(points, dtype=float).copy()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("points must be finite float Nx2") from exc
    if pts.ndim != 2 or pts.shape[1] != 2 or not bool(np.isfinite(pts).all()):
        raise ValueError("points must be finite float Nx2")
    try:
        strength = float(smoothing_strength)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("smoothing_strength must be finite") from exc
    if not np.isfinite(strength):
        raise ValueError("smoothing_strength must be finite")

    point_count = len(pts)
    if point_count < 3 or strength <= 0.0:
        return pts

    resampled = _resample_polyline_to_count(pts, point_count)
    if not bool(np.isfinite(resampled).all()):
        raise ValueError("resampled points must be finite")
    second_difference = np.zeros((point_count - 2, point_count), dtype=float)
    rows = np.arange(point_count - 2)
    second_difference[rows, rows] = 1.0
    second_difference[rows, rows + 1] = -2.0
    second_difference[rows, rows + 2] = 1.0
    with np.errstate(over="ignore", invalid="ignore"):
        system = np.eye(point_count, dtype=float) + strength * (
            second_difference.T @ second_difference
        )
    if not bool(np.isfinite(system).all()):
        raise ValueError("smoothing system must be finite")

    fixed_set: set[int] = set()
    for index in fixed_indices:
        if isinstance(index, (bool, np.bool_)):
            continue
        if isinstance(index, (int, np.integer)):
            normalized = int(index)
        elif isinstance(index, (float, np.floating)):
            value = float(index)
            if not np.isfinite(value) or not value.is_integer():
                continue
            normalized = int(value)
        else:
            continue
        if normalized < 0:
            normalized += point_count
        if 0 <= normalized < point_count:
            fixed_set.add(normalized)
    fixed = sorted(fixed_set)
    free = [index for index in range(point_count) if index not in fixed]
    smoothed = resampled.copy()
    if fixed:
        smoothed[fixed] = pts[fixed]
    if free:
        free_system = system[np.ix_(free, free)]
        fixed_system = system[np.ix_(free, fixed)]
        for axis in range(pts.shape[1]):
            right_hand_side = resampled[free, axis]
            if fixed:
                with np.errstate(over="ignore", invalid="ignore"):
                    right_hand_side = right_hand_side - fixed_system @ pts[fixed, axis]
            if not bool(np.isfinite(right_hand_side).all()):
                raise ValueError("smoothing right-hand side must be finite")
            try:
                with np.errstate(over="ignore", invalid="ignore"):
                    solution = np.linalg.solve(free_system, right_hand_side)
            except np.linalg.LinAlgError as exc:
                raise ValueError("smoothing system could not be solved") from exc
            if not bool(np.isfinite(solution).all()):
                raise ValueError("smoothed points must be finite")
            smoothed[free, axis] = solution
    if fixed:
        smoothed[fixed] = pts[fixed]
    if not bool(np.isfinite(smoothed).all()):
        raise ValueError("smoothed points must be finite")
    return smoothed


def build_prior_stroke_structure_candidate(
    labelled_segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    primitive_kinds: Sequence[str],
    max_bridge_gap_px: float = 10.0,
    endpoint_overshoots: dict[int, dict[str, float]] | None = None,
    trim_hengzhe_overlap: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collapse labelled geometry to one writable segment per prior stroke."""

    normalized_priors = [np.asarray(stroke, dtype=float) for stroke in prior_strokes]
    hengzhe_overlap_trim_details: list[tuple[int, bool, str, int, float | None]] = []

    def current_hengzhe_trim_meta() -> dict[str, Any]:
        applied = any(detail[1] for detail in hengzhe_overlap_trim_details)
        trimmed_count = sum(detail[3] for detail in hengzhe_overlap_trim_details)
        if not trim_hengzhe_overlap:
            reason = "not_requested"
        elif applied:
            reason = "one_or_more_trimmed"
        elif hengzhe_overlap_trim_details:
            joined_reasons = "|".join(
                f"{detail[0]}:{detail[2]}" for detail in hengzhe_overlap_trim_details
            )
            reason = f"no_trim:{joined_reasons}"
        else:
            reason = "eligible_hengzhe_not_found"
        return {
            "hengzhe_overlap_trim_applied": applied,
            "hengzhe_overlap_trim_reason": reason,
            "hengzhe_overlap_trimmed_point_count": trimmed_count,
            "hengzhe_overlap_trim_details": tuple(hengzhe_overlap_trim_details),
        }

    base_meta: dict[str, Any] = {
        "structure_prior_applied": False,
        "structure_prior_reason": "invalid_input",
        "structure_target_stroke_count": len(normalized_priors),
        "structure_segment_count": 0,
        "structure_bridge_count": 0,
        "structure_max_bridge_gap_px": 0.0,
        "structure_overshoot_count": 0,
        **current_hengzhe_trim_meta(),
    }
    if not normalized_priors or len(normalized_priors) != len(primitive_kinds):
        return [], base_meta

    structured: list[dict[str, Any]] = []
    bridge_count = 0
    max_bridge_gap = 0.0
    overshoot_count = 0
    overshoots = endpoint_overshoots or {}
    endpoint_roles = {
        "shu": ("free", "attached"),
        "hengzhe": ("attached", "attached"),
        "heng": ("attached", "free"),
        "gou": ("attached", "pointed"),
    }

    for component_id, (prior_stroke, primitive_kind) in enumerate(
        zip(normalized_priors, primitive_kinds),
        start=1,
    ):
        members: list[tuple[float, float, np.ndarray, dict[str, Any]]] = []
        for segment in labelled_segments:
            if int(segment.get("component_id", 0) or 0) != component_id:
                continue
            points = np.asarray(segment.get("points", ()), dtype=float)
            if len(points) < 2:
                continue
            start_arc = _closest_arc(points[0], prior_stroke)[1]
            end_arc = _closest_arc(points[-1], prior_stroke)[1]
            if end_arc < start_arc:
                points = points[::-1].copy()
                start_arc, end_arc = end_arc, start_arc
            members.append((float(start_arc), float(end_arc), points, segment))

        if not members:
            return [], {
                **base_meta,
                "structure_prior_reason": f"missing_component_{component_id}",
                **current_hengzhe_trim_meta(),
            }
        members.sort(key=lambda item: (item[0], item[1]))

        if trim_hengzhe_overlap and str(primitive_kind) == "hengzhe":
            if len(members) == 2:
                first = members[0]
                second = members[1]
                trimmed_first, trimmed_second, trim_meta = trim_overlapping_hengzhe_corner_members(
                    first[2],
                    second[2],
                    max_bridge_gap_px=max_bridge_gap_px,
                    stable_run_points=6,
                )
                members[0] = (first[0], first[1], trimmed_first, first[3])
                members[1] = (second[0], second[1], trimmed_second, second[3])
                bridge_gap = trim_meta.get("bridge_gap_px")
                hengzhe_overlap_trim_details.append(
                    (
                        component_id,
                        bool(trim_meta["trim_applied"]),
                        str(trim_meta["trim_reason"]),
                        int(trim_meta["trimmed_point_count"]),
                        None if bridge_gap is None else float(bridge_gap),
                    )
                )
            else:
                hengzhe_overlap_trim_details.append(
                    (
                        component_id,
                        False,
                        "requires_exactly_two_hengzhe_members",
                        0,
                        None,
                    )
                )

        structure_corner_index = (
            len(members[0][2]) - 1 if str(primitive_kind) == "hengzhe" else None
        )

        merged_points = members[0][2].copy()
        source_ids: list[int] = [int(value) for value in members[0][3].get("source_segment_ids", ())]
        covered_end_arc = members[0][1]
        for start_arc, end_arc, points, segment in members[1:]:
            gap_px = float(np.linalg.norm(points[0] - merged_points[-1]))
            max_bridge_gap = max(max_bridge_gap, gap_px)
            if gap_px > float(max_bridge_gap_px):
                return [], {
                    **base_meta,
                    "structure_prior_reason": f"bridge_gap_exceeds_limit_component_{component_id}",
                    "structure_bridge_count": bridge_count,
                    "structure_max_bridge_gap_px": max_bridge_gap,
                    **current_hengzhe_trim_meta(),
                }

            if gap_px > 1e-6:
                if start_arc > covered_end_arc + 0.5:
                    prior_bridge = _sample_stroke_subpath(
                        prior_stroke,
                        covered_end_arc,
                        start_arc,
                        step_px=1.0,
                    )
                    bridge_points = np.vstack([merged_points[-1], prior_bridge, points[0]])
                else:
                    bridge_count_points = max(2, int(math.ceil(gap_px)) + 1)
                    bridge_points = np.linspace(merged_points[-1], points[0], num=bridge_count_points)
                merged_points = np.vstack([merged_points, bridge_points[1:-1]])
                bridge_count += 1

            merged_points = np.vstack([merged_points, points])
            source_ids.extend(int(value) for value in segment.get("source_segment_ids", ()))
            covered_end_arc = max(covered_end_arc, end_arc)

        component_overshoots = overshoots.get(component_id, {})
        start_overshoot = max(0.0, float(component_overshoots.get("start", 0.0)))
        end_overshoot = max(0.0, float(component_overshoots.get("end", 0.0)))
        if start_overshoot > 0.0:
            extended_points = _extend_polyline_endpoint(
                merged_points,
                distance_px=start_overshoot,
                at_end=False,
            )
            if structure_corner_index is not None and len(extended_points) > len(merged_points):
                structure_corner_index += 1
            merged_points = extended_points
            overshoot_count += 1
        if end_overshoot > 0.0:
            merged_points = _extend_polyline_endpoint(merged_points, distance_px=end_overshoot, at_end=True)
            overshoot_count += 1

        start_role, end_role = endpoint_roles.get(str(primitive_kind), ("free", "free"))
        template = _copy_segment(members[0][3])
        template["points"] = [tuple(float(value) for value in point) for point in merged_points]
        template["source_segment_ids"] = tuple(dict.fromkeys(source_ids))
        template["component_id"] = component_id
        template["primitive_kind"] = str(primitive_kind)
        template["primitive_start_role"] = start_role
        template["primitive_end_role"] = end_role
        template["pointed_start"] = start_role == "pointed"
        template["pointed_end"] = end_role == "pointed"
        template["render_subpaths"] = ()
        template["render_subpath_source_ids"] = ()
        template["structure_prior_applied"] = True
        if structure_corner_index is not None:
            template["structure_corner_index"] = structure_corner_index
        structured.append(template)

    return structured, {
        **base_meta,
        "structure_prior_applied": True,
        "structure_prior_reason": "one_segment_per_prior_stroke",
        "structure_segment_count": len(structured),
        "structure_bridge_count": bridge_count,
        "structure_max_bridge_gap_px": max_bridge_gap,
        "structure_overshoot_count": overshoot_count,
        **current_hengzhe_trim_meta(),
    }


def _apply_structure_endpoint_overshoots(
    structured_segments: Sequence[dict[str, Any]],
    *,
    endpoint_overshoots: dict[int, dict[str, float]],
) -> tuple[list[dict[str, Any]], int]:
    updated = [_copy_segment(segment) for segment in structured_segments]
    overshoot_count = 0
    for segment in updated:
        component_id = int(segment.get("component_id", 0) or 0)
        component_overshoots = endpoint_overshoots.get(component_id, {})
        points = np.asarray(segment.get("points", ()), dtype=float)

        start_overshoot = max(0.0, float(component_overshoots.get("start", 0.0)))
        if start_overshoot > 0.0:
            extended = _extend_polyline_endpoint(
                points,
                distance_px=start_overshoot,
                at_end=False,
            )
            if len(extended) > len(points):
                if "structure_corner_index" in segment:
                    segment["structure_corner_index"] = int(segment["structure_corner_index"]) + 1
                overshoot_count += 1
            points = extended

        end_overshoot = max(0.0, float(component_overshoots.get("end", 0.0)))
        if end_overshoot > 0.0:
            extended = _extend_polyline_endpoint(
                points,
                distance_px=end_overshoot,
                at_end=True,
            )
            if len(extended) > len(points):
                overshoot_count += 1
            points = extended

        segment["points"] = [
            tuple(float(value) for value in point)
            for point in points
        ]
    return updated, overshoot_count


def _axis_transition_count(points: Sequence[Sequence[float]]) -> int:
    try:
        pts = np.asarray(points, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("points must be finite float Nx2") from exc
    if pts.ndim != 2 or pts.shape[1] != 2 or not bool(np.isfinite(pts).all()):
        raise ValueError("points must be finite float Nx2")
    if len(pts) < 2:
        return 0
    runs: list[str] = []
    for delta_y, delta_x in np.diff(pts, axis=0):
        if float(np.hypot(delta_y, delta_x)) <= 1e-6:
            continue
        axis = "horizontal" if abs(float(delta_x)) >= abs(float(delta_y)) else "vertical"
        if not runs or runs[-1] != axis:
            runs.append(axis)
    return max(0, len(runs) - 1)


def _hengzhe_reversal_metrics(
    points: Sequence[Sequence[float]],
    *,
    corner_index: int,
) -> tuple[float, float]:
    pts = np.asarray(points, dtype=float)
    if (
        pts.ndim != 2
        or pts.shape[1] != 2
        or not bool(np.isfinite(pts).all())
        or corner_index < 0
        or corner_index >= len(pts)
    ):
        raise ValueError("invalid hengzhe geometry")
    horizontal_dx = np.diff(pts[:corner_index + 1, 1])
    vertical_dy = np.diff(pts[corner_index:, 0])
    horizontal_reversal = float(np.maximum(-horizontal_dx, 0.0).sum())
    vertical_reversal = float(np.maximum(-vertical_dy, 0.0).sum())
    return horizontal_reversal, vertical_reversal


def regularize_kou_structure_skeleton(
    structured_segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray,
    support_radius_px: int = 2,
    min_support_ratio: float = 0.90,
    max_displacement_px: float = 2.5,
    smoothing_strength: float = 4.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    def build_meta(
        applied: bool,
        reason: str,
        *,
        transition_count: int = 0,
        measured_displacement: float = 0.0,
        support_ratio: float = 0.0,
        horizontal_reversal: float = 0.0,
        vertical_reversal: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "kou_skeleton_regularization_applied": applied,
            "kou_skeleton_regularization_reason": reason,
            "kou_hengzhe_axis_transition_count": transition_count,
            "kou_skeleton_max_displacement_px": measured_displacement,
            "kou_skeleton_foreground_support_ratio": support_ratio,
            "kou_hengzhe_horizontal_reversal_px": horizontal_reversal,
            "kou_hengzhe_vertical_reversal_px": vertical_reversal,
        }

    try:
        input_segments = list(structured_segments)
    except TypeError:
        return [], build_meta(False, "invalid_structure")

    try:
        original = [_copy_segment(segment) for segment in input_segments]
    except (TypeError, ValueError, OverflowError):
        original = []
        for segment in input_segments:
            if not isinstance(segment, dict):
                original.append({"points": []})
                continue
            copied = dict(segment)
            try:
                copied["points"] = list(copied.get("points", ()))
            except TypeError:
                copied["points"] = []
            original.append(copied)
        return original, build_meta(False, "invalid_structure")

    if len(original) != 3:
        return original, build_meta(False, "invalid_structure")

    primitive_roles = [str(segment.get("primitive_kind", "")) for segment in original]
    if primitive_roles != ["shu", "hengzhe", "heng"]:
        return original, build_meta(False, "unexpected_primitive_roles")

    component_ids = [segment.get("component_id") for segment in original]
    if (
        any(isinstance(component_id, (bool, np.bool_)) for component_id in component_ids)
        or component_ids != [1, 2, 3]
    ):
        return original, build_meta(False, "unexpected_component_order")

    point_arrays: list[np.ndarray] = []
    for segment in original:
        try:
            points = np.asarray(segment.get("points", ()), dtype=float)
        except (TypeError, ValueError, OverflowError):
            return original, build_meta(False, "invalid_structure")
        if (
            points.ndim != 2
            or points.shape[1] != 2
            or len(points) == 0
            or not bool(np.isfinite(points).all())
        ):
            return original, build_meta(False, "invalid_structure")
        point_arrays.append(points)

    corner_value = original[1].get("structure_corner_index")
    if isinstance(corner_value, (bool, np.bool_)):
        return original, build_meta(False, "missing_corner_index")
    try:
        corner_index = int(corner_value)
        if float(corner_value) != float(corner_index):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return original, build_meta(False, "missing_corner_index")
    if corner_index < 1 or corner_index > len(point_arrays[1]) - 2:
        return original, build_meta(False, "empty_leg")

    top_leg = point_arrays[1][:corner_index + 1]
    right_leg = point_arrays[1][corner_index:]
    if len(top_leg) < 2 or len(right_leg) < 2:
        return original, build_meta(False, "empty_leg")

    original_horizontal_reversal, original_vertical_reversal = _hengzhe_reversal_metrics(
        point_arrays[1],
        corner_index=corner_index,
    )

    try:
        displacement_limit = float(max_displacement_px)
        support_limit = float(min_support_ratio)
        radius_value = float(support_radius_px)
    except (TypeError, ValueError, OverflowError):
        return original, build_meta(
            False,
            "invalid_parameters",
            horizontal_reversal=original_horizontal_reversal,
            vertical_reversal=original_vertical_reversal,
        )
    invalid_radius = (
        isinstance(support_radius_px, (bool, np.bool_))
        or not np.isfinite(radius_value)
        or radius_value < 0.0
        or not radius_value.is_integer()
    )
    if (
        not np.isfinite(displacement_limit)
        or displacement_limit < 0.0
        or not np.isfinite(support_limit)
        or not 0.0 <= support_limit <= 1.0
        or invalid_radius
    ):
        return original, build_meta(
            False,
            "invalid_parameters",
            horizontal_reversal=original_horizontal_reversal,
            vertical_reversal=original_vertical_reversal,
        )
    support_radius = int(radius_value)

    try:
        raw_mask = np.asarray(foreground_mask)
        if raw_mask.ndim != 2 or np.iscomplexobj(raw_mask):
            raise ValueError
        if raw_mask.dtype == np.bool_:
            normalized_mask = raw_mask.astype(bool, copy=True)
        else:
            numeric_mask = np.asarray(raw_mask, dtype=float)
            if not bool(np.isfinite(numeric_mask).all()):
                raise ValueError
            normalized_mask = numeric_mask.astype(bool)
    except (TypeError, ValueError, OverflowError):
        return original, build_meta(
            False,
            "invalid_parameters",
            horizontal_reversal=original_horizontal_reversal,
            vertical_reversal=original_vertical_reversal,
        )

    try:
        smoothed_first = smooth_polyline_leg_bounded(
            point_arrays[0],
            fixed_indices=(0, len(point_arrays[0]) - 1),
            smoothing_strength=smoothing_strength,
        )
        smoothed_top = smooth_polyline_leg_bounded(
            top_leg,
            fixed_indices=(0, len(top_leg) - 1),
            smoothing_strength=smoothing_strength,
        )
        smoothed_right = smooth_polyline_leg_bounded(
            right_leg,
            fixed_indices=(0, len(right_leg) - 1),
            smoothing_strength=smoothing_strength,
        )
        smoothed_third = smooth_polyline_leg_bounded(
            point_arrays[2],
            fixed_indices=(0, len(point_arrays[2]) - 1),
            smoothing_strength=smoothing_strength,
        )

        candidate_first = point_arrays[0].copy()
        candidate_first[:, 1] = smoothed_first[:, 1]
        candidate_top = top_leg.copy()
        candidate_top[:, 0] = smoothed_top[:, 0]
        candidate_right = right_leg.copy()
        candidate_right[:, 1] = smoothed_right[:, 1]
        candidate_third = point_arrays[2].copy()
        candidate_third[:, 0] = smoothed_third[:, 0]
        candidate_arrays = [
            candidate_first,
            np.vstack([candidate_top, candidate_right[1:]]),
            candidate_third,
        ]
    except ValueError:
        combined_original = np.vstack(point_arrays)
        support_ratio = _support_ratio_in_radius(
            combined_original,
            normalized_mask,
            radius_px=support_radius,
        )
        return original, build_meta(
            False,
            "smoothing_failed",
            transition_count=_axis_transition_count(point_arrays[1]),
            support_ratio=support_ratio,
            horizontal_reversal=original_horizontal_reversal,
            vertical_reversal=original_vertical_reversal,
        )

    measured_displacement = max(
        float(np.linalg.norm(candidate - before, axis=1).max())
        for candidate, before in zip(candidate_arrays, point_arrays)
    )
    support_ratio = _support_ratio_in_radius(
        np.vstack(candidate_arrays),
        normalized_mask,
        radius_px=support_radius,
    )
    transition_count = _axis_transition_count(candidate_arrays[1])
    horizontal_reversal, vertical_reversal = _hengzhe_reversal_metrics(
        candidate_arrays[1],
        corner_index=corner_index,
    )

    if measured_displacement > displacement_limit:
        return original, build_meta(
            False,
            "max_displacement_exceeded",
            transition_count=transition_count,
            measured_displacement=measured_displacement,
            support_ratio=support_ratio,
            horizontal_reversal=horizontal_reversal,
            vertical_reversal=vertical_reversal,
        )
    if support_ratio < support_limit:
        return original, build_meta(
            False,
            "foreground_support_too_low",
            transition_count=transition_count,
            measured_displacement=measured_displacement,
            support_ratio=support_ratio,
            horizontal_reversal=horizontal_reversal,
            vertical_reversal=vertical_reversal,
        )
    if horizontal_reversal > 0.5:
        return original, build_meta(
            False,
            "horizontal_reversal_exceeded",
            transition_count=transition_count,
            measured_displacement=measured_displacement,
            support_ratio=support_ratio,
            horizontal_reversal=horizontal_reversal,
            vertical_reversal=vertical_reversal,
        )
    if vertical_reversal > 0.5:
        return original, build_meta(
            False,
            "vertical_reversal_exceeded",
            transition_count=transition_count,
            measured_displacement=measured_displacement,
            support_ratio=support_ratio,
            horizontal_reversal=horizontal_reversal,
            vertical_reversal=vertical_reversal,
        )
    if transition_count != 1:
        return original, build_meta(
            False,
            "unexpected_axis_transition_count",
            transition_count=transition_count,
            measured_displacement=measured_displacement,
            support_ratio=support_ratio,
            horizontal_reversal=horizontal_reversal,
            vertical_reversal=vertical_reversal,
        )

    regularized = [_copy_segment(segment) for segment in original]
    for segment, points in zip(regularized, candidate_arrays):
        segment["points"] = [
            tuple(float(value) for value in point)
            for point in points
        ]
    return regularized, build_meta(
        True,
        "overlap_trimmed_and_legs_smoothed",
        transition_count=transition_count,
        measured_displacement=measured_displacement,
        support_ratio=support_ratio,
        horizontal_reversal=horizontal_reversal,
        vertical_reversal=vertical_reversal,
    )


def build_kou_three_stroke_candidate(
    labelled_segments: Sequence[dict[str, Any]],
    *,
    canvas_shape: tuple[int, int],
    graphics_path: Path | str = DEFAULT_GRAPHICS_PATH,
    max_bridge_gap_px: float = 10.0,
    foreground_mask: np.ndarray | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the three-stroke ``shu, hengzhe, heng`` structure of ``kou``."""

    try:
        char = resolve_sample_char("kou")
        prior_strokes = normalize_medians_to_canvas(
            MakeMeAHanziKnowledge(graphics_path).get_glyph(str(char)).medians,
            canvas_shape=canvas_shape,
        )
    except (FileNotFoundError, KeyError):
        return [], {
            "structure_prior_applied": False,
            "structure_prior_reason": "kou_prior_unavailable",
            "structure_target_stroke_count": 3,
            "structure_segment_count": 0,
            "structure_bridge_count": 0,
            "structure_max_bridge_gap_px": 0.0,
            "structure_overshoot_count": 0,
            "hengzhe_overlap_trim_applied": False,
            "hengzhe_overlap_trim_reason": "kou_prior_unavailable",
            "hengzhe_overlap_trimmed_point_count": 0,
            "hengzhe_overlap_trim_details": (),
            "kou_hengzhe_overlap_trimmed_point_count": 0,
        }

    structured, structure_meta = build_prior_stroke_structure_candidate(
        labelled_segments,
        prior_strokes,
        primitive_kinds=("shu", "hengzhe", "heng"),
        max_bridge_gap_px=max_bridge_gap_px,
        trim_hengzhe_overlap=True,
    )
    if not structured:
        return structured, {
            **structure_meta,
            "kou_hengzhe_overlap_trimmed_point_count": int(
                structure_meta.get("hengzhe_overlap_trimmed_point_count", 0)
            ),
        }

    if foreground_mask is not None:
        regularized, regularization_meta = regularize_kou_structure_skeleton(
            structured,
            foreground_mask=foreground_mask,
        )
    else:
        regularized = [_copy_segment(segment) for segment in structured]
        corner_index = int(regularized[1]["structure_corner_index"])
        horizontal_reversal, vertical_reversal = _hengzhe_reversal_metrics(
            regularized[1].get("points", ()),
            corner_index=corner_index,
        )
        regularization_meta = {
            "kou_skeleton_regularization_applied": False,
            "kou_skeleton_regularization_reason": "foreground_mask_unavailable",
            "kou_hengzhe_axis_transition_count": _axis_transition_count(
                regularized[1].get("points", ())
            ),
            "kou_skeleton_max_displacement_px": 0.0,
            "kou_skeleton_foreground_support_ratio": 0.0,
            "kou_hengzhe_horizontal_reversal_px": horizontal_reversal,
            "kou_hengzhe_vertical_reversal_px": vertical_reversal,
        }

    overshot, overshoot_count = _apply_structure_endpoint_overshoots(
        regularized,
        endpoint_overshoots={1: {"end": 4.0}, 2: {"start": 2.0}, 3: {"end": 4.0}},
    )
    return overshot, {
        **structure_meta,
        **regularization_meta,
        "structure_overshoot_count": overshoot_count,
        "kou_hengzhe_overlap_trimmed_point_count": int(
            structure_meta.get("hengzhe_overlap_trimmed_point_count", 0)
        ),
    }


def regroup_ordered_segments_by_prior_strokes(
    ordered_segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    foreground_mask: np.ndarray | None,
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD,
    overlap_tolerance_px: float = DEFAULT_OVERLAP_TOLERANCE_PX,
    alignment_penalty_weight: float = DEFAULT_ALIGNMENT_PENALTY_WEIGHT,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: list[dict[str, Any]] = []
    supported_bridge_count = 0
    rejected_bridge_count = 0
    skipped_contained_segment_count = 0
    merged_group_count = 0

    ordered = [_copy_segment(segment) for segment in ordered_segments]
    normalized_priors = [np.asarray(stroke, dtype=float) for stroke in prior_strokes if len(stroke)]
    if not normalized_priors:
        return ordered, {
            "grouped_segment_count": len(ordered),
            "supported_bridge_count": 0,
            "rejected_bridge_count": 0,
            "skipped_contained_segment_count": 0,
            "merged_group_count": 0,
            "geometry_regularized_segment_count": 0,
            "local_blob_extended_segment_count": 0,
        }

    assignments = _assign_segments_to_prior_strokes(
        ordered,
        normalized_priors,
        alignment_penalty_weight=alignment_penalty_weight,
    )
    for stroke_index, stroke in enumerate(normalized_priors, start=1):
        members = [segment for segment in ordered if assignments[tuple(segment.get("source_segment_ids", ()))] == stroke_index]
        if not members:
            continue

        member_meta: list[tuple[float, float, np.ndarray, dict[str, Any]]] = []
        for segment in members:
            points = np.asarray(segment.get("points", ()), dtype=float)
            start_arc = _closest_arc(points[0], stroke)[1]
            end_arc = _closest_arc(points[-1], stroke)[1]
            if end_arc < start_arc:
                points = points[::-1].copy()
                start_arc, end_arc = end_arc, start_arc
            member_meta.append((start_arc, end_arc, points, segment))
        member_meta.sort(key=lambda item: item[0])

        merged_points: np.ndarray | None = None
        merged_ids: list[int] = []
        covered_end = 0.0
        merged_members = 0
        for start_arc, end_arc, points, segment in member_meta:
            if merged_points is None:
                merged_points = points.copy()
                merged_ids.extend(segment.get("source_segment_ids", ()))
                covered_end = end_arc
                merged_members = 1
                continue

            if end_arc <= covered_end + overlap_tolerance_px:
                skipped_contained_segment_count += 1
                continue

            if start_arc <= covered_end + overlap_tolerance_px:
                keep_index = _first_forward_index(points, stroke, covered_end)
                if keep_index is not None:
                    candidate_points = points[keep_index:]
                    if merged_members == 1 and _should_split_sharp_lead_in(
                        merged_points,
                        points,
                    ):
                        grouped_segment = _build_grouped_segment(merged_points, merged_ids, members[0])
                        grouped_segment["component_id"] = stroke_index
                        grouped.append(grouped_segment)
                        merged_points = points.copy()
                        merged_ids = list(segment.get("source_segment_ids", ()))
                        covered_end = end_arc
                        merged_members = 1
                        continue
                    overlap_bridge: np.ndarray | None = None
                    if foreground_mask is not None:
                        candidate_start_arc = _closest_arc(candidate_points[0], stroke)[1]
                        if candidate_start_arc > covered_end + 0.5:
                            candidate_bridge = _sample_stroke_subpath(
                                stroke,
                                covered_end,
                                candidate_start_arc,
                                step_px=1.0,
                            )
                            if (
                                len(candidate_bridge) >= 2
                                and (
                                    _support_ratio(candidate_bridge, foreground_mask) >= support_threshold
                                    or _support_ratio_in_radius(
                                        candidate_bridge,
                                        foreground_mask,
                                        radius_px=1,
                                    )
                                    >= support_threshold
                                )
                            ):
                                overlap_bridge = candidate_bridge
                    if _should_split_overlap_append(
                        merged_points,
                        candidate_points,
                        max_gap_px=max(DEFAULT_OVERLAP_APPEND_MAX_GAP_PX, float(overlap_tolerance_px) * 2.0),
                        direction_cos_min=DEFAULT_OVERLAP_APPEND_DIRECTION_COS_MIN,
                    ):
                        if overlap_bridge is not None:
                            merged_points = np.vstack([merged_points, overlap_bridge[1:], candidate_points[1:]])
                            merged_ids.extend(segment.get("source_segment_ids", ()))
                            covered_end = end_arc
                            supported_bridge_count += 1
                            merged_members += 1
                            continue
                        grouped_segment = _build_grouped_segment(merged_points, merged_ids, members[0])
                        grouped_segment["component_id"] = stroke_index
                        grouped.append(grouped_segment)
                        if merged_members > 1:
                            merged_group_count += 1
                        merged_points = candidate_points.copy()
                        merged_ids = list(segment.get("source_segment_ids", ()))
                        covered_end = end_arc
                        merged_members = 1
                        continue
                    merged_points = np.vstack([merged_points, candidate_points])
                    merged_ids.extend(segment.get("source_segment_ids", ()))
                    covered_end = end_arc
                    merged_members += 1
                else:
                    skipped_contained_segment_count += 1
                continue

            bridge = _sample_stroke_subpath(stroke, covered_end, start_arc, step_px=1.0)
            bridge_supported = (
                foreground_mask is not None
                and _support_ratio(bridge, foreground_mask) >= support_threshold
            )
            if bridge_supported:
                if merged_members == 1 and _should_split_sharp_lead_in(
                    merged_points,
                    points,
                ):
                    grouped_segment = _build_grouped_segment(merged_points, merged_ids, members[0])
                    grouped_segment["component_id"] = stroke_index
                    grouped.append(grouped_segment)
                    merged_points = points.copy()
                    merged_ids = list(segment.get("source_segment_ids", ()))
                    covered_end = end_arc
                    merged_members = 1
                    continue
                merged_points = np.vstack([merged_points, bridge[1:], points[1:]])
                merged_ids.extend(segment.get("source_segment_ids", ()))
                covered_end = end_arc
                supported_bridge_count += 1
                merged_members += 1
                continue

            rejected_bridge_count += 1
            grouped_segment = _build_grouped_segment(merged_points, merged_ids, members[0])
            grouped_segment["component_id"] = stroke_index
            grouped.append(grouped_segment)
            if merged_members > 1:
                merged_group_count += 1
            merged_points = points.copy()
            merged_ids = list(segment.get("source_segment_ids", ()))
            covered_end = end_arc
            merged_members = 1

        if merged_points is not None:
            grouped_segment = _build_grouped_segment(merged_points, merged_ids, members[0])
            grouped_segment["component_id"] = stroke_index
            grouped.append(grouped_segment)
            if merged_members > 1:
                merged_group_count += 1

    grouped, regularization_meta = _regularize_grouped_segments_to_prior_geometry(
        grouped,
        normalized_priors,
        foreground_mask=foreground_mask,
        support_threshold=support_threshold,
    )

    return grouped, {
        "grouped_segment_count": len(grouped),
        "supported_bridge_count": supported_bridge_count,
        "rejected_bridge_count": rejected_bridge_count,
        "skipped_contained_segment_count": skipped_contained_segment_count,
        "merged_group_count": merged_group_count,
        "geometry_regularized_segment_count": int(regularization_meta["geometry_regularized_segment_count"]),
        "local_blob_extended_segment_count": int(regularization_meta["local_blob_extended_segment_count"]),
    }


def _build_grouped_segment(points: np.ndarray, merged_ids: Sequence[int], template: dict[str, Any]) -> dict[str, Any]:
    grouped = dict(template)
    grouped["points"] = [tuple(float(value) for value in point) for point in np.asarray(points, dtype=float)]
    grouped["source_segment_ids"] = tuple(int(value) for value in merged_ids)
    return grouped


def _copy_segment(segment: dict[str, Any]) -> dict[str, Any]:
    copied = dict(segment)
    copied["source_segment_ids"] = tuple(copied.get("source_segment_ids", ()))
    copied["points"] = [tuple(float(value) for value in point) for point in copied.get("points", ())]
    return copied


def _regularize_grouped_segments_to_prior_geometry(
    grouped_segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    foreground_mask: np.ndarray | None,
    support_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not grouped_segments or not prior_strokes:
        return [_copy_segment(segment) for segment in grouped_segments], {
            "geometry_regularized_segment_count": 0,
            "local_blob_extended_segment_count": 0,
        }

    regularized: list[dict[str, Any]] = []
    regularized_count = 0
    local_blob_extended_count = 0
    for segment in grouped_segments:
        copied = _copy_segment(segment)
        component_id = int(copied.get("component_id", 0) or 0)
        if component_id <= 0 or component_id > len(prior_strokes):
            regularized.append(copied)
            continue
        copied["makemeahanzi_prior_subpath_mean_distance_px"] = _segment_prior_subpath_mean_distance(
            copied,
            np.asarray(prior_strokes[component_id - 1], dtype=float),
        )
        copied["makemeahanzi_foreground_support_ratio_r1"] = (
            _support_ratio_in_radius(np.asarray(copied.get("points", ()), dtype=float), foreground_mask, radius_px=1)
            if foreground_mask is not None
            else None
        )
        updated = _regularize_segment_to_prior_subpath(
            copied,
            np.asarray(prior_strokes[component_id - 1], dtype=float),
            foreground_mask=foreground_mask,
            support_threshold=support_threshold,
        )
        used_local_blob_extension = False
        if updated is None and foreground_mask is not None:
            updated = _regularize_short_segment_to_local_blob_axis(
                copied,
                foreground_mask=foreground_mask,
            )
            used_local_blob_extension = updated is not None
        if updated is None:
            regularized.append(copied)
            continue
        updated["makemeahanzi_prior_subpath_mean_distance_px"] = _segment_prior_subpath_mean_distance(
            updated,
            np.asarray(prior_strokes[component_id - 1], dtype=float),
        )
        updated["makemeahanzi_foreground_support_ratio_r1"] = (
            _support_ratio_in_radius(np.asarray(updated.get("points", ()), dtype=float), foreground_mask, radius_px=1)
            if foreground_mask is not None
            else None
        )
        regularized.append(updated)
        regularized_count += 1
        if used_local_blob_extension:
            local_blob_extended_count += 1

    return regularized, {
        "geometry_regularized_segment_count": regularized_count,
        "local_blob_extended_segment_count": local_blob_extended_count,
    }


def _regularize_segment_to_prior_subpath(
    segment: dict[str, Any],
    prior_stroke: np.ndarray,
    *,
    foreground_mask: np.ndarray | None,
    support_threshold: float,
    blend: float = DEFAULT_GEOMETRY_REGULARIZATION_BLEND,
    max_distance_px: float = DEFAULT_GEOMETRY_REGULARIZATION_MAX_DISTANCE_PX,
    min_support_ratio: float = DEFAULT_GEOMETRY_REGULARIZATION_MIN_SUPPORT_RATIO,
    min_changed_norm: float = DEFAULT_GEOMETRY_REGULARIZATION_MIN_CHANGED_NORM,
    min_path_ratio: float = DEFAULT_GEOMETRY_REGULARIZATION_MIN_PATH_RATIO,
    min_path_ratio_for_merged: float = DEFAULT_GEOMETRY_REGULARIZATION_MIN_PATH_RATIO_FOR_MERGED,
    support_radius_px: int = DEFAULT_GEOMETRY_REGULARIZATION_SUPPORT_RADIUS_PX,
    short_lead_in_max_length_px: float = DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_LENGTH_PX,
    short_lead_in_max_arc_fraction: float = DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_ARC_FRACTION,
    short_lead_in_max_alignment: float = DEFAULT_GEOMETRY_REGULARIZATION_SHORT_LEAD_IN_MAX_ALIGNMENT,
) -> dict[str, Any] | None:
    points = np.asarray(segment.get("points", ()), dtype=float)
    if len(points) < 2 or len(prior_stroke) < 2:
        return None

    chord_length = float(np.linalg.norm(points[-1] - points[0]))
    path_length = _polyline_length(points)
    source_segment_count = len(tuple(segment.get("source_segment_ids", ())))
    effective_min_path_ratio = (
        float(min_path_ratio_for_merged)
        if source_segment_count > 1
        else float(min_path_ratio)
    )
    if chord_length <= 1e-6:
        return None
    path_ratio = path_length / max(chord_length, 1e-6)

    support_floor = min(float(support_threshold), float(min_support_ratio))
    start_arc = _closest_arc(points[0], prior_stroke)[1]
    end_arc = _closest_arc(points[-1], prior_stroke)[1]
    if end_arc <= start_arc:
        arcs = [_closest_arc(point, prior_stroke)[1] for point in points]
        start_arc = float(min(arcs))
        end_arc = float(max(arcs))
    if end_arc - start_arc <= 1e-6:
        return None

    prior_subpath = _sample_stroke_subpath(prior_stroke, start_arc, end_arc, step_px=1.0)
    if len(prior_subpath) < 2:
        return None
    if foreground_mask is not None and _support_ratio_in_radius(prior_subpath, foreground_mask, radius_px=support_radius_px) < support_floor:
        return None

    original_resampled = _resample_polyline_to_count(points, len(prior_subpath))
    alignment = abs(float(np.dot(_direction(original_resampled), _direction(prior_subpath))))
    mean_distance = _mean_polyline_distance(original_resampled, prior_subpath)
    prior_arc_fraction = (end_arc - start_arc) / max(_polyline_length(prior_stroke), 1e-6)
    allow_short_lead_in_regularization = (
        source_segment_count == 1
        and path_length <= float(short_lead_in_max_length_px)
        and prior_arc_fraction <= float(short_lead_in_max_arc_fraction)
        and alignment <= float(short_lead_in_max_alignment)
    )
    if path_ratio < effective_min_path_ratio and not allow_short_lead_in_regularization:
        return None
    if alignment < 0.45 or mean_distance > float(max_distance_px):
        return None

    effective_blend = float(blend)
    if len(points) <= 8:
        effective_blend *= 0.85
    if allow_short_lead_in_regularization:
        effective_blend = max(effective_blend, float(blend))
    blended = original_resampled * (1.0 - effective_blend) + prior_subpath * effective_blend
    if foreground_mask is not None and _support_ratio_in_radius(blended, foreground_mask, radius_px=support_radius_px) < support_floor:
        return None
    if float(np.mean(np.linalg.norm(blended - original_resampled, axis=1))) < float(min_changed_norm):
        return None

    updated = _copy_segment(segment)
    updated["points"] = [tuple(float(value) for value in point) for point in blended]
    return updated


def _regularize_short_segment_to_local_blob_axis(
    segment: dict[str, Any],
    *,
    foreground_mask: np.ndarray,
    max_path_length_px: float = DEFAULT_LOCAL_BLOB_EXTENSION_MAX_PATH_LENGTH_PX,
    min_point_count: int = DEFAULT_LOCAL_BLOB_EXTENSION_MIN_POINT_COUNT,
    min_component_pixels: int = DEFAULT_LOCAL_BLOB_EXTENSION_MIN_COMPONENT_PIXELS,
    max_component_pixels: int = DEFAULT_LOCAL_BLOB_EXTENSION_MAX_COMPONENT_PIXELS,
    max_minor_span_px: float = DEFAULT_LOCAL_BLOB_EXTENSION_MAX_MINOR_SPAN_PX,
    min_blob_aspect_ratio: float = DEFAULT_LOCAL_BLOB_EXTENSION_MIN_BLOB_ASPECT_RATIO,
    min_alignment: float = DEFAULT_LOCAL_BLOB_EXTENSION_MIN_ALIGNMENT,
    max_coverage_ratio: float = DEFAULT_LOCAL_BLOB_EXTENSION_MAX_COVERAGE_RATIO,
    target_coverage_ratio: float = DEFAULT_LOCAL_BLOB_EXTENSION_TARGET_COVERAGE_RATIO,
    max_expansion_ratio: float = DEFAULT_LOCAL_BLOB_EXTENSION_MAX_EXPANSION_RATIO,
    trim_fraction: float = DEFAULT_LOCAL_BLOB_EXTENSION_TRIM_FRACTION,
    support_radius_px: int = DEFAULT_LOCAL_BLOB_EXTENSION_SUPPORT_RADIUS_PX,
    min_support_ratio: float = DEFAULT_LOCAL_BLOB_EXTENSION_MIN_SUPPORT_RATIO,
) -> dict[str, Any] | None:
    points = np.asarray(segment.get("points", ()), dtype=float)
    if len(points) < int(min_point_count):
        return None
    if len(tuple(segment.get("source_segment_ids", ()))) != 1:
        return None
    if _polyline_length(points) > float(max_path_length_px):
        return None

    component = _connected_component_containing_point(points[len(points) // 2], foreground_mask)
    if len(component) < int(min_component_pixels) or len(component) > int(max_component_pixels):
        return None

    component_center, component_major_axis, component_minor_axis = _principal_axes(component)
    if component_major_axis is None or component_minor_axis is None:
        return None

    component_centered = component - component_center
    component_major_projection = component_centered @ component_major_axis
    component_minor_projection = component_centered @ component_minor_axis
    component_major_span = float(component_major_projection.max() - component_major_projection.min())
    component_minor_span = float(component_minor_projection.max() - component_minor_projection.min())
    if component_major_span <= 1e-6 or component_minor_span <= 1e-6:
        return None
    if component_minor_span > float(max_minor_span_px):
        return None
    if component_major_span / component_minor_span < float(min_blob_aspect_ratio):
        return None

    points_centered = points - component_center
    point_major_projection = points_centered @ component_major_axis
    point_minor_projection = points_centered @ component_minor_axis
    point_major_span = float(point_major_projection.max() - point_major_projection.min())
    if point_major_span <= 1e-6:
        return None
    if point_major_span / component_major_span >= float(max_coverage_ratio):
        return None

    segment_axis = _direction(points)
    if float(np.linalg.norm(segment_axis)) <= 1e-9:
        return None
    if abs(float(np.dot(segment_axis, component_major_axis))) < float(min_alignment):
        return None

    trim = component_major_span * float(trim_fraction)
    target_min = float(component_major_projection.min()) + trim
    target_max = float(component_major_projection.max()) - trim
    if target_max - target_min <= point_major_span + 1e-6:
        return None

    target_span = min(
        (target_max - target_min) * float(target_coverage_ratio),
        point_major_span * float(max_expansion_ratio),
    )
    if target_span <= point_major_span + 0.5:
        return None

    current_min = float(point_major_projection.min())
    current_max = float(point_major_projection.max())
    available_before = max(0.0, current_min - target_min)
    available_after = max(0.0, target_max - current_max)
    total_available = available_before + available_after
    if total_available <= 1e-6:
        return None

    extra_span = min(target_span - point_major_span, total_available)
    if extra_span <= 0.5:
        return None
    expand_before = extra_span * (available_before / total_available)
    expand_after = extra_span * (available_after / total_available)
    extended_min = max(target_min, current_min - expand_before)
    extended_max = min(target_max, current_max + expand_after)
    if extended_max - extended_min <= point_major_span + 0.5:
        return None

    sample_count = max(len(points), int(math.ceil((extended_max - extended_min) / 0.9)) + 1)
    major_values = np.linspace(extended_min, extended_max, num=sample_count)
    if point_major_projection[-1] < point_major_projection[0]:
        major_values = major_values[::-1]
    minor_value = float(np.mean(point_minor_projection))
    candidate = (
        component_center
        + np.outer(major_values, component_major_axis)
        + np.outer(np.full(sample_count, minor_value), component_minor_axis)
    )
    if _support_ratio_in_radius(candidate, foreground_mask, radius_px=support_radius_px) < float(min_support_ratio):
        return None

    updated = _copy_segment(segment)
    updated["points"] = [tuple(float(value) for value in point) for point in candidate]
    return updated


def _segment_prior_subpath_mean_distance(
    segment: dict[str, Any],
    prior_stroke: np.ndarray,
) -> float:
    points = np.asarray(segment.get("points", ()), dtype=float)
    stroke = np.asarray(prior_stroke, dtype=float)
    if len(points) < 2 or len(stroke) < 2:
        return float("inf")
    start_arc = _closest_arc(points[0], stroke)[1]
    end_arc = _closest_arc(points[-1], stroke)[1]
    if end_arc <= start_arc:
        arcs = [_closest_arc(point, stroke)[1] for point in points]
        start_arc = float(min(arcs))
        end_arc = float(max(arcs))
    if end_arc - start_arc <= 1e-6:
        return float("inf")
    prior_subpath = _sample_stroke_subpath(stroke, start_arc, end_arc, step_px=1.0)
    if len(prior_subpath) < 2:
        return float("inf")
    aligned_points = _resample_polyline_to_count(points, len(prior_subpath))
    return float(_mean_polyline_distance(aligned_points, prior_subpath))


def _split_segments_by_prior_runs(
    segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    alignment_penalty_weight: float,
) -> list[dict[str, Any]]:
    split_segments: list[dict[str, Any]] = []
    for segment in segments:
        split_segments.extend(
            _split_segment_by_prior_runs(
                segment,
                prior_strokes,
                alignment_penalty_weight=alignment_penalty_weight,
            )
        )
    return _merge_adjacent_same_component_segments(split_segments)


def _label_segments_by_dominant_prior_component(
    segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    alignment_penalty_weight: float,
) -> list[dict[str, Any]]:
    labelled: list[dict[str, Any]] = []
    for segment in segments:
        copied = _copy_segment(segment)
        points = np.asarray(copied.get("points", ()), dtype=float)
        if len(points) == 0:
            labelled.append(copied)
            continue
        labels = _pointwise_prior_labels(
            points,
            prior_strokes,
            alignment_penalty_weight=alignment_penalty_weight,
        )
        if labels:
            labels = _smooth_prior_label_runs(labels, min_run_points=DEFAULT_MIN_PRIOR_RUN_POINTS)
            copied["component_id"] = _dominant_nonzero_label(labels)
        labelled.append(copied)
    return labelled


def _split_segment_by_prior_runs(
    segment: dict[str, Any],
    prior_strokes: Sequence[np.ndarray],
    *,
    alignment_penalty_weight: float,
) -> list[dict[str, Any]]:
    copied = _copy_segment(segment)
    points = np.asarray(copied.get("points", ()), dtype=float)
    if len(points) == 0:
        return [copied]

    labels = _pointwise_prior_labels(
        points,
        prior_strokes,
        alignment_penalty_weight=alignment_penalty_weight,
    )
    if not labels:
        return [copied]

    labels = _smooth_prior_label_runs(labels, min_run_points=DEFAULT_MIN_PRIOR_RUN_POINTS)
    runs = _label_runs(labels)
    if len(runs) <= 1:
        copied["component_id"] = _dominant_nonzero_label(labels)
        return [copied]

    split: list[dict[str, Any]] = []
    for run_index, (label, start_index, end_index) in enumerate(runs):
        if label <= 0:
            continue
        slice_start = start_index if run_index == 0 else max(0, start_index - 1)
        slice_end = end_index + 1
        run_points = [tuple(float(value) for value in point) for point in points[slice_start:slice_end]]
        if len(run_points) < 2:
            continue
        run_segment = _copy_segment(copied)
        run_segment["points"] = run_points
        run_segment["component_id"] = int(label)
        split.append(run_segment)

    if not split:
        copied["component_id"] = _dominant_nonzero_label(labels)
        return [copied]
    return split


def _merge_adjacent_same_component_segments(segments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for segment in segments:
        copied = _copy_segment(segment)
        if not merged or int(merged[-1].get("component_id", 0)) != int(copied.get("component_id", 0)):
            merged.append(copied)
            continue
        previous_points = list(merged[-1].get("points", ()))
        current_points = list(copied.get("points", ()))
        if not previous_points or not current_points:
            continue
        stitched = previous_points + current_points[1:] if previous_points[-1] == current_points[0] else previous_points + current_points
        merged[-1]["points"] = stitched
        merged[-1]["source_segment_ids"] = tuple(merged[-1].get("source_segment_ids", ())) + tuple(
            copied.get("source_segment_ids", ())
        )
    return merged


def _assign_segments_to_prior_strokes(
    ordered_segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    alignment_penalty_weight: float,
) -> dict[tuple[int, ...], int]:
    assignments: dict[tuple[int, ...], int] = {}
    for segment in ordered_segments:
        points = np.asarray(segment.get("points", ()), dtype=float)
        direction = _direction(points)
        best_cost: tuple[float, int] | None = None
        for index, stroke in enumerate(prior_strokes, start=1):
            prior_direction = _direction(stroke)
            alignment = abs(float(np.dot(direction, prior_direction))) if np.linalg.norm(prior_direction) > 0 else 0.0
            cost = _mean_polyline_distance(points, stroke) + float(alignment_penalty_weight) * (1.0 - alignment)
            candidate = (float(cost), index)
            if best_cost is None or candidate < best_cost:
                best_cost = candidate
        assignments[tuple(segment.get("source_segment_ids", ()))] = 0 if best_cost is None else int(best_cost[1])
    return assignments


def _pointwise_prior_labels(
    points: np.ndarray,
    prior_strokes: Sequence[np.ndarray],
    *,
    alignment_penalty_weight: float,
) -> list[int]:
    if len(points) == 0:
        return []

    tangents = _pointwise_tangents(points)
    labels: list[int] = []
    point_alignment_weight = min(float(alignment_penalty_weight), DEFAULT_POINT_ALIGNMENT_PENALTY_WEIGHT)
    for point, tangent in zip(np.asarray(points, dtype=float), tangents):
        best_cost: tuple[float, int] | None = None
        for index, stroke in enumerate(prior_strokes, start=1):
            distance, _, prior_tangent = _closest_arc_with_tangent(point, stroke)
            alignment = abs(float(np.dot(tangent, prior_tangent))) if float(np.linalg.norm(tangent)) > 0 and float(np.linalg.norm(prior_tangent)) > 0 else 0.0
            cost = float(distance) + point_alignment_weight * (1.0 - alignment)
            candidate = (cost, index)
            if best_cost is None or candidate < best_cost:
                best_cost = candidate
        labels.append(0 if best_cost is None else int(best_cost[1]))
    return labels


def _pointwise_tangents(points: np.ndarray) -> list[np.ndarray]:
    pts = np.asarray(points, dtype=float)
    tangents: list[np.ndarray] = []
    for index in range(len(pts)):
        if len(pts) <= 1:
            tangents.append(np.zeros(2, dtype=float))
            continue
        previous = pts[index - 1] if index > 0 else pts[index]
        following = pts[index + 1] if index + 1 < len(pts) else pts[index]
        vector = following - previous
        norm = float(np.linalg.norm(vector))
        tangents.append(np.zeros(2, dtype=float) if norm <= 1e-9 else vector / norm)
    return tangents


def _smooth_prior_label_runs(labels: Sequence[int], *, min_run_points: int) -> list[int]:
    if min_run_points <= 1:
        return [int(label) for label in labels]
    smoothed = [int(label) for label in labels]
    changed = True
    while changed:
        changed = False
        runs = _label_runs(smoothed)
        for run_index, (label, start_index, end_index) in enumerate(runs):
            if label <= 0 or end_index - start_index + 1 >= min_run_points:
                continue
            previous_label = runs[run_index - 1][0] if run_index > 0 else 0
            next_label = runs[run_index + 1][0] if run_index + 1 < len(runs) else 0
            replacement = previous_label if previous_label == next_label and previous_label > 0 else 0
            if replacement <= 0:
                previous_size = runs[run_index - 1][2] - runs[run_index - 1][1] + 1 if run_index > 0 else -1
                next_size = runs[run_index + 1][2] - runs[run_index + 1][1] + 1 if run_index + 1 < len(runs) else -1
                if previous_size >= next_size and previous_label > 0:
                    replacement = previous_label
                elif next_label > 0:
                    replacement = next_label
            if replacement <= 0:
                continue
            for point_index in range(start_index, end_index + 1):
                smoothed[point_index] = replacement
            changed = True
            break
    return smoothed


def _label_runs(labels: Sequence[int]) -> list[tuple[int, int, int]]:
    if not labels:
        return []
    runs: list[tuple[int, int, int]] = []
    start_index = 0
    current_label = int(labels[0])
    for index, label in enumerate(labels[1:], start=1):
        next_label = int(label)
        if next_label == current_label:
            continue
        runs.append((current_label, start_index, index - 1))
        current_label = next_label
        start_index = index
    runs.append((current_label, start_index, len(labels) - 1))
    return runs


def _dominant_nonzero_label(labels: Sequence[int]) -> int:
    counts: dict[int, int] = {}
    for label in labels:
        value = int(label)
        if value <= 0:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]


def _direction(points: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return np.zeros(2, dtype=float)
    vector = pts[-1] - pts[0]
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return np.zeros(2, dtype=float)
    return vector / norm


def _mean_polyline_distance(points: np.ndarray, stroke: np.ndarray) -> float:
    if len(stroke) == 1:
        return float(np.mean(np.linalg.norm(points - stroke[0], axis=1)))
    distances = []
    for point in np.asarray(points, dtype=float):
        distances.append(min(_point_to_segment_distance(point, stroke[index], stroke[index + 1]) for index in range(len(stroke) - 1)))
    return float(np.mean(distances)) if distances else 0.0


def _point_to_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    _, _, distance = _point_to_segment_projection(point, start, end)
    return distance


def _point_to_segment_projection(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, np.ndarray, float]:
    ab = end - start
    denom = float(np.dot(ab, ab))
    if denom <= 1e-9:
        return 0.0, start, float(np.linalg.norm(point - start))
    t = float(np.dot(point - start, ab) / denom)
    t = min(1.0, max(0.0, t))
    projection = start + t * ab
    return t, projection, float(np.linalg.norm(point - projection))


def _closest_arc(point: np.ndarray, stroke: np.ndarray) -> tuple[float, float]:
    distance, arc, _ = _closest_arc_with_tangent(point, stroke)
    return distance, arc


def _closest_arc_with_tangent(point: np.ndarray, stroke: np.ndarray) -> tuple[float, float, np.ndarray]:
    segment_lengths = np.linalg.norm(np.diff(stroke, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    best_distance = math.inf
    best_arc = 0.0
    best_tangent = np.zeros(2, dtype=float)
    for index in range(len(stroke) - 1):
        t, _, distance = _point_to_segment_projection(point, stroke[index], stroke[index + 1])
        arc = float(cumulative[index] + t * segment_lengths[index])
        if distance < best_distance:
            best_distance = distance
            best_arc = arc
            best_tangent = _direction(np.asarray([stroke[index], stroke[index + 1]], dtype=float))
    return best_distance, best_arc, best_tangent


def _sample_stroke_subpath(stroke: np.ndarray, start_arc: float, end_arc: float, *, step_px: float) -> np.ndarray:
    segment_lengths = np.linalg.norm(np.diff(stroke, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = float(cumulative[-1])
    start_value = min(max(0.0, float(start_arc)), total_length)
    end_value = min(max(0.0, float(end_arc)), total_length)
    reverse = end_value < start_value
    if reverse:
        start_value, end_value = end_value, start_value
    samples = np.arange(start_value, end_value + 1e-6, max(step_px, 1e-6))
    if len(samples) == 0 or samples[-1] < end_value:
        samples = np.append(samples, end_value)
    y = np.interp(samples, cumulative, stroke[:, 0])
    x = np.interp(samples, cumulative, stroke[:, 1])
    out = np.column_stack([y, x])
    return out[::-1] if reverse else out


def _resample_polyline_to_count(points: np.ndarray, count: int) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) == 0:
        return np.zeros((0, 2), dtype=float)
    if len(pts) == 1 or count <= 1:
        return np.repeat(pts[:1], max(count, 1), axis=0)

    segment_lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = float(cumulative[-1])
    if total_length <= 1e-9:
        return np.repeat(pts[:1], count, axis=0)

    targets = np.linspace(0.0, total_length, num=count)
    y = np.interp(targets, cumulative, pts[:, 0])
    x = np.interp(targets, cumulative, pts[:, 1])
    return np.column_stack([y, x])


def _connected_component_containing_point(point: np.ndarray, foreground_mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(foreground_mask, dtype=bool)
    if mask.ndim != 2:
        return np.zeros((0, 2), dtype=float)
    height, width = mask.shape
    y = int(round(float(point[0])))
    x = int(round(float(point[1])))
    if not (0 <= y < height and 0 <= x < width) or not bool(mask[y, x]):
        return np.zeros((0, 2), dtype=float)

    seen = {(y, x)}
    stack = [(y, x)]
    component: list[tuple[float, float]] = []
    while stack:
        row, col = stack.pop()
        if not bool(mask[row, col]):
            continue
        component.append((float(row), float(col)))
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = row + dy
            next_col = col + dx
            if 0 <= next_row < height and 0 <= next_col < width and (next_row, next_col) not in seen:
                if bool(mask[next_row, next_col]):
                    seen.add((next_row, next_col))
                    stack.append((next_row, next_col))
    return np.asarray(component, dtype=float)


def _principal_axes(points: np.ndarray) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return np.zeros(2, dtype=float), None, None
    center = pts.mean(axis=0)
    centered = pts - center
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    return center, np.asarray(vh[0], dtype=float), np.asarray(vh[-1], dtype=float)


def _support_ratio(points: np.ndarray, foreground_mask: np.ndarray) -> float:
    mask = np.asarray(foreground_mask, dtype=bool)
    if mask.ndim != 2 or len(points) == 0:
        return 0.0
    height, width = mask.shape
    hits = 0
    for y, x in np.asarray(points, dtype=float):
        iy = int(round(float(y)))
        ix = int(round(float(x)))
        if 0 <= iy < height and 0 <= ix < width and bool(mask[iy, ix]):
            hits += 1
    return hits / float(len(points))


def _support_ratio_in_radius(points: np.ndarray, foreground_mask: np.ndarray, *, radius_px: int) -> float:
    mask = np.asarray(foreground_mask, dtype=bool)
    if mask.ndim != 2 or len(points) == 0:
        return 0.0
    radius = max(int(radius_px), 0)
    if radius <= 0:
        return _support_ratio(points, mask)

    height, width = mask.shape
    hits = 0
    for y, x in np.asarray(points, dtype=float):
        iy = int(round(float(y)))
        ix = int(round(float(x)))
        y0 = max(0, iy - radius)
        y1 = min(height, iy + radius + 1)
        x0 = max(0, ix - radius)
        x1 = min(width, ix + radius + 1)
        if y0 < y1 and x0 < x1 and bool(mask[y0:y1, x0:x1].any()):
            hits += 1
    return hits / float(len(points))


def _first_forward_index(points: np.ndarray, stroke: np.ndarray, covered_end: float) -> int | None:
    for index, point in enumerate(np.asarray(points, dtype=float)):
        if _closest_arc(point, stroke)[1] > covered_end + 0.5:
            return index
    return None


def _should_split_overlap_append(
    merged_points: np.ndarray,
    candidate_points: np.ndarray,
    *,
    max_gap_px: float,
    direction_cos_min: float,
) -> bool:
    merged = np.asarray(merged_points, dtype=float)
    candidate = np.asarray(candidate_points, dtype=float)
    if len(merged) < 2 or len(candidate) < 2:
        return False

    gap = float(np.linalg.norm(candidate[0] - merged[-1]))
    if gap <= float(max_gap_px):
        return False

    tail_direction = _endpoint_direction(merged, at_end=True)
    head_direction = _endpoint_direction(candidate, at_end=False)
    if float(np.linalg.norm(tail_direction)) <= 1e-9 or float(np.linalg.norm(head_direction)) <= 1e-9:
        return False
    return float(np.dot(tail_direction, head_direction)) < float(direction_cos_min)


def _should_split_sharp_lead_in(
    merged_points: np.ndarray,
    candidate_points: np.ndarray,
    *,
    direction_cos_max: float = DEFAULT_SHARP_LEAD_IN_DIRECTION_COS_MAX,
    length_ratio_max: float = DEFAULT_SHARP_LEAD_IN_LENGTH_RATIO_MAX,
    max_lead_in_length_px: float = DEFAULT_SHARP_LEAD_IN_MAX_LENGTH_PX,
    min_main_length_px: float = DEFAULT_SHARP_LEAD_IN_MIN_MAIN_LENGTH_PX,
) -> bool:
    merged = np.asarray(merged_points, dtype=float)
    candidate = np.asarray(candidate_points, dtype=float)
    if len(merged) < 2 or len(candidate) < 2:
        return False

    merged_length = _polyline_length(merged)
    candidate_length = _polyline_length(candidate)
    if candidate_length < float(min_main_length_px):
        return False
    if merged_length > float(max_lead_in_length_px):
        return False
    if merged_length > candidate_length * float(length_ratio_max):
        return False

    tail_direction = _endpoint_direction(merged, at_end=True)
    head_direction = _endpoint_direction(candidate, at_end=False)
    if float(np.linalg.norm(tail_direction)) <= 1e-9 or float(np.linalg.norm(head_direction)) <= 1e-9:
        return False
    return float(np.dot(tail_direction, head_direction)) <= float(direction_cos_max)


def _endpoint_direction(points: np.ndarray, *, at_end: bool) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return np.zeros(2, dtype=float)
    if at_end:
        start = pts[max(0, len(pts) - 1 - ENDPOINT_DIRECTION_SAMPLE_STEPS)]
        end = pts[-1]
    else:
        start = pts[0]
        end = pts[min(len(pts) - 1, ENDPOINT_DIRECTION_SAMPLE_STEPS)]
    vector = end - start
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return np.zeros(2, dtype=float)
    return vector / norm


def _extend_polyline_endpoint(points: np.ndarray, *, distance_px: float, at_end: bool) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    distance = max(0.0, float(distance_px))
    if len(pts) < 2 or distance <= 0.0:
        return pts.copy()
    direction = _endpoint_direction(pts, at_end=at_end)
    if float(np.linalg.norm(direction)) <= 1e-9:
        return pts.copy()
    if at_end:
        extension = pts[-1] + direction * distance
        return np.vstack([pts, extension])
    extension = pts[0] - direction * distance
    return np.vstack([extension, pts])


def _polyline_length(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    deltas = np.diff(pts, axis=0)
    return float(np.linalg.norm(deltas, axis=1).sum())
