from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import (
    DEFAULT_DIRECTION_COS_THRESHOLD,
    DEFAULT_MERGE_GAP_PX,
    DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    DEFAULT_RESAMPLE_STEP_PX,
    DEFAULT_SIMPLIFY_TOLERANCE_PX,
    _build_component_mix_candidate_segments,
    _prepare_local_candidate_segments,
    _build_visual_crop_bbox,
    _crop_mask,
    _load_input_foreground_mask,
    _restore_render_subpaths_from_source_segments,
    _translate_segments,
    load_callirewrite_segments,
)
from makemeahanzi_prior import regroup_ordered_segments_by_makemeahanzi
from ordering import order_segments
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
)
from visualize import (
    PALETTE,
    _adjust_endpoint_caps_for_short_attached_segment,
    _build_endpoint_cap_policies,
    _build_variable_width_profile,
    _clamp_attached_endpoint_width_peaks_px,
    _coalesce_aligned_render_subpaths_for_variable_width,
    _estimate_point_brush_diameters_px,
    _flatten_grouped_render_subpath_source_ids,
    _draw_polyline,
    _repair_short_internal_width_dropouts_px,
    _regularize_straight_segment_body_diameters_px,
    _robust_segment_diameter_px,
    _sample_polyline_points,
    _history_overlap_trim_count,
    _shared_subpath_profile_overlap_trim_count,
    _should_fallback_to_segment_constant_render_for_short_volatile_segment,
    _stabilize_point_brush_diameters_px,
    _suppress_short_attached_segment_body_diameters_px,
    _boost_short_incomplete_dot_diameters_px,
    _short_incomplete_dot_endpoint_extensions_px,
    _taper_corner_terminal_branch_diameters_px,
    _taper_long_foldback_tail_diameters_px,
    _taper_endpoint_width_spikes_px,
    _taper_anchored_endpoint_diameters_px,
    render_execution_image,
    write_trajectory_png,
    write_trajectory_playback_contact_sheet,
)


def _dark_pixel_count(image) -> int:
    pixels = np.asarray(image.convert("L"), dtype=np.uint8)
    return int(np.count_nonzero(pixels < 200))


def test_draw_polyline_preserves_shallow_subpixel_centerline():
    scale = 8
    color = PALETTE[0]
    points = [(5.1 + 0.15 * index, 2.0 + index) for index in range(21)]
    canvas = Image.new("RGB", (200, 100), (255, 255, 255))

    _draw_polyline(ImageDraw.Draw(canvas), points, scale, color)

    pixels = np.asarray(canvas, dtype=np.uint8)
    colored = np.all(pixels == np.asarray(color, dtype=np.uint8), axis=2)
    colored_columns = np.flatnonzero(np.any(colored, axis=0))
    center_y_by_column = np.asarray(
        [np.flatnonzero(colored[:, x]).mean() for x in colored_columns],
        dtype=float,
    )
    first_x = points[0][1] * scale + scale / 2.0
    first_y = points[0][0] * scale + scale / 2.0
    ideal_center_y = first_y + 0.15 * (colored_columns - first_x)

    assert float(np.max(np.abs(center_y_by_column - ideal_center_y))) <= 1.5


def test_write_trajectory_png_preserves_fractional_pen_up_connector_height(tmp_path: Path):
    scale = 8
    endpoint_y = 5.49
    output_path = tmp_path / "fractional_connector.png"
    segments = [
        {"points": [(endpoint_y, 1.0), (endpoint_y, 3.0)]},
        {"points": [(endpoint_y, 12.0), (endpoint_y, 14.0)]},
    ]

    write_trajectory_png(
        output_path,
        np.zeros((16, 20), dtype=bool),
        segments,
        scale=scale,
    )

    pixels = np.asarray(Image.open(output_path).convert("RGB"), dtype=np.uint8)
    gap_pixels = pixels[:, 40:92]
    gray_connector = np.all(
        gap_pixels == np.asarray((160, 160, 160), dtype=np.uint8),
        axis=2,
    )
    gray_rows = np.flatnonzero(np.any(gray_connector, axis=1))
    expected_y = endpoint_y * scale + scale / 2.0

    assert gray_rows.size > 0
    assert abs(float(gray_rows.mean()) - expected_y) <= 1.0
    assert 44 not in gray_rows


def test_write_trajectory_playback_contact_sheet_draws_thin_centerline_steps(tmp_path: Path):
    skeleton = np.zeros((32, 32), dtype=bool)
    segments = [
        {"component_id": 1, "points": [(4.0, 4.0), (24.0, 6.0)]},
        {"component_id": 2, "points": [(6.0, 8.0), (6.0, 24.0), (24.0, 22.0)]},
        {"component_id": 3, "points": [(24.0, 7.0), (23.0, 25.0)]},
    ]
    output_path = tmp_path / "skeleton_playback.png"
    panel_size = (120, 120)
    padding = 10
    header_height = 18

    write_trajectory_playback_contact_sheet(
        output_path,
        skeleton,
        segments,
        scale=3,
        panel_size=panel_size,
        padding=padding,
        header_height=header_height,
    )

    assert output_path.exists()
    image = Image.open(output_path).convert("RGB")
    pixels = np.asarray(image, dtype=np.uint8)
    assert image.width > 0 and image.height > 0

    panel_top = padding + header_height
    step_color_counts = []
    for step in range(len(segments)):
        panel_left = padding + step * (panel_size[0] + padding)
        panel_roi = pixels[
            panel_top + 1 : panel_top + panel_size[1] - 1,
            panel_left + 1 : panel_left + panel_size[0] - 1,
        ]
        step_color_counts.append(
            [
                int(
                    np.count_nonzero(
                        np.all(panel_roi == np.asarray(color, dtype=np.uint8), axis=2)
                    )
                )
                for color in PALETTE[: len(segments)]
            ]
        )

    assert [count > 0 for count in step_color_counts[0]] == [True, False, False]
    assert [count > 0 for count in step_color_counts[1]] == [True, True, False]
    assert [count > 0 for count in step_color_counts[2]] == [True, True, True]
    colored_pixel_counts = [sum(counts) for counts in step_color_counts]
    assert colored_pixel_counts[0] < colored_pixel_counts[1] < colored_pixel_counts[2]


