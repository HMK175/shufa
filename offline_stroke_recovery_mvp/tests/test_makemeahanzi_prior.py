from pathlib import Path
import sys

import numpy as np
import pytest
from PIL import Image


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import _load_input_foreground_mask, load_callirewrite_segments
from makemeahanzi_prior import (
    MakeMeAHanziKnowledge,
    _apply_structure_endpoint_overshoots,
    _axis_transition_count,
    _closest_arc,
    _mean_polyline_distance,
    _resample_polyline_to_count,
    _sample_stroke_subpath,
    _stable_downward_suffix_index,
    build_prior_stroke_structure_candidate,
    build_kou_three_stroke_candidate,
    label_segments_by_makemeahanzi_components,
    normalize_medians_to_canvas,
    regularize_kou_structure_skeleton,
    regroup_ordered_segments_by_makemeahanzi,
    regroup_ordered_segments_by_prior_strokes,
    resolve_sample_char,
    smooth_polyline_leg_bounded,
    trim_overlapping_hengzhe_corner_members,
)
from ordering import order_segments
from preprocess import ensure_foreground_is_true
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
)


def _principal_axis_residual(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    centered = pts - pts.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    return float(np.mean(np.abs(centered @ vh[-1])))


def _connected_component_containing_point(foreground_mask: np.ndarray, point: tuple[float, float]) -> np.ndarray:
    mask = np.asarray(foreground_mask, dtype=bool)
    if mask.ndim != 2:
        return np.zeros((0, 2), dtype=float)
    height, width = mask.shape
    y = int(round(float(point[0])))
    x = int(round(float(point[1])))
    if not (0 <= y < height and 0 <= x < width) or not bool(mask[y, x]):
        return np.zeros((0, 2), dtype=float)

    stack = [(y, x)]
    seen = {(y, x)}
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


def _principal_axis_spans(points: np.ndarray) -> tuple[float, float]:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0, 0.0
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    major_projection = centered @ vh[0]
    minor_projection = centered @ vh[-1]
    return (
        float(major_projection.max() - major_projection.min()),
        float(minor_projection.max() - minor_projection.min()),
    )


def _axis_run_count(points: list[tuple[float, float]]) -> int:
    labels: list[str] = []
    for start, end in zip(points, points[1:]):
        delta_y = abs(float(end[0] - start[0]))
        delta_x = abs(float(end[1] - start[1]))
        if max(delta_y, delta_x) <= 1e-6:
            continue
        label = "horizontal" if delta_x >= delta_y else "vertical"
        if not labels or labels[-1] != label:
            labels.append(label)
    return len(labels)


def _axis_reversal_px(points: list[tuple[float, float]], axis: str) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    axis_index = 1 if axis == "horizontal" else 0
    deltas = np.diff(pts[:, axis_index])
    return float(np.maximum(-deltas, 0.0).sum())


def test_axis_transition_count_ignores_alternating_sub_tolerance_jitter():
    points = [
        (0.0, 0.0),
        (1e-8, 0.0),
        (0.0, 1e-8),
        (1e-8, 0.0),
        (0.0, 2.0),
        (2.0, 2.0),
    ]

    assert _axis_transition_count(points) == 1


def test_axis_transition_count_rejects_nonfinite_path():
    with pytest.raises(ValueError):
        _axis_transition_count([(0.0, 0.0), (np.nan, 1.0)])


def _load_real_kou_light_repair_labelled_segments():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = (
        repo_root
        / "offline_stroke_recovery_mvp"
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted"
        / "kou"
    )
    input_path = (
        repo_root
        / "offline_stroke_recovery_mvp"
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs"
        / "kou.png"
    )
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    repaired_raw, _ = light_repair_raw_segments(
        raw_segments,
        foreground_mask=foreground_mask,
    )
    ordered_segments = order_segments(
        repaired_raw,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    repaired_geometry, _ = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )
    labelled, _ = label_segments_by_makemeahanzi_components(
        repaired_geometry,
        sample_name="kou",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
    )
    return labelled, foreground_mask, graphics_path


def _synthetic_three_stroke_kou_structure():
    return [
        {
            "component_id": 1,
            "primitive_kind": "shu",
            "primitive_relative_widths": (0.9, 1.0, 1.1, 1.0),
            "points": [(2.0, 2.0), (4.1, 2.2), (6.0, 1.9), (8.0, 2.0)],
        },
        {
            "component_id": 2,
            "primitive_kind": "hengzhe",
            "primitive_relative_widths": (0.8, 1.0, 1.1, 1.0, 0.9),
            "structure_corner_index": 1,
            "points": [(2.0, 4.0), (2.0, 8.0), (4.1, 8.2), (6.0, 7.9), (8.0, 8.0)],
        },
        {
            "component_id": 3,
            "primitive_kind": "heng",
            "primitive_relative_widths": (1.0, 1.1, 0.9, 1.0),
            "points": [(10.0, 4.0), (10.2, 6.0), (9.8, 8.0), (10.0, 10.0)],
        },
    ]


def _assert_fallback_points_are_independent_copies(
    fallback: list[dict[str, object]],
    original: list[dict[str, object]],
) -> None:
    assert len(fallback) == len(original)
    for returned, source in zip(fallback, original):
        assert returned is not source
        assert returned["points"] is not source["points"]
        assert np.array_equal(
            np.asarray(returned["points"], dtype=float),
            np.asarray(source["points"], dtype=float),
            equal_nan=True,
        )


def test_resolve_sample_char_uses_known_aliases():
    assert resolve_sample_char("yong") == "永"
    assert resolve_sample_char("中") == "中"
    assert resolve_sample_char("demo", sample_char_map={"demo": "山"}) == "山"


def test_regroup_ordered_segments_by_prior_strokes_merges_supported_forward_segments_and_skips_contained_tail():
    ordered = [
        {"component_id": 1, "points": [(2.0, 2.0), (2.0, 6.0)], "source_segment_ids": (1,)},
        {"component_id": 1, "points": [(2.0, 6.0), (8.0, 6.0)], "source_segment_ids": (2,)},
        {"component_id": 1, "points": [(6.0, 6.0), (7.0, 6.0)], "source_segment_ids": (3,)},
    ]
    prior_strokes = [np.asarray([(2.0, 2.0), (2.0, 6.0), (8.0, 6.0)], dtype=float)]
    foreground_mask = np.zeros((12, 12), dtype=bool)
    foreground_mask[1:4, 2:7] = True
    foreground_mask[2:9, 5:8] = True

    regrouped, meta = regroup_ordered_segments_by_prior_strokes(
        ordered,
        prior_strokes,
        foreground_mask=foreground_mask,
    )

    assert len(regrouped) == 1
    assert regrouped[0]["source_segment_ids"] == (1, 2)
    assert meta["grouped_segment_count"] == 1
    assert meta["merged_group_count"] == 1
    assert meta["skipped_contained_segment_count"] == 1


def test_regroup_ordered_segments_by_prior_strokes_keeps_split_when_bridge_is_unsupported():
    ordered = [
        {"component_id": 1, "points": [(2.0, 2.0), (2.0, 4.0)], "source_segment_ids": (1,)},
        {"component_id": 1, "points": [(2.0, 8.0), (2.0, 10.0)], "source_segment_ids": (2,)},
    ]
    prior_strokes = [np.asarray([(2.0, 2.0), (2.0, 10.0)], dtype=float)]
    foreground_mask = np.zeros((12, 12), dtype=bool)
    foreground_mask[1:4, 2:5] = True
    foreground_mask[1:4, 8:11] = True

    regrouped, meta = regroup_ordered_segments_by_prior_strokes(
        ordered,
        prior_strokes,
        foreground_mask=foreground_mask,
    )

    assert len(regrouped) == 2
    assert meta["grouped_segment_count"] == 2
    assert meta["merged_group_count"] == 0


def test_regroup_ordered_segments_by_prior_strokes_regularizes_single_supported_wobbly_segment():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, 2.0), (2.8, 4.0), (1.3, 6.0), (2.7, 8.0)],
            "source_segment_ids": (1,),
        }
    ]
    prior_strokes = [np.asarray([(2.0, 2.0), (2.0, 8.0)], dtype=float)]
    foreground_mask = np.zeros((12, 12), dtype=bool)
    foreground_mask[1:4, 2:9] = True

    regrouped, meta = regroup_ordered_segments_by_prior_strokes(
        ordered,
        prior_strokes,
        foreground_mask=foreground_mask,
    )

    ys = [point[0] for point in regrouped[0]["points"]]
    assert max(ys) - min(ys) < 0.75
    assert meta["geometry_regularized_segment_count"] == 1


