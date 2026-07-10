from pathlib import Path
import json
import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import (
    DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    DEFAULT_REVIEW_PANEL_HIGHLIGHT_OUTLINE,
    HYBRID_CONTACT_PANELS,
    _collapse_adjacent_identical_source_segments,
    _collect_batch_summary_rows,
    _build_reference_stroke_primitive_library,
    _build_component_mix_candidate_segments,
    _load_input_foreground_mask,
    _choose_processed_postprocess_candidate,
    _recommended_review_mode,
    _restore_render_subpaths_by_source_segment_ids,
    _restore_render_subpaths_from_source_segments,
    _review_panel_filename_for_mode,
    _select_axis_reference_segment,
    _segment_color,
    _choose_postprocess_candidate,
    _should_promote_raw_to_light_repair_candidate,
    _hybrid_audit_status,
    _prepare_local_candidate_segments,
    load_callirewrite_segments,
    run_callirewrite_hybrid_probe,
)
from ordering import order_segments
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
)
from visualize import PALETTE


def _write_input_png(path: Path) -> None:
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.line((12, 12, 52, 12), fill=0, width=4)
    draw.line((32, 12, 32, 52), fill=0, width=4)
    image.save(path)


def test_build_component_mix_candidate_segments_replaces_long_foldback_only():
    local_segments = [
        {"points": [(0.0, 0.0), (1.0, 0.0)], "source_segment_ids": (8,)},
        {
            "points": [(0.0, 0.0), (0.0, 80.0), (8.0, 82.0), (2.0, 78.0)],
            "source_segment_ids": (10, 2, 3),
        },
        {"points": [(10.0, 10.0), (12.0, 12.0)], "source_segment_ids": (6,)},
    ]
    prior_segments = [
        {"points": [(0.0, 0.0), (0.0, 79.0), (8.0, 81.0), (1.0, 77.0)], "source_segment_ids": (3, 2, 10)},
        {"points": [(20.0, 20.0), (22.0, 22.0)], "source_segment_ids": (17,)},
    ]

    mixed, meta = _build_component_mix_candidate_segments(local_segments, prior_segments)

    assert meta["component_mix_applied"] is True
    assert [tuple(segment.get("source_segment_ids", ())) for segment in mixed] == [
        (8,),
        (3, 2, 10),
        (6,),
    ]


def test_select_reference_heng_uses_longest_horizontal_segment():
    segments = [
        {"points": [(0.0, 0.0), (0.0, 12.0)], "source_segment_ids": (1,)},
        {"points": [(0.0, 0.0), (0.0, 24.0)], "source_segment_ids": (2,)},
        {"points": [(0.0, 0.0), (20.0, 1.0)], "source_segment_ids": (3,)},
    ]

    selected = _select_axis_reference_segment(segments, axis="horizontal")

    assert selected is not None
    assert tuple(selected["source_segment_ids"]) == (2,)


def test_select_reference_shu_uses_longest_vertical_segment():
    segments = [
        {"points": [(0.0, 0.0), (12.0, 0.0)], "source_segment_ids": (1,)},
        {"points": [(0.0, 0.0), (25.0, 1.0)], "source_segment_ids": (2,)},
        {"points": [(0.0, 0.0), (1.0, 22.0)], "source_segment_ids": (3,)},
    ]

    selected = _select_axis_reference_segment(segments, axis="vertical")

    assert selected is not None
    assert tuple(selected["source_segment_ids"]) == (2,)


def test_build_reference_primitive_library_contains_heng_shu_and_hengzhe():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"

    library, meta = _build_reference_stroke_primitive_library(converted_dir, input_dir)

    assert library.get("heng") is not None
    assert library.get("shu") is not None
    assert library.get("hengzhe") is not None
    assert set(meta["registered_primitive_kinds"]) >= {"heng", "shu", "hengzhe"}
    assert max(library.get("shu").relative_widths) <= 1.5
    assert max(library.get("hengzhe").relative_widths) <= 1.5


def test_build_component_mix_candidate_segments_prunes_local_subpath_near_prior_foldback():
    local_segments = [
        {
            "points": [(0.0, 0.0), (0.0, 80.0), (8.0, 82.0), (2.0, 78.0)],
            "source_segment_ids": (10, 2, 3),
        },
        {
            "points": [(30.0, -18.0), (36.0, -18.0), (1.0, 76.0), (2.0, 77.0)],
            "source_segment_ids": (17, 4),
            "render_subpaths": [
                [(30.0, -18.0), (36.0, -18.0)],
                [(1.0, 76.0), (2.0, 77.0)],
            ],
            "render_subpath_source_ids": [(17,), (4,)],
        },
    ]
    prior_segments = [
        {"points": [(0.0, 0.0), (0.0, 79.0), (8.0, 81.0), (1.0, 77.0)], "source_segment_ids": (3, 2, 10)},
    ]

    mixed, meta = _build_component_mix_candidate_segments(local_segments, prior_segments)

    retained_left_dot = mixed[1]
    assert meta["component_mix_pruned_local_subpath_count"] == 1
    assert tuple(retained_left_dot["source_segment_ids"]) == (17,)
    assert retained_left_dot["render_subpaths"] == [[(30.0, -18.0), (36.0, -18.0)]]
    assert retained_left_dot["points"] == [(30.0, -18.0), (36.0, -18.0)]


