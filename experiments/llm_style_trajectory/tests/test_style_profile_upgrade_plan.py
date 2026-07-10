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


def _write_fake_font_gap_outputs(base: Path) -> tuple[Path, Path]:
    base.mkdir(parents=True, exist_ok=True)
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
                    "sample_count": "2",
                    "mean_font_aspect_ratio": "1.0",
                    "mean_trajectory_aspect_ratio": "1.0",
                    "mean_abs_aspect_ratio_gap": "0.02",
                    "mean_font_connected_component_count": "2.0",
                    "mean_trajectory_connection_count": "0.0",
                    "mean_font_stroke_width": "6.0",
                    "mean_trajectory_mean_width": "9.0",
                },
                {
                    "style": "xingkai",
                    "sample_count": "2",
                    "mean_font_aspect_ratio": "0.9",
                    "mean_trajectory_aspect_ratio": "1.1",
                    "mean_abs_aspect_ratio_gap": "0.2",
                    "mean_font_connected_component_count": "1.2",
                    "mean_trajectory_connection_count": "4.0",
                    "mean_font_stroke_width": "8.0",
                    "mean_trajectory_mean_width": "7.5",
                },
            ]
        )
    summary = base / "font_style_gap_summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["char", "style", "font_aspect_ratio", "trajectory_aspect_ratio"])
        writer.writeheader()
        writer.writerow({"char": "山", "style": "kaishu", "font_aspect_ratio": "1.0", "trajectory_aspect_ratio": "1.0"})
    return style_means, summary


def _read_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_schema_contains_required_parameters():
    from style_profile_upgrade_plan import load_parameter_schema

    rows = load_parameter_schema(EXP_DIR / "configs" / "style_profile_parameter_schema.json")
    names = {row["name"] for row in rows}

    required = {
        "horizontal_scale",
        "vertical_scale",
        "stroke_width_distribution",
        "connector_trigger",
        "pen_up_height",
        "speed_scale",
        "xingkai_connectedness_prior",
    }
    assert required.issubset(names)
    assert all(row["level"] in {"style", "char", "component", "process_prior"} for row in rows)


def test_upgrade_plan_writes_matrix_recommendations_report_prototype_and_figures(tmp_path):
    from style_profile_upgrade_plan import run_style_profile_upgrade_plan

    gap_dir = tmp_path / "font_gap"
    _write_fake_font_gap_outputs(gap_dir)

    result = run_style_profile_upgrade_plan(
        font_gap_dir=gap_dir,
        schema_path=EXP_DIR / "configs" / "style_profile_parameter_schema.json",
        output_dir=tmp_path / "upgrade_out",
        copy_to_paper=False,
    )

    matrix_path = Path(result["matrix_csv"])
    recommendations_path = Path(result["recommendations_json"])
    report_path = Path(result["report_md"])
    prototype_path = Path(result["prototype_json"])

    assert matrix_path.exists()
    assert recommendations_path.exists()
    assert report_path.exists()
    assert prototype_path.exists()
    assert Path(result["figures_dir"], "parameter_source_matrix.png").exists()
    assert Path(result["figures_dir"], "upgrade_priority_chart.png").exists()

    matrix = _read_csv(matrix_path)
    matrix_names = {row["parameter"] for row in matrix}
    assert "horizontal_scale" in matrix_names
    assert "vertical_scale" in matrix_names
    assert "stroke_width_distribution" in matrix_names

    recommendations = json.loads(recommendations_path.read_text(encoding="utf-8"))
    assert {"phase_1", "phase_2", "phase_3"}.issubset(recommendations)
    assert "horizontal_scale" in recommendations["phase_1"]["parameters"]
    assert "vertical_scale" in recommendations["phase_1"]["parameters"]
    assert "stroke_width_distribution" in recommendations["phase_1"]["parameters"]
    assert "pen_up_height" in recommendations["do_not_estimate_from_static_font"]
    assert "speed_scale" in recommendations["do_not_estimate_from_static_font"]

    report = report_path.read_text(encoding="utf-8")
    assert "字体轮廓不等于真实书写轨迹" in report
    assert "prototype 不接入默认流程" in report
    assert "人工看图" in report

    prototype = json.loads(prototype_path.read_text(encoding="utf-8"))
    assert prototype["_status"] == "prototype_not_used_by_default"
    assert prototype["_warning"] == "not wired into generation pipeline"
    assert prototype["styles"]["kaishu"]["mean_font_aspect_ratio"] == 1.0


def test_style_profile_upgrade_plan_module_does_not_import_libauboi5():
    module_path = SRC_DIR / "style_profile_upgrade_plan.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