def test_label_segments_by_makemeahanzi_components_splits_real_kou_local_candidate_into_three_groups():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "kou"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "kou.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    labelled, meta = label_segments_by_makemeahanzi_components(
        local_consolidated,
        sample_name="kou",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
    )

    assert meta["makemeahanzi_component_label_group_count"] == 3
    assert len(labelled) >= 3
    assert sorted({int(segment["component_id"]) for segment in labelled}) == [1, 2, 3]


def test_trim_overlapping_hengzhe_corner_members_removes_horizontal_return_before_downstroke():
    horizontal = np.asarray([(10.0, 10.0), (9.5, 18.0), (9.0, 26.0)], dtype=float)
    vertical_with_overlap = np.asarray(
        [(11.0, 18.0), (10.5, 22.0), (10.0, 26.0), (12.0, 26.0),
         (15.0, 25.5), (18.0, 25.0), (21.0, 24.5), (24.0, 24.0)],
        dtype=float,
    )
    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical_with_overlap, max_bridge_gap_px=10.0, stable_run_points=4
    )
    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical_with_overlap[2:])
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical_with_overlap
    assert not np.shares_memory(kept_horizontal, horizontal)
    assert not np.shares_memory(kept_vertical, vertical_with_overlap)
    assert np.allclose(kept_vertical[0], (10.0, 26.0))
    assert meta["trim_applied"] is True
    assert meta["trimmed_point_count"] == 2
    assert meta["bridge_gap_px"] == 1.0