def test_build_component_mix_candidate_segments_uses_detail_source_for_top_dots():
    local_segments = [
        {
            "points": [(0.0, 0.0), (0.0, 80.0), (8.0, 82.0), (2.0, 78.0)],
            "source_segment_ids": (10, 2, 3),
        },
        {
            "points": [(-30.0, 40.0), (-28.0, 44.0), (-26.0, 48.0)],
            "source_segment_ids": (8,),
            "component_id": 3,
        },
        {
            "points": [(28.0, -18.0), (34.0, -18.0)],
            "source_segment_ids": (17,),
            "component_id": 4,
        },
    ]
    prior_segments = [
        {"points": [(0.0, 0.0), (0.0, 79.0), (8.0, 81.0), (1.0, 77.0)], "source_segment_ids": (3, 2, 10)},
    ]
    detail_segments = [
        {
            "points": [(-31.0, 39.0), (-30.0, 42.0), (-27.0, 47.0)],
            "source_segment_ids": (8,),
            "component_id": 99,
        },
        {
            "points": [(29.0, -17.0), (34.0, -17.0)],
            "source_segment_ids": (17,),
            "component_id": 99,
        },
    ]

    mixed, meta = _build_component_mix_candidate_segments(
        local_segments,
        prior_segments,
        detail_source_segments=detail_segments,
    )

    top_dot = next(segment for segment in mixed if tuple(segment.get("source_segment_ids", ())) == (8,))
    left_dot = next(segment for segment in mixed if tuple(segment.get("source_segment_ids", ())) == (17,))
    assert meta["component_mix_detail_source_replaced_count"] == 1
    assert top_dot["points"] == [(-31.0, 39.0), (-30.0, 42.0), (-27.0, 47.0)]
    assert top_dot["component_mix_source"] == "detail"
    assert top_dot["component_id"] == 3
    assert left_dot["points"] == [(28.0, -18.0), (34.0, -18.0)]
    assert left_dot["component_id"] == 4


def _write_box_input_png(path: Path) -> None:
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 52, 52), outline=0, width=4)
    image.save(path)


def _write_band_input_png(path: Path) -> None:
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 18, 54, 24), fill=0)
    image.save(path)


def _write_vertical_band_input_png(path: Path) -> None:
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 8, 34, 54), fill=0)
    image.save(path)


