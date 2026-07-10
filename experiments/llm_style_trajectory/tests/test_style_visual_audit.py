from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "experiments" / "llm_style_trajectory" / "src"
sys.path.insert(0, str(SRC))


def _write_fake_summary(path: Path) -> None:
    fields = [
        "char",
        "style",
        "task",
        "success",
        "failure_reason",
        "output_dir",
        "aspect_ratio",
        "path_length",
        "bbox_width",
        "bbox_height",
        "connection_count",
        "connector_draw_length",
        "mean_width",
        "workspace_path_length_mm",
        "execution_render_png",
        "preview_png",
    ]
    rows = [
        ("山", "kaishu", 1.0, 100.0, 0, 0.0, 9.0, 80.0),
        ("山", "xingkai", 1.05, 130.0, 3, 180.0, 8.0, 86.0),
        ("山", "lishu", 1.9, 98.0, 0, 0.0, 10.0, 82.0),
        ("中", "kaishu", 1.0, 90.0, 0, 0.0, 9.0, 70.0),
        ("中", "xingkai", 1.01, 91.0, 0, 5.0, 8.0, 71.0),
        ("中", "lishu", 1.02, 89.0, 0, 0.0, 10.0, 70.5),
        ("永", "kaishu", 0.95, 120.0, 0, 0.0, 9.0, 100.0),
        ("永", "xingkai", 1.0, 300.0, 8, 900.0, 7.5, 180.0),
        ("永", "lishu", 1.35, 118.0, 0, 0.0, 10.0, 101.0),
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for char, style, aspect, path_len, conn_count, conn_len, width, workspace_len in rows:
            output_dir = path.parent / f"{char}_{style}"
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "execution_render.png"
            if not (char == "中" and style == "lishu"):
                image_path.write_bytes(b"fake-png")
            writer.writerow(
                {
                    "char": char,
                    "style": style,
                    "task": f"写一个{style}风格的{char}",
                    "success": "True",
                    "failure_reason": "",
                    "output_dir": str(output_dir),
                    "aspect_ratio": aspect,
                    "path_length": path_len,
                    "bbox_width": 100.0 * aspect,
                    "bbox_height": 100.0,
                    "connection_count": conn_count,
                    "connector_draw_length": conn_len,
                    "mean_width": width,
                    "workspace_path_length_mm": workspace_len,
                    "execution_render_png": str(image_path),
                    "preview_png": "",
                }
            )


def test_visual_audit_generates_candidates_report_checklist_and_manifest(tmp_path):
    from style_visual_audit import run_visual_audit

    diagnostic_dir = tmp_path / "diagnostics"
    diagnostic_dir.mkdir()
    _write_fake_summary(diagnostic_dir / "style_diagnostic_summary.csv")

    result = run_visual_audit(diagnostic_dir=diagnostic_dir, output_dir=tmp_path / "audit")

    assert result["candidate_count"] > 0
    assert result["outputs"]["candidates_csv"].exists()
    assert result["outputs"]["report_md"].exists()
    assert result["outputs"]["checklist_md"].exists()
    assert result["outputs"]["manifest_csv"].exists()

    with result["outputs"]["candidates_csv"].open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    case_types = {row["case_type"] for row in rows}
    assert "high_aspect_spread" in case_types
    assert "low_aspect_spread" in case_types
    assert "long_xingkai_connector" in case_types
    assert "representative" in case_types

    unique_keys = {(row["char"], row["style"], row["case_type"]) for row in rows}
    assert len(unique_keys) == len(rows)

    report_text = result["outputs"]["report_md"].read_text(encoding="utf-8")
    assert "人工看图" in report_text
    assert "人工校验" in report_text
    assert "不能只看指标" in report_text


def test_manifest_allows_missing_image_with_output_dir_fallback(tmp_path):
    from style_visual_audit import run_visual_audit

    diagnostic_dir = tmp_path / "diagnostics"
    diagnostic_dir.mkdir()
    _write_fake_summary(diagnostic_dir / "style_diagnostic_summary.csv")

    result = run_visual_audit(diagnostic_dir=diagnostic_dir, output_dir=tmp_path / "audit")

    with result["outputs"]["manifest_csv"].open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows
    assert all(row["image_path"] or row["output_dir"] or row["fallback_ref"] for row in rows)


def test_style_visual_audit_does_not_import_libauboi5():
    module_path = SRC / "style_visual_audit.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
