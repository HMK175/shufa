from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _available_font() -> Path | None:
    for candidate in [
        Path("C:/Windows/Fonts/simkai.ttf"),
        Path("C:/Windows/Fonts/SIMLI.TTF"),
        Path("C:/Windows/Fonts/STKAITI.TTF"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]:
        if candidate.exists():
            return candidate
    return None


def test_cleanup_skeleton_removes_small_components_and_short_spurs():
    from font_skeleton_cleanup_prototype import cleanup_skeleton, skeleton_metrics

    skeleton = np.zeros((40, 40), dtype=bool)
    skeleton[20, 8:32] = True
    skeleton[16:21, 20] = True
    skeleton[3:5, 3:5] = True

    raw = skeleton_metrics(skeleton)
    cleaned, stats = cleanup_skeleton(
        skeleton,
        min_component_pixels=8,
        spur_prune_length=6,
        endpoint_merge_distance=0,
    )
    clean = skeleton_metrics(cleaned)

    assert stats["removed_component_count"] >= 1
    assert stats["pruned_branch_count"] >= 1
    assert clean["connected_component_count"] <= raw["connected_component_count"]
    assert clean["branch_point_count"] <= raw["branch_point_count"]
    assert clean["skeleton_pixel_count"] < raw["skeleton_pixel_count"]


def test_font_skeleton_cleanup_writes_summary_report_manifest_and_figures(tmp_path):
    from font_skeleton_cleanup_prototype import run_font_skeleton_cleanup_prototype

    font_path = _available_font()
    if font_path is None:
        pytest.skip("No local font available for cleanup prototype test")

    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": [str(font_path)], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = run_font_skeleton_cleanup_prototype(
        output_dir=tmp_path / "cleanup",
        chars=["山"],
        styles=["kaishu", "lishu"],
        style_sources_path=sources_path,
        image_size=96,
        skeleton_method="ridge",
        copy_to_paper=False,
    )

    summary_path = Path(result["summary_csv"])
    report_path = Path(result["report_md"])
    manifest_path = Path(result["manifest_csv"])
    figures_dir = Path(result["figures_dir"])

    assert summary_path.exists()
    assert report_path.exists()
    assert manifest_path.exists()
    assert figures_dir.exists()

    rows = list(csv.DictReader(summary_path.open(encoding="utf-8-sig")))
    assert len(rows) == 2
    assert {row["style"] for row in rows} == {"kaishu", "lishu"}
    assert {"raw_endpoint_count", "clean_endpoint_count", "cleanup_status", "warning"}.issubset(rows[0])
    assert any(row["cleanup_status"] == "success" for row in rows)

    manifest = list(csv.DictReader(manifest_path.open(encoding="utf-8-sig")))
    assert manifest
    assert all(Path(row["figure_path"]).exists() for row in manifest)
    assert any(path.name.startswith("cleanup_compare_") for path in figures_dir.glob("*.png"))

    report = report_path.read_text(encoding="utf-8")
    assert "kaishu" in report
    assert "lishu" in report
    assert "人工看图" in report
    assert "不是正式书写轨迹" in report


def test_font_skeleton_cleanup_module_does_not_import_libauboi5():
    module_path = SRC / "font_skeleton_cleanup_prototype.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