def test_write_trajectory_playback_contact_sheet_handles_empty_segments_and_layout_boundaries(tmp_path: Path):
    output_path = tmp_path / "empty_skeleton_playback.png"

    write_trajectory_playback_contact_sheet(
        output_path,
        np.zeros((1, 1), dtype=bool),
        [],
        scale=0,
        panel_size=(0, 0),
        padding=-1,
        header_height=-1,
        max_columns=0,
    )

    image = Image.open(output_path)
    assert image.width >= 1
    assert image.height >= 1


def test_build_variable_width_profile_applies_serialized_primitive_relative_widths():
    foreground_mask = np.zeros((32, 96), dtype=bool)
    foreground_mask[11:22, 8:88] = True
    points = [(16.0, 10.0), (16.0, 86.0)]

    baseline = _build_variable_width_profile(
        points,
        foreground_mask,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(1,),
    )
    transferred = _build_variable_width_profile(
        points,
        foreground_mask,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(1,),
        primitive_relative_widths=(0.7, 1.0, 1.1),
        primitive_width_blend=1.0,
    )

    assert baseline is not None
    assert transferred is not None
    baseline_widths = np.asarray(baseline[1], dtype=float)
    transferred_widths = np.asarray(transferred[1], dtype=float)
    assert np.isclose(np.median(transferred_widths), np.median(baseline_widths), rtol=0.08)
    assert transferred_widths[0] < transferred_widths[len(transferred_widths) // 2]
    assert transferred_widths[-1] > transferred_widths[len(transferred_widths) // 2]


def test_taper_long_foldback_tail_diameters_sharpens_multi_source_hook_tail():
    points = _sample_polyline_points(
        [(0.0, 0.0), (0.0, 80.0), (8.0, 82.0), (2.0, 78.0)],
        step_px=1.0,
    )
    diameters = [8.0 for _ in points]

    tapered = _taper_long_foldback_tail_diameters_px(
        points,
        diameters,
        source_segment_ids=(3, 2, 10),
        cap_start=True,
        cap_end=False,
    )

    assert tapered[0] == 8.0
    assert tapered[len(tapered) // 2] == 8.0
    assert tapered[-1] <= 8.0 * 0.45
    assert tapered[-1] < tapered[-6] < tapered[-12]


def test_boost_short_incomplete_dot_diameters_only_affects_very_short_single_source_dots():
    short_points = _sample_polyline_points([(0.0, 0.0), (0.0, 9.5)], step_px=1.0)
    short_diameters = [2.5 for _ in short_points]
    boosted = _boost_short_incomplete_dot_diameters_px(
        short_points,
        short_diameters,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(17,),
    )

    long_points = _sample_polyline_points([(0.0, 0.0), (0.0, 12.5)], step_px=1.0)
    long_diameters = [2.5 for _ in long_points]
    unchanged = _boost_short_incomplete_dot_diameters_px(
        long_points,
        long_diameters,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(17,),
    )

    assert boosted[0] > short_diameters[0]
    assert boosted[len(boosted) // 2] > short_diameters[len(short_diameters) // 2]
    assert boosted[-1] > short_diameters[-1]
    assert unchanged == long_diameters


def test_short_incomplete_dot_endpoint_extensions_only_apply_to_very_short_single_source_dots():
    short_points = _sample_polyline_points([(0.0, 0.0), (0.0, 9.5)], step_px=1.0)
    short_extension = _short_incomplete_dot_endpoint_extensions_px(
        short_points,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(17,),
    )

    long_points = _sample_polyline_points([(0.0, 0.0), (0.0, 12.5)], step_px=1.0)
    long_extension = _short_incomplete_dot_endpoint_extensions_px(
        long_points,
        cap_start=True,
        cap_end=True,
        source_segment_ids=(17,),
    )

    assert short_extension[0] > 0.0
    assert short_extension[1] > 0.0
    assert long_extension == (0.0, 0.0)


def _load_real_sample_translated_mmh_consolidated_segments(
    sample: str,
    *,
    foreground_snap_blend: float | None = None,
) -> tuple[list[dict[str, object]], np.ndarray]:
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / sample
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / f"{sample}.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name=sample,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )
    consolidation_kwargs: dict[str, object] = {}
    if foreground_snap_blend is not None:
        consolidation_kwargs["foreground_snap_blend"] = float(foreground_snap_blend)
    consolidated_segments, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        merge_gap_px=DEFAULT_MERGE_GAP_PX,
        direction_cos_threshold=DEFAULT_DIRECTION_COS_THRESHOLD,
        simplify_tolerance_px=DEFAULT_SIMPLIFY_TOLERANCE_PX,
        resample_step_px=DEFAULT_RESAMPLE_STEP_PX,
        foreground_mask=foreground_mask,
        **consolidation_kwargs,
    )
    consolidated_segments = _restore_render_subpaths_from_source_segments(
        consolidated_segments,
        source_segments=ordered_segments,
    )
    visual_crop_bbox, _, _, _ = _build_visual_crop_bbox(raw_segments, input_path, margin_px=6)
    return _translate_segments(consolidated_segments, visual_crop_bbox), _crop_mask(foreground_mask, visual_crop_bbox)


def _load_real_sample_translated_prepared_local_segments(sample: str) -> tuple[list[dict[str, object]], np.ndarray]:
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / sample
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / f"{sample}.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    consolidated_segments, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=DEFAULT_MERGE_GAP_PX,
        direction_cos_threshold=DEFAULT_DIRECTION_COS_THRESHOLD,
        simplify_tolerance_px=DEFAULT_SIMPLIFY_TOLERANCE_PX,
        resample_step_px=DEFAULT_RESAMPLE_STEP_PX,
        foreground_mask=foreground_mask,
    )
    prepared_segments, _ = _prepare_local_candidate_segments(
        consolidated_segments,
        sample_name=sample,
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )
    visual_crop_bbox, _, _, _ = _build_visual_crop_bbox(raw_segments, input_path, margin_px=6)
    return _translate_segments(prepared_segments, visual_crop_bbox), _crop_mask(foreground_mask, visual_crop_bbox)


def _load_real_sample_translated_light_repair_segments(sample: str) -> tuple[list[dict[str, object]], np.ndarray]:
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / sample
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / f"{sample}.png"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    repaired_raw_segments, _ = light_repair_raw_segments(
        raw_segments,
        foreground_mask=foreground_mask,
    )
    ordered_segments = order_segments(
        repaired_raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    repaired_segments, _ = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )
    repaired_segments = _restore_render_subpaths_from_source_segments(
        repaired_segments,
        source_segments=ordered_segments,
    )
    visual_crop_bbox, _, _, _ = _build_visual_crop_bbox(raw_segments, input_path, margin_px=6)
    return _translate_segments(repaired_segments, visual_crop_bbox), _crop_mask(foreground_mask, visual_crop_bbox)


def _load_real_xin_component_mix_segments() -> tuple[list[dict[str, object]], np.ndarray]:
    local_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("xin")
    prior_segments, _ = _load_real_sample_translated_mmh_consolidated_segments(
        "xin",
        foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    )
    detail_segments, _ = _load_real_sample_translated_light_repair_segments("xin")
    mixed_segments, meta = _build_component_mix_candidate_segments(
        local_segments,
        prior_segments,
        detail_source_segments=detail_segments,
    )
    assert meta["component_mix_applied"] is True
    return mixed_segments, foreground_mask


def _select_segment_index_by_source_ids(segments: list[dict[str, object]], source_ids: tuple[int, ...]) -> int:
    for index, segment in enumerate(segments):
        if tuple(segment.get("source_segment_ids", ())) == source_ids:
            return index
    raise AssertionError(f"Missing segment with source ids {source_ids}")


def _coefficient_of_variation(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(arr.std() / max(arr.mean(), 1e-6))


def test_render_execution_image_uses_foreground_width_when_available():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(4.0, 12.0), (19.0, 12.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    foreground_mask = np.zeros((24, 24), dtype=bool)
    foreground_mask[4:20, 10:15] = True

    thin = render_execution_image(
        skeleton,
        [segment],
        scale=4,
    )
    thick = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
    )

    assert _dark_pixel_count(thick) > _dark_pixel_count(thin) * 2


def test_render_execution_image_fixed_mode_ignores_foreground_width():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(4.0, 12.0), (19.0, 12.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    foreground_mask = np.zeros((24, 24), dtype=bool)
    foreground_mask[4:20, 8:17] = True

    fixed_without_mask = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        render_mode="fixed",
    )
    fixed_with_mask = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
        render_mode="fixed",
    )

    assert np.array_equal(
        np.asarray(fixed_without_mask.convert("L"), dtype=np.uint8),
        np.asarray(fixed_with_mask.convert("L"), dtype=np.uint8),
    )


def test_render_execution_image_softens_edges_when_requested():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(4.0, 12.0), (19.0, 12.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    foreground_mask = np.zeros((24, 24), dtype=bool)
    foreground_mask[4:20, 10:15] = True

    softened = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=1.0,
    )

    pixels = np.asarray(softened.convert("L"), dtype=np.uint8)
    assert np.any((pixels > 24) & (pixels < 255))


def test_render_execution_image_ignores_endpoint_width_spikes_when_estimating_segment_width():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(12.0, 2.0), (12.0, 21.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    base_mask = np.zeros((24, 24), dtype=bool)
    base_mask[11:14, 2:22] = True
    corner_heavy_mask = np.asarray(base_mask, dtype=bool).copy()
    corner_heavy_mask[8:17, 2:4] = True
    corner_heavy_mask[8:17, 20:22] = True

    baseline = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=base_mask,
    )
    corner_heavy = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=corner_heavy_mask,
    )

    assert _dark_pixel_count(corner_heavy) < _dark_pixel_count(baseline) * 1.75


def test_render_execution_image_preserves_tapered_width_profile_within_one_segment():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(12.0, 2.0), (12.0, 21.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    foreground_mask = np.zeros((24, 24), dtype=bool)
    foreground_mask[11:14, 2:7] = True
    foreground_mask[9:16, 7:17] = True
    foreground_mask[11:14, 17:22] = True

    rendered = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )

    pixels = np.asarray(rendered.convert("L"), dtype=np.uint8) < 200
    left_dark = int(np.count_nonzero(pixels[:, 8:28]))
    middle_dark = int(np.count_nonzero(pixels[:, 38:58]))
    right_dark = int(np.count_nonzero(pixels[:, 68:88]))

    assert middle_dark > left_dark * 1.4
    assert middle_dark > right_dark * 1.4


def test_render_execution_image_segment_constant_mode_reduces_width_wobble():
    skeleton = np.zeros((24, 24), dtype=bool)
    segment = {
        "points": [(12.0, 2.0), (12.0, 21.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
    }
    foreground_mask = np.zeros((24, 24), dtype=bool)
    foreground_mask[11:14, 2:7] = True
    foreground_mask[9:16, 7:17] = True
    foreground_mask[11:14, 17:22] = True

    variable = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )
    conservative = render_execution_image(
        skeleton,
        [segment],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
        render_mode="segment_constant",
    )

    variable_mask = np.asarray(variable.convert("L"), dtype=np.uint8) < 200
    conservative_mask = np.asarray(conservative.convert("L"), dtype=np.uint8) < 200

    variable_left = int(np.count_nonzero(variable_mask[:, 8:28]))
    variable_middle = int(np.count_nonzero(variable_mask[:, 38:58]))
    variable_right = int(np.count_nonzero(variable_mask[:, 68:88]))
    conservative_left = int(np.count_nonzero(conservative_mask[:, 8:28]))
    conservative_middle = int(np.count_nonzero(conservative_mask[:, 38:58]))
    conservative_right = int(np.count_nonzero(conservative_mask[:, 68:88]))

    assert variable_middle > variable_left * 1.4
    assert variable_middle > variable_right * 1.4
    assert conservative_middle <= conservative_left * 1.15
    assert conservative_middle <= conservative_right * 1.15


def test_render_execution_image_uses_render_subpaths_to_preserve_branch_vs_body_width():
    skeleton = np.zeros((32, 32), dtype=bool)
    segment_without_subpaths = {
        "points": [(8.0, 8.0), (16.0, 8.0), (18.0, 8.0), (16.0, 8.0), (16.0, 16.0)],
        "component_id": 1,
        "source_segment_ids": (17, 4),
    }
    segment_with_subpaths = {
        **segment_without_subpaths,
        "render_subpaths": [
            [(8.0, 8.0), (16.0, 8.0), (18.0, 8.0)],
            [(16.0, 8.0), (16.0, 16.0)],
        ],
        "render_subpath_source_ids": [(17,), (4,)],
    }
    foreground_mask = np.zeros((32, 32), dtype=bool)
    foreground_mask[7:10, 8:19] = True
    foreground_mask[8:17, 13:20] = True

    rendered_without_subpaths = render_execution_image(
        skeleton,
        [segment_without_subpaths],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )
    rendered_with_subpaths = render_execution_image(
        skeleton,
        [segment_with_subpaths],
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )

    without_subpaths_mask = np.asarray(rendered_without_subpaths.convert("L"), dtype=np.uint8) < 200
    with_subpaths_mask = np.asarray(rendered_with_subpaths.convert("L"), dtype=np.uint8) < 200
    without_subpaths_dark = int(np.count_nonzero(without_subpaths_mask))
    with_subpaths_dark = int(np.count_nonzero(with_subpaths_mask))

    assert with_subpaths_dark < without_subpaths_dark * 0.8


def test_coalesce_aligned_render_subpaths_for_variable_width_merges_near_colinear_split():
    subpaths = [
        [(8.0, 12.0), (16.0, 12.0), (24.0, 12.0)],
        [(24.0, 12.2), (32.0, 12.1), (40.0, 12.0)],
    ]
    source_id_groups = [(1,), (2,)]

    merged_subpaths, merged_source_id_groups = _coalesce_aligned_render_subpaths_for_variable_width(
        subpaths,
        source_id_groups,
    )

    assert len(merged_subpaths) == 1
    assert merged_source_id_groups == [((1,), (2,))]
    assert len(merged_subpaths[0]) >= 5


def test_coalesce_aligned_render_subpaths_for_variable_width_keeps_right_angle_split():
    subpaths = [
        [(8.0, 12.0), (16.0, 12.0), (24.0, 12.0)],
        [(24.0, 12.0), (24.0, 20.0), (24.0, 28.0)],
    ]
    source_id_groups = [(17,), (4,)]

    merged_subpaths, merged_source_id_groups = _coalesce_aligned_render_subpaths_for_variable_width(
        subpaths,
        source_id_groups,
    )

    assert merged_subpaths == subpaths
    assert merged_source_id_groups == [((17,),), ((4,),)]


def test_coalesce_aligned_render_subpaths_for_variable_width_merges_real_shi_main_vertical_split():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "shi"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "shi.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_raw_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_raw_segments,
        sample_name="shi",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )
    consolidated_segments, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        merge_gap_px=DEFAULT_MERGE_GAP_PX,
        direction_cos_threshold=DEFAULT_DIRECTION_COS_THRESHOLD,
        simplify_tolerance_px=DEFAULT_SIMPLIFY_TOLERANCE_PX,
        resample_step_px=DEFAULT_RESAMPLE_STEP_PX,
        foreground_mask=foreground_mask,
    )
    problem_segment = _restore_render_subpaths_from_source_segments(
        consolidated_segments,
        source_segments=ordered_raw_segments,
    )[_select_segment_index_by_source_ids(consolidated_segments, (10, 2, 7))]
    render_subpaths = [
        [tuple(point) for point in subpath]
        for subpath in problem_segment.get("render_subpaths", ())
    ]
    render_subpath_source_ids = [
        tuple(group)
        for group in problem_segment.get("render_subpath_source_ids", ())
    ]

    merged_subpaths, merged_source_id_groups = _coalesce_aligned_render_subpaths_for_variable_width(
        render_subpaths,
        render_subpath_source_ids,
    )

    assert len(render_subpaths) == 3
    assert len(merged_subpaths) == 2
    assert merged_source_id_groups == [((10,),), ((2,), (7,))]


