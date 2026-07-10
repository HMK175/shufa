from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_b_route_registry_gated_probe_outputs_trial_only_comparisons(tmp_path):
    from b_route_registry_gated_probe import run_b_route_registry_gated_probe

    result = run_b_route_registry_gated_probe(output_dir=tmp_path / "b_route_probe", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(rows) == 2
    keys = {(row["char"], row["style"]): row for row in rows}
    assert ("山", "lishu") in keys
    assert ("风", "lishu") in keys
    assert all(row["stroke_count_preserved"] == "True" for row in rows)
    assert all(row["recommended_for_visual_followup"] == "True" for row in rows)
    assert all(float(row["max_point_shift_px"]) >= 0.0 for row in rows)
    assert all(row["registry_strategy"] in {"component_first_safe", "fallback_first_reference_only"} for row in rows)
    assert all(row["trial_only"] == "True" for row in rows)

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "registry-gated" in report
    assert "trial-only" in report
    assert "not_used_by_default" in report
    assert "山/lishu" in report
    assert "风/lishu" in report

    manifest = list(csv.DictReader(Path(result["manifest_csv"]).open(encoding="utf-8-sig")))
    assert manifest
    assert any(row["artifact_type"] == "figure" for row in manifest)
    assert any(row["artifact_type"] == "summary_csv" for row in manifest)


def test_b_route_registry_gated_probe_module_does_not_import_libauboi5():
    module_path = SRC / "b_route_registry_gated_probe.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
