from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ordering import order_segments


def test_order_segments_uses_orientation_independent_top_left_tie_break():
    segments = [
        {"segment_id": 1, "length_px": 10.0, "points": [(5, 5), (0, 0)]},
        {"segment_id": 2, "length_px": 10.0, "points": [(0, 2), (5, 7)]},
    ]

    ordered = order_segments(segments)

    assert [item["source_segment_ids"] for item in ordered] == [(1,), (2,)]


def test_order_segments_prefers_longer_segment_first():
    segments = [
        {"segment_id": 1, "length_px": 5.0, "points": [(0, 0), (0, 5)]},
        {"segment_id": 2, "length_px": 12.0, "points": [(5, 0), (5, 12)]},
    ]

    ordered = order_segments(segments)

    assert [item["source_segment_ids"] for item in ordered] == [(2,), (1,)]
    assert [item["order_index"] for item in ordered] == [1, 2]
    assert [item["stroke_like_id"] for item in ordered] == [1, 2]


def test_order_segments_keeps_each_component_group_contiguous_after_reordering():
    segments = [
        {"segment_id": 1, "component_id": 2, "length_px": 100.0, "points": [(5, 0), (5, 100)]},
        {"segment_id": 2, "component_id": 1, "length_px": 10.0, "points": [(0, 0), (0, 10)]},
        {"segment_id": 3, "component_id": 1, "length_px": 8.0, "points": [(2, 0), (2, 8)]},
    ]

    ordered = order_segments(segments)

    component_ids = [item["component_id"] for item in ordered]
    assert sorted(component_ids) == [1, 1, 2]
    assert component_ids.count(1) == 2
    first = component_ids.index(1)
    last = len(component_ids) - 1 - component_ids[::-1].index(1)
    assert last - first == 1


def test_order_segments_merges_nearby_collinear_segments_when_enabled():
    segments = [
        {"segment_id": 1, "length_px": 10.0, "points": [(0, 0), (0, 10)]},
        {"segment_id": 2, "length_px": 8.0, "points": [(0, 10.5), (0, 18.5)]},
    ]

    ordered = order_segments(segments, endpoint_merge_distance=1.0)

    assert len(ordered) == 1
    assert ordered[0]["source_segment_ids"] == (1, 2)
    assert ordered[0]["points"] == [(0, 0), (0, 10), (0, 10.5), (0, 18.5)]
    assert ordered[0]["length_px"] == 18.5


def test_order_segments_refreshes_merged_metadata_after_orientation_changes():
    segments = [
        {
            "segment_id": 1,
            "length_px": 10.0,
            "points": [(0, 20), (0, 10)],
            "start": (99, 99),
            "end": (98, 98),
            "pixel_count": 99,
        },
        {
            "segment_id": 2,
            "length_px": 9.5,
            "points": [(0, 0), (0, 9.5)],
            "start": (97, 97),
            "end": (96, 96),
            "pixel_count": 96,
        },
    ]

    ordered = order_segments(segments, endpoint_merge_distance=1.0)

    assert len(ordered) == 1
    assert ordered[0]["source_segment_ids"] == (1, 2)
    assert ordered[0]["points"] == [(0, 20), (0, 10), (0, 9.5), (0, 0)]
    assert ordered[0]["start"] == (0, 20)
    assert ordered[0]["end"] == (0, 0)
    assert ordered[0]["pixel_count"] == 4
    assert ordered[0]["length_px"] == 20.0


def test_order_segments_does_not_merge_nearby_perpendicular_segments():
    segments = [
        {"segment_id": 1, "length_px": 10.0, "points": [(0, 0), (0, 10)]},
        {"segment_id": 2, "length_px": 8.0, "points": [(0, 10.5), (8, 10.5)]},
    ]

    ordered = order_segments(segments, endpoint_merge_distance=1.0)

    assert len(ordered) == 2
    assert [item["source_segment_ids"] for item in ordered] == [(1,), (2,)]