def test_shared_subpath_profile_overlap_trim_count_detects_real_zhong_internal_corner_overlap():
    ordered_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("zhong")
    problem_segment = ordered_segments[_select_segment_index_by_source_ids(ordered_segments, (6, 5, 4))]
    render_subpaths = [
        [tuple(point) for point in subpath]
        for subpath in problem_segment.get("render_subpaths", ())
    ]
    render_subpath_source_ids = [
        tuple(group)
        for group in problem_segment.get("render_subpath_source_ids", ())
    ]

    render_subpaths, grouped_source_id_groups = _coalesce_aligned_render_subpaths_for_variable_width(
        render_subpaths,
        render_subpath_source_ids,
    )
    profiles = []
    for subpath, grouped_source_ids in zip(render_subpaths, grouped_source_id_groups):
        profile = _build_variable_width_profile(
            subpath,
            np.asarray(foreground_mask, dtype=bool),
            cap_start=False,
            cap_end=False,
            source_segment_ids=_flatten_grouped_render_subpath_source_ids(grouped_source_ids),
        )
        assert profile is not None
        profiles.append(profile)

    assert _shared_subpath_profile_overlap_trim_count(profiles[0][0], profiles[1][0]) == 2
    assert _shared_subpath_profile_overlap_trim_count(profiles[1][0], profiles[2][0]) == 2


