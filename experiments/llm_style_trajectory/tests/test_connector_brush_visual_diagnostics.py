from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "experiments" / "llm_style_trajectory" / "src"
sys.path.insert(0, str(SRC))


def _write_execution_csv(path: Path, with_connector: bool = True) -> None:
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
        (0, 0, 0, 20, 20, 0, 1.0, 1.0, 8.0, 1, 0, "stroke", "weak"),
        (0, 0, 1, 40, 40, 0, 1.0, 1.0, 8.5, 1, 0, "stroke", "weak"),
    ]
    if with_connector:
        rows.extend(
            [
                (1, -1, 0, 40, 40, 0, 1.5, 0.35, 3.0, 1, 1, "connector", "weak"),
                (1, -1, 1, 55, 55, 0, 1.5, 0.35, 3.0, 1, 1, "connector", "weak"),
            ]
        )
    else:
        rows.extend(
            [
                (1, -1, 0, 40, 40, 8, 2.0, 0.0, 0.0, 0, 0, "pen_up_move", "none"),
                (1, -1, 1, 55, 55, 8, 2.0, 0.0, 0.0, 0, 0, "pen_up_move", "none"),
            ]
        )
    rows.extend(
        [
            (2, 1, 0, 55, 55, 0, 1.0, 1.0, 8.0, 1, 0, "stroke", "weak"),
            (2, 1, 1, 70, 45, 0, 1.0, 1.0, 8.5, 1, 0, "stroke", "weak"),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        writer.writerows(rows)


def _write_candidates_and_samples(base: Path) -> tuple[Path, Path]:
    diagnostic_dir = base / "style_diagnostics"
    visual_dir = base / "style_visual_audit"
    diagnostic_dir.mkdir()
    visual_dir.mkdir()

    summary_fields = [
        "char",
        "style",
        "success",
        "output_dir",
        "aspect_ratio",
        "path_length",
        "bbox_width",
        "bbox_height",
        "connection_count",
        "connector_draw_length",
        "mean_width",
        "mean_pressure",
        "connector_mean_width",
        "connector_mean_pressure",
        "workspace_path_length_mm",
        "execution_trajectory_csv",
        "execution_render_png",
    ]
    rows = []
    for char in ["国", "德", "福", "人", "中", "和", "好", "风"]:
        for style in ["kaishu", "lishu", "xingkai"]:
            sample_dir = diagnostic_dir / f"u{ord(char):04x}_{style}_sample"
            execution_csv = sample_dir / "execution_trajectory.csv"
            _write_execution_csv(execution_csv, with_connector=style == "xingkai")
            render_png = sample_dir / "execution_render.png"
            render_png.write_bytes(b"not-a-real-image-but-path-exists")
            rows.append(
                {
                    "char": char,
                    "style": style,
                    "success": "True",
                    "output_dir": str(sample_dir),
                    "aspect_ratio": "1.8" if style == "lishu" else "1.0",
                    "path_length": "500",
                    "bbox_width": "180" if style == "lishu" else "120",
                    "bbox_height": "100" if style == "lishu" else "120",
                    "connection_count": "4" if style == "xingkai" else "0",
                    "connector_draw_length": "320" if style == "xingkai" else "0",
                    "mean_width": "8",
                    "mean_pressure": "0.9",
                    "connector_mean_width": "3" if style == "xingkai" else "0",
                    "connector_mean_pressure": "0.35" if style == "xingkai" else "0",
                    "workspace_path_length_mm": "250",
                    "execution_trajectory_csv": str(execution_csv),
                    "execution_render_png": str(render_png),
                }
            )
    with (diagnostic_dir / "style_diagnostic_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(rows)

    candidate_fields = [
        "char",
        "style",
        "case_type",
        "reason",
        "priority",
        "image_path",
        "summary_row_ref",
        "output_dir",
        "aspect_ratio",
        "path_length",
        "connection_count",
        "connector_draw_length",
        "mean_width",
        "workspace_path_length_mm",
        "manual_check_focus",
    ]
    candidate_rows = [
        ("国", "xingkai", "long_xingkai_connector"),
        ("德", "xingkai", "long_xingkai_connector"),
        ("福", "xingkai", "long_xingkai_connector"),
        ("人", "lishu", "high_lishu_aspect"),
        ("中", "kaishu", "low_aspect_spread"),
        ("中", "lishu", "low_aspect_spread"),
        ("中", "xingkai", "low_aspect_spread"),
        ("和", "kaishu", "representative"),
        ("和", "lishu", "representative"),
        ("和", "xingkai", "representative"),
    ]
    with (visual_dir / "visual_audit_candidates.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=candidate_fields)
        writer.writeheader()
        summary_by_key = {(row["char"], row["style"]): row for row in rows}
        for char, style, case_type in candidate_rows:
            row = summary_by_key[(char, style)]
            writer.writerow(
                {
                    "char": char,
                    "style": style,
                    "case_type": case_type,
                    "reason": case_type,
                    "priority": "1",
                    "image_path": row["execution_render_png"],
                    "summary_row_ref": f"{char}-{style}",
                    "output_dir": row["output_dir"],
                    "aspect_ratio": row["aspect_ratio"],
                    "path_length": row["path_length"],
                    "connection_count": row["connection_count"],
                    "connector_draw_length": row["connector_draw_length"],
                    "mean_width": row["mean_width"],
                    "workspace_path_length_mm": row["workspace_path_length_mm"],
                    "manual_check_focus": "check connector and brush visibility",
                }
            )
    return visual_dir, diagnostic_dir


def test_connector_brush_diagnostics_generates_report_cases_manifest_and_figures(tmp_path):
    from connector_brush_visual_diagnostics import run_connector_brush_diagnostics

    visual_dir, diagnostic_dir = _write_candidates_and_samples(tmp_path)
    result = run_connector_brush_diagnostics(
        visual_audit_dir=visual_dir,
        diagnostic_dir=diagnostic_dir,
        output_dir=tmp_path / "out",
        copy_to_paper=False,
    )

    outputs = result["outputs"]
    assert outputs["report_md"].exists()
    assert outputs["cases_csv"].exists()
    assert outputs["manifest_csv"].exists()
    assert outputs["segment_legend_png"].exists()
    assert any(path.name.startswith("connector_overlay") for path in outputs["figures_dir"].glob("*.png"))

    with outputs["cases_csv"].open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert "needs_user_review" in rows[0]
    assert any(row["case_type"] == "long_xingkai_connector" for row in rows)

    report = outputs["report_md"].read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "不能只看指标" in report
    assert "本轮不调参数" in report
    assert "灰线" in report


def test_connector_brush_diagnostics_handles_missing_sample_without_crashing(tmp_path):
    from connector_brush_visual_diagnostics import run_connector_brush_diagnostics

    visual_dir, diagnostic_dir = _write_candidates_and_samples(tmp_path)
    with (visual_dir / "visual_audit_candidates.csv").open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "缺",
                "xingkai",
                "long_xingkai_connector",
                "missing sample",
                "1",
                "",
                "missing",
                str(tmp_path / "does_not_exist"),
                "1.0",
                "0",
                "1",
                "100",
                "8",
                "0",
                "missing fallback",
            ]
        )

    result = run_connector_brush_diagnostics(
        visual_audit_dir=visual_dir,
        diagnostic_dir=diagnostic_dir,
        output_dir=tmp_path / "out",
        copy_to_paper=False,
    )

    report = result["outputs"]["report_md"].read_text(encoding="utf-8")
    assert "Warnings" in report
    assert "missing" in report.lower()
    with result["outputs"]["manifest_csv"].open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert all(row["generated_figure"] or row["source_output_dir"] for row in rows)


def test_connector_brush_visual_diagnostics_does_not_import_libauboi5():
    module_path = SRC / "connector_brush_visual_diagnostics.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
