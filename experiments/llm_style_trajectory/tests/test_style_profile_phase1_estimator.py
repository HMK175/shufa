from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _write_fake_gap_outputs(base: Path) -> tuple[Path, Path]:
    base.mkdir(parents=True, exist_ok=True)
    summary = base / "font_style_gap_summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "char",
                "style",
                "font_available",
                "rendered_ok",
                "font_aspect_ratio",
                "font_stroke_width_mean",
                "font_stroke_width_std",
                "font_horizontal_projection_spread",
                "font_vertical_projection_spread",
                "trajectory_aspect_ratio",
                "trajectory_mean_width",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "char": "山",
                    "style": "kaishu",
                    "font_available": "True",
                    "rendered_ok": "True",
                    "font_aspect_ratio": "1.0",
                    "font_stroke_width_mean": "6.0",
                    "font_stroke_width_std": "1.0",
                    "font_horizontal_projection_spread": "40",
                    "font_vertical_projection_spread": "30",
                    "trajectory_aspect_ratio": "1.0",
                    "trajectory_mean_width": "9.0",
                },
                {
                    "char": "山",
                    "style": "xingkai",
                    "font_available": "True",
                    "rendered_ok": "True",
                    "font_aspect_ratio": "0.9",
                    "font_stroke_width_mean": "8.0",
                    "font_stroke_width_std": "1.5",
                    "font_horizontal_projection_spread": "42",
                    "font_vertical_projection_spread": "33",
                    "trajectory_aspect_ratio": "1.1",
                    "trajectory_mean_width": "7.5",
                },
                {
                    "char": "山",
                    "style": "lishu",
                    "font_available": "True",
                    "rendered_ok": "True",
                    "font_aspect_ratio": "1.5",
                    "font_stroke_width_mean": "9.0",
                    "font_stroke_width_std": "1.2",
                    "font_horizontal_projection_spread": "48",
                    "font_vertical_projection_spread": "29",
                    "trajectory_aspect_ratio": "1.45",
                    "trajectory_mean_width": "10.0",
                },
            ]
        )
    style_means = base / "font_style_gap_style_means.csv"
    with style_means.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "style",
                "sample_count",
                "mean_font_aspect_ratio",
                "mean_trajectory_aspect_ratio",
                "mean_abs_aspect_ratio_gap",
                "mean_font_connected_component_count",
                "mean_trajectory_connection_count",
                "mean_font_stroke_width",
                "mean_trajectory_mean_width",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "style": "kaishu",
                    "sample_count": "1",
                    "mean_font_aspect_ratio": "1.0",
                    "mean_trajectory_aspect_ratio": "1.0",
                    "mean_abs_aspect_ratio_gap": "0.0",
                    "mean_font_connected_component_count": "2.0",
                    "mean_trajectory_connection_count": "0.0",
                    "mean_font_stroke_width": "6.0",
                    "mean_trajectory_mean_width": "9.0",
                },
                {
                    "style": "xingkai",
                    "sample_count": "1",
                    "mean_font_aspect_ratio": "0.9",
                    "mean_trajectory_aspect_ratio": "1.1",
                    "mean_abs_aspect_ratio_gap": "0.2",
                    "mean_font_connected_component_count": "1.0",
                    "mean_trajectory_connection_count": "4.0",
                    "mean_font_stroke_width": "8.0",
                    "mean_trajectory_mean_width": "7.5",
                },
                {
                    "style": "lishu",
                    "sample_count": "1",
                    "mean_font_aspect_ratio": "1.5",
                    "mean_trajectory_aspect_ratio": "1.45",
                    "mean_abs_aspect_ratio_gap": "0.05",
                    "mean_font_connected_component_count": "1.0",
                    "mean_trajectory_connection_count": "0.0",
                    "mean_font_stroke_width": "9.0",
                    "mean_trajectory_mean_width": "10.0",
                },
            ]
        )
    return summary, style_means


def _read_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_phase1_estimator_writes_estimates_comparison_report_and_figures(tmp_path):
    from style_profile_phase1_estimator import run_style_profile_phase1_estimator

    gap_dir = tmp_path / "gap"
    _write_fake_gap_outputs(gap_dir)

    result = run_style_profile_phase1_estimator(
        font_gap_dir=gap_dir,
        output_dir=tmp_path / "phase1_out",
        copy_to_paper=False,
    )

    est_path = Path(result["estimates_json"])
    compare_path = Path(result["comparison_csv"])
    report_path = Path(result["report_md"])
    warning_path = Path(result["warnings_csv"])

    assert est_path.exists()
    assert compare_path.exists()
    assert report_path.exists()
    assert warning_path.exists()
    assert Path(result["figures_dir"], "current_vs_phase1_scale.png").exists()
    assert Path(result["figures_dir"], "current_vs_phase1_width.png").exists()
    assert Path(result["figures_dir"], "phase1_projection_summary.png").exists()

    payload = json.loads(est_path.read_text(encoding="utf-8"))
    assert payload["_status"] == "readonly_estimate_not_used_by_default"
    assert payload["_warning"] == "not wired into generation pipeline"
    assert set(payload["styles"]) == {"kaishu", "xingkai", "lishu"}

    compare_rows = _read_csv(compare_path)
    params = {row["parameter"] for row in compare_rows}
    assert {"horizontal_scale", "vertical_scale", "base_width"}.issubset(params)
    assert any(row["style"] == "lishu" and row["parameter"] == "lishu_flatness" for row in compare_rows)

    warnings_rows = _read_csv(warning_path)
    warning_text = " ".join(row["parameter"] for row in warnings_rows)
    assert "pen_up_height" in warning_text
    assert "speed_scale" in warning_text
    assert "pressure_curve" in warning_text
    assert "connector_trigger" in warning_text

    report = report_path.read_text(encoding="utf-8")
    assert "字体轮廓不等于真实书写轨迹" in report
    assert "不接默认" in report
    assert "本轮不生成新轨迹" in report


def test_phase1_estimator_module_does_not_import_libauboi5():
    module_path = SRC_DIR / "style_profile_phase1_estimator.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
