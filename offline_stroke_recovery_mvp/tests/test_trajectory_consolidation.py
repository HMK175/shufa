from pathlib import Path
import sys

import numpy as np
from PIL import Image

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import load_callirewrite_segments
from makemeahanzi_prior import (
    MakeMeAHanziKnowledge,
    _closest_arc,
    _mean_polyline_distance,
    _resample_polyline_to_count,
    _sample_stroke_subpath,
    _support_ratio_in_radius,
    normalize_medians_to_canvas,
    regroup_ordered_segments_by_makemeahanzi,
    resolve_sample_char,
)
from ordering import order_segments
from preprocess import ensure_foreground_is_true
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
)


def _load_repo_input_foreground_mask(sample: str) -> np.ndarray:
    image_path = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs"
        / f"{sample}.png"
    )
    with Image.open(image_path) as image:
        return ensure_foreground_is_true(np.asarray(image.convert("L")), threshold=200)


def _max_axis_backtrack(points: list[tuple[float, float]], axis: int, *, limit: int | None = None) -> float:
    deltas = []
    pairs = zip(points[:limit], points[1:limit] if limit is not None else points[1:])
    for previous, current in pairs:
        delta = float(current[axis]) - float(previous[axis])
        if delta < 0:
            deltas.append(-delta)
    return max(deltas, default=0.0)


def _select_zhong_vertical_group(segments: list[dict[str, object]]) -> dict[str, object]:
    return next(
        segment
        for segment in segments
        if 2 in tuple(segment.get("source_segment_ids", ())) and 13 in tuple(segment.get("source_segment_ids", ()))
    )


def _select_segment_by_source_ids(segments: list[dict[str, object]], source_ids: tuple[int, ...]) -> dict[str, object]:
    return next(
        segment
        for segment in segments
        if tuple(segment.get("source_segment_ids", ())) == source_ids
    )


def _mean_distance_to_prior_subpath(
    segment: dict[str, object],
    prior_strokes: list[np.ndarray],
) -> float:
    points = np.asarray(segment.get("points", ()), dtype=float)
    prior = np.asarray(prior_strokes[int(segment.get("component_id", 0)) - 1], dtype=float)
    arcs = [_closest_arc(point, prior)[1] for point in points]
    prior_subpath = _sample_stroke_subpath(prior, min(arcs), max(arcs), step_px=1.0)
    aligned_points = _resample_polyline_to_count(points, len(prior_subpath))
    return float(_mean_polyline_distance(aligned_points, prior_subpath))


def _principal_axis_residual(points: list[tuple[float, float]]) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    return float(np.mean(np.abs(centered @ vh[-1])))