def test_history_overlap_trim_count_detects_non_adjacent_retrace_window():
    history_points = [
        [(8.0, 8.0), (8.0, 16.0), (8.0, 24.0), (8.0, 32.0)],
        [(0.0, 0.0), (0.0, 4.0)],
        [(20.0, 20.0), (22.0, 21.0)],
    ]
    current_points = [(8.0, 16.0), (8.0, 24.0), (8.0, 32.0), (8.0, 40.0)]

    assert _history_overlap_trim_count(history_points, current_points) == 4


def test_should_fallback_to_segment_constant_render_for_short_volatile_segment_accepts_short_attached_wobble():
    points = [(70.0, 29.0), (65.0, 32.0), (60.0, 35.0), (55.0, 39.0)]
    diameters = [4.8, 7.1, 2.0, 7.8, 1.8, 6.9]

    assert _should_fallback_to_segment_constant_render_for_short_volatile_segment(
        points,
        diameters,
        cap_start=False,
        cap_end=False,
        source_segment_ids=(4,),
    )


def test_should_fallback_to_segment_constant_render_for_short_volatile_segment_rejects_tiny_or_capped_segments():
    assert not _should_fallback_to_segment_constant_render_for_short_volatile_segment(
        [(0.0, 0.0), (4.0, 0.0), (8.0, 0.0)],
        [5.0, 7.5, 6.5, 7.0],
        cap_start=True,
        cap_end=True,
        source_segment_ids=(8,),
    )
    assert not _should_fallback_to_segment_constant_render_for_short_volatile_segment(
        [(0.0, 0.0), (20.0, 0.0), (40.0, 0.0)],
        [5.0, 7.5, 6.5, 7.0, 6.8, 7.2],
        cap_start=False,
        cap_end=False,
        source_segment_ids=(2, 13),
    )