def test_trim_overlapping_hengzhe_corner_members_rejects_excessive_bridge_gap():
    horizontal = np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float)
    vertical = np.asarray([(1.0, 30.0), (4.0, 30.0), (7.0, 29.5), (10.0, 29.0)], dtype=float)
    kept_horizontal, unchanged_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, max_bridge_gap_px=10.0, stable_run_points=4
    )
    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(unchanged_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert unchanged_vertical is not vertical
    assert not np.shares_memory(kept_horizontal, horizontal)
    assert not np.shares_memory(unchanged_vertical, vertical)
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "trimmed_bridge_gap_exceeds_limit"


def test_stable_downward_suffix_index_rejects_upward_reversal_above_bound():
    points = np.asarray([(0.0, 0.0), (3.0, 0.0), (2.0, 0.0), (6.0, 0.0)], dtype=float)

    assert _stable_downward_suffix_index(
        points,
        stable_run_points=4,
        max_upward_reversal_px=0.5,
    ) is None


def test_stable_downward_suffix_index_rejects_zero_net_lateral_oscillation():
    points = np.asarray([(0.0, 0.0), (3.0, 1.0), (6.0, -1.0), (9.0, 0.0)], dtype=float)

    assert _stable_downward_suffix_index(
        points,
        stable_run_points=4,
        max_lateral_reversal_px=0.5,
    ) is None


@pytest.mark.parametrize(
    ("points", "kwargs"),
    [
        (np.asarray([0.0, 1.0, 2.0, 3.0], dtype=float), {}),
        (np.asarray([(0.0, 0.0), (3.0, 0.0), (np.nan, 0.0), (9.0, 0.0)], dtype=float), {}),
        (
            np.asarray([(0.0, 0.0), (3.0, 0.0), (6.0, 0.0), (9.0, 0.0)], dtype=float),
            {"max_upward_reversal_px": np.nan},
        ),
        (
            np.asarray([(0.0, 0.0), (3.0, 0.0), (6.0, 0.0), (9.0, 0.0)], dtype=float),
            {"max_lateral_reversal_px": np.inf},
        ),
        (
            np.asarray([(0.0, 0.0), (3.0, 0.0), (6.0, 0.0), (9.0, 0.0)], dtype=float),
            {"stable_run_points": np.nan},
        ),
    ],
)
def test_stable_downward_suffix_index_returns_none_for_invalid_geometry_or_bounds(
    points: np.ndarray,
    kwargs: dict[str, float],
):
    parameters = {"stable_run_points": 4, **kwargs}
    assert _stable_downward_suffix_index(points, **parameters) is None


def test_trim_overlapping_hengzhe_corner_members_reports_missing_stable_suffix():
    horizontal = np.asarray([(0.0, 0.0), (0.0, 4.0)], dtype=float)
    vertical = np.asarray([(0.0, 4.0), (0.0, 5.0), (0.0, 6.0), (0.0, 7.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, stable_run_points=4
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "stable_downward_suffix_not_found"
    assert meta["trimmed_point_count"] == 0


@pytest.mark.parametrize("bad_value", [np.nan, np.inf])
def test_trim_overlapping_hengzhe_corner_members_rejects_nonfinite_coordinates(bad_value: float):
    horizontal = np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float)
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)
    vertical[1, 0] = bad_value

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, stable_run_points=4
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical, equal_nan=True)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_members"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


@pytest.mark.parametrize(
    "invalid_horizontal",
    [
        [[0.0, 0.0], [1.0]],
        [["left", "top"], ["right", "bottom"]],
    ],
)
def test_trim_overlapping_hengzhe_corner_members_rejects_unconvertible_members_without_exception(
    invalid_horizontal: list[list[object]],
):
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        invalid_horizontal, vertical, stable_run_points=4
    )

    assert kept_horizontal.dtype == object
    assert kept_horizontal.tolist() == invalid_horizontal
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not invalid_horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_members"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


def test_trim_overlapping_hengzhe_corner_members_prioritizes_invalid_members_over_invalid_bridge_limit():
    invalid_horizontal = [["left", "top"], ["right", "bottom"]]
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        invalid_horizontal,
        vertical,
        max_bridge_gap_px=np.nan,
        stable_run_points=4,
    )

    assert kept_horizontal.dtype == object
    assert kept_horizontal.tolist() == invalid_horizontal
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not invalid_horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_members"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


@pytest.mark.parametrize("max_bridge_gap_px", [np.nan, -1.0])
def test_trim_overlapping_hengzhe_corner_members_rejects_invalid_bridge_limit(max_bridge_gap_px: float):
    horizontal = np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float)
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal,
        vertical,
        max_bridge_gap_px=max_bridge_gap_px,
        stable_run_points=4,
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_parameters"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


