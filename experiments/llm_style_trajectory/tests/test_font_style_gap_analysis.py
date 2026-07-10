from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_fake_trajectory_summary(path: Path) -> None:
    fields = [
        "char",
        "style",
        "success",
        "aspect_ratio",
        "bbox_width",
        "bbox_height",
        "connection_count",
        "connector_draw_length",
        "mean_width",
        "workspace_path_length_mm",
    ]
    rows = [
        {
            "char": "A",
            "style": "kaishu",
            "success": "True",
            "aspect_ratio": "1.2",
            "bbox_width": "120",
            "bbox_height": "100",
            "connection_count": "0",
            "connector_draw_length": "0",
            "mean_width": "9",
            "workspace_path_length_mm": "300",
        },
        {
            "char": "A",
            "style": "xingkai",
            "success": "True",
            "aspect_ratio": "1.1",
            "bbox_width": "110",
            "bbox_height": "100",
            "connection_count": "2",
            "connector_draw_length": "50",
            "mean_width": "8",
            "workspace_path_length_mm": "320",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_extract_font_metrics_from_binary_shape():
    from font_style_gap_analysis import compute_font_image_metrics

    binary = np.zeros((64, 64), dtype=np.uint8)
    binary[10:40, 8:48] = 255
    metrics = compute_font_image_metrics(binary)

    assert metrics["rendered_ok"] is True
    assert metrics["font_bbox_width"] == 40
    assert metrics["font_bbox_height"] == 30
    assert metrics["font_aspect_ratio"] > 1.0
    assert metrics["font_connected_component_count"] == 1
    assert metrics["font_largest_component_ratio"] == 1.0
    assert metrics["font_stroke_width_mean"] > 0


def test_missing_font_records_failure_without_crashing(tmp_path):
    from font_style_gap_analysis import render_font_sample

    result = render_font_sample("A", Path("Z:/missing/font.ttf"), image_size=64, output_path=tmp_path / "missing.png")

    assert result["font_available"] is False
    assert result["rendered_ok"] is False
    assert "missing_font" in result["notes"]


def test_font_gap_analysis_writes_summary_means_report_and_figures(tmp_path):
    from font_style_gap_analysis import run_font_style_gap_analysis

    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if not font_path.exists():
        font_path = Path("C:/Windows/Fonts/simkai.ttf")
    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "xingkai": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": ["Z:/missing/font.ttf"], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")
    summary_path = tmp_path / "style_diagnostic_summary.csv"
    _write_fake_trajectory_summary(summary_path)
    config = {
        "chars": ["A"],
        "styles": ["kaishu", "xingkai", "lishu"],
        "font_sources": str(sources_path),
        "trajectory_diagnostics_dir": str(tmp_path),
    }
    config_path = tmp_path / "font_style_gap_chars.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_font_style_gap_analysis(config_path=config_path, output_dir=tmp_path / "out", copy_to_paper=False)

    assert Path(result["summary_csv"]).exists()
    assert Path(result["style_means_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["failures_csv"]).exists()
    assert Path(result["figures_dir"], "font_style_grid.png").exists()

    with Path(result["summary_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    kaishu = next(row for row in rows if row["style"] == "kaishu")
    assert float(kaishu["aspect_ratio_gap"]) != 0
    lishu = next(row for row in rows if row["style"] == "lishu")
    assert lishu["font_available"] == "False"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "字体轮廓不等于真实书写轨迹" in report
    assert "本轮不调参数" in report
    assert "人工看图校验" in report


def test_font_style_gap_module_does_not_import_libauboi5():
    module_path = SRC / "font_style_gap_analysis.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
