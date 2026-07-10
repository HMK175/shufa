from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graph_extract import extract_segments


def test_extract_segments_from_t_shape_returns_three_segments_and_one_branch():
    skel = np.zeros((32, 32), dtype=bool)
    skel[16, 8:24] = True
    skel[8:17, 16] = True
    result = extract_segments(skel, min_segment_pixels=3)
    assert result["component_count"] == 1
    assert result["segment_count"] == 3
    assert result["endpoint_count"] == 3
    assert result["branch_point_count"] == 1
    assert len(result["components"]) == 1
    assert result["components"][0]["is_loop"] is False
    assert result["components"][0]["segment_count"] == 3
    assert all(segment["length_px"] > 0 for segment in result["segments"])
    assert all(segment["is_loop"] is False for segment in result["segments"])


def test_extract_segments_filters_short_spurs():
    skel = np.zeros((24, 24), dtype=bool)
    skel[12, 4:20] = True
    skel[10:13, 10] = True
    result = extract_segments(skel, min_segment_pixels=4)
    assert result["component_count"] == 1
    assert result["segment_count"] == 2
    assert result["endpoint_count"] == 3
    assert result["branch_point_count"] == 1
    assert result["components"][0]["segment_count"] == 2
    assert all(segment["pixel_count"] >= 4 for segment in result["segments"])
    assert all((10, 10) not in segment["points"] and (11, 10) not in segment["points"] for segment in result["segments"])


def test_extract_segments_preserves_loop_components():
    skel = np.zeros((16, 16), dtype=bool)
    skel[4, 4:10] = True
    skel[9, 4:10] = True
    skel[4:10, 4] = True
    skel[4:10, 9] = True
    result = extract_segments(skel, min_segment_pixels=3)
    assert result["component_count"] == 1
    assert result["segment_count"] == 1
    assert result["segments"][0]["is_loop"] is True
    assert result["components"][0]["is_loop"] is True
    assert result["components"][0]["segment_count"] == 1
    assert result["components"][0]["pixel_count"] == int(skel.sum())
    assert result["segments"][0]["start"] == result["segments"][0]["end"]
    assert result["segments"][0]["length_px"] > 0


def test_extract_segments_treats_thick_branch_cluster_as_one_supernode():
    skel = np.zeros((24, 24), dtype=bool)
    skel[11:13, 11:13] = True
    skel[5:11, 11] = True
    skel[13:19, 12] = True
    skel[11, 5:11] = True
    skel[12, 13:19] = True

    result = extract_segments(skel, min_segment_pixels=3)

    assert result["component_count"] == 1
    assert result["branch_point_count"] == 1
    assert result["segment_count"] == 4
    assert result["components"][0]["segment_count"] == 4
    assert result["components"][0]["is_loop"] is False
    assert all(segment["is_loop"] is False for segment in result["segments"])
    assert all(segment["pixel_count"] >= 6 for segment in result["segments"])
    assert all(segment["start"] != segment["end"] for segment in result["segments"])


def test_extract_segments_handles_empty_skeleton_cleanly():
    skel = np.zeros((8, 8), dtype=bool)

    result = extract_segments(skel, min_segment_pixels=3)

    assert result["segment_count"] == 0
    assert result["component_count"] == 0
    assert result["endpoint_count"] == 0
    assert result["branch_point_count"] == 0
    assert result["segments"] == []
    assert result["components"] == []


def test_extract_segments_preserves_loop_metadata_for_loop_plus_spur_component():
    skel = np.zeros((20, 20), dtype=bool)
    skel[6, 6:12] = True
    skel[11, 6:12] = True
    skel[6:12, 6] = True
    skel[6:12, 11] = True
    skel[2:7, 8] = True

    result = extract_segments(skel, min_segment_pixels=3)

    assert result["component_count"] == 1
    assert result["branch_point_count"] == 1
    assert result["endpoint_count"] == 1
    assert result["segment_count"] == 2
    assert sum(1 for segment in result["segments"] if segment["is_loop"]) == 1
    assert any(segment["start"] == segment["end"] and segment["is_loop"] for segment in result["segments"])
    assert result["components"][0]["segment_count"] == 2
    assert result["components"][0]["is_loop"] is True


def test_extract_segments_treats_short_side_stub_corner_as_passthrough():
    skel = np.zeros((12, 12), dtype=bool)
    skel[5, 1:7] = True
    skel[5:10, 5] = True

    result = extract_segments(skel, min_segment_pixels=2)

    assert result["component_count"] == 1
    assert result["branch_point_count"] == 0
    assert result["segment_count"] == 2
    endpoints = {(segment["start"], segment["end"]) for segment in result["segments"]}
    assert any({(5, 1), (9, 5)} == {start, end} for start, end in endpoints)
    assert any({(5, 6), (5, 5)} == {start, end} for start, end in endpoints)


def test_extract_segments_treats_hook_like_branch_with_short_spur_as_passthrough():
    skel = np.zeros((14, 16), dtype=bool)
    skel[6, 1:11] = True
    skel[6:10, 6] = True
    skel[4:9, 10] = True

    result = extract_segments(skel, min_segment_pixels=2)

    assert result["component_count"] == 1
    assert result["branch_point_count"] == 1
    assert result["segment_count"] == 4
    endpoints = {(segment["start"], segment["end"]) for segment in result["segments"]}
    assert any({(6, 1), (6, 10)} == {start, end} for start, end in endpoints)
    assert any({(9, 6), (6, 6)} == {start, end} for start, end in endpoints)