def test_trim_overlapping_hengzhe_corner_members_accepts_already_stable_member_without_trim():
    horizontal = np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float)
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, max_bridge_gap_px=10.0, stable_run_points=4
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "stable_downward_suffix"
    assert meta["trimmed_point_count"] == 0


def test_trim_overlapping_hengzhe_corner_members_rejects_empty_horizontal_as_invalid_members():
    horizontal = np.zeros((0, 2), dtype=float)
    vertical = np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float)

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, stable_run_points=4
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_members"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


@pytest.mark.parametrize(
    ("horizontal", "vertical"),
    [
        (
            np.asarray([0.0, 10.0], dtype=float),
            np.asarray([(1.0, 10.0), (4.0, 10.0), (7.0, 9.5), (10.0, 9.0)], dtype=float),
        ),
        (
            np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float),
            np.asarray([1.0, 10.0, 4.0, 10.0], dtype=float),
        ),
    ],
)
def test_trim_overlapping_hengzhe_corner_members_rejects_one_dimensional_members(
    horizontal: np.ndarray,
    vertical: np.ndarray,
):
    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal, vertical, stable_run_points=4
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.array_equal(kept_vertical, vertical)
    assert kept_horizontal is not horizontal
    assert kept_vertical is not vertical
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "invalid_members"
    assert meta["trimmed_point_count"] == 0
    assert np.isinf(meta["bridge_gap_px"])


def test_build_prior_structure_aggregates_multiple_hengzhe_trim_results_and_preserves_corner():
    first_horizontal = np.asarray(
        [(10.0, 10.0), (9.5, 18.0), (9.0, 26.0)],
        dtype=float,
    )
    first_vertical = np.asarray(
        [
            (11.0, 18.0),
            (10.5, 22.0),
            (10.0, 26.0),
            (12.0, 26.0),
            (15.0, 25.5),
            (18.0, 25.0),
            (21.0, 24.5),
            (24.0, 24.0),
        ],
        dtype=float,
    )
    second_horizontal = np.asarray(
        [(40.0, 10.0), (40.0, 15.0), (40.0, 20.0)],
        dtype=float,
    )
    second_vertical = np.asarray(
        [(40.0, 20.0), (43.0, 20.0), (46.0, 19.8), (49.0, 19.6), (52.0, 19.4), (55.0, 19.2)],
        dtype=float,
    )
    labelled = [
        {"component_id": 1, "points": first_horizontal, "source_segment_ids": (1,)},
        {"component_id": 1, "points": first_vertical, "source_segment_ids": (2,)},
        {"component_id": 2, "points": second_horizontal, "source_segment_ids": (3,)},
        {"component_id": 2, "points": second_vertical, "source_segment_ids": (4,)},
    ]
    priors = [
        np.asarray([(10.0, 10.0), (9.0, 26.0), (24.0, 24.0)], dtype=float),
        np.asarray([(40.0, 10.0), (40.0, 20.0), (55.0, 19.2)], dtype=float),
    ]

    structured, meta = build_prior_stroke_structure_candidate(
        labelled,
        priors,
        primitive_kinds=("hengzhe", "hengzhe"),
        trim_hengzhe_overlap=True,
    )

    assert len(structured) == 2
    assert meta["hengzhe_overlap_trim_applied"] is True
    assert meta["hengzhe_overlap_trimmed_point_count"] == 2
    assert meta["hengzhe_overlap_trim_reason"] == "one_or_more_trimmed"
    details = meta["hengzhe_overlap_trim_details"]
    assert isinstance(details, tuple)
    assert details[0][:4] == (1, True, "stable_downward_suffix", 2)
    assert details[1][:4] == (2, False, "stable_downward_suffix", 0)

    corner_index = int(structured[0]["structure_corner_index"])
    assert corner_index == len(first_horizontal) - 1
    assert len(structured[0]["points"]) > corner_index + 1
    extended, overshoot_count = _apply_structure_endpoint_overshoots(
        structured,
        endpoint_overshoots={1: {"start": 2.0}},
    )
    assert overshoot_count == 1
    assert int(extended[0]["structure_corner_index"]) == corner_index + 1


