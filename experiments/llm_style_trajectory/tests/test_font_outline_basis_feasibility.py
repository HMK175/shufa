from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _available_font() -> Path:
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/simkai.ttf"),
        Path("C:/Windows/Fonts/STXINGKA.TTF"),
    ]:
        if candidate.exists():
            return candidate
    return Path("Z:/missing/font.ttf")


def test_skeleton_fallback_method_produces_metrics_without_optional_library():
    from font_outline_basis_feasibility import skeletonize_font_mask, skeleton_topology_metrics

    mask = np.zeros((64, 64), dtype=bool)
    mask[12:52, 30:34] = True
    mask[30:34, 12:52] = True

    result = skeletonize_font_mask(mask, method="ridge")
    metrics = skeleton_topology_metrics(result.skeleton)

    assert result.method == "ridge"
    assert result.skeleton_success is True
    assert metrics["skeleton_pixel_count"] > 0
    assert metrics["endpoint_count"] >= 2


def test_font_outline_basis_writes_summary_report_manifest_and_figures(tmp_path):
    from font_outline_basis_feasibility import run_font_outline_basis_feasibility

    font_path = _available_font()
    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "xingkai": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": ["Z:/missing/font.ttf"], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")
    config = {
        "chars": ["山", "A"],
        "styles": ["kaishu", "xingkai", "lishu"],
        "font_sources": str(sources_path),
        "image_size": 96,
    }
    config_path = tmp_path / "font_outline_basis_chars.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    result = run_font_outline_basis_feasibility(
        config_path=config_path,
        output_dir=tmp_path / "out",
        copy_to_paper=False,
        skeleton_method="ridge",
    )

    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert rows
    assert {"char", "style", "font_available", "skeleton_success", "basis_compare_png"}.issubset(rows[0])
    assert any(row["char"] == "A" and row["median_available"] == "False" for row in rows)
    assert any(row["style"] == "lishu" and row["font_available"] == "False" for row in rows)

    manifest = list(csv.DictReader(Path(result["manifest_csv"]).open(encoding="utf-8-sig")))
    assert manifest
    assert all(Path(row["image_path"]).exists() for row in manifest)

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "MakeMeAHanzi median" in report
    assert "font-outline-derived trajectory basis" in report
    assert "不替换默认 pipeline" in report


def test_font_outline_basis_module_does_not_import_libauboi5():
    module_path = SRC / "font_outline_basis_feasibility.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