def _write_converted_sample(
    sample_dir: Path,
    *,
    sample: str,
    segments: list[list[tuple[float, float]]],
) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "callirewrite_npz",
        "coordinate_frame": "callirewrite_image_pixels",
        "segments": [
            {
                "segment_id": index + 1,
                "source_segment_ids": [index + 1],
                "points": [[float(y), float(x)] for y, x in points],
                "pixel_count": len(points),
                "length_px": 0.0,
                "start": list(points[0]),
                "end": list(points[-1]),
                "component_id": 1,
                "is_loop": False,
            }
            for index, points in enumerate(segments)
        ],
        "boundary_note": "offline test fixture",
    }
    (sample_dir / "callirewrite_recovered_strokes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (sample_dir / "callirewrite_summary.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "source": "callirewrite_npz",
                "sample": sample,
                "segment_count": len(segments),
                "trajectory_point_count": sum(len(points) for points in segments),
                "manual_audit_required": True,
                "failure_reason": "",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_load_callirewrite_segments_reads_recovered_json(tmp_path: Path):
    sample_dir = tmp_path / "converted" / "yong"
    _write_converted_sample(
        sample_dir,
        sample="yong",
        segments=[
            [(10.0, 10.0), (10.0, 20.0)],
            [(10.0, 20.0), (20.0, 20.0)],
        ],
    )

    segments, meta = load_callirewrite_segments(sample_dir)

    assert meta["load_backend"] == "recovered_json"
    assert meta["external_source"] == "callirewrite_npz"
    assert len(segments) == 2
    assert segments[0]["points"] == [(10.0, 10.0), (10.0, 20.0)]
    assert segments[0]["source_segment_ids"] == (1,)
    assert segments[1]["source_segment_ids"] == (2,)


def test_run_callirewrite_hybrid_probe_writes_expected_outputs(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True)

    _write_input_png(input_dir / "yong.png")
    _write_input_png(input_dir / "zhong.png")
    _write_converted_sample(
        converted_dir / "yong",
        sample="yong",
        segments=[
            [(12.0, 12.0), (12.0, 30.0)],
            [(12.0, 30.0), (12.0, 52.0)],
        ],
    )
    _write_converted_sample(
        converted_dir / "zhong",
        sample="zhong",
        segments=[
            [(15.0, 15.0), (15.0, 25.0)],
            [(30.0, 30.0), (40.0, 30.0)],
        ],
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["yong", "zhong"],
    )

    assert payload["status"] == "ok"
    assert payload["stage"] == "callirewrite_hybrid_probe"
    batch_dir = Path(payload["batch_dir"])
    assert batch_dir.exists()
    assert Path(payload["visual_audit_contact_sheet"]).exists()
    assert Path(payload["manual_audit_sheet"]).exists()
    assert Path(payload["report_path"]).exists()

    yong_dir = batch_dir / "yong"
    summary = json.loads((yong_dir / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["source"] == "callirewrite_hybrid"
    assert summary["external_source"] == "callirewrite_npz"
    assert summary["ordered_segment_count"] == 2
    assert summary["consolidated_segment_count"] >= 1
    assert summary["merged_segment_count"] >= 0
    assert summary["trajectory_point_count"] >= 2
    assert summary["visual_canvas_shape"][0] > 40
    assert summary["visual_canvas_shape"][1] > 40
    assert sorted(summary["ordered_source_segment_ids"]) == [[1], [2]]
    assert summary["visual_crop_strategy"] == "union_input_foreground_and_trajectory"
    assert summary["position_layer_policy"] == "weak_foreground_snap"
    assert summary["position_layer_source"] == "local_candidate"
    assert summary["width_layer_source"] == "input_foreground_mask"
    assert summary["width_layer_render_mode"] == "variable"
    assert summary["structure_skeleton_trajectory_image"] == "n/a"
    assert summary["structure_skeleton_overlay_image"] == "n/a"
    assert summary["structure_skeleton_playback_contact_sheet"] == "n/a"
    assert abs(float(summary["position_layer_foreground_snap_blend"]) - 0.35) <= 1e-6
    assert (yong_dir / "input_image.png").exists()
    assert (yong_dir / "candidate_order.png").exists()
    assert (yong_dir / "callirewrite_source_trajectory.png").exists()
    assert (yong_dir / "raw_rendered_execution.png").exists()
    assert (yong_dir / "constant_width_render.png").exists()
    assert (yong_dir / "conservative_width_render.png").exists()
    assert (yong_dir / "local_rendered_execution.png").exists()
    assert (yong_dir / "makemeahanzi_rendered_execution.png").exists()
    assert (yong_dir / "final_trajectory.png").exists()
    assert (yong_dir / "callirewrite_overlay.png").exists()
    assert (yong_dir / "hybrid_overlay.png").exists()
    assert (yong_dir / "rendered_execution.png").exists()
    assert (yong_dir / "playback_contact_sheet.png").exists()
    assert (yong_dir / "callirewrite_pen_up.png").exists()
    assert (yong_dir / "hybrid_pen_up.png").exists()
    assert (yong_dir / "trial_ordered_trajectory.csv").exists()
    with Image.open(yong_dir / "input_image.png") as image:
        assert image.width > 40
        assert image.height > 40
    with Image.open(yong_dir / "rendered_execution.png") as image:
        pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
        assert image.width > 40
        assert image.height > 40
        assert int(np.min(pixels)) < 250
    with Image.open(yong_dir / "playback_contact_sheet.png") as image:
        assert image.width > 0
        assert image.height > 0
    with Image.open(payload["visual_audit_contact_sheet"]) as image:
        assert image.width > 1900
        assert image.width < 2400
        pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
        highlight = np.asarray(DEFAULT_REVIEW_PANEL_HIGHLIGHT_OUTLINE, dtype=np.uint8)
        assert int(np.count_nonzero(np.all(pixels == highlight, axis=2))) > 0
    summary_rows = _collect_batch_summary_rows(batch_dir)
    yong_row = next(row for row in summary_rows if row["sample"] == "yong")
    assert yong_row["selected_postprocess_mode"] in {"local", "makemeahanzi_regroup"}
    assert yong_row["review_recommended_mode"] in {"raw", "raw_light_repair", "local", "makemeahanzi_regroup"}


def test_run_callirewrite_hybrid_probe_reorders_raw_callirewrite_segments(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True)

    _write_input_png(input_dir / "zhong.png")
    _write_converted_sample(
        converted_dir / "zhong",
        sample="zhong",
        segments=[
            [(10.0, 10.0), (10.0, 20.0)],
            [(20.0, 20.0), (20.0, 30.0)],
            [(10.0, 20.0), (20.0, 20.0)],
        ],
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["zhong"],
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "zhong" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["raw_max_pen_up_jump_px"] > summary["max_pen_up_jump_px"]
    assert summary["ordered_source_segment_ids"] == [[1], [3], [2]]


def test_collapse_adjacent_identical_source_segments_preserves_component_boundaries():
    segments = [
        {
            "points": [(10.0, 10.0), (10.0, 20.0)],
            "source_segment_ids": (1, 2),
            "component_id": 2,
        },
        {
            "points": [(10.0, 20.0), (20.0, 20.0)],
            "source_segment_ids": (1, 2),
            "component_id": 1,
        },
    ]

    collapsed = _collapse_adjacent_identical_source_segments(segments)

    assert len(collapsed) == 2
    assert [tuple(segment.get("source_segment_ids", ())) for segment in collapsed] == [(1, 2), (1, 2)]
    assert [int(segment.get("component_id", 0) or 0) for segment in collapsed] == [2, 1]


def test_collapse_adjacent_identical_source_segments_merges_short_cross_component_sliver():
    segments = [
        {
            "points": [(10.0, 10.0), (10.0, 28.0)],
            "source_segment_ids": (1, 2),
            "component_id": 2,
        },
        {
            "points": [(10.0, 28.0), (12.0, 31.0), (13.0, 33.0)],
            "source_segment_ids": (1, 2),
            "component_id": 1,
        },
    ]

    collapsed = _collapse_adjacent_identical_source_segments(segments)

    assert len(collapsed) == 1
    assert tuple(collapsed[0].get("source_segment_ids", ())) == (1, 2)
    assert int(collapsed[0].get("component_id", 0) or 0) == 2


def test_restore_render_subpaths_by_source_segment_ids_falls_back_to_segment_points_for_component_slice():
    segments = [
        {
            "points": [(10.0, 10.0), (10.0, 20.0)],
            "source_segment_ids": (1, 2),
            "component_id": 1,
        }
    ]
    render_subpath_map = {
        (1, 2): {
            "render_subpaths": [[(10.0, 10.0), (10.0, 20.0), (20.0, 20.0)]],
            "render_subpath_source_ids": [(1, 2)],
        }
    }

    restored = _restore_render_subpaths_by_source_segment_ids(
        segments,
        render_subpath_map=render_subpath_map,
    )

    assert len(restored) == 1
    assert restored[0]["render_subpaths"] == [[(10.0, 10.0), (10.0, 20.0)]]
    assert restored[0]["render_subpath_source_ids"] == [(1, 2)]


def test_run_callirewrite_hybrid_probe_supports_makemeahanzi_regroup_mode(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    graphics_path = tmp_path / "graphics.txt"
    input_dir.mkdir(parents=True)

    char_zhong = chr(0x4E2D)
    _write_input_png(input_dir / "zhong.png")
    _write_converted_sample(
        converted_dir / "zhong",
        sample="zhong",
        segments=[
            [(12.0, 12.0), (12.0, 32.0)],
            [(12.0, 32.0), (12.0, 52.0)],
            [(12.0, 12.0), (32.0, 12.0)],
            [(32.0, 12.0), (52.0, 12.0)],
        ],
    )
    graphics_path.write_text(
        json.dumps(
                {
                    "character": char_zhong,
                    "strokes": ["a", "b"],
                "medians": [
                    [[12.0, 12.0], [12.0, 52.0]],
                    [[12.0, 12.0], [52.0, 12.0]],
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["zhong"],
        postprocess_mode="makemeahanzi_regroup",
        makemeahanzi_graphics_path=graphics_path,
        sample_char_map={"zhong": char_zhong},
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "zhong" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["postprocess_mode"] == "makemeahanzi_regroup"
    assert summary["makemeahanzi_prior_available"] is True
    assert summary["makemeahanzi_prior_applied"] is True
    assert summary["makemeahanzi_target_stroke_count"] == 2
    assert summary["makemeahanzi_geometry_regularized_segment_count"] >= 0
    assert summary["consolidated_segment_count"] <= 2
    assert summary["consolidated_segment_count"] < summary["ordered_segment_count"]


def test_run_callirewrite_hybrid_probe_postprocesses_makemeahanzi_regrouped_strokes(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    graphics_path = tmp_path / "graphics.txt"
    input_dir.mkdir(parents=True)

    char_yi = chr(0x4E00)
    _write_band_input_png(input_dir / "yi.png")
    _write_converted_sample(
        converted_dir / "yi",
        sample="yi",
        segments=[
            [(18.0, 12.0), (18.0, 30.0)],
            [(18.0, 30.0), (18.0, 52.0)],
        ],
    )
    graphics_path.write_text(
        json.dumps(
            {
                "character": char_yi,
                "strokes": ["a"],
                "medians": [
                    [[21.0, 12.0], [21.0, 52.0]],
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["yi"],
        postprocess_mode="makemeahanzi_regroup",
        makemeahanzi_graphics_path=graphics_path,
        sample_char_map={"yi": char_yi},
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "yi" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["selected_postprocess_mode"] == "makemeahanzi_regroup"
    assert summary["consolidated_segment_count"] == 1
    assert summary["resampled_point_delta"] > 0
    assert summary["snapped_point_count"] > 0


def test_run_callirewrite_hybrid_probe_supports_raw_light_repair_mode(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True)

    _write_vertical_band_input_png(input_dir / "split_vertical.png")
    _write_converted_sample(
        converted_dir / "split_vertical",
        sample="split_vertical",
        segments=[
            [(8.0, 32.0), (24.0, 32.0)],
            [(26.0, 32.0), (52.0, 32.0)],
        ],
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["split_vertical"],
        postprocess_mode="raw_light_repair",
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "split_vertical" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["selected_postprocess_mode"] == "raw_light_repair"
    assert summary["consolidated_segment_count"] == 1
    assert summary["light_repair_merged_segment_count"] == 1
    assert (batch_dir / "split_vertical" / "light_repair_rendered_execution.png").exists()


def test_choose_postprocess_candidate_prefers_local_when_local_is_already_continuous():
    mode, reason = _choose_postprocess_candidate(
        {
            "consolidated_segment_count": 2,
            "internal_max_pen_up_jump_px": 0.34,
            "avoidable_internal_max_jump_px": 0.0,
        },
        {
            "makemeahanzi_prior_available": True,
            "makemeahanzi_target_stroke_count": 3,
            "consolidated_segment_count": 3,
        },
    )

    assert mode == "local"
    assert reason == "local_already_continuous"


@pytest.mark.parametrize(
    ("regularization_meta", "expected_mode"),
    [
        pytest.param({}, "local", id="regularization-missing"),
        pytest.param({"kou_skeleton_regularization_applied": False}, "local", id="regularization-failed"),
        pytest.param({"kou_skeleton_regularization_applied": True}, "structure_primitive", id="regularization-succeeded"),
    ],
)
def test_choose_postprocess_candidate_promotes_structure_primitive_only_after_kou_regularization_succeeds(
    regularization_meta,
    expected_mode,
):
    structure_meta = {
        "structure_prior_applied": True,
        "primitive_transfer_applied": True,
        "structure_target_stroke_count": 3,
        **regularization_meta,
    }

    mode, _ = _choose_postprocess_candidate(
        {
            "consolidated_segment_count": 2,
            "internal_max_pen_up_jump_px": 0.34,
            "avoidable_internal_max_jump_px": 0.0,
            "rendered_similarity_to_input": 0.90,
        },
        {
            "makemeahanzi_prior_available": False,
            "consolidated_segment_count": 3,
            "rendered_similarity_to_input": 0.89,
        },
        structure_primitive_summary={
            "consolidated_segment_count": 3,
            "rendered_similarity_to_input": 0.95,
        },
        structure_primitive_meta=structure_meta,
    )

    assert mode == expected_mode


def test_choose_processed_postprocess_candidate_prefers_exact_single_stroke_prior_when_it_is_visibly_cleaner():
    mode, reason = _choose_processed_postprocess_candidate(
        {
            "consolidated_segment_count": 1,
            "internal_max_pen_up_jump_px": 0.0,
            "avoidable_internal_max_jump_px": 0.0,
            "min_turn_cos": -0.99,
            "rendered_similarity_to_input": 0.723,
        },
        {
            "makemeahanzi_prior_available": True,
            "makemeahanzi_target_stroke_count": 1,
            "consolidated_segment_count": 1,
            "min_turn_cos": 0.97,
            "rendered_similarity_to_input": 0.782,
        },
    )

    assert mode == "makemeahanzi_regroup"
    assert reason == "prior_exact_simple_match_is_visually_cleaner"


def test_choose_postprocess_candidate_prefers_simple_exact_local_over_fragmented_raw():
    mode, reason = _choose_postprocess_candidate(
        {
            "consolidated_segment_count": 1,
            "internal_max_pen_up_jump_px": 0.0,
            "avoidable_internal_max_jump_px": 0.0,
            "min_turn_cos": -0.99,
            "rendered_similarity_to_input": 0.723,
        },
        {
            "makemeahanzi_prior_available": True,
            "makemeahanzi_target_stroke_count": 1,
            "consolidated_segment_count": 1,
            "min_turn_cos": 0.68,
            "rendered_similarity_to_input": 0.687,
        },
        raw_summary={
            "consolidated_segment_count": 4,
            "internal_max_pen_up_jump_px": 0.0,
            "min_turn_cos": 0.999,
            "rendered_similarity_to_input": 0.722,
        },
    )

    assert mode == "local"
    assert reason == "simple_exact_local_is_visually_cleaner_than_raw"


def test_recommended_review_mode_prefers_highest_similarity_candidate():
    mode = _recommended_review_mode(
        selected_postprocess_mode="raw",
        raw_summary={"rendered_similarity_to_input": 0.72},
        light_repair_summary={"rendered_similarity_to_input": 0.79},
        local_summary={"rendered_similarity_to_input": 0.75},
        prior_summary={"rendered_similarity_to_input": 0.68},
    )

    assert mode == "raw_light_repair"


def test_review_panel_filename_for_mode_maps_candidates_to_contact_sheet_panels():
    assert _review_panel_filename_for_mode("raw") == "raw_rendered_execution.png"
    assert _review_panel_filename_for_mode("raw_light_repair") == "light_repair_rendered_execution.png"
    assert _review_panel_filename_for_mode("local") == "local_rendered_execution.png"
    assert _review_panel_filename_for_mode("makemeahanzi_regroup") == "makemeahanzi_rendered_execution.png"
    assert _review_panel_filename_for_mode("component_mix") == "component_mix_rendered_execution.png"
    assert _review_panel_filename_for_mode("structure_primitive") == "structure_primitive_rendered_execution.png"
    assert _review_panel_filename_for_mode("unknown") is None


def test_hybrid_contact_panels_keep_conservative_width_out_of_default_sheet():
    filenames = [filename for _, filename in HYBRID_CONTACT_PANELS]
    assert "conservative_width_render.png" not in filenames


def test_hybrid_contact_panels_include_review_recommended_trajectory_panel():
    filenames = [filename for _, filename in HYBRID_CONTACT_PANELS]
    assert "review_recommended_trajectory.png" in filenames


def test_segment_color_prefers_component_palette_when_requested():
    assert _segment_color({"component_id": 3}, index=0, color_by_component=True) == PALETTE[2]
    assert _segment_color({"component_id": 0}, index=2, color_by_component=True) == PALETTE[2]
    assert _segment_color({"component_id": 3}, index=1, color_by_component=False) == PALETTE[1]


def test_choose_postprocess_candidate_prefers_makemeahanzi_when_it_reduces_oversegmentation():
    mode, reason = _choose_postprocess_candidate(
        {
            "consolidated_segment_count": 6,
            "internal_max_pen_up_jump_px": 23.75,
            "avoidable_internal_max_jump_px": 0.0,
        },
        {
            "makemeahanzi_prior_available": True,
            "makemeahanzi_target_stroke_count": 4,
            "consolidated_segment_count": 4,
        },
    )

    assert mode == "makemeahanzi_regroup"
    assert reason == "prior_reduces_oversegmentation_on_discontinuous_local"


def test_choose_postprocess_candidate_rejects_prior_when_it_adds_severe_foldback():
    mode, reason = _choose_postprocess_candidate(
        {
            "consolidated_segment_count": 6,
            "internal_max_pen_up_jump_px": 23.75,
            "avoidable_internal_max_jump_px": 0.0,
            "min_turn_cos": 0.69,
        },
        {
            "makemeahanzi_prior_available": True,
            "makemeahanzi_target_stroke_count": 4,
            "consolidated_segment_count": 4,
            "min_turn_cos": -0.79,
        },
    )

    assert mode == "local"
    assert reason == "prior_introduces_severe_internal_foldback"


def test_should_promote_raw_to_light_repair_candidate_allows_structured_corner_cleanup():
    promoted = _should_promote_raw_to_light_repair_candidate(
        {
            "rendered_similarity_to_input": 0.6039,
            "internal_max_pen_up_jump_px": 0.0,
            "min_turn_cos": 0.0,
            "consolidated_segment_count": 5,
        },
        {
            "rendered_similarity_to_input": 0.8366,
            "internal_max_pen_up_jump_px": 0.0,
            "min_turn_cos": 0.0,
            "consolidated_segment_count": 5,
        },
    )

    assert promoted is True


def test_should_promote_raw_to_light_repair_candidate_allows_large_gain_fragment_cleanup():
    promoted = _should_promote_raw_to_light_repair_candidate(
        {
            "rendered_similarity_to_input": 0.6039,
            "internal_max_pen_up_jump_px": 2.94,
            "min_turn_cos": 0.98,
            "consolidated_segment_count": 5,
        },
        {
            "rendered_similarity_to_input": 0.8366,
            "internal_max_pen_up_jump_px": 1.70,
            "min_turn_cos": 0.52,
            "consolidated_segment_count": 5,
        },
    )

    assert promoted is True


def test_should_promote_raw_to_light_repair_candidate_keeps_small_gain_structured_corner_raw():
    promoted = _should_promote_raw_to_light_repair_candidate(
        {
            "rendered_similarity_to_input": 0.6845,
            "internal_max_pen_up_jump_px": 0.0,
            "min_turn_cos": 0.0,
            "consolidated_segment_count": 9,
        },
        {
            "rendered_similarity_to_input": 0.7300,
            "internal_max_pen_up_jump_px": 0.0,
            "min_turn_cos": 0.0,
            "consolidated_segment_count": 9,
        },
    )

    assert promoted is False


def test_hybrid_audit_status_skips_reorder_gap_penalty_when_makemeahanzi_prior_is_applied():
    status = _hybrid_audit_status(
        {
            "status": "ok",
            "ordered_segment_count": 8,
            "consolidated_segment_count": 6,
            "trajectory_point_count": 215,
            "internal_pen_up_jump_count": 1,
            "internal_max_pen_up_jump_px": 10.7,
            "internal_mean_pen_up_jump_px": 10.7,
            "cross_component_best_is_exact": True,
            "avoidable_cross_component_max_jump_px": 47.9,
            "makemeahanzi_prior_applied": True,
        }
    )

    assert status == "promising"


def test_hybrid_audit_status_skips_reorder_gap_penalty_when_only_prior_component_labels_are_applied():
    status = _hybrid_audit_status(
        {
            "status": "ok",
            "ordered_segment_count": 5,
            "consolidated_segment_count": 4,
            "trajectory_point_count": 153,
            "internal_pen_up_jump_count": 1,
            "internal_max_pen_up_jump_px": 5.1,
            "internal_mean_pen_up_jump_px": 5.1,
            "cross_component_best_is_exact": True,
            "avoidable_cross_component_max_jump_px": 33.3,
            "makemeahanzi_prior_applied": False,
            "makemeahanzi_component_labels_applied": True,
        }
    )

    assert status == "promising"


def test_run_callirewrite_hybrid_probe_auto_mode_promotes_xin_component_mix_candidate(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    output_dir = tmp_path / "outputs"

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["xin"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "xin" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["component_mix_applied"] is True
    assert summary["selected_postprocess_mode"] == "component_mix"
    assert "gou" in summary["registered_primitive_kinds"]
    assert summary["gou_primitive_source_sample"] == "xin"
    assert summary["gou_primitive_pointed_end"] is True
    assert summary["gou_primitive_last_relative_width"] == 0.0
    assert summary["audit_status"] == "promising"
    assert summary["internal_pen_up_jump_count"] <= 1
    assert summary["cross_component_pen_up_jump_count"] >= 1
    rendered = np.asarray(Image.open(batch_dir / "xin" / "rendered_execution.png").convert("L"))
    component_mix = np.asarray(Image.open(batch_dir / "xin" / "component_mix_rendered_execution.png").convert("L"))
    assert np.array_equal(rendered, component_mix)


def test_run_callirewrite_hybrid_probe_auto_mode_exports_and_selects_real_kou_three_stroke_primitive_candidate(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    output_dir = tmp_path / "outputs"

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["kou"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
    )

    batch_dir = Path(payload["batch_dir"])
    sample_dir = batch_dir / "kou"
    summary = json.loads((sample_dir / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["structure_prior_applied"] is True
    assert summary["kou_skeleton_regularization_applied"] is True
    assert summary["kou_hengzhe_overlap_trimmed_point_count"] >= 10
    assert summary["kou_hengzhe_axis_transition_count"] == 1
    assert summary["kou_hengzhe_horizontal_reversal_px"] <= 0.5
    assert summary["kou_hengzhe_vertical_reversal_px"] <= 0.5
    assert summary["kou_skeleton_max_displacement_px"] <= 2.5
    assert summary["kou_skeleton_foreground_support_ratio"] >= 0.90
    assert summary["primitive_transfer_applied"] is True
    assert summary["primitive_transfer_segment_count"] == 3
    assert summary["primitive_transfer_kinds"] == ["shu", "hengzhe", "heng"]
    assert summary["structure_segment_count"] == 3
    assert summary["consolidated_segment_count"] == 3
    assert summary["selected_postprocess_mode"] == "structure_primitive"
    assert summary["review_recommended_mode"] == "structure_primitive"
    assert summary["structure_primitive_rendered_execution_image"] == str(
        sample_dir / "structure_primitive_rendered_execution.png"
    )
    assert (sample_dir / "structure_primitive_rendered_execution.png").exists()
    assert Path(summary["structure_skeleton_trajectory_image"]).exists()
    assert Path(summary["structure_skeleton_overlay_image"]).exists()
    assert Path(summary["structure_skeleton_playback_contact_sheet"]).exists()
    assert summary["structure_primitive_visual_similarity_to_input"] >= max(
        summary["raw_visual_similarity_to_input"],
        summary["light_repair_visual_similarity_to_input"],
        summary["local_visual_similarity_to_input"],
        summary["makemeahanzi_visual_similarity_to_input"],
    ) - 0.10


def test_run_callirewrite_hybrid_probe_auto_mode_prefers_real_zhong_light_repair_when_it_is_cleaner_than_local(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    output_dir = tmp_path / "outputs"

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["zhong"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "zhong" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["light_repair_visual_similarity_to_input"] > summary["raw_visual_similarity_to_input"]
    assert summary["light_repair_visual_similarity_to_input"] > summary["local_visual_similarity_to_input"]
    assert summary["selected_postprocess_mode"] == "raw_light_repair"
    assert summary["position_layer_source"] == "raw_light_repair"


def test_run_callirewrite_hybrid_probe_auto_mode_exports_review_recommended_trajectory(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    output_dir = tmp_path / "outputs"

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["zhong"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "zhong" / "recovery_summary.json").read_text(encoding="utf-8"))
    review_path = Path(summary["review_recommended_trajectory_image"])
    assert review_path.exists()
    assert review_path.name == "review_recommended_trajectory.png"
    assert review_path.parent == batch_dir / "zhong"
    review_pixels = np.asarray(Image.open(review_path).convert("L"))
    final_pixels = np.asarray(Image.open(batch_dir / "zhong" / "final_trajectory.png").convert("L"))
    assert review_pixels.shape == final_pixels.shape
    assert summary["review_recommended_mode"] == summary["selected_postprocess_mode"] == "raw_light_repair"


def test_light_repair_geometry_recenters_real_zhong_bottom_bar(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"

    segments, _ = load_callirewrite_segments(converted_dir / "zhong")
    foreground_mask = _load_input_foreground_mask(input_dir / "zhong.png")
    light_repaired_raw_segments, _ = light_repair_raw_segments(segments, foreground_mask=foreground_mask)
    ordered_segments = order_segments(
        light_repaired_raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    bottom_bar_before = next(
        segment for segment in ordered_segments if tuple(segment.get("source_segment_ids", ())) == (5,)
    )
    bottom_bar_before_y_mean = float(np.mean([point[0] for point in bottom_bar_before["points"]]))

    repaired_segments, meta = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )
    bottom_bar_after = next(
        segment for segment in repaired_segments if tuple(segment.get("source_segment_ids", ())) == (5,)
    )
    bottom_bar_after_y_mean = float(np.mean([point[0] for point in bottom_bar_after["points"]]))

    assert bottom_bar_after_y_mean < bottom_bar_before_y_mean - 0.75
    assert meta["light_repair_geometry_adjusted_segment_count"] >= 2


def test_light_repair_geometry_recenters_real_zhong_top_bar_body(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"

    segments, _ = load_callirewrite_segments(converted_dir / "zhong")
    foreground_mask = _load_input_foreground_mask(input_dir / "zhong.png")
    light_repaired_raw_segments, _ = light_repair_raw_segments(segments, foreground_mask=foreground_mask)
    ordered_segments = order_segments(
        light_repaired_raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    top_bar_before = next(
        segment for segment in ordered_segments if tuple(segment.get("source_segment_ids", ())) == (7, 8)
    )
    top_body_before_y_mean = float(
        np.mean([point[0] for point in top_bar_before["points"] if 65.0 <= float(point[1]) <= 84.0])
    )

    repaired_segments, meta = light_repair_ordered_segments_geometry(
        ordered_segments,
        foreground_mask=foreground_mask,
    )
    top_bar_after = next(
        segment for segment in repaired_segments if tuple(segment.get("source_segment_ids", ())) == (7, 8)
    )
    top_body_after_y_mean = float(
        np.mean([point[0] for point in top_bar_after["points"] if 65.0 <= float(point[1]) <= 84.0])
    )

    assert top_body_after_y_mean < top_body_before_y_mean - 0.75
    assert meta["light_repair_geometry_adjusted_segment_count"] >= 3


def test_prepare_local_candidate_segments_stitches_real_yong_same_component_corner_gap(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "yong")
    foreground_mask = _load_input_foreground_mask(input_dir / "yong.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    prepared_segments, meta = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="yong",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )

    assert meta["makemeahanzi_component_labels_applied"] is True
    corner_left = next(segment for segment in prepared_segments if tuple(segment.get("source_segment_ids", ())) == (6,))
    corner_right = next(segment for segment in prepared_segments if tuple(segment.get("source_segment_ids", ())) == (8,))
    assert np.linalg.norm(np.asarray(corner_left["points"][-1]) - np.asarray(corner_right["points"][0])) <= 1e-6


def test_prepare_local_candidate_segments_uses_local_render_subpaths_for_real_kou_component_slices(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "kou")
    foreground_mask = _load_input_foreground_mask(input_dir / "kou.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
        foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    )

    prepared_segments, meta = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="kou",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )

    assert meta["makemeahanzi_component_labels_applied"] is True
    assert len(prepared_segments) == 4
    assert [len(segment.get("render_subpaths", ()) or []) for segment in prepared_segments] == [1, 1, 1, 1]
    assert [tuple(segment.get("source_segment_ids", ())) for segment in prepared_segments] == [
        (5, 4, 3, 2),
        (5, 4, 3, 2),
        (5, 4, 3, 2),
        (5, 4, 3, 2, 8),
    ]


def test_prepare_local_candidate_segments_merges_real_xin_left_short_stroke_fragments(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "xin")
    foreground_mask = _load_input_foreground_mask(input_dir / "xin.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    prepared_segments, meta = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="xin",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )

    assert meta["makemeahanzi_component_labels_applied"] is True
    merged_left_short_stroke = next(
        segment for segment in prepared_segments if tuple(segment.get("source_segment_ids", ())) == (17, 4)
    )
    assert len(prepared_segments) == 4
    assert merged_left_short_stroke["length_px"] > 20.0
    assert len(merged_left_short_stroke.get("render_subpaths", ())) == 2
    assert tuple(tuple(ids) for ids in merged_left_short_stroke.get("render_subpath_source_ids", ())) == ((17,), (4,))
    render_subpaths = [
        np.asarray(subpath, dtype=float)
        for subpath in merged_left_short_stroke.get("render_subpaths", ())
    ]
    assert float(np.linalg.norm(render_subpaths[0][-2] - render_subpaths[1][0])) <= 1e-6
    assert not any(tuple(segment.get("source_segment_ids", ())) == (17,) for segment in prepared_segments)
    assert not any(tuple(segment.get("source_segment_ids", ())) == (4,) for segment in prepared_segments)


def test_prepare_local_candidate_segments_merges_real_xin_left_short_stroke_fragments_with_runtime_blend(tmp_path: Path):
    del tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "xin")
    foreground_mask = _load_input_foreground_mask(input_dir / "xin.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
        foreground_snap_blend=DEFAULT_POSITION_LAYER_FOREGROUND_SNAP_BLEND,
    )

    prepared_segments, meta = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="xin",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )

    assert meta["makemeahanzi_component_labels_applied"] is True
    merged_left_short_stroke = next(
        segment for segment in prepared_segments if tuple(segment.get("source_segment_ids", ())) == (17, 4)
    )
    assert len(prepared_segments) == 4
    assert merged_left_short_stroke["length_px"] > 20.0
    assert len(merged_left_short_stroke.get("render_subpaths", ())) == 2
    assert tuple(tuple(ids) for ids in merged_left_short_stroke.get("render_subpath_source_ids", ())) == ((17,), (4,))
    render_subpaths = [
        np.asarray(subpath, dtype=float)
        for subpath in merged_left_short_stroke.get("render_subpaths", ())
    ]
    assert float(np.linalg.norm(render_subpaths[0][-2] - render_subpaths[1][0])) <= 1e-6
    assert not any(tuple(segment.get("source_segment_ids", ())) == (17,) for segment in prepared_segments)
    assert not any(tuple(segment.get("source_segment_ids", ())) == (4,) for segment in prepared_segments)


def test_prepare_local_candidate_segments_preserves_render_subpaths_for_real_xin_merged_wogou():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "xin")
    foreground_mask = _load_input_foreground_mask(input_dir / "xin.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    local_consolidated, _ = consolidate_ordered_segments(
        ordered_segments,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )
    prepared_segments, _ = _prepare_local_candidate_segments(
        local_consolidated,
        sample_name="xin",
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )

    merged_wogou = next(
        segment
        for segment in prepared_segments
        if tuple(segment.get("source_segment_ids", ())) == (10, 2, 3)
    )

    assert len(merged_wogou.get("render_subpaths", ())) == 3
    assert tuple(tuple(ids) for ids in merged_wogou.get("render_subpath_source_ids", ())) == ((10,), (2,), (3,))
    render_subpaths = [
        np.asarray(subpath, dtype=float)
        for subpath in merged_wogou.get("render_subpaths", ())
    ]
    assert float(np.linalg.norm(render_subpaths[0][-1] - render_subpaths[1][0])) <= 1e-6
    assert float(np.linalg.norm(render_subpaths[1][-1] - render_subpaths[2][0])) <= 1e-6


def test_restore_render_subpaths_from_source_segments_reconstructs_real_shi_vertical_merge():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"

    segments, _ = load_callirewrite_segments(converted_dir / "shi")
    foreground_mask = _load_input_foreground_mask(input_dir / "shi.png")
    ordered_segments = order_segments(
        segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    from makemeahanzi_prior import regroup_ordered_segments_by_makemeahanzi

    grouped_segments, _ = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name="shi",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
        sample_char_map=None,
    )
    consolidated_segments, _ = consolidate_ordered_segments(
        grouped_segments,
        merge_adjacent=False,
        merge_gap_px=1.5,
        direction_cos_threshold=0.35,
        simplify_tolerance_px=0.75,
        resample_step_px=1.0,
        foreground_mask=foreground_mask,
    )

    restored = _restore_render_subpaths_from_source_segments(
        consolidated_segments,
        source_segments=ordered_segments,
    )

    merged_vertical = next(
        segment
        for segment in restored
        if tuple(segment.get("source_segment_ids", ())) == (10, 2, 7)
    )

    assert len(merged_vertical.get("render_subpaths", ())) == 3
    assert tuple(tuple(ids) for ids in merged_vertical.get("render_subpath_source_ids", ())) == ((10,), (2,), (7,))


def test_run_callirewrite_hybrid_probe_auto_mode_keeps_real_yong_on_structured_candidate(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted"
    input_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    output_dir = tmp_path / "outputs"

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["yong"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
    )

    batch_dir = Path(payload["batch_dir"])
    summary = json.loads((batch_dir / "yong" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["selected_postprocess_mode"] in {"local", "makemeahanzi_regroup"}
    assert summary["audit_status"] == "promising"


def test_run_callirewrite_hybrid_probe_auto_mode_chooses_local_or_prior_per_sample(tmp_path: Path):
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    graphics_path = tmp_path / "graphics.txt"
    input_dir.mkdir(parents=True)

    char_kou = chr(0x53E3)
    char_zhong = chr(0x4E2D)

    _write_box_input_png(input_dir / "kou.png")
    _write_input_png(input_dir / "zhong.png")
    _write_converted_sample(
        converted_dir / "kou",
        sample="kou",
        segments=[
            [(12.0, 12.0), (12.0, 52.0), (52.0, 52.0), (52.0, 12.0), (12.0, 12.0)],
        ],
    )
    _write_converted_sample(
        converted_dir / "zhong",
        sample="zhong",
        segments=[
            [(12.0, 32.0), (24.0, 32.0)],
            [(24.0, 32.0), (52.0, 32.0)],
            [(32.0, 12.0), (32.0, 30.0)],
            [(32.0, 30.0), (32.0, 52.0)],
        ],
    )
    graphics_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "character": char_kou,
                        "strokes": ["a", "b", "c"],
                        "medians": [
                            [[12.0, 12.0], [52.0, 12.0]],
                            [[12.0, 12.0], [12.0, 52.0], [52.0, 52.0]],
                            [[52.0, 12.0], [52.0, 52.0]],
                        ],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "character": char_zhong,
                        "strokes": ["a", "b"],
                        "medians": [
                            [[32.0, 12.0], [32.0, 52.0]],
                            [[12.0, 32.0], [52.0, 32.0]],
                        ],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["kou", "zhong"],
        postprocess_mode="auto",
        makemeahanzi_graphics_path=graphics_path,
        sample_char_map={"kou": char_kou, "zhong": char_zhong},
    )

    batch_dir = Path(payload["batch_dir"])
    kou_summary = json.loads((batch_dir / "kou" / "recovery_summary.json").read_text(encoding="utf-8"))
    zhong_summary = json.loads((batch_dir / "zhong" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert kou_summary["selected_postprocess_mode"] == "local"
    assert kou_summary["position_layer_source"] == "local_candidate"
    assert kou_summary["makemeahanzi_target_stroke_count"] == 3
    assert zhong_summary["selected_postprocess_mode"] == "makemeahanzi_regroup"
    assert zhong_summary["makemeahanzi_target_stroke_count"] == 2
