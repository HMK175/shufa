import os
import sys

import numpy as np


ROOT = os.path.dirname(os.path.dirname(__file__))
CODE_DIR = os.path.join(ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from skeleton import clean_junction_spurs, skeletonize, straighten_junctions
from stroke import (
    _extract_strokes_global,
    build_skeleton_graph,
    get_last_trace_diagnostics,
    get_stroke_list,
    prune_skeleton,
    set_trace_context,
)
from stroke_knowledge import get_stroke_count, guided_merge, _split_cross_component
from utils import estimate_stroke_width, load_image, preprocess


def _prepared_skeleton(name, subset="tune_set"):
    image_path = os.path.join(CODE_DIR, subset, f"{name}.png")
    image = load_image(image_path)
    binary = preprocess(image, blur_ksize=21)
    half_width = estimate_stroke_width(binary)
    skeleton = skeletonize(binary)
    skeleton = prune_skeleton(skeleton, min_branch_len=max(30, int(half_width * 1.8)))
    skeleton = straighten_junctions(skeleton)
    skeleton = clean_junction_spurs(skeleton)
    return skeleton


def _post_knowledge_strokes(name):
    set_trace_context(name)
    strokes = get_stroke_list(_prepared_skeleton(name))
    strokes = [np.array(stroke) for stroke in strokes]
    strokes = _split_cross_component(strokes, name)
    expected = get_stroke_count(name)
    if expected and len(strokes) != expected:
        strokes = guided_merge(strokes, name)
    return strokes


def _post_knowledge_strokes_from_subset(name, subset):
    set_trace_context(name)
    strokes = get_stroke_list(_prepared_skeleton(name, subset=subset))
    strokes = [np.array(stroke) for stroke in strokes]
    strokes = _split_cross_component(strokes, name)
    expected = get_stroke_count(name)
    if expected and len(strokes) != expected:
        strokes = guided_merge(strokes, name)
    return strokes


def _stroke_path_ratio(stroke):
    pts = np.array(stroke).astype(float)
    if len(pts) < 2:
        return 0.0
    path = np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))
    endpoint_distance = np.linalg.norm(pts[-1] - pts[0])
    return path / endpoint_distance if endpoint_distance > 1 else 999.0


def _glyph_bbox(name):
    points = np.array(list(build_skeleton_graph(_prepared_skeleton(name)).keys())).astype(float)
    return points.min(axis=0), points.max(axis=0)


def _right_side_frame_detours(name):
    strokes = _post_knowledge_strokes(name)
    (glyph_y0, glyph_x0), (glyph_y1, glyph_x1) = _glyph_bbox(name)
    glyph_h = glyph_y1 - glyph_y0
    glyph_w = glyph_x1 - glyph_x0
    detours = []
    for stroke in strokes:
        pts = np.array(stroke).astype(float)
        s_y0, s_x0 = pts.min(axis=0)
        s_y1, s_x1 = pts.max(axis=0)
        right_anchored = (s_x1 - glyph_x0) / glyph_w > 0.88
        starts_in_right_half = (s_x0 - glyph_x0) / glyph_w > 0.35
        touches_top = (s_y0 - glyph_y0) / glyph_h < 0.12
        tall = (s_y1 - s_y0) / glyph_h > 0.45
        wide = (s_x1 - s_x0) / glyph_w > 0.45
        ratio = _stroke_path_ratio(stroke)
        if right_anchored and starts_in_right_half and touches_top and tall and wide and ratio > 1.6:
            detours.append(
                {
                    "ratio": ratio,
                    "height_frac": (s_y1 - s_y0) / glyph_h,
                    "width_frac": (s_x1 - s_x0) / glyph_w,
                }
            )
    return detours


def test_global_yi_does_not_duplicate_covered_edges():
    skeleton = _prepared_skeleton("yi")
    graph = build_skeleton_graph(skeleton)

    strokes = _extract_strokes_global(skeleton, expected_count=1)
    stroke_pixels = sum(len(stroke) for stroke in strokes)

    assert len(strokes) <= 2
    assert stroke_pixels <= int(len(graph) * 1.25)


def test_global_kou_does_not_create_large_duplicate_paths():
    skeleton = _prepared_skeleton("kou")
    graph = build_skeleton_graph(skeleton)

    strokes = _extract_strokes_global(skeleton, expected_count=3)
    stroke_pixels = sum(len(stroke) for stroke in strokes)

    assert len(strokes) <= 4
    assert stroke_pixels <= int(len(graph) * 1.30)


def test_global_tian_does_not_overcover_closed_structure():
    skeleton = _prepared_skeleton("tian")
    graph = build_skeleton_graph(skeleton)

    strokes = _extract_strokes_global(skeleton, expected_count=5)
    stroke_pixels = sum(len(stroke) for stroke in strokes)

    assert stroke_pixels <= int(len(graph) * 1.35)


def test_global_zhong_does_not_overcover_closed_structure():
    skeleton = _prepared_skeleton("zhong")
    graph = build_skeleton_graph(skeleton)

    strokes = _extract_strokes_global(skeleton, expected_count=4)
    stroke_pixels = sum(len(stroke) for stroke in strokes)

    assert stroke_pixels <= int(len(graph) * 1.35)


def test_tian_closed_structure_has_no_high_winding_strokes():
    strokes = _post_knowledge_strokes("tian")
    ratios = [_stroke_path_ratio(stroke) for stroke in strokes]

    assert max(ratios) < 3.0


def test_tian_right_frame_does_not_detour_around_half_glyph():
    detours = _right_side_frame_detours("tian")

    assert detours == []


def test_zhong_right_frame_does_not_detour_around_half_glyph():
    detours = _right_side_frame_detours("zhong")

    assert detours == []


def test_safe_extractor_uses_global_for_chuan():
    set_trace_context("chuan")
    skeleton = _prepared_skeleton("chuan")

    strokes = get_stroke_list(skeleton)
    diag = get_last_trace_diagnostics()

    assert diag["method"] == "global"
    assert len(strokes) == 3


def test_safe_extractor_applies_simple_prior_for_yi():
    set_trace_context("yi")
    skeleton = _prepared_skeleton("yi")

    strokes = get_stroke_list(skeleton)
    diag = get_last_trace_diagnostics()

    assert len(strokes) == 1
    assert "simple_prior_longest_main_stroke" in diag["fallback_reason"]


def test_holdout_expected_counts_are_available():
    expected_counts = {
        "ri": 4,
        "ren": 2,
        "da": 3,
        "shan": 3,
        "xin": 4,
        "xiao": 3,
        "shui": 4,
    }

    for name, expected in expected_counts.items():
        assert get_stroke_count(name) == expected


def test_holdout_shui_has_no_extreme_winding_stroke():
    strokes = _post_knowledge_strokes_from_subset("shui", "holdout_set")
    ratios = [_stroke_path_ratio(stroke) for stroke in strokes]

    assert max(ratios) < 5.0


def test_holdout_hao_has_no_high_winding_stroke_after_count_merge():
    strokes = _post_knowledge_strokes_from_subset("hao", "holdout_set")
    ratios = [_stroke_path_ratio(stroke) for stroke in strokes]

    assert len(strokes) == 6
    assert max(ratios) < 4.0