def _mean_abs_x_displacement_near_and_far_foreign_segments(
    baseline_segment: dict[str, object],
    updated_segment: dict[str, object],
    foreign_segments: list[dict[str, object]],
    *,
    resample_count: int = 80,
    near_distance_px: float = 10.0,
    far_distance_px: float = 18.0,
) -> tuple[float, float]:
    baseline_points = _resample_polyline_to_count(
        np.asarray(baseline_segment.get("points", ()), dtype=float),
        resample_count,
    )
    updated_points = _resample_polyline_to_count(
        np.asarray(updated_segment.get("points", ()), dtype=float),
        resample_count,
    )
    foreign_points = np.vstack(
        [
            np.asarray(segment.get("points", ()), dtype=float)
            for segment in foreign_segments
            if len(segment.get("points", ())) > 0
        ]
    )
    foreign_distance = np.sqrt(((baseline_points[:, None, :] - foreign_points[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    x_displacement = np.abs(updated_points[:, 1] - baseline_points[:, 1])
    near = x_displacement[foreign_distance <= near_distance_px]
    far = x_displacement[foreign_distance >= far_distance_px]
    return float(near.mean()), float(far.mean())


def test_consolidate_ordered_segments_merges_short_same_component_bridge():
    ordered = [
        {"component_id": 1, "points": [(0, 0), (0, 1), (0, 2)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 1, "points": [(0, 2), (1, 2), (2, 2)], "stroke_like_id": 2, "order_index": 2},
    ]

    consolidated, meta = consolidate_ordered_segments(ordered)

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (0, 0)
    assert consolidated[0]["points"][-1] == (2, 2)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_records_render_subpaths_for_touching_corner_merge():
    ordered = [
        {
            "component_id": 1,
            "points": [(0.0, 0.0), (0.0, 2.0)],
            "stroke_like_id": 1,
            "order_index": 1,
            "source_segment_ids": (10,),
        },
        {
            "component_id": 1,
            "points": [(0.0, 2.0), (2.0, 2.0)],
            "stroke_like_id": 2,
            "order_index": 2,
            "source_segment_ids": (2,),
        },
    ]

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_snap_radius_px=0.0,
    )

    assert len(consolidated) == 1
    assert meta["merged_segment_count"] == 1
    assert tuple(consolidated[0]["source_segment_ids"]) == (10, 2)
    assert consolidated[0]["render_subpaths"] == [
        [(0.0, 0.0), (0.0, 2.0)],
        [(0.0, 2.0), (2.0, 2.0)],
    ]
    assert consolidated[0]["render_subpath_source_ids"] == [(10,), (2,)]


def test_light_repair_raw_segments_merges_small_supported_collinear_split():
    raw_segments = [
        {"component_id": 1, "points": [(4.0, 2.0), (4.0, 5.0)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(4.0, 7.0), (4.0, 10.0)], "stroke_like_id": 2, "order_index": 2},
    ]
    foreground_mask = np.zeros((10, 14), dtype=bool)
    foreground_mask[3:6, 1:11] = True

    repaired, meta = light_repair_raw_segments(
        raw_segments,
        foreground_mask=foreground_mask,
    )

    assert len(repaired) == 1
    assert repaired[0]["points"][0] == (4.0, 2.0)
    assert repaired[0]["points"][-1] == (4.0, 10.0)
    assert meta["light_repair_merged_segment_count"] == 1


def test_light_repair_raw_segments_keeps_orthogonal_corner_split():
    raw_segments = [
        {"component_id": 1, "points": [(2.0, 4.0), (5.0, 4.0)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(5.0, 4.0), (5.0, 8.0)], "stroke_like_id": 2, "order_index": 2},
    ]

    repaired, meta = light_repair_raw_segments(raw_segments)

    assert len(repaired) == 2
    assert meta["light_repair_merged_segment_count"] == 0


def test_light_repair_ordered_segments_geometry_recenters_left_wall_and_keeps_connected_corners_attached():
    ordered_segments = [
        {"component_id": 1, "points": [(2.0, float(x)) for x in range(4, 11)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(2.0 + 0.5 * index, 4.0) for index in range(13)], "stroke_like_id": 2, "order_index": 2},
        {"component_id": 3, "points": [(8.0, float(x)) for x in range(4, 11)], "stroke_like_id": 3, "order_index": 3},
    ]
    foreground_mask = np.zeros((12, 14), dtype=bool)
    foreground_mask[1:10, 1:5] = True
    foreground_mask[1:4, 1:11] = True
    foreground_mask[7:10, 1:11] = True

    repaired, meta = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )

    left_wall = repaired[1]
    top = repaired[0]
    bottom = repaired[2]
    left_wall_x_mean = float(np.mean([point[1] for point in left_wall["points"]]))

    assert left_wall_x_mean < 3.25
    assert left_wall["points"][0] == top["points"][0]
    assert left_wall["points"][-1] == bottom["points"][0]
    assert meta["light_repair_geometry_adjusted_segment_count"] == 1


def test_light_repair_ordered_segments_geometry_recenters_bottom_bar_and_keeps_sidewalls_attached():
    ordered_segments = [
        {"component_id": 1, "points": [(2.0, 2.0 + 0.5 * index) for index in range(13)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(2.0 + 0.5 * index, 2.0) for index in range(13)], "stroke_like_id": 2, "order_index": 2},
        {"component_id": 3, "points": [(2.0 + 0.5 * index, 8.0) for index in range(13)], "stroke_like_id": 3, "order_index": 3},
        {"component_id": 4, "points": [(8.8, 2.0 + 0.5 * index) for index in range(13)], "stroke_like_id": 4, "order_index": 4},
    ]
    foreground_mask = np.zeros((14, 14), dtype=bool)
    foreground_mask[1:4, 1:9] = True
    foreground_mask[1:11, 1:4] = True
    foreground_mask[7:10, 1:9] = True
    foreground_mask[1:11, 7:10] = True

    repaired, meta = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )

    bottom = repaired[3]
    left_wall = repaired[1]
    right_wall = repaired[2]
    bottom_y_mean = float(np.mean([point[0] for point in bottom["points"]]))

    assert bottom_y_mean < 8.2
    assert left_wall["points"][-1] == bottom["points"][0]
    assert right_wall["points"][-1] == bottom["points"][-1]
    assert meta["light_repair_geometry_adjusted_segment_count"] >= 1


def test_consolidate_ordered_segments_keeps_cross_component_jump_split():
    ordered = [
        {"component_id": 1, "points": [(0, 0), (0, 1)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(5, 5), (5, 6)], "stroke_like_id": 2, "order_index": 2},
    ]

    consolidated, meta = consolidate_ordered_segments(ordered)

    assert len(consolidated) == 2
    assert meta["merged_segment_count"] == 0


def test_consolidate_ordered_segments_can_skip_merge_while_still_running_postprocess():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, 2.0), (2.0, 5.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(2.0, 5.0), (2.0, 8.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((8, 12), dtype=bool)
    foreground_mask[2:6, 1:10] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        merge_adjacent=False,
        simplify_tolerance_px=0.0,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    assert len(consolidated) == 2
    assert meta["merged_segment_count"] == 0
    assert meta["resampled_point_delta"] > 0
    assert meta["snapped_point_count"] > 0


def test_consolidate_ordered_segments_supports_conservative_foreground_snap_blend():
    ordered = [
        {
            "component_id": 1,
            "points": [(float(y), 4.0) for y in range(2, 18)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
    ]
    foreground_mask = np.zeros((22, 14), dtype=bool)
    foreground_mask[2:18, 7:11] = True

    conservative, conservative_meta = consolidate_ordered_segments(
        ordered,
        merge_adjacent=False,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
        foreground_snap_blend=0.25,
    )
    full, full_meta = consolidate_ordered_segments(
        ordered,
        merge_adjacent=False,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
        foreground_snap_blend=1.0,
    )

    conservative_mean_x = float(np.mean([point[1] for point in conservative[0]["points"]]))
    full_mean_x = float(np.mean([point[1] for point in full[0]["points"]]))

    assert conservative_meta["snapped_point_count"] > 0
    assert full_meta["snapped_point_count"] > 0
    assert conservative_mean_x > 4.25
    assert full_mean_x > conservative_mean_x + 1.0


def test_consolidate_ordered_segments_avoids_local_backtrack_on_zhong_hooked_stem():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target_segment = _select_zhong_vertical_group(grouped_segments)

    consolidated, _ = consolidate_ordered_segments(
        [target_segment],
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    assert _max_axis_backtrack(consolidated[0]["points"], axis=0, limit=20) <= 0.5


def test_consolidate_ordered_segments_keeps_zhong_hooked_stem_monotone_at_top():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target_segment = _select_zhong_vertical_group(grouped_segments)

    consolidated, _ = consolidate_ordered_segments(
        [target_segment],
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    top_points = consolidated[0]["points"][:12]
    y_steps = [float(current[0]) - float(previous[0]) for previous, current in zip(top_points[:-1], top_points[1:])]
    assert min(y_steps) >= -1e-6


def test_consolidate_ordered_segments_preserves_strong_downward_progress_on_zhong_top_stem():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target_segment = _select_zhong_vertical_group(grouped_segments)

    consolidated, _ = consolidate_ordered_segments(
        [target_segment],
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    top_points = consolidated[0]["points"][:12]
    y_steps = [float(current[0]) - float(previous[0]) for previous, current in zip(top_points[:-1], top_points[1:])]
    assert min(y_steps) >= 0.6


def test_consolidate_ordered_segments_stitches_small_internal_gap_between_zhong_lead_in_and_main_stem():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    lead_in = _select_segment_by_source_ids(consolidated, (10,))
    main_stem = _select_segment_by_source_ids(consolidated, (2, 13))
    lead_end = np.asarray(lead_in["points"][-1], dtype=float)
    main_start = np.asarray(main_stem["points"][0], dtype=float)

    assert float(np.linalg.norm(lead_end - main_start)) <= 1.0


def test_consolidate_ordered_segments_keeps_zhong_right_segment_supported_by_input_foreground():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    target = _select_segment_by_source_ids(consolidated, (7, 8, 4))
    points = np.asarray(target.get("points", ()), dtype=float)

    assert _support_ratio_in_radius(points, foreground_mask, radius_px=1) >= 0.9


def test_consolidate_ordered_segments_preserves_prior_aligned_yong_left_heng_pie_geometry():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "yong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("yong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="yong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    prior_strokes = normalize_medians_to_canvas(
        MakeMeAHanziKnowledge(graphics_path).get_glyph(resolve_sample_char("yong")).medians,
        canvas_shape=tuple(foreground_mask.shape),
    )
    target = _select_segment_by_source_ids(consolidated, (8, 6))

    assert _mean_distance_to_prior_subpath(target, prior_strokes) <= 1.0


def test_consolidate_ordered_segments_does_not_bend_prior_aligned_zhong_main_stem():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target_segment = _select_segment_by_source_ids(grouped_segments, (2, 13))
    grouped_residual = _principal_axis_residual(target_segment["points"])

    consolidated, _ = consolidate_ordered_segments(
        [target_segment],
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )
    consolidated_residual = _principal_axis_residual(consolidated[0]["points"])

    assert grouped_residual <= 0.15
    assert consolidated_residual <= grouped_residual + 0.05


def test_consolidate_ordered_segments_only_locally_snaps_zhong_main_stem_near_mouth_structure():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target_segment = _select_segment_by_source_ids(grouped_segments, (2, 13))
    foreign_segments = [
        segment
        for segment in grouped_segments
        if tuple(segment.get("source_segment_ids", ())) != (2, 13)
    ]
    no_snap_consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=None,
    )
    no_snap_segment = _select_segment_by_source_ids(no_snap_consolidated, (2, 13))

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )
    updated_segment = _select_segment_by_source_ids(consolidated, (2, 13))
    near_mean, far_mean = _mean_abs_x_displacement_near_and_far_foreign_segments(
        no_snap_segment,
        updated_segment,
        foreign_segments,
    )

    assert near_mean >= 0.4
    assert far_mean <= 0.1


def test_consolidate_ordered_segments_attaches_supported_zhong_frame_corners_across_components():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "zhong"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("zhong")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    top_segment = _select_segment_by_source_ids(consolidated, (6, 16))
    frame_loop_segment = _select_segment_by_source_ids(consolidated, (7, 8, 4))
    right_segment = _select_segment_by_source_ids(consolidated, (5,))

    top_left_gap = float(
        np.linalg.norm(np.asarray(top_segment["points"][0], dtype=float) - np.asarray(frame_loop_segment["points"][0], dtype=float))
    )
    top_right_gap = float(
        np.linalg.norm(np.asarray(top_segment["points"][-1], dtype=float) - np.asarray(right_segment["points"][0], dtype=float))
    )
    bottom_right_gap = float(
        np.linalg.norm(np.asarray(frame_loop_segment["points"][-1], dtype=float) - np.asarray(right_segment["points"][-1], dtype=float))
    )

    assert top_left_gap <= 1.0
    assert top_right_gap <= 1.0
    assert bottom_right_gap <= 1.0


def test_consolidate_ordered_segments_stitches_supported_internal_corner_gap_between_kou_bottom_and_right_segments():
    converted_dir = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "kou"
    )
    graphics_path = Path(__file__).resolve().parents[2] / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_repo_input_foreground_mask("kou")
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="kou",
        canvas_shape=tuple(foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    consolidated, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    right_segment = _select_segment_by_source_ids(consolidated, (5,))
    bottom_segment = _select_segment_by_source_ids(consolidated, (2,))
    right_end = np.asarray(right_segment["points"][-1], dtype=float)
    bottom_start = np.asarray(bottom_segment["points"][0], dtype=float)

    assert float(np.linalg.norm(right_end - bottom_start)) <= 1.0


def test_consolidate_ordered_segments_does_not_attach_supported_parallel_cross_component_endpoints():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, 2.0), (6.0, 2.0)],
            "stroke_like_id": 1,
            "order_index": 1,
            "source_segment_ids": (1,),
        },
        {
            "component_id": 2,
            "points": [(8.0, 2.0), (12.0, 2.0)],
            "stroke_like_id": 2,
            "order_index": 2,
            "source_segment_ids": (2,),
        },
    ]
    foreground_mask = np.zeros((16, 16), dtype=bool)
    foreground_mask[1:4, 1:13] = True

    consolidated, _ = consolidate_ordered_segments(
        ordered,
        merge_adjacent=False,
        foreground_mask=foreground_mask,
    )

    first_end = np.asarray(consolidated[0]["points"][-1], dtype=float)
    second_start = np.asarray(consolidated[1]["points"][0], dtype=float)

    assert float(np.linalg.norm(first_end - second_start)) >= 1.5


def test_consolidate_ordered_segments_simplifies_small_zigzag_without_moving_endpoints():
    ordered = [
        {
            "component_id": 1,
            "points": [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]

    consolidated, meta = consolidate_ordered_segments(ordered, simplify_tolerance_px=1.1, resample_step_px=None)

    assert consolidated[0]["points"][0] == (0, 0)
    assert consolidated[0]["points"][-1] == (2, 2)
    assert len(consolidated[0]["points"]) < len(ordered[0]["points"])
    assert meta["simplified_point_delta"] > 0


def test_consolidate_ordered_segments_resamples_long_segment_without_moving_endpoints():
    ordered = [
        {
            "component_id": 1,
            "points": [(0, 0), (0, 3)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]

    consolidated, meta = consolidate_ordered_segments(ordered, simplify_tolerance_px=0.0, resample_step_px=1.0)

    assert consolidated[0]["points"][0] == (0, 0)
    assert consolidated[0]["points"][-1] == (0, 3)
    assert len(consolidated[0]["points"]) >= 4
    assert meta["resampled_point_delta"] > 0


def test_consolidate_ordered_segments_merges_when_following_segment_needs_reversal():
    ordered = [
        {
            "component_id": 1,
            "points": [(0.0, 0.0), (0.0, 3.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(0.0, 6.0), (0.0, 3.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
    )

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (0.0, 0.0)
    assert consolidated[0]["points"][-1] == (0.0, 6.0)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_snaps_edge_hugging_line_toward_foreground_midline():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, 2.0), (2.0, 10.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]
    foreground_mask = np.zeros((10, 14), dtype=bool)
    foreground_mask[2:6, 1:12] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    ys = [point[0] for point in consolidated[0]["points"]]
    assert min(ys) > 2.5
    assert max(ys) < 4.5
    assert meta["snapped_point_count"] == len(consolidated[0]["points"])


def test_consolidate_ordered_segments_smooths_pixel_jitter_after_foreground_snapping():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, float(x)) for x in range(2, 12)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]
    foreground_mask = np.zeros((10, 16), dtype=bool)
    for x in range(1, 13):
        if x % 2 == 0:
            foreground_mask[2:6, x] = True
        else:
            foreground_mask[2:4, x] = True

    consolidated, _ = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    ys = [point[0] for point in consolidated[0]["points"]]
    assert max(ys) - min(ys) < 0.35


def test_consolidate_ordered_segments_reapplies_simplify_after_snapping_to_remove_small_waves():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, float(x)) for x in range(2, 12)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]
    foreground_mask = np.zeros((10, 16), dtype=bool)
    for x in range(1, 13):
        if x % 2 == 0:
            foreground_mask[2:6, x] = True
        else:
            foreground_mask[2:4, x] = True

    consolidated, _ = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.75,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    assert len(consolidated[0]["points"]) <= 4


def test_consolidate_ordered_segments_merges_collinear_gap_when_bridge_is_supported_by_foreground():
    ordered = [
        {
            "component_id": 1,
            "points": [(4.0, 2.0), (4.0, 5.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(4.0, 9.0), (4.0, 12.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((10, 16), dtype=bool)
    foreground_mask[3:6, 1:13] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
        foreground_snap_radius_px=0.0,
    )

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (4.0, 2.0)
    assert consolidated[0]["points"][-1] == (4.0, 12.0)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_keeps_collinear_gap_split_when_bridge_is_not_supported():
    ordered = [
        {
            "component_id": 1,
            "points": [(4.0, 2.0), (4.0, 5.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(4.0, 9.0), (4.0, 12.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((10, 16), dtype=bool)
    foreground_mask[3:6, 1:6] = True
    foreground_mask[3:6, 9:13] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    assert len(consolidated) == 2
    assert meta["merged_segment_count"] == 0


def test_consolidate_ordered_segments_merges_small_aligned_overlap_when_foreground_supported():
    ordered = [
        {
            "component_id": 1,
            "points": [(4.0, 2.0), (4.0, 5.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(4.0, 3.4), (4.0, 8.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((10, 12), dtype=bool)
    foreground_mask[3:6, 1:9] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (4.0, 2.0)
    assert consolidated[0]["points"][-1] == (4.0, 8.0)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_merges_small_supported_corner_gap():
    ordered = [
        {
            "component_id": 1,
            "points": [(0.0, 6.0), (2.0, 4.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(1.0, 1.0), (3.0, 3.0), (5.0, 5.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((8, 8), dtype=bool)
    foreground_mask[0:6, 0:7] = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 0, 0, 0, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 1, 0],
            [0, 0, 0, 0, 1, 1, 0],
            [0, 0, 0, 0, 0, 1, 0],
        ],
        dtype=bool,
    )

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
        foreground_snap_radius_px=0.0,
    )

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (0.0, 6.0)
    assert consolidated[0]["points"][-1] == (5.0, 5.0)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_keeps_corner_gap_split_without_foreground_support():
    ordered = [
        {
            "component_id": 1,
            "points": [(0.0, 6.0), (2.0, 4.0)],
            "stroke_like_id": 1,
            "order_index": 1,
        },
        {
            "component_id": 1,
            "points": [(1.0, 1.0), (3.0, 3.0), (5.0, 5.0)],
            "stroke_like_id": 2,
            "order_index": 2,
        },
    ]
    foreground_mask = np.zeros((8, 8), dtype=bool)
    foreground_mask[1:3, 1:3] = True
    foreground_mask[3:6, 3:6] = True

    consolidated, meta = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    assert len(consolidated) == 2
    assert meta["merged_segment_count"] == 0


def test_consolidate_ordered_segments_avoids_crossing_induced_wiggle_on_vertical_stroke():
    ordered = [
        {
            "component_id": 1,
            "points": [(float(y), 10.0) for y in range(2, 18)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]
    foreground_mask = np.zeros((22, 22), dtype=bool)
    foreground_mask[1:19, 9:12] = True
    foreground_mask[4:13, 4:6] = True
    foreground_mask[4:13, 14:16] = True
    foreground_mask[4:6, 4:16] = True
    foreground_mask[10:12, 4:16] = True

    consolidated, _ = consolidate_ordered_segments(
        ordered,
        simplify_tolerance_px=0.0,
        resample_step_px=None,
        foreground_mask=foreground_mask,
    )

    xs = [point[1] for point in consolidated[0]["points"]]
    assert max(xs) - min(xs) < 0.4