def test_should_not_fallback_to_segment_constant_render_after_real_xin_left_short_stroke_merge():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "xin")
    foreground_mask = _load_input_foreground_mask(input_dir / "xin.png")
    assert foreground_mask is not None
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=DEFAULT_ORDERING_DIRECTION_COS_THRESHOLD,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=DEFAULT_MERGE_GAP_PX,
        direction_cos_threshold=DEFAULT_DIRECTION_COS_THRESHOLD,
        simplify_tolerance_px=DEFAULT_SIMPLIFY_TOLERANCE_PX,
        resample_step_px=DEFAULT_RESAMPLE_STEP_PX,
        foreground_mask=foreground_mask,
        foreground_snap_blend=0.35,
    )
    prepared_segments, _ = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="xin",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )
    visual_crop_bbox, _, _, _ = _build_visual_crop_bbox(segments, input_dir / "xin.png", margin_px=6)
    ordered_segments = _translate_segments(prepared_segments, visual_crop_bbox)
    foreground_mask = _crop_mask(foreground_mask, visual_crop_bbox)
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (17, 4))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))

    assert not _should_fallback_to_segment_constant_render_for_short_volatile_segment(
        sampled_points,
        diameters,
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(17, 4),
    )


def test_render_execution_image_avoids_large_corner_blob_for_touching_segments():
    skeleton = np.zeros((32, 32), dtype=bool)
    ordered_segments = [
        {
            "points": [(8.0, 6.0), (24.0, 6.0)],
            "component_id": 1,
            "source_segment_ids": (1,),
        },
        {
            "points": [(24.0, 6.0), (24.0, 22.0)],
            "component_id": 2,
            "source_segment_ids": (2,),
        },
    ]
    foreground_mask = np.zeros((32, 32), dtype=bool)
    foreground_mask[7:10, 6:23] = True
    foreground_mask[23:26, 5:23] = True

    rendered = render_execution_image(
        skeleton,
        ordered_segments,
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )

    rendered_mask = np.asarray(rendered.convert("L"), dtype=np.uint8) < 200
    corner_dark = int(np.count_nonzero(rendered_mask[88:108, 16:36]))

    assert corner_dark <= 180


def test_build_endpoint_cap_policies_treats_small_offset_contacts_as_anchored():
    ordered_segments = [
        {
            "points": [(8.0, 6.0), (24.0, 6.0)],
            "component_id": 1,
            "source_segment_ids": (1,),
        },
        {
            "points": [(24.0, 8.0), (24.0, 22.0)],
            "component_id": 2,
            "source_segment_ids": (2,),
        },
    ]

    policies = _build_endpoint_cap_policies(ordered_segments)

    assert policies[0]["cap_end"] is False
    assert policies[1]["cap_start"] is False


def test_build_endpoint_cap_policies_assigns_tangential_extension_for_anchored_frame_corners():
    ordered_segments = [
        {
            "points": [(4.0, 4.0), (4.0, 12.0)],
            "component_id": 1,
            "source_segment_ids": (1,),
        },
        {
            "points": [(4.0, 4.0), (12.0, 4.0)],
            "component_id": 2,
            "source_segment_ids": (2,),
        },
        {
            "points": [(12.0, 4.0), (12.0, 12.0)],
            "component_id": 3,
            "source_segment_ids": (3,),
        },
        {
            "points": [(4.0, 12.0), (12.0, 12.0)],
            "component_id": 4,
            "source_segment_ids": (4,),
        },
    ]

    policies = _build_endpoint_cap_policies(ordered_segments)

    assert policies[0]["cap_start"] is False
    assert policies[1]["cap_start"] is False
    assert policies[0]["extend_start_px"] > 0.0
    assert policies[1]["extend_start_px"] > 0.0