def test_order_segments_sequences_box_like_component_by_nearest_continuation():
    segments = [
        {"segment_id": 1, "component_id": 1, "length_px": 10.0, "points": [(0, 0), (0, 10)]},
        {"segment_id": 2, "component_id": 1, "length_px": 10.0, "points": [(10, 0), (0, 0)]},
        {"segment_id": 3, "component_id": 1, "length_px": 10.0, "points": [(10, 10), (10, 0)]},
        {"segment_id": 4, "component_id": 1, "length_px": 10.0, "points": [(0, 10), (10, 10)]},
    ]

    ordered = order_segments(segments)

    assert [item["source_segment_ids"] for item in ordered] == [(1,), (4,), (3,), (2,)]
    assert all(first["end"] == second["start"] for first, second in zip(ordered[:-1], ordered[1:]))


def test_order_segments_sequences_components_by_nearest_continuation():
    segments = [
        {"segment_id": 1, "component_id": 1, "length_px": 10.0, "points": [(0, 0), (0, 10)]},
        {"segment_id": 2, "component_id": 2, "length_px": 10.0, "points": [(50, 50), (50, 60)]},
        {"segment_id": 3, "component_id": 3, "length_px": 9.0, "points": [(1, 11), (1, 20)]},
    ]

    ordered = order_segments(segments)

    assert [item["source_segment_ids"] for item in ordered] == [(1,), (3,), (2,)]


def test_order_segments_merges_shared_endpoint_segments_despite_branch_kink():
    segments = [
        {
            "segment_id": 1,
            "length_px": 39.0,
            "points": [(30, 42), (32, 40), (32, 39), (32, 38), (32, 37), (34, 3)],
        },
        {
            "segment_id": 2,
            "length_px": 37.0,
            "points": [(30, 42), (31, 44), (31, 45), (31, 46), (31, 47), (31, 79)],
        },
    ]

    ordered = order_segments(segments, endpoint_merge_distance=1.0)

    assert len(ordered) == 1
    assert ordered[0]["source_segment_ids"] == (1, 2)
    assert ordered[0]["points"][0] == (34.0, 3.0)
    assert ordered[0]["points"][-1] == (31.0, 79.0)


def test_order_segments_does_not_merge_loop_segments_with_tails_by_default():
    segments = [
        {"segment_id": 1, "length_px": 4.0, "points": [(0, 0), (0, 2), (2, 2), (0, 0)], "is_loop": True},
        {"segment_id": 2, "length_px": 6.0, "points": [(0, 0.5), (0, 6.5)], "is_loop": False},
    ]

    ordered = order_segments(segments, endpoint_merge_distance=1.0)

    assert len(ordered) == 2
    assert [item["source_segment_ids"] for item in ordered] == [(2,), (1,)]
    assert ordered[1]["is_loop"] is True


def test_order_segments_splits_through_segment_around_closed_anchor_loop():
    segments = [
        {
            "segment_id": 1,
            "component_id": 1,
            "length_px": 8.0,
            "points": [(2, 2), (2, 4), (4, 4), (4, 2), (2, 2)],
        },
        {
            "segment_id": 2,
            "component_id": 1,
            "length_px": 5.0,
            "points": [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)],
        },
    ]

    ordered = order_segments(segments)

    assert len(ordered) == 3
    assert ordered[0]["points"] == [(0, 2), (1, 2), (2, 2)]
    assert ordered[1]["points"][0] == (2, 2)
    assert ordered[1]["points"][-1] == (2, 2)
    assert ordered[2]["points"] == [(2, 2), (3, 2), (4, 2), (5, 2)]
    assert all(first["end"] == second["start"] for first, second in zip(ordered[:-1], ordered[1:]))


def test_order_segments_sequences_component_groups_by_global_jump_cost_not_greedy_next():
    segments = [
        {"segment_id": 1, "component_id": 1, "length_px": 17.0, "points": [(2, 30), (15, 41)]},
        {"segment_id": 2, "component_id": 2, "length_px": 21.0, "points": [(5, 61), (17, 78)]},
        {"segment_id": 3, "component_id": 3, "length_px": 23.0, "points": [(19, 8), (42, 5)]},
        {"segment_id": 4, "component_id": 4, "length_px": 37.0, "points": [(28, 57), (22, 21)]},
    ]

    ordered = order_segments(segments)

    assert [item["source_segment_ids"] for item in ordered] == [(1,), (2,), (4,), (3,)]


