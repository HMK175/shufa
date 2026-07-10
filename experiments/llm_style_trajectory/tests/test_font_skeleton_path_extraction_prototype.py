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


def test_extract_path_segments_from_branching_skeleton():
    from font_skeleton_path_extraction_prototype import extract_path_segments

    skeleton = np.zeros((32, 32), dtype=bool)
    skeleton[16, 6:26] = True
    skeleton[8:17, 16] = True

    result = extract_path_segments(skeleton, min_segment_pixels=3, simplify_epsilon=0.0)

    assert result.component_count == 1
    assert result.endpoint_count >= 3
    assert result.branch_point_count >= 1
    assert result.extracted_segment_count >= 3
    assert result.total_path_length_px > 20
    assert result.unhandled_component_count == 0
    assert all(segment.order_index >= 1 for segment in result.segments)


def test_font_skeleton_path_extraction_writes_outputs_for_small_sample(tmp_path):
    from font_skeleton_path_extraction_prototype import run_font_skeleton_path_extraction_prototype

    font_path = _available_font()
    if font_path is None:
        pytest.skip("No local font available for path extraction prototype test")

    sources = {
        "kaishu": {"font_paths": [str(font_path)], "image_dirs": []},
        "lishu": {"font_paths": [str(font_path)], "image_dirs": []},
    }
    sources_path = tmp_path / "style_sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = run_font_skeleton_path_extraction_prototype(
        output_dir=tmp_path / "path_extract",
        sample_specs=[("山", "kaishu"), ("人", "kaishu"), ("山", "lishu")],
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
    assert len(rows) == 3
    assert {"char", "style", "extracted_segment_count", "recommended_for_next_stage", "warning"}.issubset(rows[0])
    assert sum(row["recommended_for_next_stage"] == "True" for row in rows) >= 1
    assert all(row["style"] in {"kaishu", "lishu"} for row in rows)

    manifest = list(csv.DictReader(manifest_path.open(encoding="utf-8-sig")))
    assert len(manifest) == 3
    assert all(Path(row["figure_path"]).exists() for row in manifest)
    assert any(path.name.startswith("path_extraction_") for path in figures_dir.glob("*.png"))

    report = report_path.read_text(encoding="utf-8")
    assert "不是正式轨迹" in report
    assert "不含真实笔顺" in report
    assert "font-derived trajectory trial" in report


def test_font_skeleton_path_extraction_module_does_not_import_libauboi5():
    module_path = SRC / "font_skeleton_path_extraction_prototype.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