def test_build_endpoint_cap_policies_marks_real_zhong_frame_loop_endpoints_as_anchored():
    ordered_segments, _ = _load_real_sample_translated_mmh_consolidated_segments("zhong")

    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (7, 8, 4))

    assert policies[problem_index]["cap_start"] is False
    assert policies[problem_index]["cap_end"] is False


def test_build_endpoint_cap_policies_keeps_real_yong_right_falling_stroke_start_anchored_without_trim():
    ordered_segments, _ = _load_real_sample_translated_mmh_consolidated_segments("yong")

    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (4,))

    assert policies[problem_index]["cap_start"] is False
    assert policies[problem_index]["cap_end"] is True
    assert policies[problem_index]["trim_start_points"] == 0
    assert policies[problem_index]["trim_end_points"] == 0


def test_build_endpoint_cap_policies_trims_real_zhong_local_short_right_corner_bridge_start():
    ordered_segments, _ = _load_real_sample_translated_prepared_local_segments("zhong")

    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (8,))

    assert policies[problem_index]["trim_start_points"] == 1
    assert policies[problem_index]["extend_start_px"] == 0.0


def test_build_endpoint_cap_policies_suppresses_real_xin_nearby_free_end_caps():
    ordered_segments, _ = _load_real_sample_translated_prepared_local_segments("xin")

    policies = _build_endpoint_cap_policies(ordered_segments)
    left_dot_index = _select_segment_index_by_source_ids(ordered_segments, (17, 4))
    wogou_index = _select_segment_index_by_source_ids(ordered_segments, (10, 2, 3))

    assert policies[left_dot_index]["cap_end"] is False
    assert policies[wogou_index]["cap_end"] is False


def test_repair_short_internal_width_dropouts_lifts_short_valley_between_thick_runs():
    repaired = _repair_short_internal_width_dropouts_px(
        [8.0, 8.0, 7.8, 2.0, 2.2, 7.9, 8.1, 8.0],
    )

    assert repaired[3] >= 6.0
    assert repaired[4] >= 6.0
    assert repaired[0] == 8.0
    assert repaired[-1] == 8.0


def test_clamp_attached_endpoint_width_peaks_tames_start_spike_without_flattening_tail():
    clamped = _clamp_attached_endpoint_width_peaks_px(
        [12.0, 11.0, 9.5, 8.0, 8.0, 8.0, 7.8],
        cap_start=False,
        cap_end=True,
    )

    assert clamped[0] < 11.0
    assert clamped[1] < 10.5
    assert clamped[-1] == 7.8


def test_render_execution_image_tapers_width_spike_at_anchored_endpoint():
    skeleton = np.zeros((34, 34), dtype=bool)
    ordered_segments = [
        {
            "points": [(16.0, 4.0), (16.0, 24.0)],
            "component_id": 1,
            "source_segment_ids": (1,),
        },
        {
            "points": [(16.0, 24.0), (26.0, 24.0)],
            "component_id": 2,
            "source_segment_ids": (2,),
        },
    ]
    foreground_mask = np.zeros((34, 34), dtype=bool)
    foreground_mask[15:18, 4:23] = True
    foreground_mask[15:18, 24:30] = True
    foreground_mask[12:21, 22:27] = True

    rendered = render_execution_image(
        skeleton,
        ordered_segments,
        scale=4,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    )

    rendered_mask = np.asarray(rendered.convert("L"), dtype=np.uint8) < 200
    joint_dark = int(np.count_nonzero(rendered_mask[44:84, 80:112]))

    assert joint_dark <= 420


def test_taper_anchored_endpoint_diameters_shrinks_anchored_tip_below_body_width():
    diameters = [8.0] * 9

    tapered = _taper_anchored_endpoint_diameters_px(
        diameters,
        cap_start=True,
        cap_end=False,
    )

    assert tapered[-1] < 7.0
    assert tapered[0] == 8.0
    assert tapered[3] >= tapered[-1]


def test_taper_endpoint_width_spikes_shrinks_capped_endpoint_spike_without_flattening_body():
    diameters = [5.0, 5.2, 5.1, 5.0, 5.0, 6.2, 7.4, 8.8]

    tapered = _taper_endpoint_width_spikes_px(
        diameters,
        cap_start=False,
        cap_end=True,
    )

    assert tapered[-1] < 7.5
    assert tapered[-2] < diameters[-2]
    assert tapered[0] == diameters[0]
    assert tapered[3] == diameters[3]


def test_adjust_endpoint_caps_for_short_attached_segment_suppresses_free_cap_on_tiny_lead_in():
    points = [(6.0, 10.0), (8.0, 10.2), (9.7, 10.4)]
    diameters = [9.0, 9.5, 9.0]

    cap_start, cap_end = _adjust_endpoint_caps_for_short_attached_segment(
        points,
        diameters,
        cap_start=True,
        cap_end=False,
    )

    assert cap_start is False
    assert cap_end is False


def test_suppress_short_attached_segment_body_diameters_shrinks_real_zhong_top_stub():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
    original_reference = _robust_segment_diameter_px(diameters)

    suppressed = _suppress_short_attached_segment_body_diameters_px(
        points,
        diameters,
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
    )

    assert len(suppressed) == len(diameters)
    assert _robust_segment_diameter_px(suppressed) <= original_reference * 0.7