def _second_difference_energy(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return 0.0
    second = pts[:-2] - 2.0 * pts[1:-1] + pts[2:]
    return float(np.square(second).sum())


def test_smooth_polyline_leg_bounded_preserves_fixed_endpoints_and_reduces_stair_steps():
    points = np.asarray([(0.0, 0.0), (0.8, 2.0), (0.1, 4.0), (0.9, 6.0), (0.0, 8.0)], dtype=float)
    resampled = _resample_polyline_to_count(points, len(points))
    smoothed = smooth_polyline_leg_bounded(
        points, fixed_indices=(0, len(points) - 1), smoothing_strength=4.0
    )
    assert np.array_equal(smoothed[0], points[0])
    assert np.array_equal(smoothed[-1], points[-1])
    assert _second_difference_energy(smoothed) < _second_difference_energy(resampled)


def test_smooth_polyline_leg_bounded_preserves_explicit_corner_anchor():
    points = np.asarray([(0.0, 0.0), (0.2, 2.0), (0.0, 4.0), (2.0, 4.2), (4.0, 4.0)], dtype=float)
    resampled = _resample_polyline_to_count(points, len(points))
    smoothed = smooth_polyline_leg_bounded(
        points, fixed_indices=(0, 2, 4), smoothing_strength=4.0
    )
    assert np.array_equal(smoothed[0], points[0])
    assert np.array_equal(smoothed[2], points[2])
    assert np.array_equal(smoothed[4], points[4])
    assert not np.allclose(smoothed[[1, 3]], resampled[[1, 3]])


def test_smooth_polyline_leg_bounded_normalizes_valid_and_ignores_malformed_fixed_indices():
    points = np.asarray(
        [(0.0, 0.0), (0.8, 2.0), (0.1, 4.0), (0.9, 6.0), (0.0, 8.0)],
        dtype=float,
    )
    smoothed = smooth_polyline_leg_bounded(
        points,
        fixed_indices=(
            0,
            -1,
            np.int64(2),
            2,
            2.0,
            99,
            -99,
            True,
            False,
            None,
            np.nan,
            np.inf,
            "1",
            3.5,
            object(),
        ),
        smoothing_strength=4.0,
    )
    assert np.array_equal(smoothed[0], points[0])
    assert np.array_equal(smoothed[2], points[2])
    assert np.array_equal(smoothed[-1], points[-1])
    assert not np.array_equal(smoothed[1], points[1])
    assert not np.array_equal(smoothed[3], points[3])


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_smooth_polyline_leg_bounded_rejects_nonfinite_points(bad_value: float):
    points = np.asarray([(0.0, 0.0), (0.8, 2.0), (0.1, 4.0)], dtype=float)
    points[1, 0] = bad_value

    with pytest.raises(ValueError):
        smooth_polyline_leg_bounded(points, fixed_indices=(0, -1), smoothing_strength=4.0)


@pytest.mark.parametrize(
    "points",
    [
        np.asarray([0.0, 1.0, 2.0], dtype=float),
        np.zeros((3, 3), dtype=float),
        [[0.0, 0.0], ["bad", 1.0], [2.0, 2.0]],
    ],
)
def test_smooth_polyline_leg_bounded_rejects_non_numeric_or_non_nx2_points(points: object):
    with pytest.raises(ValueError):
        smooth_polyline_leg_bounded(points, fixed_indices=(0, -1), smoothing_strength=4.0)


@pytest.mark.parametrize("smoothing_strength", [np.nan, np.inf, -np.inf, None, "bad"])
def test_smooth_polyline_leg_bounded_rejects_nonfinite_or_unconvertible_strength(
    smoothing_strength: object,
):
    points = np.asarray([(0.0, 0.0), (0.8, 2.0), (0.1, 4.0)], dtype=float)

    with pytest.raises(ValueError):
        smooth_polyline_leg_bounded(
            points,
            fixed_indices=(0, -1),
            smoothing_strength=smoothing_strength,
        )


@pytest.mark.parametrize("smoothing_strength", [0.0, -1.0])
def test_smooth_polyline_leg_bounded_nonpositive_strength_returns_independent_copy(
    smoothing_strength: float,
):
    points = np.asarray([(0.0, 0.0), (0.8, 2.0), (0.1, 4.0)], dtype=float)

    unchanged = smooth_polyline_leg_bounded(
        points,
        fixed_indices=(0, -1),
        smoothing_strength=smoothing_strength,
    )

    assert np.array_equal(unchanged, points)
    assert unchanged is not points
    assert not np.shares_memory(unchanged, points)


@pytest.mark.parametrize(
    "points",
    [
        np.asarray([(1.0, 2.0), (1.0, 2.0), (1.0, 2.0), (1.0, 2.0)], dtype=float),
        np.asarray([(0.0, 0.0), (0.0, 0.0), (1.0, 2.0), (1.0, 2.0)], dtype=float),
    ],
)
def test_smooth_polyline_leg_bounded_handles_repeated_and_zero_length_segments(points: np.ndarray):
    smoothed = smooth_polyline_leg_bounded(
        points,
        fixed_indices=(0, -1),
        smoothing_strength=4.0,
    )

    assert smoothed.shape == points.shape
    assert np.isfinite(smoothed).all()
    assert np.array_equal(smoothed[0], points[0])
    assert np.array_equal(smoothed[-1], points[-1])
    assert smoothed is not points
    assert not np.shares_memory(smoothed, points)


def test_regularize_kou_structure_skeleton_preserves_primitives_widths_and_anchors():
    structured = _synthetic_three_stroke_kou_structure()
    original_points = [np.asarray(segment["points"], dtype=float) for segment in structured]
    original_kinds = [segment["primitive_kind"] for segment in structured]
    original_widths = [segment["primitive_relative_widths"] for segment in structured]

    regularized, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is True
    assert [segment["primitive_kind"] for segment in regularized] == original_kinds
    assert [segment["primitive_relative_widths"] for segment in regularized] == original_widths
    for index in (0, 2):
        points = np.asarray(regularized[index]["points"], dtype=float)
        assert np.array_equal(points[0], original_points[index][0])
        assert np.array_equal(points[-1], original_points[index][-1])
    hengzhe_points = np.asarray(regularized[1]["points"], dtype=float)
    corner_index = int(regularized[1]["structure_corner_index"])
    assert corner_index == 1
    assert np.array_equal(hengzhe_points[0], original_points[1][0])
    assert np.array_equal(hengzhe_points[corner_index], original_points[1][corner_index])
    assert np.array_equal(hengzhe_points[-1], original_points[1][-1])


def test_regularize_kou_structure_skeleton_rejects_unsupported_geometry_without_mutation():
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.zeros((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "foreground_support_too_low"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_unexpected_primitive_roles():
    structured = _synthetic_three_stroke_kou_structure()
    structured[0]["primitive_kind"] = "heng"

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "unexpected_primitive_roles"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_unexpected_component_order():
    structured = _synthetic_three_stroke_kou_structure()
    structured[1]["component_id"] = 3
    structured[2]["component_id"] = 2

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "unexpected_component_order"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_horizontal_backward_reversal():
    structured = _synthetic_three_stroke_kou_structure()
    structured[1]["structure_corner_index"] = 2
    structured[1]["points"] = [
        (2.0, 4.0),
        (2.0, 8.0),
        (2.0, 6.0),
        (5.0, 6.0),
        (8.0, 6.0),
    ]

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "horizontal_reversal_exceeded"
    assert meta["kou_hengzhe_horizontal_reversal_px"] == pytest.approx(2.0)
    assert meta["kou_hengzhe_vertical_reversal_px"] == pytest.approx(0.0)
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_vertical_upward_reversal():
    structured = _synthetic_three_stroke_kou_structure()
    structured[1]["points"] = [
        (2.0, 4.0),
        (2.0, 8.0),
        (6.0, 8.0),
        (4.0, 8.0),
        (8.0, 8.0),
    ]

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "vertical_reversal_exceeded"
    assert meta["kou_hengzhe_horizontal_reversal_px"] == pytest.approx(0.0)
    assert meta["kou_hengzhe_vertical_reversal_px"] == pytest.approx(2.0)
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_excessive_displacement():
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
        max_displacement_px=0.01,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "max_displacement_exceeded"
    assert meta["kou_skeleton_max_displacement_px"] > 0.01
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_unexpected_axis_transitions():
    structured = _synthetic_three_stroke_kou_structure()
    structured[1]["points"] = [
        (2.0, 4.0),
        (2.0, 8.0),
        (5.0, 8.0),
        (6.0, 12.0),
        (9.0, 12.0),
    ]

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
        smoothing_strength=0.0,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "unexpected_axis_transition_count"
    assert meta["kou_hengzhe_axis_transition_count"] == 3
    _assert_fallback_points_are_independent_copies(unchanged, structured)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_support_ratio": -0.1},
        {"min_support_ratio": 1.1},
        {"min_support_ratio": np.nan},
        {"min_support_ratio": np.inf},
        {"support_radius_px": -1},
        {"support_radius_px": 1.5},
        {"support_radius_px": np.nan},
        {"support_radius_px": np.inf},
        {"max_displacement_px": -0.1},
        {"max_displacement_px": np.nan},
        {"max_displacement_px": np.inf},
    ],
)
def test_regularize_kou_structure_skeleton_rejects_invalid_parameters(kwargs: dict[str, float]):
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
        **kwargs,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "invalid_parameters"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


@pytest.mark.parametrize(
    "foreground_mask",
    [
        np.ones((4,), dtype=bool),
        np.asarray([[np.nan]], dtype=float),
        np.asarray([["not-a-mask"]], dtype=object),
    ],
)
def test_regularize_kou_structure_skeleton_rejects_invalid_foreground_mask(
    foreground_mask: np.ndarray,
):
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=foreground_mask,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "invalid_parameters"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_empty_mask_fails_support_safely():
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.zeros((0, 0), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "foreground_support_too_low"
    assert meta["kou_skeleton_foreground_support_ratio"] == pytest.approx(0.0)
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_catches_smoother_value_error():
    structured = _synthetic_three_stroke_kou_structure()

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
        smoothing_strength=np.nan,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "smoothing_failed"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_regularize_kou_structure_skeleton_rejects_nonfinite_source_points():
    structured = _synthetic_three_stroke_kou_structure()
    structured[0]["points"][1] = (np.nan, 2.0)

    unchanged, meta = regularize_kou_structure_skeleton(
        structured,
        foreground_mask=np.ones((16, 16), dtype=bool),
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "invalid_structure"
    _assert_fallback_points_are_independent_copies(unchanged, structured)


def test_apply_structure_endpoint_overshoots_adjusts_hengzhe_corner_index_without_mutating_input():
    structured = _synthetic_three_stroke_kou_structure()

    extended, overshoot_count = _apply_structure_endpoint_overshoots(
        structured,
        endpoint_overshoots={2: {"start": 2.0}},
    )

    assert overshoot_count == 1
    assert int(structured[1]["structure_corner_index"]) == 1
    assert int(extended[1]["structure_corner_index"]) == 2
    assert len(extended[1]["points"]) == len(structured[1]["points"]) + 1
    assert extended[1] is not structured[1]


def test_build_kou_three_stroke_candidate_joins_hengzhe_and_preserves_intersection_overshoots():
    labelled, foreground_mask, graphics_path = _load_real_kou_light_repair_labelled_segments()

    structured, meta = build_kou_three_stroke_candidate(
        labelled,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
        foreground_mask=foreground_mask,
    )

    assert meta["structure_prior_applied"] is True
    assert len(structured) == 3
    assert [segment["primitive_kind"] for segment in structured] == ["shu", "hengzhe", "heng"]
    assert [int(segment["component_id"]) for segment in structured] == [1, 2, 3]
    assert meta["kou_skeleton_regularization_applied"] is True
    assert meta["kou_hengzhe_overlap_trimmed_point_count"] == 16
    assert meta["structure_overshoot_count"] == 3
    assert _axis_run_count(structured[1]["points"]) == 2
    assert float(structured[1]["points"][0][1]) < float(structured[0]["points"][0][1])
    assert float(structured[0]["points"][-1][0]) > float(structured[2]["points"][0][0])
    assert float(structured[2]["points"][-1][1]) > float(structured[1]["points"][-1][1])


def test_build_kou_three_stroke_candidate_trims_real_hengzhe_loop_and_regularizes_skeleton():
    labelled, foreground_mask, graphics_path = _load_real_kou_light_repair_labelled_segments()

    structured, meta = build_kou_three_stroke_candidate(
        labelled,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
        foreground_mask=foreground_mask,
    )

    hengzhe = structured[1]
    corner_index = int(hengzhe["structure_corner_index"])
    top_leg = hengzhe["points"][:corner_index + 1]
    right_leg = hengzhe["points"][corner_index:]
    assert meta["kou_skeleton_regularization_applied"] is True
    assert meta["kou_hengzhe_overlap_trimmed_point_count"] == 16
    assert meta["kou_hengzhe_axis_transition_count"] == 1
    assert meta["kou_hengzhe_horizontal_reversal_px"] <= 0.5
    assert meta["kou_hengzhe_vertical_reversal_px"] <= 0.5
    assert _axis_reversal_px(top_leg, axis="horizontal") <= 0.5
    assert _axis_reversal_px(right_leg, axis="vertical") <= 0.5
    assert meta["kou_skeleton_max_displacement_px"] <= 2.5
    assert meta["kou_skeleton_foreground_support_ratio"] >= 0.90


def test_label_segments_by_makemeahanzi_components_can_preserve_yong_local_geometry_while_assigning_labels():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "yong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "yong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    image = Image.open(input_path).convert("L")
    foreground_mask = ensure_foreground_is_true(np.asarray(image, dtype=np.uint8) < 200)
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    labelled, meta = label_segments_by_makemeahanzi_components(
        local_consolidated,
        sample_name="yong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
        split_geometry=False,
    )

    assert len(labelled) == len(local_consolidated)
    assert [tuple(segment.get("source_segment_ids", ())) for segment in labelled] == [
        tuple(segment.get("source_segment_ids", ())) for segment in local_consolidated
    ]
    assert meta["makemeahanzi_component_label_group_count"] >= 4
    assigned_component_ids = {int(segment["component_id"]) for segment in labelled}
    assert min(assigned_component_ids) >= 1
    assert len(assigned_component_ids) >= 4


def test_regroup_ordered_segments_by_makemeahanzi_merges_yong_left_heng_pie_real_sample():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "yong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "yong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="yong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    grouped_source_ids = [tuple(segment.get("source_segment_ids", ())) for segment in regrouped]
    component_by_source = {
        tuple(segment.get("source_segment_ids", ())): int(segment.get("component_id", 0) or 0)
        for segment in regrouped
    }
    assert any(tuple(ids) == (8, 6) or set(ids) == {8, 6} for ids in grouped_source_ids)
    assert any(component_by_source.get(tuple(ids), 0) == 3 for ids in grouped_source_ids if set(ids) == {8, 6})
    assert meta["makemeahanzi_prior_applied"] is True


def test_regroup_ordered_segments_by_makemeahanzi_keeps_zhong_vertical_lead_in_split_from_main_stem():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "zhong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "zhong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    grouped_source_ids = [tuple(segment.get("source_segment_ids", ())) for segment in regrouped]
    assert (10,) in grouped_source_ids
    assert any(2 in ids and 13 in ids for ids in grouped_source_ids)
    assert not any(10 in ids and 2 in ids for ids in grouped_source_ids)
    assert meta["makemeahanzi_prior_applied"] is True


def test_regroup_ordered_segments_by_makemeahanzi_reduces_zhong_top_right_foldback():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "zhong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "zhong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    prior_strokes = normalize_medians_to_canvas(
        MakeMeAHanziKnowledge(graphics_path).get_glyph(resolve_sample_char("zhong")).medians,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
    )
    target = next(
        segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == (7, 8, 4)
    )
    points = np.asarray(target.get("points", ()), dtype=float)
    prior = np.asarray(prior_strokes[int(target.get("component_id", 0)) - 1], dtype=float)
    start_arc = _closest_arc(points[0], prior)[1]
    end_arc = _closest_arc(points[-1], prior)[1]
    if end_arc <= start_arc:
        arcs = [_closest_arc(point, prior)[1] for point in points]
        start_arc = min(arcs)
        end_arc = max(arcs)
    prior_subpath = _sample_stroke_subpath(prior, start_arc, end_arc, step_px=1.0)
    points = _resample_polyline_to_count(points, len(prior_subpath))

    assert _mean_polyline_distance(points, prior_subpath) < 1.7
    assert meta["makemeahanzi_geometry_regularized_segment_count"] >= 1


def test_regroup_ordered_segments_by_makemeahanzi_regularizes_merged_zhong_left_shoulder_segment():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "zhong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "zhong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    prior_strokes = normalize_medians_to_canvas(
        MakeMeAHanziKnowledge(graphics_path).get_glyph(resolve_sample_char("zhong")).medians,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
    )
    target = next(
        segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == (6, 16)
    )
    points = np.asarray(target.get("points", ()), dtype=float)
    prior = np.asarray(prior_strokes[int(target.get("component_id", 0)) - 1], dtype=float)
    arcs = [_closest_arc(point, prior)[1] for point in points]
    prior_subpath = _sample_stroke_subpath(prior, min(arcs), max(arcs), step_px=1.0)
    points = _resample_polyline_to_count(points, len(prior_subpath))

    assert _mean_polyline_distance(points, prior_subpath) < 3.2
    assert meta["makemeahanzi_geometry_regularized_segment_count"] >= 2


def test_regroup_ordered_segments_by_makemeahanzi_regularizes_zhong_top_lead_in_fragment():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "zhong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "zhong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="zhong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    prior_strokes = normalize_medians_to_canvas(
        MakeMeAHanziKnowledge(graphics_path).get_glyph(resolve_sample_char("zhong")).medians,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
    )
    target = next(
        segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == (10,)
    )
    points = np.asarray(target.get("points", ()), dtype=float)
    prior = np.asarray(prior_strokes[int(target.get("component_id", 0)) - 1], dtype=float)
    arcs = [_closest_arc(point, prior)[1] for point in points]
    prior_subpath = _sample_stroke_subpath(prior, min(arcs), max(arcs), step_px=1.0)
    points = _resample_polyline_to_count(points, len(prior_subpath))

    assert _mean_polyline_distance(points, prior_subpath) < 2.5
    assert meta["makemeahanzi_geometry_regularized_segment_count"] >= 3


def test_regroup_ordered_segments_by_makemeahanzi_extends_xin_short_dot_across_more_of_local_blob():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "xin"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "xin.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="xin",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    target = next(
        segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == (17,)
    )
    points = np.asarray(target.get("points", ()), dtype=float)
    blob = _connected_component_containing_point(foreground_mask, tuple(points[len(points) // 2]))
    blob_major_span, _ = _principal_axis_spans(blob)
    segment_major_span, _ = _principal_axis_spans(points)

    assert blob_major_span > 0.0
    assert segment_major_span / blob_major_span >= 0.4
    assert meta["makemeahanzi_prior_applied"] is True


def test_regroup_ordered_segments_by_makemeahanzi_keeps_yong_horizontal_lead_in_split_from_main_stem():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "yong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "yong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    image = Image.open(input_path).convert("L")
    foreground_mask = ensure_foreground_is_true(np.asarray(image, dtype=np.uint8) < 200)

    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="yong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    grouped_source_ids = [tuple(segment.get("source_segment_ids", ())) for segment in regrouped]
    assert (10,) in grouped_source_ids
    assert any(2 in ids for ids in grouped_source_ids)
    assert not any(10 in ids and 2 in ids for ids in grouped_source_ids)
    assert meta["makemeahanzi_prior_applied"] is True


def test_regroup_ordered_segments_by_makemeahanzi_assigns_prior_stroke_component_ids_on_yong_real_sample():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "yong"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "yong.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    image = Image.open(input_path).convert("L")
    foreground_mask = ensure_foreground_is_true(np.asarray(image, dtype=np.uint8) < 200)

    regrouped, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="yong",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )

    grouped_source_ids = [tuple(segment.get("source_segment_ids", ())) for segment in regrouped]
    grouped_component_ids = [int(segment.get("component_id", -1)) for segment in regrouped]
    assert len(set(grouped_component_ids)) > 1
    component_by_source = dict(zip(grouped_source_ids, grouped_component_ids))
    merged_key = next(ids for ids in grouped_source_ids if set(ids) == {8, 6})
    assert component_by_source[merged_key] == 3
