import csv
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_style_profiles import (
    DEFAULT_PROFILE_KEYS,
    build_estimated_profiles,
    compare_profiles,
    compute_binary_metrics,
    load_style_sources,
    render_style_samples,
    write_profile_outputs,
)
from planner import load_style_profiles


def test_style_sources_config_loads_three_styles():
    sources = load_style_sources(EXP_DIR / "configs" / "style_sources.json")

    assert {"kaishu", "xingkai", "lishu"}.issubset(sources.keys())
    for style in ["kaishu", "xingkai", "lishu"]:
        assert "font_paths" in sources[style]
        assert "image_dirs" in sources[style]


def test_missing_font_is_skipped_without_traceback(tmp_path):
    config_path = tmp_path / "style_sources.json"
    config_path.write_text(
        json.dumps(
            {
                "kaishu": {
                    "font_paths": [str(tmp_path / "missing-font.ttf")],
                    "image_dirs": [],
                }
            }
        ),
        encoding="utf-8",
    )
    sources = load_style_sources(config_path)

    rows, rendered = render_style_samples(
        sources,
        chars=["山"],
        image_size=64,
        output_dir=tmp_path / "rendered",
        config_dir=config_path.parent,
    )

    assert rendered == []
    assert len(rows) == 1
    assert rows[0]["style"] == "kaishu"
    assert rows[0]["render_success"] is False
    assert "missing" in rows[0]["note"]


def test_compute_binary_metrics_for_toy_image():
    img = np.zeros((20, 20), dtype=np.uint8)
    img[5:15, 8:12] = 255

    metrics = compute_binary_metrics(img)

    assert metrics["render_success"] is True
    assert metrics["bbox_width"] == 4
    assert metrics["bbox_height"] == 10
    assert metrics["aspect_ratio"] == 0.4
    assert 0.09 <= metrics["foreground_ratio"] <= 0.11
    assert metrics["connected_components"] == 1
    assert metrics["estimated_stroke_width"] > 0
    assert metrics["out_of_bounds"] is False


def test_estimated_profile_and_comparison_are_complete(tmp_path):
    metrics_rows = [
        {
            "style": "kaishu",
            "render_success": True,
            "aspect_ratio": 1.0,
            "turning": 0.2,
            "estimated_stroke_width": 8.0,
            "foreground_ratio": 0.2,
            "center_offset": 0.05,
        },
        {
            "style": "lishu",
            "render_success": True,
            "aspect_ratio": 1.4,
            "turning": 0.3,
            "estimated_stroke_width": 10.0,
            "foreground_ratio": 0.24,
            "center_offset": 0.08,
        },
    ]
    manual = json.loads((EXP_DIR / "configs" / "style_profiles.json").read_text(encoding="utf-8"))

    estimated = build_estimated_profiles(metrics_rows, manual)
    comparisons = compare_profiles(manual, estimated)
    outputs = write_profile_outputs(
        output_dir=tmp_path,
        metrics_rows=metrics_rows,
        estimated_profiles=estimated,
        comparison_rows=comparisons,
        rendered_samples=[],
    )

    for style in ["kaishu", "xingkai", "lishu"]:
        assert style in estimated
        for key in DEFAULT_PROFILE_KEYS:
            assert key in estimated[style]
            assert "value" in estimated[style][key]
            assert estimated[style][key]["source"] in {"estimated", "default_prior"}

    assert any(row["parameter"] == "horizontal_scale" for row in comparisons)
    profile_path = Path(outputs["style_profile_estimated"])
    assert profile_path.exists()
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    assert isinstance(data["kaishu"]["horizontal_scale"], (int, float))
    assert data["_parameter_sources"]["kaishu"]["horizontal_scale"] in {"estimated", "default_prior"}
    loaded_for_demo = load_style_profiles(profile_path)
    assert "_parameter_sources" not in loaded_for_demo
    assert isinstance(loaded_for_demo["kaishu"]["horizontal_scale"], float)

    with Path(outputs["comparison_csv"]).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {"style", "parameter", "manual_value", "estimated_value", "source"}.issubset(rows[0].keys())