def test_order_segments_sequences_within_component_by_global_jump_cost_not_greedy_next():
    segments = [
        {"segment_id": 1, "component_id": 2, "source_segment_ids": (4, 2), "length_px": 52.5, "points": [(26, 21), (76, 37)]},
        {"segment_id": 2, "component_id": 2, "source_segment_ids": (5, 3), "length_px": 51.0, "points": [(66, 85), (40, 41)]},
        {"segment_id": 3, "component_id": 2, "source_segment_ids": (1,), "length_px": 22.0, "points": [(26, 63), (42, 48)]},
        {"segment_id": 4, "component_id": 2, "source_segment_ids": (6,), "length_px": 12.0, "points": [(72, 26), (76, 37)]},
    ]

    ordered = order_segments(segments)

    jumps = []
    for first, second in zip(ordered[:-1], ordered[1:]):
        y0, x0 = first["end"]
        y1, x1 = second["start"]
        jumps.append(((y0 - y1) ** 2 + (x0 - x1) ** 2) ** 0.5)

    assert max(jumps) <= 42.0
    assert [item["source_segment_ids"] for item in ordered] != [(4, 2), (5, 3), (1,), (6,)]


def test_order_segments_uses_bounded_search_beyond_exact_limit_for_large_component_group():
    segments = [
        {"segment_id": 1, "component_id": 1, "length_px": 120.0, "points": [(0, 0), (0, 120)]},
        {"segment_id": 2, "component_id": 1, "length_px": 100.0, "points": [(0, 121), (100, 121)]},
        {"segment_id": 3, "component_id": 1, "length_px": 2.0, "points": [(0, 124), (0, 126)]},
        {"segment_id": 4, "component_id": 1, "length_px": 2.0, "points": [(0, 126), (0, 128)]},
        {"segment_id": 5, "component_id": 1, "length_px": 2.0, "points": [(0, 128), (0, 130)]},
        {"segment_id": 6, "component_id": 1, "length_px": 2.0, "points": [(0, 130), (0, 132)]},
        {"segment_id": 7, "component_id": 1, "length_px": 2.0, "points": [(0, 132), (0, 134)]},
    ]

    ordered = order_segments(segments)

    jumps = []
    for first, second in zip(ordered[:-1], ordered[1:]):
        y0, x0 = first["end"]
        y1, x1 = second["start"]
        jumps.append(((y0 - y1) ** 2 + (x0 - x1) ** 2) ** 0.5)

    assert ordered[1]["source_segment_ids"] != (2,)
    assert ordered[-1]["source_segment_ids"] == (2,)
    assert max(jumps) <= 13.0


def test_order_segments_uses_exact_search_for_seven_segment_group_without_fixing_longest_seed():
    segments = [
        {"segment_id": 3, "component_id": 1, "length_px": 37.68, "points": [(82.15, 64.41), (55.74, 38.95)]},
        {"segment_id": 17, "component_id": 1, "length_px": 6.71, "points": [(68.08, 27.32), (74.63, 28.27)]},
        {"segment_id": 4, "component_id": 1, "length_px": 20.14, "points": [(71.23, 29.14), (55.74, 38.95)]},
        {"segment_id": 6, "component_id": 1, "length_px": 12.54, "points": [(37.01, 54.26), (45.17, 62.84)]},
        {"segment_id": 8, "component_id": 1, "length_px": 16.29, "points": [(39.16, 87.03), (47.53, 100.14)]},
        {"segment_id": 10, "component_id": 1, "length_px": 15.74, "points": [(63.38, 81.68), (76.42, 90.25)]},
        {"segment_id": 2, "component_id": 1, "length_px": 30.12, "points": [(77.34, 93.86), (82.15, 64.41)]},
    ]

    ordered = order_segments(segments)

    jumps = []
    for first, second in zip(ordered[:-1], ordered[1:]):
        y0, x0 = first["end"]
        y1, x1 = second["start"]
        jumps.append(((y0 - y1) ** 2 + (x0 - x1) ** 2) ** 0.5)

    assert ordered[0]["source_segment_ids"] != (3,)
    assert max(jumps) <= 24.34
    assert sum(jumps) <= 72.72
