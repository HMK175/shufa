import csv
import json
import math
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from render_eval import (
    compute_brush_widths,
    chamfer_distance,
    compute_render_eval_metrics,
    evaluate_batch,
    evaluate_batch_both,
    load_trajectory_csv,
    load_brush_profiles,
    mask_bbox_metrics,
    render_target_style,
    render_style_brush_mask,
    render_trajectory_mask,
)


def _write_trajectory(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y", "x"])
        writer.writerows(rows)


def test_nan_pen_up_does_not_connect_segments(tmp_path):
    csv_path = tmp_path / "trajectory.csv"
    _write_trajectory(
        csv_path,
        [
            ("10", "10"),
            ("10", "20"),
            ("nan", "nan"),
            ("10", "40"),
            ("10", "50"),
            ("nan", "nan"),
        ],
    )

    strokes = load_trajectory_csv(csv_path)
    mask = render_trajectory_mask(strokes, canvas_size=64, stroke_width=1)

    assert len(strokes) == 2
    assert mask[10, 15] > 0
    assert mask[10, 45] > 0
    assert mask[10, 30] == 0


def test_simple_line_renders_non_empty_mask(tmp_path):
    csv_path = tmp_path / "trajectory.csv"
    _write_trajectory(csv_path, [("5", "5"), ("5", "25"), ("nan", "nan")])

    mask = render_trajectory_mask(load_trajectory_csv(csv_path), canvas_size=40, stroke_width=3)

    assert int(mask.sum()) > 0


def test_iou_and_chamfer_protect_empty_masks():
    empty = np.zeros((32, 32), dtype=np.uint8)
    filled = np.zeros((32, 32), dtype=np.uint8)
    filled[10:15, 10:15] = 255

    metrics = compute_render_eval_metrics(empty, filled)

    assert metrics["iou"] == 0.0
    assert metrics["chamfer_distance"] is None
    assert math.isfinite(chamfer_distance(filled, filled))


def test_bbox_aspect_and_center_fields_complete():
    rendered = np.zeros((32, 32), dtype=np.uint8)
    target = np.zeros((32, 32), dtype=np.uint8)
    rendered[8:18, 10:14] = 255
    target[7:17, 9:13] = 255

    metrics = compute_render_eval_metrics(rendered, target)
    bbox = mask_bbox_metrics(rendered)

    for key in [
        "bbox_width",
        "bbox_height",
        "aspect_ratio",
        "aspect_ratio_error",
        "center_offset",
        "foreground_ratio_rendered",
        "foreground_ratio_target",
        "out_of_bounds",
    ]:
        assert key in metrics
    assert bbox["bbox_width"] == 4
    assert bbox["bbox_height"] == 10


def test_missing_font_is_reported_without_traceback(tmp_path):
    config_path = tmp_path / "style_sources.json"
    config_path.write_text(
        json.dumps({"kaishu": {"font_paths": [str(tmp_path / "missing.ttf")], "image_dirs": []}}),
        encoding="utf-8",
    )

    target, info = render_target_style("山", "kaishu", config_path, canvas_size=64)

    assert target is None
    assert info["target_render_success"] is False
    assert "missing" in info["note"]


def test_batch_summary_is_generated(tmp_path):
    batch_dir = tmp_path / "batch"
    demo_dir = batch_dir / "u5c71_kaishu_demo"
    demo_dir.mkdir(parents=True)
    _write_trajectory(demo_dir / "trajectory.csv", [("5", "5"), ("5", "25"), ("nan", "nan")])
    (demo_dir / "plan.json").write_text(
        json.dumps(
            {
                "char": "山",
                "style": "kaishu",
                "stroke_plan": {"stroke_count": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (demo_dir / "summary.json").write_text(
        json.dumps({"point_count": 2, "stroke_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    config_path = tmp_path / "style_sources.json"
    config_path.write_text(
        json.dumps({"kaishu": {"font_paths": [str(tmp_path / "missing.ttf")], "image_dirs": []}}),
        encoding="utf-8",
    )

    result = evaluate_batch(batch_dir, style_sources_path=config_path, canvas_size=64, stroke_width=2, renderer="fixed")

    summary_path = Path(result["render_eval_summary_csv"])
    assert summary_path.exists()
    assert summary_path.name == "render_eval_fixed_summary.csv"
    with summary_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["char"] == "山"
    assert rows[0]["target_render_success"] == "False"
    assert rows[0]["renderer"] == "fixed"


def test_batch_both_generates_fixed_and_brush_summaries(tmp_path):
    batch_dir = tmp_path / "batch"
    for style in ["kaishu", "xingkai"]:
        demo_dir = batch_dir / f"u5c71_{style}_demo"
        demo_dir.mkdir(parents=True)
        _write_trajectory(demo_dir / "trajectory.csv", [("5", "5"), ("5", "25"), ("nan", "nan")])
        (demo_dir / "plan.json").write_text(
            json.dumps({"char": "山", "style": style, "stroke_plan": {"stroke_count": 1}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (demo_dir / "summary.json").write_text(json.dumps({"point_count": 2, "stroke_count": 1}, ensure_ascii=False), encoding="utf-8")
    config_path = tmp_path / "style_sources.json"
    config_path.write_text(
        json.dumps(
            {
                "kaishu": {"font_paths": [str(tmp_path / "missing.ttf")], "image_dirs": []},
                "xingkai": {"font_paths": [str(tmp_path / "missing.ttf")], "image_dirs": []},
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_batch_both(batch_dir, style_sources_path=config_path, canvas_size=64, stroke_width=2)

    assert Path(result["fixed"]["render_eval_summary_csv"]).name == "render_eval_fixed_summary.csv"
    assert Path(result["style_brush"]["render_eval_summary_csv"]).name == "render_eval_style_brush_summary.csv"
    assert (batch_dir / "render_compare_brush_u5c71.png").exists()


def test_style_brush_renders_non_empty_and_differs_from_fixed():
    stroke = np.asarray([[8.0, 8.0], [8.0, 28.0], [18.0, 38.0], [28.0, 38.0]])
    strokes = [stroke]
    brush = load_brush_profiles()["kaishu"]

    fixed = render_trajectory_mask(strokes, canvas_size=48, stroke_width=int(brush["base_width"]))
    brushed = render_style_brush_mask(strokes, brush, canvas_size=48)

    assert int(brushed.sum()) > 0
    assert not np.array_equal(fixed, brushed)


def test_brush_widths_stay_in_min_max_and_turn_gets_wider():
    stroke = np.asarray(
        [
            [10.0, 10.0],
            [10.0, 24.0],
            [10.0, 38.0],
            [24.0, 38.0],
            [38.0, 38.0],
        ]
    )
    brush = {
        "base_width": 8,
        "min_width": 3,
        "max_width": 14,
        "start_taper": 0.2,
        "end_taper": 0.2,
        "turn_width_gain": 0.8,
        "horizontal_width_gain": 0.0,
        "vertical_width_gain": 0.0,
        "antialias_scale": 2,
    }

    widths = compute_brush_widths(stroke, brush)

    assert float(widths.min()) >= brush["min_width"]
    assert float(widths.max()) <= brush["max_width"]
    assert widths[2] >= np.mean([widths[1], widths[3]])


def test_style_brush_keeps_nan_pen_up_gap(tmp_path):
    csv_path = tmp_path / "trajectory.csv"
    _write_trajectory(
        csv_path,
        [
            ("10", "10"),
            ("10", "20"),
            ("nan", "nan"),
            ("10", "44"),
            ("10", "54"),
            ("nan", "nan"),
        ],
    )
    brush = load_brush_profiles()["kaishu"] | {"max_width": 5, "base_width": 3, "min_width": 1}

    mask = render_style_brush_mask(load_trajectory_csv(csv_path), brush, canvas_size=64)

    assert mask[10, 15] > 0
    assert mask[10, 49] > 0
    assert mask[10, 32] == 0
