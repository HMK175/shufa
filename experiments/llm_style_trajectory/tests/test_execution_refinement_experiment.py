from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "experiments" / "llm_style_trajectory" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_execution_csv(path: Path, *, style: str) -> None:
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
    rows = [
        [1, 1, 0, 10, 10, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [1, 1, 1, 20, 20, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [2, 2, 0, 20, 20, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
        [2, 2, 1, 24, 24, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
        [3, 2, 0, 24, 24, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [3, 2, 1, 34, 34, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [4, 3, 0, 34, 34, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
        [4, 3, 1, 160, 160, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
        [5, 3, 0, 160, 160, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [5, 3, 1, 170, 180, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
    ]
    if style != "xingkai":
        rows = [row for row in rows if row[11] != "connector"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        writer.writerows(rows)


def _write_fake_cases(tmp_path: Path) -> Path:
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
    cases = [("国", "xingkai"), ("人", "kaishu")]
    cases_csv = tmp_path / "cases.csv"
    with cases_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for char, style in cases:
            sample_dir = tmp_path / f"u{ord(char):04x}_{style}_sample"
            _write_execution_csv(sample_dir / "execution_trajectory.csv", style=style)
            (sample_dir / "summary.json").write_text(
                json.dumps({"char": char, "style": style, "style_modifiers": {"connection_preference": "weak"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            writer.writerow(
                {
                    "char": char,
                    "style": style,
                    "case_type": "test",
                    "source_output_dir": str(sample_dir),
                    "connection_count": 2 if style == "xingkai" else 0,
                    "connector_draw_length": 100 if style == "xingkai" else 0,
                    "connector_mean_width": 4 if style == "xingkai" else 0,
                    "connector_mean_pressure": 0.35 if style == "xingkai" else 0,
                    "mean_width": 9,
                    "aspect_ratio": 1,
                    "diagnostic_focus": "fake",
                    "needs_user_review": "true",
                }
            )
    return cases_csv


def test_execution_refinement_experiment_outputs_summary_report_and_figures(tmp_path):
    from execution_refinement_experiment import run_execution_refinement_experiment

    cases_csv = _write_fake_cases(tmp_path)
    result = run_execution_refinement_experiment(
        cases_csv=cases_csv,
        output_dir=tmp_path / "out",
        copy_to_paper=False,
    )

    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["cases_csv"]).exists()
    assert Path(result["figures_dir"]).exists()

    with Path(result["summary_csv"]).open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    xingkai = next(row for row in rows if row["style"] == "xingkai")
    kaishu = next(row for row in rows if row["style"] == "kaishu")
    assert int(xingkai["after_connection_count"]) < int(xingkai["before_connection_count"])
    assert float(xingkai["after_stroke_width_range"]) > 0.0
    assert int(kaishu["after_connection_count"]) == 0

    figure_names = {path.name for path in Path(result["figures_dir"]).glob("*.png")}
    assert "before_after_connector_u56fd_xingkai.png" in figure_names
    assert "stroke_taper_u4eba_kaishu.png" in figure_names

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "本轮不是最终参数" in report
    assert "本轮颜色只为可读性" in report


def test_execution_refinement_experiment_does_not_import_libauboi5():
    module_path = SRC / "execution_refinement_experiment.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