def test_build_variable_width_profile_softens_real_zhong_local_short_top_branch():
    ordered_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    raw_diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
    raw_reference = _robust_segment_diameter_px(raw_diameters)

    from visualize import _build_variable_width_profile

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(10,),
    )

    assert profile is not None
    _, softened_diameters, effective_cap_start, effective_cap_end = profile
    assert effective_cap_start is True
    assert effective_cap_end is True
    assert _robust_segment_diameter_px(softened_diameters) <= raw_reference * 0.55


def test_build_variable_width_profile_tapers_real_zhong_local_short_top_branch_tip():
    ordered_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    from visualize import _build_variable_width_profile

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(10,),
    )

    assert profile is not None
    _, softened_diameters, _, _ = profile
    body_reference = _robust_segment_diameter_px(softened_diameters[3:-3])
    endpoint_diameters = (float(softened_diameters[0]), float(softened_diameters[-1]))
    assert min(endpoint_diameters) <= body_reference * 0.75
    assert max(endpoint_diameters) >= body_reference * 0.85


def test_build_variable_width_profile_tames_real_zhong_light_repair_right_wall_tail_peak():
    ordered_segments, foreground_mask = _load_real_sample_translated_light_repair_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (4,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(4,),
    )

    assert profile is not None
    _, softened_diameters, _, _ = profile
    tail_mean = float(np.mean(np.asarray(softened_diameters[-4:], dtype=float)))
    tail_peak = float(np.max(np.asarray(softened_diameters[-6:], dtype=float)))
    robust_reference = _robust_segment_diameter_px(softened_diameters)

    assert tail_mean <= robust_reference * 1.05
    assert tail_peak <= robust_reference * 1.25


def test_build_variable_width_profile_keeps_real_zhong_light_repair_top_lead_in_slender():
    ordered_segments, foreground_mask = _load_real_sample_translated_light_repair_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(10,),
    )

    assert profile is not None
    _, softened_diameters, _, _ = profile
    robust_reference = _robust_segment_diameter_px(softened_diameters)

    assert robust_reference <= 5.5


def test_build_variable_width_profile_keeps_real_zhong_light_repair_top_lead_in_free_cap():
    ordered_segments, foreground_mask = _load_real_sample_translated_light_repair_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(10,),
    )

    assert profile is not None
    _, _, effective_cap_start, effective_cap_end = profile
    assert effective_cap_start is True
    assert effective_cap_end is False


def test_build_variable_width_profile_tapers_real_zhong_light_repair_top_lead_in_free_tip():
    ordered_segments, foreground_mask = _load_real_sample_translated_light_repair_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (10,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(10,),
    )

    assert profile is not None
    _, softened_diameters, _, _ = profile
    robust_reference = _robust_segment_diameter_px(softened_diameters)
    assert softened_diameters[0] <= robust_reference * 0.55
    assert softened_diameters[-1] >= robust_reference * 0.85


def test_build_variable_width_profile_softens_real_kou_light_repair_short_corner_bridge():
    ordered_segments, foreground_mask = _load_real_sample_translated_light_repair_segments("kou")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (8,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(8,),
    )

    assert profile is not None
    _, softened_diameters, _, _ = profile
    assert _robust_segment_diameter_px(softened_diameters) <= 6.0


def test_render_execution_image_fills_real_xin_makemeahanzi_hook_join_gap():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments(
        "xin",
        foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    )
    skeleton = np.zeros_like(foreground_mask, dtype=bool)

    image = render_execution_image(
        skeleton,
        ordered_segments,
        scale=6,
        foreground_mask=foreground_mask,
    ).convert("L")

    assert image.getpixel((424, 294)) < 80


def test_build_variable_width_profile_clamps_real_xin_component_mix_wogou_turn_peak():
    mixed_segments, foreground_mask = _load_real_xin_component_mix_segments()

    policies = _build_endpoint_cap_policies(mixed_segments)
    problem_index = _select_segment_index_by_source_ids(mixed_segments, (3, 2, 10))
    points = [tuple(point) for point in mixed_segments[problem_index].get("points", ())]
    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(3, 2, 10),
    )

    assert profile is not None
    sampled_points, softened_diameters, _, _ = profile
    turn_cosines = []
    for index in range(1, len(sampled_points) - 1):
        incoming = np.asarray(sampled_points[index], dtype=float) - np.asarray(sampled_points[index - 1], dtype=float)
        outgoing = np.asarray(sampled_points[index + 1], dtype=float) - np.asarray(sampled_points[index], dtype=float)
        cosine = float(
            np.dot(incoming, outgoing)
            / max(float(np.linalg.norm(incoming) * np.linalg.norm(outgoing)), 1e-9)
        )
        turn_cosines.append((cosine, index))
    turn_cosine, turn_index = min(turn_cosines)
    robust_reference = _robust_segment_diameter_px(softened_diameters[:-18])

    assert turn_cosine <= -0.5
    assert softened_diameters[turn_index] <= robust_reference * 1.08


def test_build_variable_width_profile_makes_real_xin_component_mix_wogou_terminal_zero_width():
    mixed_segments, foreground_mask = _load_real_xin_component_mix_segments()
    policies = _build_endpoint_cap_policies(mixed_segments)
    problem_index = _select_segment_index_by_source_ids(mixed_segments, (3, 2, 10))
    points = [tuple(point) for point in mixed_segments[problem_index].get("points", ())]

    profile = _build_variable_width_profile(
        points,
        np.asarray(foreground_mask, dtype=bool),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
        source_segment_ids=(3, 2, 10),
    )

    assert profile is not None
    _, diameters, _, _ = profile
    tail = np.asarray(diameters[-18:], dtype=float)
    assert diameters[-1] == 0.0
    assert np.all(np.diff(tail) <= 1e-9)


