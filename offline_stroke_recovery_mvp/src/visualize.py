"""Dependency-light PNG debug writers for offline stroke recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from stroke_primitives import transfer_relative_width_factors


PALETTE = [
    (230, 57, 70),
    (29, 53, 87),
    (42, 157, 143),
    (244, 162, 97),
    (131, 56, 236),
    (255, 183, 3),
    (0, 109, 119),
]
DEFAULT_EXECUTION_WIDTH_SEARCH_RADIUS_PX = 12.0
DEFAULT_EXECUTION_WIDTH_SAMPLE_STEP_PX = 0.5
DEFAULT_EXECUTION_WIDTH_RENDER_SCALE = 0.85
DEFAULT_EXECUTION_RENDER_MODE = "variable"
DEFAULT_EXECUTION_EDGE_SOFTEN_RADIUS_PX = 0.0
DEFAULT_EXECUTION_WIDTH_SMOOTH_WINDOW_RADIUS = 2
DEFAULT_EXECUTION_WIDTH_UPPER_SCALE = 1.35
DEFAULT_RENDER_SUBPATH_COALESCE_GAP_PX = 6.5
DEFAULT_RENDER_SUBPATH_COALESCE_DIRECTION_COS_THRESHOLD = 0.95
DEFAULT_RENDER_SUBPATH_COALESCE_MIN_AXIS_RATIO = 14.0
DEFAULT_RENDER_SUBPATH_COALESCE_MAX_AXIS_RESIDUAL_PX = 0.35
DEFAULT_RENDER_SUBPATH_COALESCE_MIN_SUBPATH_LENGTH_PX = 12.0
DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_DISTANCE_PX = 1.5
DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_POINT_COUNT = 15
DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_REFERENCE_SCALE = 0.38
DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_DISTANCE_PX = 1.25
DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_MAX_TRIM_POINTS = 4
DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MIN_LENGTH_PX = 12.0
DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MAX_LENGTH_PX = 28.0
DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MIN_CV = 0.35
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MIN_POINT_COUNT = 12
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MIN_AXIS_RATIO = 20.0
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_AXIS_RESIDUAL_PX = 0.35
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_CV = 0.25
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_SPAN_RATIO = 0.6
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_SHARP_TURNS = 2
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_BLEND = 0.9
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_ENDPOINT_PRESERVE_COUNT = 6
DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_BODY_BAND_RATIO = 0.15
DEFAULT_ANCHORED_ENDPOINT_DISTANCE_PX = 2.25
DEFAULT_NEARBY_FREE_ENDPOINT_DISTANCE_PX = 4.0
DEFAULT_ANCHORED_ENDPOINT_TAPER_POINT_COUNT = 5
DEFAULT_ANCHORED_ENDPOINT_TAPER_REFERENCE_SCALE = 0.75
DEFAULT_ATTACHED_ENDPOINT_SPIKE_RATIO = 1.18
DEFAULT_ATTACHED_ENDPOINT_TAPER_POINT_COUNT = 5
DEFAULT_ATTACHED_ENDPOINT_TAPER_REFERENCE_SCALE = 0.9
DEFAULT_FREE_ENDPOINT_SPIKE_RATIO = 1.18
DEFAULT_FREE_ENDPOINT_TAPER_POINT_COUNT = 4
DEFAULT_FREE_ENDPOINT_TAPER_REFERENCE_SCALE = 1.0
DEFAULT_SHORT_ATTACHED_SEGMENT_MAX_PATH_TO_DIAMETER_RATIO = 1.15
DEFAULT_SHORT_ATTACHED_SEGMENT_FREE_CAP_MIN_PATH_TO_DIAMETER_RATIO = 0.85
DEFAULT_SHORT_ATTACHED_SEGMENT_BODY_TARGET_PATH_TO_DIAMETER_RATIO = 0.75
DEFAULT_SHORT_ATTACHED_SEGMENT_BODY_MIN_SCALE = 0.5
DEFAULT_SHORT_ATTACHED_SINGLE_SOURCE_TARGET_PATH_TO_DIAMETER_RATIO = 1.5
DEFAULT_SHORT_ATTACHED_SINGLE_SOURCE_BODY_MIN_SCALE = 0.3
DEFAULT_SHORT_ATTACHED_FREE_TIP_MIN_PATH_TO_DIAMETER_RATIO = 0.75
DEFAULT_SHORT_ATTACHED_FREE_TIP_MAX_PATH_TO_DIAMETER_RATIO = 1.75
DEFAULT_SHORT_ATTACHED_FREE_TIP_MAX_LENGTH_PX = 10.5
DEFAULT_SHORT_ATTACHED_FREE_TIP_TAPER_POINT_COUNT = 4
DEFAULT_SHORT_ATTACHED_FREE_TIP_REFERENCE_SCALE = 0.45
DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_LENGTH_PX = 5.0
DEFAULT_SHORT_FREE_LINEAR_BRANCH_MAX_LENGTH_PX = 10.5
DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_AXIS_RATIO = 6.0
DEFAULT_SHORT_FREE_LINEAR_BRANCH_TARGET_PATH_TO_DIAMETER_RATIO = 1.8
DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_SCALE = 0.5
DEFAULT_SHORT_FREE_LINEAR_BRANCH_TIP_TAPER_POINT_COUNT = 4
DEFAULT_SHORT_FREE_LINEAR_BRANCH_TIP_SCALE = 0.65
DEFAULT_SHORT_INCOMPLETE_DOT_MAX_LENGTH_PX = 10.5
DEFAULT_SHORT_INCOMPLETE_DOT_MAX_POINT_COUNT = 12
DEFAULT_SHORT_INCOMPLETE_DOT_BOOST_SCALE = 1.18
DEFAULT_SHORT_INCOMPLETE_DOT_ENDPOINT_SCALE = 1.08
DEFAULT_SHORT_INCOMPLETE_DOT_ENDPOINT_EXTENSION_PX = 0.85
DEFAULT_VARIABLE_WIDTH_ROUND_JOIN_MAX_COS = 0.65
DEFAULT_VARIABLE_WIDTH_ROUND_JOIN_RADIUS_SCALE = 0.55
DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_RADIUS_SCALE = 0.90
DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_MIN_PATH_LENGTH_PX = 70.0
DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_FOLDBACK_MAX_COS = -0.50
DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_WINDOW_POINTS = 12
DEFAULT_INTERNAL_WIDTH_DROPOUT_MAX_RUN_POINTS = 4
DEFAULT_INTERNAL_WIDTH_DROPOUT_DROP_RATIO = 0.55
DEFAULT_INTERNAL_WIDTH_DROPOUT_RECOVERY_RATIO = 0.85
DEFAULT_INTERNAL_WIDTH_DROPOUT_ENDPOINT_GUARD_POINTS = 6
DEFAULT_ANCHORED_OVERLAP_TRIM_MAX_STEP_PX = 2.0
DEFAULT_ANCHORED_OVERLAP_TRIM_MIN_IMPROVEMENT_PX = 0.05
DEFAULT_DOUBLE_ANCHORED_OVERLAP_TRIM_MAX_TOTAL_LENGTH_PX = 10.0
DEFAULT_CORNER_TERMINAL_CAP_TURN_COS_THRESHOLD = 0.6
DEFAULT_CORNER_TERMINAL_CAP_MAX_BRANCH_RATIO = 0.3
DEFAULT_CORNER_TERMINAL_CAP_MIN_BRANCH_LENGTH_PX = 6.0
DEFAULT_CORNER_TERMINAL_BRANCH_TAPER_REFERENCE_SCALE = 0.6
DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MIN_PATH_LENGTH_PX = 70.0
DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MAX_TURN_COS = -0.5
DEFAULT_LONG_FOLDBACK_TAIL_TAPER_POINT_COUNT = 14
DEFAULT_LONG_FOLDBACK_TAIL_TAPER_REFERENCE_SCALE = 0.4
DEFAULT_LONG_FOLDBACK_TURN_CLAMP_WINDOW_POINTS = 8
DEFAULT_LONG_FOLDBACK_TURN_CLAMP_MAX_SCALE = 1.05
DEFAULT_POINTED_FOLDBACK_TAPER_FRACTION = 0.25
DEFAULT_POINTED_FOLDBACK_MIN_TAPER_POINTS = 18
DEFAULT_ANCHORED_CORNER_EXTENSION_PX = 0.75
DEFAULT_ANCHORED_CORNER_EXTENSION_DIRECTION_DOT_MAX = 0.45


def write_mask_png(path: Path, mask: np.ndarray, *, scale: int = 8) -> None:
    canvas = _base(mask, scale=scale)
    pixels = np.asarray(mask, dtype=bool)
    draw = ImageDraw.Draw(canvas)
    for y, x in zip(*np.nonzero(pixels)):
        _cell(draw, int(y), int(x), scale, (20, 20, 20))
    _save(canvas, path)


def write_skeleton_png(path: Path, skeleton: np.ndarray, *, scale: int = 8) -> None:
    canvas = _base(skeleton, scale=scale)
    draw = ImageDraw.Draw(canvas)
    for y, x in zip(*np.nonzero(np.asarray(skeleton, dtype=bool))):
        _cell(draw, int(y), int(x), scale, (220, 20, 60))
    _save(canvas, path)


def write_segments_png(path: Path, skeleton: np.ndarray, segments: Sequence[dict[str, Any]], *, scale: int = 8) -> None:
    canvas = _base(skeleton, scale=scale)
    draw = ImageDraw.Draw(canvas)
    _draw_light_skeleton(draw, skeleton, scale)
    for index, segment in enumerate(segments):
        _draw_points(draw, segment.get("points", ()), scale, PALETTE[index % len(PALETTE)])
    _save(canvas, path)


def write_order_png(path: Path, skeleton: np.ndarray, ordered_segments: Sequence[dict[str, Any]], *, scale: int = 8) -> None:
    canvas = _base(skeleton, scale=scale)
    draw = ImageDraw.Draw(canvas)
    _draw_light_skeleton(draw, skeleton, scale)
    label_positions: dict[tuple[int, int], int] = {}
    for index, segment in enumerate(ordered_segments):
        color = PALETTE[index % len(PALETTE)]
        points = list(segment.get("points", ()))
        _draw_points(draw, points, scale, color)
        if points:
            label = str(segment.get("order_index", index + 1))
            label_xy = _label_xy(points, scale, label_positions)
            _draw_label(draw, label_xy, label)
    _save(canvas, path)


def write_trajectory_png(
    path: Path,
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 8,
    show_pen_up_connectors: bool = True,
) -> None:
    canvas = _base(skeleton, scale=scale)
    draw = ImageDraw.Draw(canvas)
    _draw_light_skeleton(draw, skeleton, scale)
    history_points: list[list[tuple[float, float]]] = []
    if show_pen_up_connectors:
        _draw_pen_up_connectors(draw, ordered_segments, scale)
    for index, segment in enumerate(ordered_segments):
        points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
        if points and (
            len(tuple(segment.get("source_segment_ids", ()))) > 1
            or len(tuple(segment.get("render_subpaths", ()))) > 1
        ):
            trim_start_points = _history_overlap_trim_count(history_points, points)
            if trim_start_points > 0:
                points = _trim_render_overlap_stub_points(
                    points,
                    trim_start_points=trim_start_points,
                    trim_end_points=0,
                )
        _draw_polyline(draw, points, scale, PALETTE[index % len(PALETTE)])
        if points:
            history_points.append(points)
    _save(canvas, path)


def write_execution_render_png(
    path: Path,
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 8,
    foreground_mask: np.ndarray | None = None,
    render_mode: str = DEFAULT_EXECUTION_RENDER_MODE,
    edge_soften_radius_px: float = DEFAULT_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
) -> None:
    canvas = render_execution_image(
        skeleton,
        ordered_segments,
        scale=scale,
        foreground_mask=foreground_mask,
        render_mode=render_mode,
        edge_soften_radius_px=edge_soften_radius_px,
    )
    _save(canvas, path)


def write_execution_playback_contact_sheet(
    path: Path,
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 3,
    panel_size: tuple[int, int] = (180, 180),
    padding: int = 10,
    header_height: int = 18,
    max_columns: int = 4,
    foreground_mask: np.ndarray | None = None,
    edge_soften_radius_px: float = DEFAULT_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
) -> None:
    segment_count = max(len(ordered_segments), 1)
    columns = max(1, min(max_columns, segment_count))
    rows = max(int(np.ceil(segment_count / float(columns))), 1)
    width = padding + columns * (panel_size[0] + padding)
    height = padding + rows * (header_height + panel_size[1] + padding)

    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for step in range(segment_count):
        row = step // columns
        column = step % columns
        left = padding + column * (panel_size[0] + padding)
        top = padding + row * (header_height + panel_size[1] + padding)
        draw.text((left, top), f"step {step + 1}", fill=(30, 30, 30))
        rendered = render_execution_image(
            skeleton,
            ordered_segments[: step + 1],
            scale=scale,
            foreground_mask=foreground_mask,
            edge_soften_radius_px=edge_soften_radius_px,
        )
        panel = _fit_image_to_panel(rendered, panel_size)
        panel_top = top + header_height
        canvas.paste(panel, (left, panel_top))
        draw.rectangle(
            (left, panel_top, left + panel_size[0] - 1, panel_top + panel_size[1] - 1),
            outline=(200, 200, 200),
        )
    _save(canvas, path)


def write_trajectory_playback_contact_sheet(
    path: Path,
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 3,
    panel_size: tuple[int, int] = (180, 180),
    padding: int = 10,
    header_height: int = 18,
    max_columns: int = 4,
) -> None:
    scale = max(int(scale), 1)
    panel_size = (
        max(int(panel_size[0]), 1),
        max(int(panel_size[1]), 1),
    )
    padding = max(int(padding), 0)
    header_height = max(int(header_height), 0)
    max_columns = max(int(max_columns), 1)

    segment_count = max(len(ordered_segments), 1)
    columns = max(1, min(max_columns, segment_count))
    rows = max(int(np.ceil(segment_count / float(columns))), 1)
    width = padding + columns * (panel_size[0] + padding)
    height = padding + rows * (header_height + panel_size[1] + padding)

    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for step in range(segment_count):
        row = step // columns
        column = step % columns
        left = padding + column * (panel_size[0] + padding)
        top = padding + row * (header_height + panel_size[1] + padding)
        draw.text((left, top), f"step {step + 1}", fill=(30, 30, 30))
        panel_canvas = _base(skeleton, scale=scale)
        panel_draw = ImageDraw.Draw(panel_canvas)
        for index, segment in enumerate(ordered_segments[: step + 1]):
            _draw_polyline(
                panel_draw,
                segment.get("points", ()),
                scale,
                PALETTE[index % len(PALETTE)],
            )
        panel = _fit_image_to_panel(panel_canvas, panel_size)
        panel_top = top + header_height
        canvas.paste(panel, (left, panel_top))
        draw.rectangle(
            (left, panel_top, left + panel_size[0] - 1, panel_top + panel_size[1] - 1),
            outline=(200, 200, 200),
        )
    _save(canvas, path)


def render_execution_image(
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 8,
    foreground_mask: np.ndarray | None = None,
    render_mode: str = DEFAULT_EXECUTION_RENDER_MODE,
    edge_soften_radius_px: float = DEFAULT_EXECUTION_EDGE_SOFTEN_RADIUS_PX,
) -> Image.Image:
    if render_mode not in {"variable", "segment_constant", "fixed"}:
        raise ValueError(f"Unsupported render_mode: {render_mode}")
    canvas = _base(skeleton, scale=scale)
    ink_mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(ink_mask)
    endpoint_cap_policies = _build_endpoint_cap_policies(ordered_segments)
    history_points: list[list[tuple[float, float]]] = []
    for segment, endpoint_cap_policy in zip(ordered_segments, endpoint_cap_policies):
        segment_points = [tuple(_as_float_point(point)) for point in segment.get("points", ())]
        history_overlap_trim_points = 0
        if segment_points and (
            len(tuple(segment.get("source_segment_ids", ()))) > 1
            or len(tuple(segment.get("render_subpaths", ()))) > 1
        ):
            history_overlap_trim_points = _history_overlap_trim_count(history_points, segment_points)
        _draw_execution_polyline(
            draw,
            segment_points,
            scale,
            foreground_mask=foreground_mask,
            cap_start=bool(endpoint_cap_policy["cap_start"]),
            cap_end=bool(endpoint_cap_policy["cap_end"]),
            extend_start_px=float(endpoint_cap_policy.get("extend_start_px", 0.0)),
            extend_end_px=float(endpoint_cap_policy.get("extend_end_px", 0.0)),
            trim_start_points=int(endpoint_cap_policy.get("trim_start_points", 0)) + int(history_overlap_trim_points),
            trim_end_points=int(endpoint_cap_policy.get("trim_end_points", 0)),
            source_segment_ids=segment.get("source_segment_ids", ()),
            render_subpaths=segment.get("render_subpaths", ()),
            render_subpath_source_ids=segment.get("render_subpath_source_ids", ()),
            render_mode=render_mode,
            pointed_start=bool(segment.get("pointed_start", False)),
            pointed_end=bool(segment.get("pointed_end", False)),
            primitive_relative_widths=segment.get("primitive_relative_widths", ()),
            primitive_width_blend=float(segment.get("primitive_width_blend", 0.7)),
        )
        if segment_points:
            history_points.append(segment_points)
    alpha_mask = ink_mask
    if edge_soften_radius_px > 0:
        blurred_mask = ink_mask.filter(ImageFilter.GaussianBlur(radius=float(edge_soften_radius_px)))
        alpha_mask = ImageChops.lighter(ink_mask, blurred_mask)
    ink_layer = Image.new("RGB", canvas.size, (24, 24, 24))
    canvas.paste(ink_layer, mask=alpha_mask)
    return canvas


def _base(mask: np.ndarray, *, scale: int) -> Image.Image:
    arr = np.asarray(mask)
    height, width = arr.shape
    return Image.new("RGB", (max(width * scale, 1), max(height * scale, 1)), (255, 255, 255))


def _draw_light_skeleton(draw: ImageDraw.ImageDraw, skeleton: np.ndarray, scale: int) -> None:
    for y, x in zip(*np.nonzero(np.asarray(skeleton, dtype=bool))):
        _cell(draw, int(y), int(x), scale, (220, 220, 220))


def _draw_points(draw: ImageDraw.ImageDraw, points: Iterable[Any], scale: int, color: tuple[int, int, int]) -> None:
    for point in points:
        y, x = _as_int_point(point)
        _cell(draw, y, x, scale, color)


def _draw_polyline(draw: ImageDraw.ImageDraw, points: Iterable[Any], scale: int, color: tuple[int, int, int]) -> None:
    scaled_points = [(_scaled_xy_continuous(point, scale)) for point in points]
    if len(scaled_points) == 1:
        x, y = scaled_points[0]
        radius = max(scale // 3, 1)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    elif len(scaled_points) > 1:
        draw.line(scaled_points, fill=color, width=max(scale // 2, 1), joint="curve")


def _draw_execution_polyline(
    draw: ImageDraw.ImageDraw,
    points: Iterable[Any],
    scale: int,
    *,
    foreground_mask: np.ndarray | None,
    cap_start: bool,
    cap_end: bool,
    extend_start_px: float = 0.0,
    extend_end_px: float = 0.0,
    trim_start_points: int = 0,
    trim_end_points: int = 0,
    source_segment_ids: Sequence[Any] = (),
    render_subpaths: Sequence[Sequence[tuple[float, float]]] = (),
    render_subpath_source_ids: Sequence[Sequence[Any]] = (),
    render_mode: str = DEFAULT_EXECUTION_RENDER_MODE,
    pointed_start: bool = False,
    pointed_end: bool = False,
    primitive_relative_widths: Sequence[float] = (),
    primitive_width_blend: float = 0.7,
) -> None:
    original_points = [tuple(_as_float_point(point)) for point in points]
    original_points = _trim_render_overlap_stub_points(
        original_points,
        trim_start_points=trim_start_points,
        trim_end_points=trim_end_points,
    )
    dot_extend_start_px, dot_extend_end_px = _short_incomplete_dot_endpoint_extensions_px(
        original_points,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    original_points = _apply_endpoint_extensions(
        original_points,
        extend_start_px=extend_start_px + dot_extend_start_px,
        extend_end_px=extend_end_px + dot_extend_end_px,
    )
    point_list = _simplify_render_points(original_points)
    scaled_points = [(_scaled_xy_continuous(point, scale)) for point in point_list]
    ink = 255
    radius = max(scale // 3, 1)
    if len(scaled_points) == 1:
        x, y = scaled_points[0]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ink)
        return
    if len(scaled_points) <= 1:
        return

    auto_pointed_start, auto_pointed_end = _pointed_foldback_terminal_flags(
        original_points,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    pointed_start = bool(pointed_start) or auto_pointed_start
    pointed_end = bool(pointed_end) or auto_pointed_end

    if render_mode == "fixed" or foreground_mask is None:
        _draw_constant_width_execution_polyline(
            draw,
            scaled_points,
            ink=ink,
            width=max((scale * 3) // 4, 1),
            cap_start=cap_start,
            cap_end=cap_end,
            min_cap_radius=float(radius),
        )
        return

    sampled_points = _sample_polyline_points(
        original_points,
        step_px=1.0,
    )
    if not sampled_points:
        return
    if render_mode == "segment_constant":
        segment_diameter = _estimate_segment_brush_diameter_px(
            sampled_points,
            np.asarray(foreground_mask, dtype=bool),
        )
        execution_width = max(
            int(round(segment_diameter * float(scale) * DEFAULT_EXECUTION_WIDTH_RENDER_SCALE)),
            max((scale * 3) // 4, 1),
        )
        _draw_constant_width_execution_polyline(
            draw,
            scaled_points,
            ink=ink,
            width=execution_width,
            cap_start=cap_start,
            cap_end=cap_end,
            min_cap_radius=float(radius),
        )
        return

    if render_subpaths and not primitive_relative_widths and _draw_piecewise_variable_width_subpaths(
        draw,
        render_subpaths=render_subpaths,
        render_subpath_source_ids=render_subpath_source_ids,
        scale=scale,
        foreground_mask=np.asarray(foreground_mask, dtype=bool),
        ink=ink,
        min_width=max((scale * 3) // 4, 1),
        min_radius=float(radius),
        cap_start=cap_start,
        cap_end=cap_end,
        pointed_start=pointed_start,
        pointed_end=pointed_end,
    ):
        return

    profile = _build_variable_width_profile(
        original_points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
        primitive_relative_widths=primitive_relative_widths,
        primitive_width_blend=primitive_width_blend,
    )
    if profile is None:
        return
    sampled_points, tapered_diameters, effective_cap_start, effective_cap_end = profile
    if not (pointed_start or pointed_end) and _should_fallback_to_segment_constant_render_for_short_volatile_segment(
        sampled_points,
        tapered_diameters,
        cap_start=effective_cap_start,
        cap_end=effective_cap_end,
        source_segment_ids=source_segment_ids,
    ):
        segment_diameter = _robust_segment_diameter_px(tapered_diameters)
        execution_width = max(
            int(round(segment_diameter * float(scale) * DEFAULT_EXECUTION_WIDTH_RENDER_SCALE)),
            max((scale * 3) // 4, 1),
        )
        _draw_constant_width_execution_polyline(
            draw,
            scaled_points,
            ink=ink,
            width=execution_width,
            cap_start=effective_cap_start,
            cap_end=effective_cap_end,
            min_cap_radius=float(radius),
        )
        return
    if _draw_variable_width_polyline(
        draw,
        sampled_points,
        tapered_diameters,
        scale,
        ink=ink,
        min_width=max((scale * 3) // 4, 1),
        min_radius=float(radius),
        cap_start=effective_cap_start,
        cap_end=effective_cap_end,
        pointed_start=pointed_start,
        pointed_end=pointed_end,
    ):
        return

    segment_diameter = _robust_segment_diameter_px(tapered_diameters)
    execution_width = max(
        int(round(segment_diameter * float(scale) * DEFAULT_EXECUTION_WIDTH_RENDER_SCALE)),
        max((scale * 3) // 4, 1),
    )
    _draw_constant_width_execution_polyline(
        draw,
        scaled_points,
        ink=ink,
        width=execution_width,
        cap_start=effective_cap_start,
        cap_end=effective_cap_end,
        min_cap_radius=float(radius),
    )


def _build_variable_width_profile(
    points: Sequence[tuple[float, float]],
    foreground_mask: np.ndarray,
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    primitive_relative_widths: Sequence[float] = (),
    primitive_width_blend: float = 0.7,
) -> tuple[list[tuple[float, float]], list[float], bool, bool] | None:
    sampled_points = _sample_polyline_points(
        points,
        step_px=1.0,
    )
    if not sampled_points:
        return None
    point_diameters = _estimate_point_brush_diameters_px(
        sampled_points,
        np.asarray(foreground_mask, dtype=bool),
    )
    stabilized_diameters = _stabilize_point_brush_diameters_px(point_diameters)
    stabilized_diameters = _repair_short_internal_width_dropouts_px(stabilized_diameters)
    if primitive_relative_widths:
        stabilized_diameters = transfer_relative_width_factors(
            stabilized_diameters,
            primitive_relative_widths,
            blend=primitive_width_blend,
        )
    tapered_diameters = _taper_anchored_endpoint_diameters_px(
        stabilized_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _clamp_attached_endpoint_width_peaks_px(
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _taper_endpoint_width_spikes_px(
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _suppress_short_attached_segment_body_diameters_px(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    tapered_diameters = _suppress_short_free_linear_branch_diameters_px(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    tapered_diameters = _boost_short_incomplete_dot_diameters_px(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    tapered_diameters = _taper_corner_terminal_branch_diameters_px(
        sampled_points,
        tapered_diameters,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _taper_long_foldback_tail_diameters_px(
        sampled_points,
        tapered_diameters,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _clamp_long_foldback_turn_diameters_px(
        sampled_points,
        tapered_diameters,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    tapered_diameters = _regularize_straight_segment_body_diameters_px(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    tapered_diameters = _taper_short_attached_free_tip_diameters_px(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
        source_segment_ids=source_segment_ids,
    )
    tapered_diameters = _taper_pointed_foldback_terminal_diameters_px(
        sampled_points,
        tapered_diameters,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    effective_cap_start, effective_cap_end = _adjust_endpoint_caps_for_short_attached_segment(
        sampled_points,
        tapered_diameters,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    return sampled_points, tapered_diameters, effective_cap_start, effective_cap_end


def _draw_piecewise_variable_width_subpaths(
    draw: ImageDraw.ImageDraw,
    *,
    render_subpaths: Sequence[Sequence[tuple[float, float]]],
    render_subpath_source_ids: Sequence[Sequence[Any]],
    scale: int,
    foreground_mask: np.ndarray,
    ink: int,
    min_width: int,
    min_radius: float,
    cap_start: bool,
    cap_end: bool,
    pointed_start: bool = False,
    pointed_end: bool = False,
) -> bool:
    normalized_subpaths = [
        [tuple(_as_float_point(point)) for point in subpath]
        for subpath in render_subpaths
        if len(subpath) >= 2
    ]
    if len(normalized_subpaths) < 2:
        return False
    source_id_groups = [
        tuple(group)
        for group in render_subpath_source_ids
    ]
    while len(source_id_groups) < len(normalized_subpaths):
        source_id_groups.append(())
    normalized_subpaths, grouped_source_id_groups = _coalesce_aligned_render_subpaths_for_variable_width(
        normalized_subpaths,
        source_id_groups,
    )

    profiles: list[dict[str, Any]] = []
    for index, subpath in enumerate(normalized_subpaths):
        sub_cap_start = bool(cap_start) if index == 0 else False
        sub_cap_end = bool(cap_end) if index == len(normalized_subpaths) - 1 else False
        profile = _build_variable_width_profile(
            subpath,
            foreground_mask,
            cap_start=sub_cap_start,
            cap_end=sub_cap_end,
            source_segment_ids=_flatten_grouped_render_subpath_source_ids(grouped_source_id_groups[index]),
        )
        if profile is None:
            return False
        sampled_points, tapered_diameters, effective_cap_start, effective_cap_end = profile
        profiles.append(
            {
                "sampled_points": sampled_points,
                "diameters": tapered_diameters,
                "cap_start": effective_cap_start,
                "cap_end": effective_cap_end,
            }
        )

    trim_start_points = [0 for _ in profiles]
    for index in range(1, len(profiles)):
        trim_start_points[index] = _shared_subpath_profile_overlap_trim_count(
            profiles[index - 1]["sampled_points"],
            profiles[index]["sampled_points"],
        )

    for index, profile in enumerate(profiles):
        sampled_points, tapered_diameters = _trim_variable_width_profile(
            profile["sampled_points"],
            profile["diameters"],
            trim_start_points=trim_start_points[index],
            trim_end_points=0,
        )
        current_subpath = normalized_subpaths[index]
        taper_shared_start = index > 0 and _points_are_near(
            normalized_subpaths[index - 1][-1],
            current_subpath[0],
        )
        taper_shared_end = index + 1 < len(normalized_subpaths) and _points_are_near(
            current_subpath[-1],
            normalized_subpaths[index + 1][0],
        )
        tapered_diameters = _taper_shared_subpath_endpoint_diameters_px(
            tapered_diameters,
            taper_start=taper_shared_start,
            taper_end=taper_shared_end,
        )
        if len(sampled_points) < 2 or len(tapered_diameters) < 2:
            return False
        if not _draw_variable_width_polyline(
            draw,
            sampled_points,
            tapered_diameters,
            scale,
            ink=ink,
            min_width=min_width,
            min_radius=min_radius,
            cap_start=bool(profile["cap_start"]),
            cap_end=bool(profile["cap_end"]),
            pointed_start=bool(pointed_start) and index == 0,
            pointed_end=bool(pointed_end) and index == len(profiles) - 1,
        ):
            return False
    return True


def _points_are_near(
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    distance_px: float = DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_DISTANCE_PX,
) -> bool:
    return float(np.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))) <= float(distance_px)


def _taper_shared_subpath_endpoint_diameters_px(
    diameters: Sequence[float],
    *,
    taper_start: bool,
    taper_end: bool,
    taper_point_count: int = DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_SHARED_SUBPATH_ENDPOINT_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if not bool(taper_start) and not bool(taper_end):
        return arr.tolist()
    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)
    count = min(max(int(taper_point_count), 0), int(arr.size))
    if count <= 0 or reference <= 0.0:
        return arr.tolist()
    if bool(taper_start):
        _taper_endpoint_window(arr, start=0, step=1, count=count, reference=reference)
    if bool(taper_end):
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=count, reference=reference)
    return arr.tolist()


def _shared_subpath_profile_overlap_trim_count(
    previous_points: Sequence[tuple[float, float]],
    next_points: Sequence[tuple[float, float]],
    *,
    overlap_distance_px: float = DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_DISTANCE_PX,
    max_trim_points: int = DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_MAX_TRIM_POINTS,
) -> int:
    if len(previous_points) < 2 or len(next_points) < 2:
        return 0
    limit = min(
        max(int(max_trim_points), 0),
        len(previous_points) - 1,
        len(next_points) - 1,
    )
    count = 0
    for offset in range(limit):
        distance = float(np.hypot(
            float(previous_points[-1 - offset][0]) - float(next_points[offset][0]),
            float(previous_points[-1 - offset][1]) - float(next_points[offset][1]),
        ))
        if distance > float(overlap_distance_px):
            break
        count += 1
    return count


def _history_overlap_trim_count(
    history_points: Sequence[Sequence[tuple[float, float]]],
    current_points: Sequence[tuple[float, float]],
    *,
    overlap_distance_px: float = DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_DISTANCE_PX,
    max_trim_points: int = DEFAULT_SHARED_SUBPATH_PROFILE_OVERLAP_MAX_TRIM_POINTS,
) -> int:
    sampled_current = _sample_polyline_points(
        [tuple(_as_float_point(point)) for point in current_points],
        step_px=1.0,
    )
    if len(sampled_current) < 2:
        return 0

    limit = min(max(int(max_trim_points), 0), len(sampled_current))
    if limit < 2:
        return 0

    sampled_history = [
        _sample_polyline_points(
            [tuple(_as_float_point(point)) for point in points],
            step_px=1.0,
        )
        for points in history_points
        if len(points) >= 2
    ]
    if not sampled_history:
        return 0

    current_arr = np.asarray(sampled_current, dtype=float)
    for trim_count in range(limit, 1, -1):
        current_prefix = current_arr[:trim_count]
        if len(current_prefix) < 2:
            continue
        for previous_points in sampled_history:
            if len(previous_points) < trim_count:
                continue
            previous_arr = np.asarray(previous_points, dtype=float)
            for start in range(0, len(previous_arr) - trim_count + 1):
                window = previous_arr[start : start + trim_count]
                if np.max(np.linalg.norm(window - current_prefix, axis=1)) <= float(overlap_distance_px):
                    return trim_count
                if np.max(np.linalg.norm(window[::-1] - current_prefix, axis=1)) <= float(overlap_distance_px):
                    return trim_count
    return 0


def _trim_variable_width_profile(
    sampled_points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    trim_start_points: int,
    trim_end_points: int,
) -> tuple[list[tuple[float, float]], list[float]]:
    points = [tuple(_as_float_point(point)) for point in sampled_points]
    values = [max(float(value), 1.0) for value in diameters]
    if len(points) != len(values) or len(points) <= 2:
        return points, values
    start = min(max(int(trim_start_points), 0), len(points) - 2)
    remaining_after_start = len(points) - start
    end_trim = min(max(int(trim_end_points), 0), remaining_after_start - 2)
    end = len(points) - end_trim
    trimmed_points = points[start:end]
    trimmed_values = values[start:end]
    if len(trimmed_points) >= 2 and len(trimmed_points) == len(trimmed_values):
        return trimmed_points, trimmed_values
    return points, values


def _should_fallback_to_segment_constant_render_for_short_volatile_segment(
    points: Sequence[tuple[float, float]],
    diameters_px: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    min_length_px: float = DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MIN_LENGTH_PX,
    max_length_px: float = DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MAX_LENGTH_PX,
    min_cv: float = DEFAULT_SHORT_VOLATILE_SEGMENT_CONSTANT_RENDER_MIN_CV,
) -> bool:
    if bool(cap_start) or bool(cap_end):
        return False
    if len(tuple(source_segment_ids)) != 1:
        return False
    if len(points) < 2 or len(diameters_px) < 3:
        return False
    path_length = _polyline_length(points)
    if path_length < float(min_length_px) or path_length > float(max_length_px):
        return False
    arr = np.asarray([max(float(value), 1.0) for value in diameters_px], dtype=float)
    if arr.size < 3:
        return False
    coefficient_of_variation = float(arr.std() / max(arr.mean(), 1e-6))
    if coefficient_of_variation < float(min_cv):
        return False
    return True


def _coalesce_aligned_render_subpaths_for_variable_width(
    render_subpaths: Sequence[Sequence[tuple[float, float]]],
    render_subpath_source_ids: Sequence[Sequence[Any]],
    *,
    gap_px: float = DEFAULT_RENDER_SUBPATH_COALESCE_GAP_PX,
    direction_cos_threshold: float = DEFAULT_RENDER_SUBPATH_COALESCE_DIRECTION_COS_THRESHOLD,
    min_axis_ratio: float = DEFAULT_RENDER_SUBPATH_COALESCE_MIN_AXIS_RATIO,
    max_axis_residual_px: float = DEFAULT_RENDER_SUBPATH_COALESCE_MAX_AXIS_RESIDUAL_PX,
    min_subpath_length_px: float = DEFAULT_RENDER_SUBPATH_COALESCE_MIN_SUBPATH_LENGTH_PX,
) -> tuple[list[list[tuple[float, float]]], list[tuple[tuple[Any, ...], ...]]]:
    normalized_subpaths = [
        [tuple(_as_float_point(point)) for point in subpath]
        for subpath in render_subpaths
        if len(subpath) >= 2
    ]
    if not normalized_subpaths:
        return [], []

    source_id_groups = [tuple(group) for group in render_subpath_source_ids]
    while len(source_id_groups) < len(normalized_subpaths):
        source_id_groups.append(())

    merged_subpaths: list[list[tuple[float, float]]] = [list(normalized_subpaths[0])]
    merged_source_id_groups: list[tuple[tuple[Any, ...], ...]] = [(tuple(source_id_groups[0]),)]

    for next_subpath, next_group in zip(normalized_subpaths[1:], source_id_groups[1:]):
        previous_subpath = merged_subpaths[-1]
        if _should_coalesce_adjacent_render_subpaths(
            previous_subpath,
            next_subpath,
            gap_px=gap_px,
            direction_cos_threshold=direction_cos_threshold,
            min_axis_ratio=min_axis_ratio,
            max_axis_residual_px=max_axis_residual_px,
            min_subpath_length_px=min_subpath_length_px,
        ):
            merged_subpaths[-1] = _merge_render_subpaths(previous_subpath, next_subpath)
            merged_source_id_groups[-1] = merged_source_id_groups[-1] + (tuple(next_group),)
            continue
        merged_subpaths.append(list(next_subpath))
        merged_source_id_groups.append((tuple(next_group),))
    return merged_subpaths, merged_source_id_groups


def _should_coalesce_adjacent_render_subpaths(
    previous_subpath: Sequence[tuple[float, float]],
    next_subpath: Sequence[tuple[float, float]],
    *,
    gap_px: float,
    direction_cos_threshold: float,
    min_axis_ratio: float,
    max_axis_residual_px: float,
    min_subpath_length_px: float,
) -> bool:
    if len(previous_subpath) < 2 or len(next_subpath) < 2:
        return False
    if _polyline_length(previous_subpath) < float(min_subpath_length_px):
        return False
    if _polyline_length(next_subpath) < float(min_subpath_length_px):
        return False
    if float(np.hypot(
        float(next_subpath[0][0]) - float(previous_subpath[-1][0]),
        float(next_subpath[0][1]) - float(previous_subpath[-1][1]),
    )) > float(gap_px):
        return False

    previous_direction = _unit_direction(previous_subpath[-2], previous_subpath[-1])
    next_direction = _unit_direction(next_subpath[0], next_subpath[1])
    if previous_direction is None or next_direction is None:
        return False
    direction_cos = float(
        previous_direction[0] * next_direction[0] + previous_direction[1] * next_direction[1]
    )
    if direction_cos < float(direction_cos_threshold):
        return False

    merged = _merge_render_subpaths(previous_subpath, next_subpath)
    if _principal_axis_ratio(merged) < float(min_axis_ratio):
        return False
    if _principal_axis_residual(merged) > float(max_axis_residual_px):
        return False
    return True


def _merge_render_subpaths(
    previous_subpath: Sequence[tuple[float, float]],
    next_subpath: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    merged = [tuple(_as_float_point(point)) for point in previous_subpath]
    if not merged:
        return [tuple(_as_float_point(point)) for point in next_subpath]
    appended = [tuple(_as_float_point(point)) for point in next_subpath]
    if appended:
        gap = float(np.hypot(
            float(appended[0][0]) - float(merged[-1][0]),
            float(appended[0][1]) - float(merged[-1][1]),
        ))
        if gap <= 1e-6:
            appended = appended[1:]
    merged.extend(appended)
    return merged


def _flatten_grouped_render_subpath_source_ids(
    grouped_source_ids: Sequence[Sequence[Any]],
) -> tuple[Any, ...]:
    flattened: list[Any] = []
    for group in grouped_source_ids:
        flattened.extend(list(group))
    return tuple(flattened)


def _draw_constant_width_execution_polyline(
    draw: ImageDraw.ImageDraw,
    scaled_points: Sequence[tuple[float, float]],
    *,
    ink: int,
    width: int,
    cap_start: bool,
    cap_end: bool,
    min_cap_radius: float,
) -> None:
    if len(scaled_points) <= 1:
        return
    draw.line(scaled_points, fill=ink, width=max(int(width), 1), joint="curve")
    cap_radius = max(float(width) / 2.0, float(min_cap_radius))
    start_x, start_y = scaled_points[0]
    end_x, end_y = scaled_points[-1]
    if cap_start:
        draw.ellipse((start_x - cap_radius, start_y - cap_radius, start_x + cap_radius, start_y + cap_radius), fill=ink)
    if cap_end:
        draw.ellipse((end_x - cap_radius, end_y - cap_radius, end_x + cap_radius, end_y + cap_radius), fill=ink)


def _draw_variable_width_polyline(
    draw: ImageDraw.ImageDraw,
    points: Sequence[tuple[float, float]],
    diameters_px: Sequence[float],
    scale: int,
    *,
    ink: int,
    min_width: int,
    min_radius: float,
    cap_start: bool,
    cap_end: bool,
    pointed_start: bool = False,
    pointed_end: bool = False,
) -> bool:
    if len(points) < 2 or len(diameters_px) < 2:
        return False
    if _has_excessive_turning_for_variable_width(points):
        return False

    scaled_points = np.asarray([_scaled_xy_continuous(point, scale) for point in points], dtype=float)
    radius_floor = max(float(min_width) / 2.0, float(min_radius))
    radii_values: list[float] = []
    for index, diameter in enumerate(diameters_px):
        is_pointed_endpoint = (
            (bool(pointed_start) and index == 0)
            or (bool(pointed_end) and index == len(diameters_px) - 1)
        )
        if is_pointed_endpoint:
            radii_values.append(0.0)
            continue
        floor = 0.0 if is_pointed_endpoint else radius_floor
        radii_values.append(
            max(
                float(diameter) * float(scale) * DEFAULT_EXECUTION_WIDTH_RENDER_SCALE / 2.0,
                floor,
            )
        )
    radii = np.asarray(radii_values, dtype=float)
    left_side: list[tuple[float, float]] = []
    right_side: list[tuple[float, float]] = []
    previous_normal = np.asarray([0.0, 1.0], dtype=float)
    for index, point in enumerate(scaled_points):
        previous_point = scaled_points[index - 1] if index > 0 else point
        next_point = scaled_points[index + 1] if index + 1 < len(scaled_points) else point
        tangent = next_point - previous_point
        tangent_norm = float(np.linalg.norm(tangent))
        if tangent_norm <= 1e-9:
            normal = previous_normal
        else:
            normal = np.asarray([-tangent[1], tangent[0]], dtype=float) / tangent_norm
            previous_normal = normal
        radius = float(radii[index])
        left_side.append((float(point[0] + normal[0] * radius), float(point[1] + normal[1] * radius)))
        right_side.append((float(point[0] - normal[0] * radius), float(point[1] - normal[1] * radius)))

    polygon = left_side + list(reversed(right_side))
    if len(polygon) >= 3:
        draw.polygon(polygon, fill=ink)

    _draw_variable_width_centerline_core(
        draw,
        scaled_points,
        radii,
        ink=ink,
        min_radius=min_radius,
    )
    _draw_variable_width_round_joins(
        draw,
        scaled_points,
        radii,
        ink=ink,
        min_radius=min_radius,
    )

    start_x, start_y = scaled_points[0]
    end_x, end_y = scaled_points[-1]
    start_radius = float(radii[0]) if pointed_start else max(float(radii[0]), float(min_radius))
    end_radius = float(radii[-1]) if pointed_end else max(float(radii[-1]), float(min_radius))
    if cap_start and not pointed_start:
        draw.ellipse((start_x - start_radius, start_y - start_radius, start_x + start_radius, start_y + start_radius), fill=ink)
    if cap_end and not pointed_end:
        draw.ellipse((end_x - end_radius, end_y - end_radius, end_x + end_radius, end_y + end_radius), fill=ink)
    if pointed_start:
        _sharpen_pointed_endpoint_raster(
            draw,
            endpoint=scaled_points[0],
            adjacent=scaled_points[1],
            erase_radius=max(float(radii[1]), float(min_radius)),
            ink=ink,
        )
    if pointed_end:
        _sharpen_pointed_endpoint_raster(
            draw,
            endpoint=scaled_points[-1],
            adjacent=scaled_points[-2],
            erase_radius=max(float(radii[-2]), float(min_radius)),
            ink=ink,
        )
    return True


def _sharpen_pointed_endpoint_raster(
    draw: ImageDraw.ImageDraw,
    *,
    endpoint: np.ndarray,
    adjacent: np.ndarray,
    erase_radius: float,
    ink: int,
) -> None:
    tangent = np.asarray(endpoint, dtype=float) - np.asarray(adjacent, dtype=float)
    tangent_norm = float(np.linalg.norm(tangent))
    if tangent_norm <= 1e-9:
        return
    tangent /= tangent_norm
    normal = np.asarray([-tangent[1], tangent[0]], dtype=float)
    radius = max(float(erase_radius), 1.0) + 1.0
    start = np.asarray(endpoint, dtype=float) - normal * radius
    end = np.asarray(endpoint, dtype=float) + normal * radius
    draw.line(
        (float(start[0]), float(start[1]), float(end[0]), float(end[1])),
        fill=0,
        width=2,
    )
    draw.point((int(round(float(endpoint[0]))), int(round(float(endpoint[1])))), fill=ink)


def _draw_variable_width_centerline_core(
    draw: ImageDraw.ImageDraw,
    scaled_points: np.ndarray,
    radii: np.ndarray,
    *,
    ink: int,
    min_radius: float,
    radius_scale: float = DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_RADIUS_SCALE,
    min_path_length_px: float = DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_MIN_PATH_LENGTH_PX,
    foldback_max_cos: float = DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_FOLDBACK_MAX_COS,
    window_points: int = DEFAULT_VARIABLE_WIDTH_CENTERLINE_CORE_WINDOW_POINTS,
) -> None:
    if len(scaled_points) < 3 or len(radii) < 3:
        return
    unscaled_path_length = _polyline_length([(float(y) / 1.0, float(x) / 1.0) for x, y in scaled_points])
    scale_estimate = _estimate_scaled_polyline_scale(scaled_points)
    if scale_estimate > 0:
        unscaled_path_length = unscaled_path_length / scale_estimate
    if unscaled_path_length < float(min_path_length_px):
        return

    foldback_indices: list[int] = []
    for index in range(1, len(scaled_points) - 1):
        incoming = scaled_points[index] - scaled_points[index - 1]
        outgoing = scaled_points[index + 1] - scaled_points[index]
        incoming_norm = float(np.linalg.norm(incoming))
        outgoing_norm = float(np.linalg.norm(outgoing))
        if incoming_norm <= 1e-9 or outgoing_norm <= 1e-9:
            continue
        turn_cos = float(np.dot(incoming, outgoing) / (incoming_norm * outgoing_norm))
        if turn_cos <= float(foldback_max_cos):
            foldback_indices.append(index)
    if not foldback_indices:
        return

    active_indices: set[int] = set()
    window = max(int(window_points), 0)
    for index in foldback_indices:
        start = max(0, index - window)
        end = min(len(scaled_points), index + window + 1)
        active_indices.update(range(start, end))

    for index in sorted(active_indices):
        point = scaled_points[index]
        radius_px = radii[index]
        radius = max(float(radius_px) * float(radius_scale), float(min_radius))
        x, y = point
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ink)


def _estimate_scaled_polyline_scale(scaled_points: np.ndarray) -> float:
    if len(scaled_points) < 2:
        return 1.0
    deltas = np.diff(scaled_points, axis=0)
    step_lengths = np.linalg.norm(deltas, axis=1)
    positive = step_lengths[step_lengths > 1e-9]
    if positive.size == 0:
        return 1.0
    return max(float(np.median(positive)), 1.0)


def _draw_variable_width_round_joins(
    draw: ImageDraw.ImageDraw,
    scaled_points: np.ndarray,
    radii: np.ndarray,
    *,
    ink: int,
    min_radius: float,
    max_turn_cos: float = DEFAULT_VARIABLE_WIDTH_ROUND_JOIN_MAX_COS,
    radius_scale: float = DEFAULT_VARIABLE_WIDTH_ROUND_JOIN_RADIUS_SCALE,
) -> None:
    if len(scaled_points) < 3 or len(radii) < 3:
        return
    for index in range(1, len(scaled_points) - 1):
        incoming = scaled_points[index] - scaled_points[index - 1]
        outgoing = scaled_points[index + 1] - scaled_points[index]
        incoming_norm = float(np.linalg.norm(incoming))
        outgoing_norm = float(np.linalg.norm(outgoing))
        if incoming_norm <= 1e-9 or outgoing_norm <= 1e-9:
            continue
        turn_cos = float(np.dot(incoming, outgoing) / (incoming_norm * outgoing_norm))
        if turn_cos > float(max_turn_cos):
            continue
        radius = max(float(radii[index]) * float(radius_scale), float(min_radius))
        x, y = scaled_points[index]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ink)


def _build_endpoint_cap_policies(
    ordered_segments: Sequence[dict[str, Any]],
    *,
    anchor_distance_px: float = DEFAULT_ANCHORED_ENDPOINT_DISTANCE_PX,
    nearby_free_endpoint_distance_px: float = DEFAULT_NEARBY_FREE_ENDPOINT_DISTANCE_PX,
) -> list[dict[str, bool]]:
    point_sets = [
        [tuple(_as_float_point(point)) for point in segment.get("points", ())]
        for segment in ordered_segments
    ]
    policies: list[dict[str, bool]] = []
    for index, (segment, points) in enumerate(zip(ordered_segments, point_sets)):
        if len(points) <= 1:
            policies.append({"cap_start": True, "cap_end": True})
            continue
        start_is_anchored = _endpoint_has_nearby_foreign_point(
            points[0],
            point_sets,
            segment_index=index,
            anchor_distance_px=anchor_distance_px,
        )
        end_is_anchored = _endpoint_has_nearby_foreign_point(
            points[-1],
            point_sets,
            segment_index=index,
            anchor_distance_px=anchor_distance_px,
        )
        if not start_is_anchored:
            start_is_anchored = _endpoint_has_nearby_free_foreign_endpoint(
                points[0],
                point_sets,
                segment_index=index,
                endpoint_tangent=_local_tangent(points, 0),
                nearby_endpoint_distance_px=nearby_free_endpoint_distance_px,
                anchor_distance_px=anchor_distance_px,
            )
        if not end_is_anchored:
            end_is_anchored = _endpoint_has_nearby_free_foreign_endpoint(
                points[-1],
                point_sets,
                segment_index=index,
                endpoint_tangent=_local_tangent(points, len(points) - 1),
                nearby_endpoint_distance_px=nearby_free_endpoint_distance_px,
                anchor_distance_px=anchor_distance_px,
            )
        cap_start, cap_end = _suppress_corner_terminal_free_caps(
            points,
            source_segment_ids=segment.get("source_segment_ids", ()),
            cap_start=not start_is_anchored,
            cap_end=not end_is_anchored,
        )
        trim_start_points = _endpoint_overlap_stub_trim_count(
            points,
            point_sets,
            segment_index=index,
            trim_start=True,
            cap_start=cap_start,
            cap_end=cap_end,
            anchor_distance_px=anchor_distance_px,
        )
        trim_end_points = _endpoint_overlap_stub_trim_count(
            points,
            point_sets,
            segment_index=index,
            trim_start=False,
            cap_start=cap_start,
            cap_end=cap_end,
            anchor_distance_px=anchor_distance_px,
        )
        extend_start_px = _anchored_corner_endpoint_extension_px(
            points[0],
            point_sets,
            segment_index=index,
            endpoint_tangent=_local_tangent(points, 0),
            anchor_distance_px=anchor_distance_px,
            is_free_endpoint=cap_start,
        ) if trim_start_points <= 0 else 0.0
        extend_end_px = _anchored_corner_endpoint_extension_px(
            points[-1],
            point_sets,
            segment_index=index,
            endpoint_tangent=_local_tangent(points, len(points) - 1),
            anchor_distance_px=anchor_distance_px,
            is_free_endpoint=cap_end,
        ) if trim_end_points <= 0 else 0.0
        policies.append(
            {
                "cap_start": cap_start,
                "cap_end": cap_end,
                "extend_start_px": extend_start_px,
                "extend_end_px": extend_end_px,
                "trim_start_points": trim_start_points,
                "trim_end_points": trim_end_points,
            }
        )
    return policies


def _anchored_corner_endpoint_extension_px(
    endpoint: tuple[float, float],
    point_sets: Sequence[Sequence[tuple[float, float]]],
    *,
    segment_index: int,
    endpoint_tangent: tuple[float, float],
    anchor_distance_px: float,
    is_free_endpoint: bool,
    extension_px: float = DEFAULT_ANCHORED_CORNER_EXTENSION_PX,
    max_direction_dot: float = DEFAULT_ANCHORED_CORNER_EXTENSION_DIRECTION_DOT_MAX,
) -> float:
    if bool(is_free_endpoint):
        return 0.0
    endpoint_direction = _unit_vector(endpoint_tangent)
    if endpoint_direction is None:
        return 0.0
    y0, x0 = endpoint
    for other_index, other_points in enumerate(point_sets):
        if other_index == segment_index or len(other_points) < 2:
            continue
        for other_endpoint_index in (0, len(other_points) - 1):
            y1, x1 = other_points[other_endpoint_index]
            distance = float(np.hypot(float(y1) - float(y0), float(x1) - float(x0)))
            if distance > float(anchor_distance_px):
                continue
            other_tangent = _local_tangent(other_points, other_endpoint_index)
            other_direction = _unit_vector(other_tangent)
            if other_direction is None:
                continue
            if abs(float(np.dot(endpoint_direction, other_direction))) <= float(max_direction_dot):
                return max(float(extension_px), 0.0)
    return 0.0


def _suppress_corner_terminal_free_caps(
    points: Sequence[tuple[float, float]],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
    turn_cos_threshold: float = DEFAULT_CORNER_TERMINAL_CAP_TURN_COS_THRESHOLD,
    max_branch_ratio: float = DEFAULT_CORNER_TERMINAL_CAP_MAX_BRANCH_RATIO,
    min_branch_length_px: float = DEFAULT_CORNER_TERMINAL_CAP_MIN_BRANCH_LENGTH_PX,
) -> tuple[bool, bool]:
    cap_start = bool(cap_start)
    cap_end = bool(cap_end)
    if (not cap_start and not cap_end) or len(points) < 3:
        return cap_start, cap_end
    if len(tuple(source_segment_ids)) <= 1:
        return cap_start, cap_end

    simplified = _simplify_render_points([tuple(_as_float_point(point)) for point in points])
    if len(simplified) < 3:
        return cap_start, cap_end

    sharp_turn_indices: list[int] = []
    for index, point_triplet in enumerate(zip(simplified[:-2], simplified[1:-1], simplified[2:]), start=1):
        previous, current, following = point_triplet
        first = np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
        second = np.asarray(following, dtype=float) - np.asarray(current, dtype=float)
        first_norm = float(np.linalg.norm(first))
        second_norm = float(np.linalg.norm(second))
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = float(np.dot(first, second) / max(first_norm * second_norm, 1e-9))
        if cosine < float(turn_cos_threshold):
            sharp_turn_indices.append(index)
            if len(sharp_turn_indices) > 1:
                return cap_start, cap_end
    if len(sharp_turn_indices) != 1:
        return cap_start, cap_end

    total_length = _polyline_length(simplified)
    if total_length <= 0.0:
        return cap_start, cap_end
    max_branch_length = total_length * max(float(max_branch_ratio), 0.0)
    if max_branch_length < float(min_branch_length_px):
        return cap_start, cap_end

    turn_index = sharp_turn_indices[0]
    start_branch_length = _polyline_length(simplified[: turn_index + 1])
    end_branch_length = _polyline_length(simplified[turn_index:])
    if cap_start and float(min_branch_length_px) <= start_branch_length <= max_branch_length:
        cap_start = False
    if cap_end and float(min_branch_length_px) <= end_branch_length <= max_branch_length:
        cap_end = False
    return cap_start, cap_end


def _endpoint_has_nearby_foreign_point(
    endpoint: tuple[float, float],
    point_sets: Sequence[Sequence[tuple[float, float]]],
    *,
    segment_index: int,
    anchor_distance_px: float,
) -> bool:
    limit = float(anchor_distance_px)
    if limit <= 0:
        return False
    y0, x0 = endpoint
    for other_index, other_points in enumerate(point_sets):
        if other_index == segment_index:
            continue
        for y1, x1 in other_points:
            distance = ((float(y1) - float(y0)) ** 2 + (float(x1) - float(x0)) ** 2) ** 0.5
            if distance <= limit:
                return True
    return False


def _endpoint_has_nearby_free_foreign_endpoint(
    endpoint: tuple[float, float],
    point_sets: Sequence[Sequence[tuple[float, float]]],
    *,
    segment_index: int,
    endpoint_tangent: tuple[float, float],
    nearby_endpoint_distance_px: float,
    anchor_distance_px: float,
    min_gap_alignment: float = 0.0,
) -> bool:
    limit = float(nearby_endpoint_distance_px)
    if limit <= 0:
        return False
    y0, x0 = endpoint
    for other_index, other_points in enumerate(point_sets):
        if other_index == segment_index or not other_points:
            continue
        endpoint_candidates = [other_points[0]]
        if len(other_points) > 1:
            endpoint_candidates.append(other_points[-1])
        for y1, x1 in endpoint_candidates:
            gap_y = float(y1) - float(y0)
            gap_x = float(x1) - float(x0)
            distance = (gap_y ** 2 + gap_x ** 2) ** 0.5
            if distance > 1e-9:
                gap_alignment = (
                    (float(endpoint_tangent[0]) * gap_y + float(endpoint_tangent[1]) * gap_x)
                    / distance
                )
                if gap_alignment < float(min_gap_alignment):
                    continue
            if distance <= limit and not _endpoint_has_nearby_foreign_point(
                (float(y1), float(x1)),
                point_sets,
                segment_index=other_index,
                anchor_distance_px=anchor_distance_px,
            ):
                return True
    return False


def _nearest_foreign_point(
    endpoint: tuple[float, float],
    point_sets: Sequence[Sequence[tuple[float, float]]],
    *,
    segment_index: int,
) -> tuple[float, tuple[float, float]] | None:
    best_distance: float | None = None
    best_point: tuple[float, float] | None = None
    y0, x0 = endpoint
    for other_index, other_points in enumerate(point_sets):
        if other_index == segment_index:
            continue
        for y1, x1 in other_points:
            distance = float(np.hypot(float(y1) - float(y0), float(x1) - float(x0)))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_point = (float(y1), float(x1))
    if best_distance is None or best_point is None:
        return None
    return best_distance, best_point


def _endpoint_overlap_stub_trim_count(
    points: Sequence[tuple[float, float]],
    point_sets: Sequence[Sequence[tuple[float, float]]],
    *,
    segment_index: int,
    trim_start: bool,
    cap_start: bool,
    cap_end: bool,
    anchor_distance_px: float,
    max_step_px: float = DEFAULT_ANCHORED_OVERLAP_TRIM_MAX_STEP_PX,
    min_improvement_px: float = DEFAULT_ANCHORED_OVERLAP_TRIM_MIN_IMPROVEMENT_PX,
    max_double_anchored_total_length_px: float = DEFAULT_DOUBLE_ANCHORED_OVERLAP_TRIM_MAX_TOTAL_LENGTH_PX,
) -> int:
    if len(points) < 2:
        return 0
    if trim_start:
        if bool(cap_start):
            return 0
        opposite_is_free = bool(cap_end)
        endpoint = points[0]
        adjacent_point = points[1]
    else:
        if bool(cap_end):
            return 0
        opposite_is_free = bool(cap_start)
        endpoint = points[-1]
        adjacent_point = points[-2]
    if not opposite_is_free and _polyline_length(points) > float(max_double_anchored_total_length_px):
        return 0

    nearest = _nearest_foreign_point(endpoint, point_sets, segment_index=segment_index)
    if nearest is None:
        return 0
    nearest_distance, nearest_point = nearest
    if nearest_distance > float(anchor_distance_px):
        return 0

    step_length = float(np.hypot(float(adjacent_point[0]) - float(endpoint[0]), float(adjacent_point[1]) - float(endpoint[1])))
    if step_length > float(max_step_px):
        return 0

    adjacent_distance = float(
        np.hypot(float(adjacent_point[0]) - float(nearest_point[0]), float(adjacent_point[1]) - float(nearest_point[1]))
    )
    if adjacent_distance + float(min_improvement_px) < nearest_distance:
        return 1
    return 0


def _taper_anchored_endpoint_diameters_px(
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    taper_point_count: int = DEFAULT_ANCHORED_ENDPOINT_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_ANCHORED_ENDPOINT_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)
    count = min(max(int(taper_point_count), 0), int(arr.size))
    if count <= 0:
        return arr.tolist()

    if not cap_start:
        _taper_endpoint_window(arr, start=0, step=1, count=count, reference=reference)
    if not cap_end:
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=count, reference=reference)
    return arr.tolist()


def _clamp_attached_endpoint_width_peaks_px(
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    spike_ratio: float = DEFAULT_ATTACHED_ENDPOINT_SPIKE_RATIO,
    taper_point_count: int = DEFAULT_ATTACHED_ENDPOINT_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_ATTACHED_ENDPOINT_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)
    count = min(max(int(taper_point_count), 0), int(arr.size))
    if count <= 0 or reference <= 0.0:
        return arr.tolist()

    limit = reference * max(float(spike_ratio), 1.0)
    start_window_max = float(np.max(arr[:count]))
    end_window_max = float(np.max(arr[-count:]))
    if not bool(cap_start) and start_window_max > limit:
        start_count = _expand_endpoint_taper_count_to_cover_peak(
            arr,
            start=0,
            step=1,
            base_count=count,
            limit=limit,
        )
        _taper_endpoint_window(arr, start=0, step=1, count=start_count, reference=reference)
    if not bool(cap_end) and end_window_max > limit:
        end_count = _expand_endpoint_taper_count_to_cover_peak(
            arr,
            start=int(arr.size) - 1,
            step=-1,
            base_count=count,
            limit=limit,
        )
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=end_count, reference=reference)
    return arr.tolist()


def _taper_endpoint_width_spikes_px(
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    spike_ratio: float = DEFAULT_FREE_ENDPOINT_SPIKE_RATIO,
    taper_point_count: int = DEFAULT_FREE_ENDPOINT_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_FREE_ENDPOINT_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)
    count = min(max(int(taper_point_count), 0), int(arr.size))
    if count <= 0 or reference <= 0:
        return arr.tolist()

    limit = reference * max(float(spike_ratio), 1.0)
    if cap_start and float(arr[0]) > limit:
        start_count = _expand_endpoint_taper_count_to_cover_peak(
            arr,
            start=0,
            step=1,
            base_count=count,
            limit=limit,
        )
        _taper_endpoint_window(arr, start=0, step=1, count=start_count, reference=reference)
    if cap_end and float(arr[-1]) > limit:
        end_count = _expand_endpoint_taper_count_to_cover_peak(
            arr,
            start=int(arr.size) - 1,
            step=-1,
            base_count=count,
            limit=limit,
        )
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=end_count, reference=reference)
    return arr.tolist()


def _expand_endpoint_taper_count_to_cover_peak(
    diameters: np.ndarray,
    *,
    start: int,
    step: int,
    base_count: int,
    limit: float,
) -> int:
    count = min(max(int(base_count), 0), int(diameters.size))
    if count <= 0:
        return 0
    while count < int(diameters.size):
        boundary_index = int(start + step * (count - 1))
        if boundary_index < 0 or boundary_index >= int(diameters.size):
            break
        if float(diameters[boundary_index]) <= float(limit):
            break
        count += 1
    return count


def _adjust_endpoint_caps_for_short_attached_segment(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    max_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_SEGMENT_MAX_PATH_TO_DIAMETER_RATIO,
    free_cap_min_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_SEGMENT_FREE_CAP_MIN_PATH_TO_DIAMETER_RATIO,
) -> tuple[bool, bool]:
    if bool(cap_start) == bool(cap_end):
        return bool(cap_start), bool(cap_end)
    if len(points) < 2 or not diameters:
        return bool(cap_start), bool(cap_end)
    reference = _robust_segment_diameter_px(diameters)
    if reference <= 0.0:
        return bool(cap_start), bool(cap_end)
    path_length = float(
        sum(
            np.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
            for start, end in zip(points[:-1], points[1:])
        )
    )
    path_to_diameter_ratio = path_length / reference
    if path_to_diameter_ratio > max(float(max_path_to_diameter_ratio), 0.0):
        return bool(cap_start), bool(cap_end)
    if path_to_diameter_ratio >= max(float(free_cap_min_path_to_diameter_ratio), 0.0):
        return bool(cap_start), bool(cap_end)
    return False, False


def _suppress_short_attached_segment_body_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any] = (),
    max_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_SEGMENT_MAX_PATH_TO_DIAMETER_RATIO,
    target_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_SEGMENT_BODY_TARGET_PATH_TO_DIAMETER_RATIO,
    single_source_target_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_SINGLE_SOURCE_TARGET_PATH_TO_DIAMETER_RATIO,
    min_scale: float = DEFAULT_SHORT_ATTACHED_SEGMENT_BODY_MIN_SCALE,
    single_source_min_scale: float = DEFAULT_SHORT_ATTACHED_SINGLE_SOURCE_BODY_MIN_SCALE,
) -> list[float]:
    if bool(cap_start) == bool(cap_end):
        return [max(float(value), 1.0) for value in diameters]
    if len(points) < 2 or not diameters:
        return [max(float(value), 1.0) for value in diameters]

    reference = _robust_segment_diameter_px(diameters)
    if reference <= 0.0:
        return [max(float(value), 1.0) for value in diameters]

    path_length = _polyline_length(points)
    ratio = path_length / reference
    if ratio > max(float(max_path_to_diameter_ratio), 0.0):
        return [max(float(value), 1.0) for value in diameters]

    safe_target_ratio = max(float(target_path_to_diameter_ratio), 1e-6)
    short_single_source = (
        len(tuple(source_segment_ids)) == 1
        and path_length <= float(DEFAULT_SHORT_FREE_LINEAR_BRANCH_MAX_LENGTH_PX)
    )
    if short_single_source:
        safe_target_ratio = max(
            safe_target_ratio,
            float(single_source_target_path_to_diameter_ratio),
        )
    if ratio >= safe_target_ratio:
        return [max(float(value), 1.0) for value in diameters]

    effective_min_scale = float(single_source_min_scale) if short_single_source else float(min_scale)
    scale = max(min(float(ratio) / safe_target_ratio, 1.0), max(effective_min_scale, 0.0))
    return [max(float(value) * scale, 1.0) for value in diameters]


def _taper_short_attached_free_tip_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    min_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_FREE_TIP_MIN_PATH_TO_DIAMETER_RATIO,
    max_path_to_diameter_ratio: float = DEFAULT_SHORT_ATTACHED_FREE_TIP_MAX_PATH_TO_DIAMETER_RATIO,
    max_length_px: float = DEFAULT_SHORT_ATTACHED_FREE_TIP_MAX_LENGTH_PX,
    taper_point_count: int = DEFAULT_SHORT_ATTACHED_FREE_TIP_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_SHORT_ATTACHED_FREE_TIP_REFERENCE_SCALE,
) -> list[float]:
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if bool(cap_start) == bool(cap_end):
        return arr.tolist()
    if len(tuple(source_segment_ids)) != 1 or len(points) < 2 or arr.size < 2:
        return arr.tolist()

    path_length = _polyline_length(points)
    if path_length > float(max_length_px):
        return arr.tolist()
    reference = _robust_segment_diameter_px(arr.tolist())
    if reference <= 0.0:
        return arr.tolist()
    ratio = path_length / reference
    if ratio < float(min_path_to_diameter_ratio) or ratio > float(max_path_to_diameter_ratio):
        return arr.tolist()

    count = min(max(int(taper_point_count), 0), int(arr.size))
    tapered_reference = reference * max(float(reference_scale), 0.0)
    if bool(cap_start):
        _taper_endpoint_window(arr, start=0, step=1, count=count, reference=tapered_reference)
    else:
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=count, reference=tapered_reference)
    return arr.tolist()


def _suppress_short_free_linear_branch_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    min_length_px: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_LENGTH_PX,
    max_length_px: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_MAX_LENGTH_PX,
    min_axis_ratio: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_AXIS_RATIO,
    target_path_to_diameter_ratio: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_TARGET_PATH_TO_DIAMETER_RATIO,
    min_scale: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_MIN_SCALE,
    tip_taper_point_count: int = DEFAULT_SHORT_FREE_LINEAR_BRANCH_TIP_TAPER_POINT_COUNT,
    tip_scale: float = DEFAULT_SHORT_FREE_LINEAR_BRANCH_TIP_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if not (bool(cap_start) and bool(cap_end)):
        return arr.tolist()
    if len(tuple(source_segment_ids)) != 1 or len(points) < 3:
        return arr.tolist()

    path_length = _polyline_length(points)
    if path_length < float(min_length_px) or path_length > float(max_length_px):
        return arr.tolist()
    if _principal_axis_ratio(points) < float(min_axis_ratio):
        return arr.tolist()

    reference = _robust_segment_diameter_px(arr.tolist())
    if reference <= 0.0:
        return arr.tolist()
    target_diameter = path_length / max(float(target_path_to_diameter_ratio), 1e-6)
    if reference <= target_diameter:
        return arr.tolist()

    scale = max(min(float(target_diameter) / max(reference, 1e-6), 1.0), max(float(min_scale), 0.0))
    suppressed = np.asarray([max(float(value) * scale, 1.0) for value in arr.tolist()], dtype=float)
    taper_count = min(max(int(tip_taper_point_count), 0), max(int(suppressed.size // 2), 0))
    if taper_count > 1:
        endpoint_index = 0 if float(suppressed[0]) < float(suppressed[-1]) else int(suppressed.size) - 1
        taper_scales = np.linspace(max(float(tip_scale), 0.0), 1.0, taper_count)
        if endpoint_index == 0:
            suppressed[:taper_count] *= taper_scales
        else:
            suppressed[-taper_count:] *= taper_scales[::-1]
        suppressed = np.maximum(suppressed, 1.0)
    return suppressed.tolist()


def _boost_short_incomplete_dot_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    max_length_px: float = DEFAULT_SHORT_INCOMPLETE_DOT_MAX_LENGTH_PX,
    max_point_count: int = DEFAULT_SHORT_INCOMPLETE_DOT_MAX_POINT_COUNT,
    boost_scale: float = DEFAULT_SHORT_INCOMPLETE_DOT_BOOST_SCALE,
    endpoint_scale: float = DEFAULT_SHORT_INCOMPLETE_DOT_ENDPOINT_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if len(points) < 2 or len(points) > max(int(max_point_count), 0):
        return arr.tolist()
    if len(tuple(source_segment_ids)) != 1:
        return arr.tolist()
    if not (bool(cap_start) and bool(cap_end)):
        return arr.tolist()
    path_length = _polyline_length(points)
    if path_length > float(max_length_px):
        return arr.tolist()

    reference = _robust_segment_diameter_px(arr.tolist())
    if reference <= 0.0:
        return arr.tolist()

    boosted = np.maximum(arr, float(reference) * max(float(boost_scale), 1.0))
    endpoint_count = min(max(int(round(boosted.size * 0.3)), 2), int(boosted.size // 2))
    if endpoint_count > 1:
        _taper_endpoint_window(
            boosted,
            start=0,
            step=1,
            count=endpoint_count,
            reference=float(reference) * max(float(endpoint_scale), 1.0),
        )
        _taper_endpoint_window(
            boosted,
            start=int(boosted.size) - 1,
            step=-1,
            count=endpoint_count,
            reference=float(reference) * max(float(endpoint_scale), 1.0),
        )
    return boosted.tolist()


def _short_incomplete_dot_endpoint_extensions_px(
    points: Sequence[tuple[float, float]],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    max_length_px: float = DEFAULT_SHORT_INCOMPLETE_DOT_MAX_LENGTH_PX,
    max_point_count: int = DEFAULT_SHORT_INCOMPLETE_DOT_MAX_POINT_COUNT,
    extension_px: float = DEFAULT_SHORT_INCOMPLETE_DOT_ENDPOINT_EXTENSION_PX,
) -> tuple[float, float]:
    if len(points) < 2 or len(points) > max(int(max_point_count), 0):
        return 0.0, 0.0
    if len(tuple(source_segment_ids)) != 1:
        return 0.0, 0.0
    if not (bool(cap_start) and bool(cap_end)):
        return 0.0, 0.0
    if _polyline_length(points) > float(max_length_px):
        return 0.0, 0.0
    extend = max(float(extension_px), 0.0)
    return extend, extend


def _repair_short_internal_width_dropouts_px(
    diameters: Sequence[float],
    *,
    max_run_points: int = DEFAULT_INTERNAL_WIDTH_DROPOUT_MAX_RUN_POINTS,
    drop_ratio: float = DEFAULT_INTERNAL_WIDTH_DROPOUT_DROP_RATIO,
    recovery_ratio: float = DEFAULT_INTERNAL_WIDTH_DROPOUT_RECOVERY_RATIO,
    endpoint_guard_points: int = DEFAULT_INTERNAL_WIDTH_DROPOUT_ENDPOINT_GUARD_POINTS,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if arr.size < 5:
        return arr.tolist()
    reference = _robust_segment_diameter_px(arr.tolist())
    low_threshold = reference * max(float(drop_ratio), 0.0)
    recovery_threshold = reference * max(float(recovery_ratio), 0.0)
    guard = min(max(int(endpoint_guard_points), 0), max(int(arr.size // 3), 0))
    start_index = guard
    end_index = int(arr.size) - guard
    if end_index - start_index < 3:
        start_index = 1
        end_index = int(arr.size) - 1

    index = start_index
    while index < end_index:
        if float(arr[index]) >= low_threshold:
            index += 1
            continue
        run_start = index
        while index < end_index and float(arr[index]) < low_threshold:
            index += 1
        run_end = index
        run_length = run_end - run_start
        if run_start <= 0 or run_end >= int(arr.size):
            continue
        if run_length <= 0 or run_length > max(int(max_run_points), 0):
            continue
        left_value = float(arr[run_start - 1])
        right_value = float(arr[run_end])
        if left_value < recovery_threshold or right_value < recovery_threshold:
            continue
        fill_value = float(np.median(np.asarray([left_value, right_value, reference], dtype=float)))
        arr[run_start:run_end] = fill_value
    return arr.tolist()


def _taper_corner_terminal_branch_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
    turn_cos_threshold: float = DEFAULT_CORNER_TERMINAL_CAP_TURN_COS_THRESHOLD,
    max_branch_ratio: float = DEFAULT_CORNER_TERMINAL_CAP_MAX_BRANCH_RATIO,
    min_branch_length_px: float = DEFAULT_CORNER_TERMINAL_CAP_MIN_BRANCH_LENGTH_PX,
    reference_scale: float = DEFAULT_CORNER_TERMINAL_BRANCH_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if len(points) < 3 or len(tuple(source_segment_ids)) <= 1:
        return arr.tolist()

    simplified = _simplify_render_points(points)
    if len(simplified) < 3:
        return arr.tolist()

    sharp_turn_indices: list[int] = []
    for index, point_triplet in enumerate(zip(simplified[:-2], simplified[1:-1], simplified[2:]), start=1):
        previous, current, following = point_triplet
        first = np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
        second = np.asarray(following, dtype=float) - np.asarray(current, dtype=float)
        first_norm = float(np.linalg.norm(first))
        second_norm = float(np.linalg.norm(second))
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = float(np.dot(first, second) / max(first_norm * second_norm, 1e-9))
        if cosine < float(turn_cos_threshold):
            sharp_turn_indices.append(index)
            if len(sharp_turn_indices) > 1:
                return arr.tolist()
    if len(sharp_turn_indices) != 1:
        return arr.tolist()

    total_length = _polyline_length(simplified)
    if total_length <= 0.0:
        return arr.tolist()
    max_branch_length = total_length * max(float(max_branch_ratio), 0.0)
    if max_branch_length < float(min_branch_length_px):
        return arr.tolist()

    turn_index = sharp_turn_indices[0]
    start_branch_length = _polyline_length(simplified[: turn_index + 1])
    end_branch_length = _polyline_length(simplified[turn_index:])
    sampled_total_length = max(_polyline_length(points), 1e-6)
    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)

    if not bool(cap_start) and float(min_branch_length_px) <= start_branch_length <= max_branch_length:
        count = max(int(round(arr.size * (start_branch_length / sampled_total_length))), 2)
        _taper_endpoint_window(arr, start=0, step=1, count=min(count, int(arr.size)), reference=reference)
    if not bool(cap_end) and float(min_branch_length_px) <= end_branch_length <= max_branch_length:
        count = max(int(round(arr.size * (end_branch_length / sampled_total_length))), 2)
        _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=min(count, int(arr.size)), reference=reference)
    return arr.tolist()


def _taper_long_foldback_tail_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
    min_path_length_px: float = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MIN_PATH_LENGTH_PX,
    max_turn_cos: float = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MAX_TURN_COS,
    taper_point_count: int = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_POINT_COUNT,
    reference_scale: float = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_REFERENCE_SCALE,
) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if not (bool(cap_start) and not bool(cap_end)):
        return arr.tolist()
    if len(tuple(source_segment_ids)) <= 1 or len(points) < 3:
        return arr.tolist()
    if _polyline_length(points) < float(min_path_length_px):
        return arr.tolist()
    if not _has_foldback_turn(points, max_turn_cos=max_turn_cos):
        return arr.tolist()

    reference = _robust_segment_diameter_px(arr.tolist()) * max(float(reference_scale), 0.0)
    if reference <= 0.0:
        return arr.tolist()
    count = min(max(int(taper_point_count), 0), int(arr.size))
    _taper_endpoint_window(arr, start=int(arr.size) - 1, step=-1, count=count, reference=reference)
    return arr.tolist()


def _clamp_long_foldback_turn_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
    min_path_length_px: float = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MIN_PATH_LENGTH_PX,
    max_turn_cos: float = DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MAX_TURN_COS,
    window_points: int = DEFAULT_LONG_FOLDBACK_TURN_CLAMP_WINDOW_POINTS,
    max_scale: float = DEFAULT_LONG_FOLDBACK_TURN_CLAMP_MAX_SCALE,
) -> list[float]:
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if not (bool(cap_start) and not bool(cap_end)):
        return arr.tolist()
    if len(tuple(source_segment_ids)) <= 1 or len(points) < 3:
        return arr.tolist()
    if _polyline_length(points) < float(min_path_length_px):
        return arr.tolist()

    foldback_indices: list[tuple[float, int]] = []
    for index, (previous, current, following) in enumerate(
        zip(points[:-2], points[1:-1], points[2:]),
        start=1,
    ):
        incoming = np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
        outgoing = np.asarray(following, dtype=float) - np.asarray(current, dtype=float)
        incoming_norm = float(np.linalg.norm(incoming))
        outgoing_norm = float(np.linalg.norm(outgoing))
        if incoming_norm <= 1e-9 or outgoing_norm <= 1e-9:
            continue
        cosine = float(np.dot(incoming, outgoing) / max(incoming_norm * outgoing_norm, 1e-9))
        if cosine <= float(max_turn_cos):
            foldback_indices.append((cosine, index))
    if not foldback_indices:
        return arr.tolist()

    _, turn_index = min(foldback_indices)
    reference = _robust_segment_diameter_px(arr.tolist())
    if reference <= 0.0:
        return arr.tolist()
    radius = min(max(int(window_points), 0), max(int(arr.size) - 1, 0))
    if radius <= 0:
        return arr.tolist()

    start = max(int(turn_index) - radius, 0)
    end = min(int(turn_index) + radius + 1, int(arr.size))
    local_peak = float(np.max(arr[start:end]))
    center_limit = reference * max(float(max_scale), 0.0)
    for index in range(start, end):
        distance = abs(int(index) - int(turn_index))
        blend = min(float(distance) / float(radius), 1.0)
        allowed = center_limit * (1.0 - blend) + local_peak * blend
        arr[index] = min(float(arr[index]), allowed)
    return arr.tolist()


def _pointed_foldback_terminal_flags(
    points: Sequence[tuple[float, float]],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
) -> tuple[bool, bool]:
    if len(tuple(source_segment_ids)) <= 1 or len(points) < 3:
        return False, False
    if _polyline_length(points) < float(DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MIN_PATH_LENGTH_PX):
        return False, False
    if not _has_foldback_turn(points, max_turn_cos=DEFAULT_LONG_FOLDBACK_TAIL_TAPER_MAX_TURN_COS):
        return False, False
    if bool(cap_start) and not bool(cap_end):
        return False, True
    if bool(cap_end) and not bool(cap_start):
        return True, False
    return False, False


def _taper_pointed_foldback_terminal_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    source_segment_ids: Sequence[Any],
    cap_start: bool,
    cap_end: bool,
    taper_fraction: float = DEFAULT_POINTED_FOLDBACK_TAPER_FRACTION,
    min_taper_points: int = DEFAULT_POINTED_FOLDBACK_MIN_TAPER_POINTS,
) -> list[float]:
    arr = np.asarray([max(float(value), 0.0) for value in diameters], dtype=float)
    pointed_start, pointed_end = _pointed_foldback_terminal_flags(
        points,
        source_segment_ids=source_segment_ids,
        cap_start=cap_start,
        cap_end=cap_end,
    )
    if not pointed_start and not pointed_end:
        return arr.tolist()

    count = max(
        int(min_taper_points),
        int(np.ceil(float(arr.size) * max(float(taper_fraction), 0.0))),
    )
    count = min(max(count, 2), int(arr.size))
    if pointed_end:
        start = int(arr.size) - count
        reference = min(float(arr[start]), _robust_segment_diameter_px(arr.tolist()))
        limits = np.linspace(max(reference, 0.0), 0.0, count)
        arr[start:] = np.minimum(arr[start:], limits)
        for index in range(start + 1, int(arr.size)):
            arr[index] = min(float(arr[index]), float(arr[index - 1]))
        arr[-1] = 0.0
    else:
        end = count
        reference = min(float(arr[end - 1]), _robust_segment_diameter_px(arr.tolist()))
        limits = np.linspace(0.0, max(reference, 0.0), count)
        arr[:end] = np.minimum(arr[:end], limits)
        for index in range(end - 2, -1, -1):
            arr[index] = min(float(arr[index]), float(arr[index + 1]))
        arr[0] = 0.0
    return arr.tolist()


def _has_foldback_turn(
    points: Sequence[tuple[float, float]],
    *,
    max_turn_cos: float,
) -> bool:
    simplified = _simplify_render_points(points)
    if len(simplified) < 3:
        return False
    for previous, current, following in zip(simplified[:-2], simplified[1:-1], simplified[2:]):
        first = np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
        second = np.asarray(following, dtype=float) - np.asarray(current, dtype=float)
        first_norm = float(np.linalg.norm(first))
        second_norm = float(np.linalg.norm(second))
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = float(np.dot(first, second) / max(first_norm * second_norm, 1e-9))
        if cosine <= float(max_turn_cos):
            return True
    return False


def _taper_endpoint_window(
    diameters: np.ndarray,
    *,
    start: int,
    step: int,
    count: int,
    reference: float,
) -> None:
    if count <= 0:
        return
    denom = max(count - 1, 1)
    for offset in range(count):
        index = int(start + step * offset)
        if index < 0 or index >= int(diameters.size):
            continue
        blend = offset / float(denom)
        tapered = float(reference) * (1.0 - blend) + float(diameters[index]) * blend
        diameters[index] = min(float(diameters[index]), tapered)


def _regularize_straight_segment_body_diameters_px(
    points: Sequence[tuple[float, float]],
    diameters: Sequence[float],
    *,
    cap_start: bool,
    cap_end: bool,
    source_segment_ids: Sequence[Any],
    min_point_count: int = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MIN_POINT_COUNT,
    min_axis_ratio: float = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MIN_AXIS_RATIO,
    max_axis_residual_px: float = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_AXIS_RESIDUAL_PX,
    max_cv: float = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_CV,
    max_span_ratio: float = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_SPAN_RATIO,
    max_sharp_turns: int = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_MAX_SHARP_TURNS,
    blend: float = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_BLEND,
    endpoint_preserve_count: int = DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_ENDPOINT_PRESERVE_COUNT,
) -> list[float]:
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    if len(points) < max(int(min_point_count), 2) or arr.size < max(int(min_point_count), 2):
        return arr.tolist()
    if _has_excessive_turning_for_variable_width(
        points,
        direction_cos_threshold=0.92,
        max_sharp_turns=max(int(max_sharp_turns), 0),
    ):
        return arr.tolist()
    if _principal_axis_ratio(points) < float(min_axis_ratio):
        return arr.tolist()
    if _principal_axis_residual(points) > float(max_axis_residual_px):
        return arr.tolist()

    preserve = min(max(int(endpoint_preserve_count), 0), max(int(arr.size // 2), 0))
    body_start = preserve
    body_end = int(arr.size) - preserve
    body = arr[body_start:body_end]
    if body.size < max(int(min_point_count // 2), 3):
        body_start = 0
        body_end = int(arr.size)
        body = arr

    reference = _robust_segment_diameter_px(body.tolist())
    if reference <= 0.0:
        return arr.tolist()
    lower_span = float(np.percentile(body, 10.0))
    upper_span = float(np.percentile(body, 90.0))
    span_ratio = float((upper_span - lower_span) / max(reference, 1e-6))
    coefficient_of_variation = float(body.std() / max(body.mean(), 1e-6))
    if span_ratio > float(max_span_ratio) or coefficient_of_variation > float(max_cv):
        return arr.tolist()

    regularized = arr.copy()
    effective_blend = min(max(float(blend), 0.0), 1.0)
    regularized[body_start:body_end] = arr[body_start:body_end] * (1.0 - effective_blend) + float(reference) * effective_blend
    body_reference = _robust_segment_diameter_px(regularized[body_start:body_end].tolist())
    if body_reference > 0.0 and body_end > body_start:
        band_ratio = float(DEFAULT_STRAIGHT_SEGMENT_WIDTH_REGULARIZATION_BODY_BAND_RATIO)
        lower_bound = max(1.0, body_reference * (1.0 - band_ratio))
        upper_bound = max(lower_bound, body_reference * (1.0 + band_ratio))
        regularized[body_start:body_end] = np.clip(regularized[body_start:body_end], lower_bound, upper_bound)
    return regularized.tolist()


def _trim_render_overlap_stub_points(
    points: Sequence[tuple[float, float]],
    *,
    trim_start_points: int,
    trim_end_points: int,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    start = min(max(int(trim_start_points), 0), len(points) - 2)
    remaining_after_start = len(points) - start
    end_trim = min(max(int(trim_end_points), 0), remaining_after_start - 2)
    end = len(points) - end_trim
    trimmed = list(points[start:end])
    if len(trimmed) >= 2:
        return trimmed
    return list(points)


def _apply_endpoint_extensions(
    points: Sequence[tuple[float, float]],
    *,
    extend_start_px: float,
    extend_end_px: float,
) -> list[tuple[float, float]]:
    updated = [tuple(_as_float_point(point)) for point in points]
    if len(updated) < 2:
        return updated
    if float(extend_start_px) > 1e-9:
        direction = _unit_direction(updated[0], updated[1])
        if direction is not None:
            updated = [
                (
                    float(updated[0][0]) - float(direction[0]) * float(extend_start_px),
                    float(updated[0][1]) - float(direction[1]) * float(extend_start_px),
                )
            ] + updated
    if float(extend_end_px) > 1e-9:
        direction = _unit_direction(updated[-2], updated[-1])
        if direction is not None:
            updated = updated + [
                (
                    float(updated[-1][0]) + float(direction[0]) * float(extend_end_px),
                    float(updated[-1][1]) + float(direction[1]) * float(extend_end_px),
                )
            ]
    return updated


def _draw_pen_up_connectors(draw: ImageDraw.ImageDraw, ordered_segments: Sequence[dict[str, Any]], scale: int) -> None:
    previous_end: Any | None = None
    for segment in ordered_segments:
        points = list(segment.get("points", ()))
        if previous_end is not None and points:
            _draw_dashed_line(
                draw,
                _scaled_xy_continuous(previous_end, scale),
                _scaled_xy_continuous(points[0], scale),
                (160, 160, 160),
                scale,
            )
        if points:
            previous_end = points[-1]


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int],
    scale: int,
    *,
    dash_px: int = 6,
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
            width=max(scale // 4, 1),
        )


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    return float(
        sum(
            np.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
            for start, end in zip(points[:-1], points[1:])
        )
    )


def _label_xy(points: Sequence[Any], scale: int, label_positions: dict[tuple[int, int], int]) -> tuple[int, int]:
    y, x = _as_int_point(points[len(points) // 2])
    key = (y, x)
    collision_index = label_positions.get(key, 0)
    label_positions[key] = collision_index + 1
    return (x * scale + 1 + collision_index * scale, y * scale + 1 + collision_index * scale)


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str) -> None:
    x, y = xy
    bbox = draw.textbbox((x, y), label)
    pad = 1
    draw.rectangle(
        (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad),
        fill=(255, 255, 255),
        outline=(40, 40, 40),
    )
    draw.text((x, y), label, fill=(0, 0, 0))


def _cell(draw: ImageDraw.ImageDraw, y: int, x: int, scale: int, color: tuple[int, int, int]) -> None:
    draw.rectangle((x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1), fill=color)


def _scaled_xy(point: Any, scale: int) -> tuple[int, int]:
    y, x = _as_int_point(point)
    return (x * scale + scale // 2, y * scale + scale // 2)


def _scaled_xy_continuous(point: Any, scale: int) -> tuple[float, float]:
    y, x = _as_float_point(point)
    return (float(x) * scale + scale / 2.0, float(y) * scale + scale / 2.0)


def _as_int_point(point: Any) -> tuple[int, int]:
    y, x = point
    return int(round(float(y))), int(round(float(x)))


def _as_float_point(point: Any) -> tuple[float, float]:
    y, x = point
    return (float(y), float(x))


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _fit_image_to_panel(image: Image.Image, panel_size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", panel_size, (255, 255, 255))
    fitted = image.copy()
    fitted.thumbnail(panel_size, Image.Resampling.LANCZOS)
    left = max((panel_size[0] - fitted.width) // 2, 0)
    top = max((panel_size[1] - fitted.height) // 2, 0)
    panel.paste(fitted, (left, top))
    return panel


def _estimate_foreground_brush_diameter_px(
    points: Sequence[tuple[float, float]],
    index: int,
    foreground_mask: np.ndarray,
) -> float:
    tangent = _local_tangent(points, index)
    norm = float(np.hypot(tangent[0], tangent[1]))
    if norm <= 1e-9:
        return 1.0
    normal = (-float(tangent[1]) / norm, float(tangent[0]) / norm)
    offsets = _foreground_offsets_along_normal(
        points[index],
        normal,
        foreground_mask,
        radius_px=DEFAULT_EXECUTION_WIDTH_SEARCH_RADIUS_PX,
        sample_step_px=DEFAULT_EXECUTION_WIDTH_SAMPLE_STEP_PX,
    )
    if not offsets:
        return 1.0
    run = _select_local_offset_run(offsets, step_px=DEFAULT_EXECUTION_WIDTH_SAMPLE_STEP_PX)
    if not run:
        return 1.0
    return max(float(run[-1] - run[0] + DEFAULT_EXECUTION_WIDTH_SAMPLE_STEP_PX), 1.0)


def _estimate_segment_brush_diameter_px(
    points: Sequence[tuple[float, float]],
    foreground_mask: np.ndarray,
) -> float:
    point_diameters = _estimate_point_brush_diameters_px(points, foreground_mask)
    if not point_diameters:
        return 1.0
    return _robust_segment_diameter_px(point_diameters)


def _estimate_point_brush_diameters_px(
    points: Sequence[tuple[float, float]],
    foreground_mask: np.ndarray,
) -> list[float]:
    sampled_points = _sample_polyline_points(
        points,
        step_px=1.0,
    )
    if not sampled_points:
        return []
    return [
        _estimate_foreground_brush_diameter_px(
            sampled_points,
            index,
            foreground_mask,
        )
        for index in range(len(sampled_points))
    ]


def _local_tangent(points: Sequence[tuple[float, float]], index: int) -> tuple[float, float]:
    if len(points) <= 1:
        return (0.0, 0.0)
    current = points[index]
    previous = points[index - 1] if index > 0 else current
    following = points[index + 1] if index + 1 < len(points) else current
    return (float(following[0]) - float(previous[0]), float(following[1]) - float(previous[1]))


def _unit_vector(vector: Sequence[float]) -> tuple[float, float] | None:
    if len(vector) < 2:
        return None
    vy = float(vector[0])
    vx = float(vector[1])
    norm = float(np.hypot(vy, vx))
    if norm <= 1e-9:
        return None
    return (vy / norm, vx / norm)


def _unit_direction(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float] | None:
    return _unit_vector((float(end[0]) - float(start[0]), float(end[1]) - float(start[1])))


def _foreground_offsets_along_normal(
    point: tuple[float, float],
    normal: tuple[float, float],
    foreground_mask: np.ndarray,
    *,
    radius_px: float,
    sample_step_px: float,
) -> list[float]:
    height, width = foreground_mask.shape
    offsets: list[float] = []
    steps = int(np.floor(radius_px / sample_step_px))
    for step_index in range(-steps, steps + 1):
        offset = step_index * sample_step_px
        y = float(point[0]) + float(normal[0]) * offset
        x = float(point[1]) + float(normal[1]) * offset
        iy = int(round(y))
        ix = int(round(x))
        if 0 <= iy < height and 0 <= ix < width and bool(foreground_mask[iy, ix]):
            offsets.append(offset)
    return offsets


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


def _robust_segment_diameter_px(diameters: Sequence[float]) -> float:
    if not diameters:
        return 1.0
    arr = np.asarray([float(value) for value in diameters if float(value) > 0.0], dtype=float)
    if arr.size == 0:
        return 1.0
    return max(float(np.median(arr)), 1.0)


def _stabilize_point_brush_diameters_px(diameters: Sequence[float]) -> list[float]:
    if not diameters:
        return []
    arr = np.asarray([max(float(value), 1.0) for value in diameters], dtype=float)
    radius = max(int(DEFAULT_EXECUTION_WIDTH_SMOOTH_WINDOW_RADIUS), 0)
    if arr.size > 2 and radius > 0:
        smoothed = np.empty_like(arr)
        for index in range(arr.size):
            start = max(0, index - radius)
            end = min(arr.size, index + radius + 1)
            smoothed[index] = float(np.median(arr[start:end]))
    else:
        smoothed = arr
    reference = _robust_segment_diameter_px(arr.tolist())
    upper = max(float(reference) * float(DEFAULT_EXECUTION_WIDTH_UPPER_SCALE), float(reference))
    return [min(max(float(value), 1.0), upper) for value in smoothed.tolist()]


def _principal_axis_residual(points: Sequence[tuple[float, float]]) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    return float(np.mean(np.abs(centered @ vh[-1])))


def _principal_axis_ratio(points: Sequence[tuple[float, float]]) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    if singular_values.size == 0:
        return 0.0
    return float(singular_values[0] / max(float(singular_values[-1]), 1e-6))


def _sample_polyline_points(
    points: Sequence[tuple[float, float]],
    *,
    step_px: float,
) -> list[tuple[float, float]]:
    if not points:
        return []
    if len(points) == 1:
        return [points[0]]

    sampled: list[tuple[float, float]] = [points[0]]
    safe_step = max(float(step_px), 1e-6)
    for start, end in zip(points[:-1], points[1:]):
        dy = float(end[0] - start[0])
        dx = float(end[1] - start[1])
        distance = float(np.hypot(dy, dx))
        steps = max(int(np.ceil(distance / safe_step)), 1)
        for step in range(1, steps + 1):
            ratio = step / float(steps)
            sampled.append((float(start[0] + dy * ratio), float(start[1] + dx * ratio)))
    return sampled


def _simplify_render_points(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    simplified = [points[0]]
    for index in range(1, len(points) - 1):
        previous = np.asarray(simplified[-1], dtype=float)
        current = np.asarray(points[index], dtype=float)
        following = np.asarray(points[index + 1], dtype=float)
        first = current - previous
        second = following - current
        first_norm = float(np.linalg.norm(first))
        second_norm = float(np.linalg.norm(second))
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = float(np.dot(first, second) / max(first_norm * second_norm, 1e-9))
        if cosine >= 0.999:
            continue
        simplified.append(points[index])
    simplified.append(points[-1])
    return simplified


def _has_excessive_turning_for_variable_width(
    points: Sequence[tuple[float, float]],
    *,
    direction_cos_threshold: float = 0.82,
    max_sharp_turns: int = 1,
) -> bool:
    simplified = _simplify_render_points(points)
    if len(simplified) <= 2:
        return False

    sharp_turns = 0
    for previous, current, following in zip(simplified[:-2], simplified[1:-1], simplified[2:]):
        first = np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
        second = np.asarray(following, dtype=float) - np.asarray(current, dtype=float)
        first_norm = float(np.linalg.norm(first))
        second_norm = float(np.linalg.norm(second))
        if first_norm <= 1e-9 or second_norm <= 1e-9:
            continue
        cosine = float(np.dot(first, second) / max(first_norm * second_norm, 1e-9))
        if cosine < float(direction_cos_threshold):
            sharp_turns += 1
            if sharp_turns > int(max_sharp_turns):
                return True
    return False
