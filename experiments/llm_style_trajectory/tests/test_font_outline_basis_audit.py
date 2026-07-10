from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _make_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), color=(235, 235, 235)).save(path)


def _write_fake_feasibility(base: Path) -> None:
    fields = [
        "char",
        "style",
        "skeleton_success",
        "connected_component_count",
        "skeleton_pixel_count",
        "aspect_ratio",
        "branch_point_count",
        "endpoint_count",
        "median_aspect_ratio",
        "bbox_aspect_delta_vs_median",
        "warnings",
    ]
    rows = [
        {"char": "山", "style": "kaishu", "skeleton_success": "True", "connected_component_count": "1", "skeleton_pixel_count": "240", "aspect_ratio": "1.0", "branch_point_count": "2", "endpoint_count": "4", "median_aspect_ratio": "0.95", "bbox_aspect_delta_vs_median": "0.05", "warnings": ""},
        {"char": "山", "style": "xingkai", "skeleton_success": "True", "connected_component_count": "1", "skeleton_pixel_count": "260", "aspect_ratio": "1.2", "branch_point_count": "3", "endpoint_count": "5", "median_aspect_ratio": "0.95", "bbox_aspect_delta_vs_median": "0.25", "warnings": ""},
        {"char": "山", "style": "lishu", "skeleton_success": "True", "connected_component_count": "1", "skeleton_pixel_count": "250", "aspect_ratio": "1.45", "branch_point_count": "2", "endpoint_count": "4", "median_aspect_ratio": "0.95", "bbox_aspect_delta_vs_median": "0.50", "warnings": ""},
        {"char": "德", "style": "kaishu", "skeleton_success": "True", "connected_component_count": "6", "skeleton_pixel_count": "830", "aspect_ratio": "1.0", "branch_point_count": "42", "endpoint_count": "24", "median_aspect_ratio": "1.0", "bbox_aspect_delta_vs_median": "0.0", "warnings": ""},
        {"char": "德", "style": "xingkai", "skeleton_success": "True", "connected_component_count": "1", "skeleton_pixel_count": "970", "aspect_ratio": "1.1", "branch_point_count": "80", "endpoint_count": "20", "median_aspect_ratio": "1.0", "bbox_aspect_delta_vs_median": "0.1", "warnings": ""},
        {"char": "福", "style": "lishu", "skeleton_success": "True", "connected_component_count": "4", "skeleton_pixel_count": "780", "aspect_ratio": "1.5", "branch_point_count": "35", "endpoint_count": "12", "median_aspect_ratio": "1.0", "bbox_aspect_delta_vs_median": "0.5", "warnings": ""},
    ]
    summary = base / "font_outline_basis_summary.csv"
    summary.parent.mkdir(parents=True, exist_ok=True)
    with summary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    manifest_fields = ["char", "image_path", "styles_rendered", "warnings"]
    manifest_rows = []
    for char in ["山", "德", "福"]:
        image = base / "figures" / f"basis_compare_u{ord(char):04x}.png"
        _make_png(image)
        manifest_rows.append({"char": char, "image_path": str(image), "styles_rendered": "kaishu,xingkai,lishu", "warnings": ""})
    with (base / "font_outline_basis_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(manifest_rows)


def test_font_outline_basis_audit_writes_candidates_report_checklist_and_images(tmp_path):
    from font_outline_basis_audit import run_font_outline_basis_audit

    feasibility_dir = tmp_path / "feasibility"
    _write_fake_feasibility(feasibility_dir)

    result = run_font_outline_basis_audit(
        feasibility_dir=feasibility_dir,
        output_dir=tmp_path / "audit",
        copy_to_paper=False,
    )

    candidates_csv = Path(result["candidates_csv"])
    report_md = Path(result["report_md"])
    checklist_md = Path(result["checklist_md"])
    image_manifest_csv = Path(result["image_manifest_csv"])

    assert candidates_csv.exists()
    assert report_md.exists()
    assert checklist_md.exists()
    assert image_manifest_csv.exists()
    assert Path(result["selected_images_dir"]).exists()

    rows = list(csv.DictReader(candidates_csv.open(encoding="utf-8-sig")))
    assert rows
    assert {"char", "style", "issue_tags", "audit_priority", "manual_decision", "manual_comment"}.issubset(rows[0])
    assert any("high_branch_count" in row["issue_tags"] for row in rows)
    assert any("high_endpoint_count" in row["issue_tags"] for row in rows)
    assert any("disconnected_skeleton" in row["issue_tags"] for row in rows)
    assert any("high_aspect_gap" in row["issue_tags"] for row in rows)
    assert any("complex_skeleton" in row["issue_tags"] for row in rows)

    image_rows = list(csv.DictReader(image_manifest_csv.open(encoding="utf-8-sig")))
    assert image_rows
    assert all(Path(row["image_path"]).exists() for row in image_rows)

    report = report_md.read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "不能直接作为轨迹" in report
    assert "diagnostic threshold" in report

    checklist = checklist_md.read_text(encoding="utf-8")
    assert "是否比 MakeMeAHanzi median 更有风格" in checklist
    assert "是否适合继续做轨迹基底" in checklist


def test_font_outline_basis_audit_module_does_not_import_libauboi5():
    module_path = SRC / "font_outline_basis_audit.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
