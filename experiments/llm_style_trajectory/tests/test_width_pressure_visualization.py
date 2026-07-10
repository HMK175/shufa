from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "experiments" / "llm_style_trajectory" / "src"
sys.path.insert(0, str(SRC))


def _write_execution_csv(path: Path, *, with_connector: bool, constant_stroke: bool) -> None:
    fields = [
        "segment_id",
        "stroke_id",
        "point_id",
        "y",
        "x",
        "z",
        "speed",
        "pressure",
        "width",
        "pen_down",
        "is_connector",
        "segment_type",
        "connection_preference",
    ]
    stroke_widths = [8.0, 8.0, 8.0] if constant_stroke else [6.0, 8.0, 10.0]
    rows = [
        [0, 1, 0, 20, 20, 0, 1.0, 0.8, stroke_widths[0], 1, 0, "stroke", "weak"],
        [0, 1, 1, 35, 35, 0, 1.0, 0.9, stroke_widths[1], 1, 0, "stroke", "weak"],
        [0, 1, 2, 50, 40, 0, 1.0, 1.0, stroke_widths[2], 1, 0, "stroke", "weak"],
    ]
    if with_connector:
        rows.extend(
            [
                [1, -1, 0, 50, 40, 0, 1.4, 0.30, 3.0, 1, 1, "connector", "weak"],
                [1, -1, 1, 62, 52, 0, 1.4, 0.35, 4.0, 1, 1, "connector", "weak"],
            ]
        )
    rows.extend(
        [
            [2, 2, 0, 62, 52, 0, 1.0, 0.95, stroke_widths[-1], 1, 0, "stroke", "weak"],
            [2, 2, 1, 70, 60, 0, 1.0, 0.95, stroke_widths[-1], 1, 0, "stroke", "weak"],
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        writer.writerows(rows)


def _write_cases(base: Path) -> Path:
    fields = [
        "char",
        "style",
        "case_type",
        "source_output_dir",
        "generated_figure",
        "connection_count",
        "connector_draw_length",
        "connector_mean_width",
        "connector_mean_pressure",
        "mean_width",
        "aspect_ratio",
        "diagnostic_focus",
        "needs_user_review",
    ]
    samples = [
        ("国", "xingkai", True, False),
        ("人", "kaishu", False, True),
    ]
    cases_csv = base / "connector_brush_diagnostic_cases.csv"
    with cases_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for char, style, has_connector, constant_stroke in samples:
            sample_dir = base / f"u{ord(char):04x}_{style}_sample"
            _write_execution_csv(
                sample_dir / "execution_trajectory.csv",
                with_connector=has_connector,
                constant_stroke=constant_stroke,
            )
            writer.writerow(
                {
                    "char": char,
                    "style": style,
                    "case_type": "long_xingkai_connector" if has_connector else "style_side_by_side",
                    "source_output_dir": str(sample_dir),
                    "generated_figure": "",
                    "connection_count": "1" if has_connector else "0",
                    "connector_draw_length": "20" if has_connector else "0",
                    "connector_mean_width": "3.5" if has_connector else "0",
                    "connector_mean_pressure": "0.32" if has_connector else "0",
                    "mean_width": "8",
                    "aspect_ratio": "1.0",
                    "diagnostic_focus": "fake",
                    "needs_user_review": "true",
                }
            )
    return cases_csv


def test_width_pressure_visualization_generates_global_and_per_image_outputs(tmp_path):
    from width_pressure_visualization import run_width_pressure_visualization

    cases_csv = _write_cases(tmp_path)
    result = run_width_pressure_visualization(
        cases_csv=cases_csv,
        output_dir=tmp_path / "out",
        value_mode="both",
        normalization="both",
        copy_to_paper=False,
    )

    outputs = result["outputs"]
    assert outputs["report_md"].exists()
    assert outputs["manifest_csv"].exists()
    assert outputs["value_ranges_json"].exists()

    figures = list(outputs["figures_dir"].glob("*.png"))
    names = {path.name for path in figures}
    assert "width_global_u56fd_xingkai.png" in names
    assert "pressure_global_u56fd_xingkai.png" in names
    assert "width_per_image_u56fd_xingkai.png" in names
    assert "width_global_u4eba_kaishu.png" in names

    with outputs["manifest_csv"].open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert "needs_user_review" in rows[0]
    assert any(row["normalization"] == "global" for row in rows)
    assert any(row["normalization"] == "per-image" for row in rows)
    assert any(row["stroke_width_nearly_constant"] == "true" for row in rows)
    assert any(row["connector_width_min"] == "" for row in rows)


def test_report_mentions_manual_review_and_no_parameter_tuning(tmp_path):
    from width_pressure_visualization import run_width_pressure_visualization

    cases_csv = _write_cases(tmp_path)
    result = run_width_pressure_visualization(
        cases_csv=cases_csv,
        output_dir=tmp_path / "out",
        value_mode="width",
        normalization="global",
        copy_to_paper=False,
    )
    report = result["outputs"]["report_md"].read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "本轮不调参数" in report
    assert "不能只看指标" in report
    assert "stroke width nearly constant" in report


def test_visualization_uses_non_white_light_colors_and_records_readability_settings(tmp_path):
    from width_pressure_visualization import run_width_pressure_visualization, visual_color_diagnostics

    cases_csv = _write_cases(tmp_path)
    result = run_width_pressure_visualization(
        cases_csv=cases_csv,
        output_dir=tmp_path / "out",
        value_mode="width",
        normalization="global",
        background_color="#f7f7f2",
        stroke_light_color="#6baed6",
        stroke_dark_color="#08306b",
        connector_light_color="#b07d62",
        connector_dark_color="#5a2a1a",
        min_alpha=0.55,
        min_visible_linewidth=1.2,
        copy_to_paper=False,
    )

    diagnostics = visual_color_diagnostics(
        background_color="#f7f7f2",
        stroke_light_color="#6baed6",
        connector_light_color="#b07d62",
        min_alpha=0.55,
        min_visible_linewidth=1.2,
    )
    assert diagnostics["stroke_light_distance_from_white"] > 0.05
    assert diagnostics["connector_light_distance_from_white"] > 0.05
    assert diagnostics["min_alpha"] == 0.55
    assert diagnostics["min_visible_linewidth"] == 1.2

    report = result["outputs"]["report_md"].read_text(encoding="utf-8")
    assert "本轮颜色只为可读性" in report
    assert "#f7f7f2" in report
    assert "min_alpha" in report


def test_width_pressure_visualization_does_not_import_libauboi5():
    module_path = SRC / "width_pressure_visualization.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