def test_render_execution_image_allows_explicit_pointed_end_to_converge_to_a_tip():
    skeleton = np.zeros((32, 32), dtype=bool)
    foreground_mask = np.zeros((32, 32), dtype=bool)
    foreground_mask[9:16, 3:28] = True
    segment = {
        "points": [(12.0, 4.0), (12.0, 24.0)],
        "component_id": 1,
        "source_segment_ids": (1,),
        "pointed_end": True,
    }

    image = render_execution_image(
        skeleton,
        [segment],
        scale=6,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=0.0,
    ).convert("L")

    pixels = np.asarray(image, dtype=np.uint8) < 200
    endpoint_x = int(round(24.0 * 6 + 3.0))
    body_x = int(round(20.0 * 6 + 3.0))
    assert int(np.count_nonzero(pixels[:, endpoint_x])) <= 2
    assert int(np.count_nonzero(pixels[:, body_x])) >= 6


def test_render_execution_image_keeps_real_zhong_right_corner_gap_unfilled():
    ordered_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("zhong")
    skeleton = np.zeros_like(foreground_mask, dtype=bool)

    image = render_execution_image(
        skeleton,
        ordered_segments,
        scale=6,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=1.0,
    ).convert("L")

    assert image.getpixel((410, 180)) > 200


def test_render_execution_image_keeps_real_zhong_left_bottom_corner_close_to_single_path_baseline():
    ordered_segments, foreground_mask = _load_real_sample_translated_prepared_local_segments("zhong")
    skeleton = np.zeros_like(foreground_mask, dtype=bool)

    with_subpaths = render_execution_image(
        skeleton,
        ordered_segments,
        scale=6,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=1.0,
    ).convert("L")
    single_path_segments = []
    for segment in ordered_segments:
        single_path_segments.append(
            {
                key: value
                for key, value in segment.items()
                if key not in {"render_subpaths", "render_subpath_source_ids"}
            }
        )
    without_subpaths = render_execution_image(
        skeleton,
        single_path_segments,
        scale=6,
        foreground_mask=foreground_mask,
        edge_soften_radius_px=1.0,
    ).convert("L")

    with_mask = np.asarray(with_subpaths, dtype=np.uint8) < 200
    without_mask = np.asarray(without_subpaths, dtype=np.uint8) < 200
    left_bottom_crop = np.s_[240:318, 60:102]
    with_dark = int(np.count_nonzero(with_mask[left_bottom_crop]))
    without_dark = int(np.count_nonzero(without_mask[left_bottom_crop]))

    assert with_dark <= without_dark * 1.03


def test_taper_corner_terminal_branch_diameters_shrinks_real_zhong_right_tail():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments("zhong")
    policies = _build_endpoint_cap_policies(ordered_segments)
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (7, 8, 4))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
    diameters = _taper_anchored_endpoint_diameters_px(
        diameters,
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
    )
    diameters = _taper_endpoint_width_spikes_px(
        diameters,
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
    )

    tapered = _taper_corner_terminal_branch_diameters_px(
        sampled_points,
        diameters,
        source_segment_ids=(7, 8, 4),
        cap_start=policies[problem_index]["cap_start"],
        cap_end=policies[problem_index]["cap_end"],
    )

    original_tail_mean = float(np.mean(diameters[-4:]))
    tapered_tail_mean = float(np.mean(tapered[-4:]))
    assert tapered_tail_mean <= original_tail_mean * 0.9


def test_regularize_straight_segment_body_diameters_stabilizes_real_zhong_bottom_horizontal_width():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments("zhong")
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (5,))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
    stabilized = _stabilize_point_brush_diameters_px(diameters)

    regularized = _regularize_straight_segment_body_diameters_px(
        sampled_points,
        stabilized,
        cap_start=False,
        cap_end=False,
        source_segment_ids=(5,),
    )

    assert len(regularized) == len(stabilized)
    assert _coefficient_of_variation(regularized) <= _coefficient_of_variation(stabilized) * 0.65
    assert abs(_robust_segment_diameter_px(regularized) - _robust_segment_diameter_px(stabilized)) <= 0.5


def test_regularize_straight_segment_body_diameters_stabilizes_real_zhong_main_vertical_width():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments("zhong")
    problem_index = _select_segment_index_by_source_ids(ordered_segments, (2, 13))
    points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
    sampled_points = _sample_polyline_points(points, step_px=1.0)
    diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
    stabilized = _stabilize_point_brush_diameters_px(diameters)

    regularized = _regularize_straight_segment_body_diameters_px(
        sampled_points,
        stabilized,
        cap_start=False,
        cap_end=False,
        source_segment_ids=(2, 13),
    )

    assert len(regularized) == len(stabilized)
    assert _coefficient_of_variation(regularized) <= _coefficient_of_variation(stabilized) * 0.75
    assert abs(_robust_segment_diameter_px(regularized) - _robust_segment_diameter_px(stabilized)) <= 0.5


def test_regularize_straight_segment_body_diameters_keeps_real_zhong_mouth_frame_natural_variation():
    ordered_segments, foreground_mask = _load_real_sample_translated_mmh_consolidated_segments("zhong")
    for source_ids in ((5,), (2, 13)):
        problem_index = _select_segment_index_by_source_ids(ordered_segments, source_ids)
        points = [tuple(point) for point in ordered_segments[problem_index].get("points", ())]
        sampled_points = _sample_polyline_points(points, step_px=1.0)
        diameters = _estimate_point_brush_diameters_px(sampled_points, np.asarray(foreground_mask, dtype=bool))
        stabilized = _stabilize_point_brush_diameters_px(diameters)

        regularized = _regularize_straight_segment_body_diameters_px(
            sampled_points,
            stabilized,
            cap_start=False,
            cap_end=False,
            source_segment_ids=source_ids,
        )

        assert _coefficient_of_variation(regularized) >= 0.09
