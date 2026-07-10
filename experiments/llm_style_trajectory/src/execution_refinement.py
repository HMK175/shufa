"""Experimental execution-layer refinement helpers.

This module is intentionally local and deterministic. It does not call APIs,
CoppeliaSim, robot SDKs, IK, or real robot commands.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from trajectory_tools import stroke_path_length


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REFINEMENT_PROFILE = EXP_DIR / "configs" / "execution_refinement_profiles.json"


BASELINE_CONNECTOR_RULE = {
    "mode": "all_adjacent",
    "description": "old behavior",
}

FLAT_STROKE_WIDTH_PROFILE = {
    "mode": "constant",
}


def load_refinement_profiles(path: Path | str = DEFAULT_REFINEMENT_PROFILE) -> dict[str, Any]:
    profile_path = Path(path)
    if not profile_path.exists():
        return {
            "connector_rules": {"baseline": dict(BASELINE_CONNECTOR_RULE)},
            "stroke_width_profiles": {"flat": dict(FLAT_STROKE_WIDTH_PROFILE)},
            "visualization": {},
        }
    return json.loads(profile_path.read_text(encoding="utf-8"))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _group_segments(rows: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current_id: Any = object()
    for row in rows:
        segment_id = row.get("segment_id")
        if not groups or segment_id != current_id:
            groups.append([])
            current_id = segment_id
        groups[-1].append(row)
    return groups


def _is_connector_group(group: Sequence[dict[str, Any]]) -> bool:
    return bool(group and str(group[0].get("segment_type")) == "connector")


def _points(group: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[_float(row.get("y")), _float(row.get("x"))] for row in group], dtype=float)


def _stroke_groups(groups: Sequence[Sequence[dict[str, Any]]]) -> list[Sequence[dict[str, Any]]]:
    return [group for group in groups if group and str(group[0].get("segment_type")) == "stroke"]


def _bbox_diagonal(strokes: Sequence[Sequence[dict[str, Any]]]) -> float:
    point_sets = [_points(group) for group in strokes if group]
    if not point_sets:
        return 1.0
    pts = np.vstack(point_sets)
    span = np.max(pts, axis=0) - np.min(pts, axis=0)
    return max(float(np.linalg.norm(span)), 1.0)


def _bbox_center(strokes: Sequence[Sequence[dict[str, Any]]]) -> np.ndarray:
    point_sets = [_points(group) for group in strokes if group]
    if not point_sets:
        return np.asarray([0.0, 0.0], dtype=float)
    pts = np.vstack(point_sets)
    return (np.max(pts, axis=0) + np.min(pts, axis=0)) * 0.5


def _angle_deg(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= 1e-9 or right_norm <= 1e-9:
        return 0.0
    cos_value = float(np.dot(left, right) / (left_norm * right_norm))
    cos_value = max(-1.0, min(1.0, cos_value))
    return math.degrees(math.acos(cos_value))


def _line_passes_near_center(start: np.ndarray, end: np.ndarray, center: np.ndarray, diagonal: float) -> bool:
    segment = end - start
    length = float(np.linalg.norm(segment))
    if length <= 1e-9 or length < diagonal * 0.25:
        return False
    t = float(np.dot(center - start, segment) / max(length * length, 1e-9))
    if t <= 0.0 or t >= 1.0:
        return False
    projection = start + segment * t
    distance = float(np.linalg.norm(center - projection))
    return distance < diagonal * 0.08


def _neighbor_strokes(
    groups: Sequence[Sequence[dict[str, Any]]],
    index: int,
) -> tuple[Sequence[dict[str, Any]] | None, Sequence[dict[str, Any]] | None]:
    prev_stroke = None
    for left in range(index - 1, -1, -1):
        if groups[left] and str(groups[left][0].get("segment_type")) == "stroke":
            prev_stroke = groups[left]
            break
    next_stroke = None
    for right in range(index + 1, len(groups)):
        if groups[right] and str(groups[right][0].get("segment_type")) == "stroke":
            next_stroke = groups[right]
            break
    return prev_stroke, next_stroke


def _connector_distance(group: Sequence[dict[str, Any]]) -> float:
    pts = _points(group)
    if len(pts) < 2:
        return 0.0
    return float(np.linalg.norm(pts[-1] - pts[0]))


def _connector_distance_limit(
    *,
    rule: dict[str, Any],
    groups: Sequence[Sequence[dict[str, Any]]],
) -> float | None:
    if not bool(rule.get("prefer_short_connectors", False)):
        return None
    connector_distances: list[float] = []
    for index, group in enumerate(groups):
        if not _is_connector_group(group):
            continue
        prev_stroke, next_stroke = _neighbor_strokes(groups, index)
        if prev_stroke is None or next_stroke is None:
            continue
        distance = _connector_distance(group)
        if distance > 1e-9:
            connector_distances.append(distance)
    if not connector_distances:
        return None
    quantile = max(0.0, min(1.0, _float(rule.get("short_connector_quantile"), 1.0)))
    return float(np.quantile(np.asarray(connector_distances, dtype=float), quantile))


def should_keep_connector(
    *,
    connector_group: Sequence[dict[str, Any]],
    prev_stroke: Sequence[dict[str, Any]] | None,
    next_stroke: Sequence[dict[str, Any]] | None,
    connector_rule: dict[str, Any] | None,
    style: str,
    connection_preference: str,
    connector_index: int = 1,
    all_strokes: Sequence[Sequence[dict[str, Any]]] | None = None,
    distance_limit: float | None = None,
) -> bool:
    rule = connector_rule or BASELINE_CONNECTOR_RULE
    mode = str(rule.get("mode", "all_adjacent"))
    if mode == "all_adjacent":
        return True
    if style != "xingkai" or connection_preference == "none":
        return False
    if not connector_group or prev_stroke is None or next_stroke is None:
        return False

    connector_pts = _points(connector_group)
    if len(connector_pts) < 2:
        return False
    start = connector_pts[0]
    end = connector_pts[-1]
    distance = float(np.linalg.norm(end - start))

    min_distance = _float(rule.get("min_stroke_endpoint_distance"), 0.0)
    if distance < min_distance:
        return False
    if distance_limit is not None and distance > distance_limit:
        return False
    max_abs = _float(rule.get("max_connector_distance_abs"), float("inf"))
    if distance > max_abs:
        return False

    strokes = list(all_strokes or [])
    diagonal = _bbox_diagonal(strokes)
    max_ratio = _float(rule.get("max_connector_distance_ratio"), float("inf"))
    if distance / diagonal > max_ratio:
        return False

    every_n = max(1, _int(rule.get("connect_every_n"), 1))
    if every_n > 1 and (connector_index - 1) % every_n != 0:
        return False

    prev_pts = _points(prev_stroke)
    next_pts = _points(next_stroke)
    prev_dir = prev_pts[-1] - prev_pts[-2] if len(prev_pts) >= 2 else end - start
    next_dir = next_pts[1] - next_pts[0] if len(next_pts) >= 2 else end - start
    conn_dir = end - start
    max_angle = _float(rule.get("max_turn_angle_deg"), 180.0)
    if max(_angle_deg(prev_dir, conn_dir), _angle_deg(conn_dir, next_dir)) > max_angle:
        return False

    if bool(rule.get("skip_if_crosses_bbox_center", False)) and strokes:
        if _line_passes_near_center(start, end, _bbox_center(strokes), diagonal):
            return False

    return True


def _convert_connector_to_pen_up(group: Sequence[dict[str, Any]], pen_up_height: float) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in group:
        item = deepcopy(row)
        item["z"] = float(pen_up_height)
        item["speed"] = max(_float(item.get("speed"), 1.0), 1.6)
        item["pressure"] = 0.0
        item["width"] = 0.0
        item["pen_down"] = 0
        item["is_connector"] = 0
        item["segment_type"] = "pen_up_move"
        converted.append(item)
    return converted


def _curve_connector(group: Sequence[dict[str, Any]], connector_shape: dict[str, Any] | None) -> list[dict[str, Any]]:
    shape = connector_shape or {"mode": "straight"}
    if str(shape.get("mode", "straight")) != "quadratic_bezier" or len(group) < 2:
        return [deepcopy(row) for row in group]

    pts = _points(group)
    start = pts[0]
    end = pts[-1]
    delta = end - start
    length = float(np.linalg.norm(delta))
    if length <= 1e-9:
        return [deepcopy(row) for row in group]

    normal = np.asarray([-delta[1], delta[0]], dtype=float) / length
    offset = min(_float(shape.get("max_offset"), 18.0), length * _float(shape.get("offset_ratio"), 0.12))
    control = (start + end) * 0.5 + normal * offset
    count = max(len(group), _int(shape.get("resample_points"), 5))
    curved: list[dict[str, Any]] = []
    first = group[0]
    last = group[-1]
    for idx, t in enumerate(np.linspace(0.0, 1.0, count)):
        point = ((1.0 - t) ** 2) * start + 2.0 * (1.0 - t) * t * control + (t**2) * end
        template = first if idx < count - 1 else last
        item = deepcopy(template)
        item["point_id"] = _int(first.get("point_id"), 0) + idx
        item["y"] = float(point[0])
        item["x"] = float(point[1])
        item["connector_shape"] = "slight_curve"
        curved.append(item)
    return curved


def _ease(left: float, right: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    eased = 0.5 - 0.5 * math.cos(math.pi * t)
    return left + (right - left) * eased


def _taper_scale(s: float, start: float, mid: float, end: float) -> float:
    if s <= 0.5:
        return _ease(start, mid, s / 0.5)
    return _ease(mid, end, (s - 0.5) / 0.5)


def _stroke_positions(group: Sequence[dict[str, Any]]) -> list[float]:
    pts = _points(group)
    if len(pts) <= 1:
        return [0.0 for _ in group]
    distances = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = float(np.sum(distances))
    if total <= 1e-9:
        return [0.0 for _ in group]
    arc = np.concatenate([[0.0], np.cumsum(distances)])
    return [float(value / total) for value in arc]


def _apply_stroke_taper(group: Sequence[dict[str, Any]], profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    profile = profile or FLAT_STROKE_WIDTH_PROFILE
    if str(profile.get("mode", "constant")) == "constant":
        return [deepcopy(row) for row in group]
    start_w = _float(profile.get("start_width_scale"), 0.78)
    mid_w = _float(profile.get("mid_width_scale"), 1.12)
    end_w = _float(profile.get("end_width_scale"), 0.82)
    start_p = _float(profile.get("start_pressure_scale"), 0.82)
    mid_p = _float(profile.get("mid_pressure_scale"), 1.0)
    end_p = _float(profile.get("end_pressure_scale"), 0.88)
    out: list[dict[str, Any]] = []
    for row, s in zip(group, _stroke_positions(group)):
        item = deepcopy(row)
        item["width"] = max(0.1, _float(item.get("width"), 0.0) * _taper_scale(s, start_w, mid_w, end_w))
        item["pressure"] = max(0.0, min(1.0, _float(item.get("pressure"), 1.0) * _taper_scale(s, start_p, mid_p, end_p)))
        out.append(item)
    return out


def refine_execution_rows(
    rows: Sequence[dict[str, Any]],
    *,
    style: str,
    style_modifiers: dict[str, str] | None,
    connector_rule: dict[str, Any] | None = None,
    stroke_width_profile: dict[str, Any] | None = None,
    connector_shape: dict[str, Any] | None = None,
    pen_up_height: float | None = None,
) -> list[dict[str, Any]]:
    groups = _group_segments(rows)
    strokes = _stroke_groups(groups)
    preference = str((style_modifiers or {}).get("connection_preference", "weak"))
    rule = connector_rule or BASELINE_CONNECTOR_RULE
    profile = stroke_width_profile or FLAT_STROKE_WIDTH_PROFILE
    lift = float(pen_up_height if pen_up_height is not None else 8.0)
    out: list[dict[str, Any]] = []
    connector_index = 0
    distance_limit = _connector_distance_limit(rule=rule, groups=groups)

    for index, group in enumerate(groups):
        if not group:
            continue
        segment_type = str(group[0].get("segment_type"))
        if segment_type == "stroke":
            out.extend(_apply_stroke_taper(group, profile))
        elif segment_type == "connector":
            connector_index += 1
            prev_stroke, next_stroke = _neighbor_strokes(groups, index)
            keep = should_keep_connector(
                connector_group=group,
                prev_stroke=prev_stroke,
                next_stroke=next_stroke,
                connector_rule=rule,
                style=style,
                connection_preference=preference,
                connector_index=connector_index,
                all_strokes=strokes,
                distance_limit=distance_limit,
            )
            out.extend(_curve_connector(group, connector_shape) if keep else _convert_connector_to_pen_up(group, lift))
        else:
            out.extend([deepcopy(row) for row in group])
    return out


def execution_refinement_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float | int]:
    connector_ids = {row.get("segment_id") for row in rows if str(row.get("segment_type")) == "connector"}
    stroke_widths = [_float(row.get("width")) for row in rows if str(row.get("segment_type")) == "stroke"]
    stroke_pressures = [_float(row.get("pressure")) for row in rows if str(row.get("segment_type")) == "stroke"]
    lengths = {"stroke": 0.0, "connector": 0.0, "pen_up_move": 0.0}
    connector_width_weight = 0.0
    connector_pressure_weight = 0.0
    connector_weight = 0.0
    draw_weight = 0.0
    mean_width_weight = 0.0

    for group in _group_segments(rows):
        if not group:
            continue
        segment_type = str(group[0].get("segment_type"))
        length = stroke_path_length(_points(group))
        lengths[segment_type] = lengths.get(segment_type, 0.0) + length
        width = _float(group[0].get("width"))
        pressure = _float(group[0].get("pressure"))
        if _int(group[0].get("pen_down")):
            draw_weight += length
            mean_width_weight += width * length
        if segment_type == "connector":
            connector_weight += length
            connector_width_weight += width * length
            connector_pressure_weight += pressure * length

    return {
        "connection_count": len(connector_ids),
        "connector_draw_length": round(lengths.get("connector", 0.0), 3),
        "pen_up_move_length": round(lengths.get("pen_up_move", 0.0), 3),
        "connector_mean_width": round(connector_width_weight / connector_weight, 6) if connector_weight else 0.0,
        "connector_mean_pressure": round(connector_pressure_weight / connector_weight, 6) if connector_weight else 0.0,
        "stroke_width_min": round(min(stroke_widths), 6) if stroke_widths else 0.0,
        "stroke_width_max": round(max(stroke_widths), 6) if stroke_widths else 0.0,
        "stroke_width_range": round(max(stroke_widths) - min(stroke_widths), 6) if stroke_widths else 0.0,
        "stroke_pressure_min": round(min(stroke_pressures), 6) if stroke_pressures else 0.0,
        "stroke_pressure_max": round(max(stroke_pressures), 6) if stroke_pressures else 0.0,
        "stroke_pressure_range": round(max(stroke_pressures) - min(stroke_pressures), 6) if stroke_pressures else 0.0,
        "mean_width": round(mean_width_weight / draw_weight, 6) if draw_weight else 0.0,
        "path_length": round(sum(lengths.values()), 3),
    }
