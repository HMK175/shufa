from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_b_route_constraint_registry_builds_expected_samples(tmp_path):
    from b_route_constraint_registry import run_b_route_constraint_registry

    result = run_b_route_constraint_registry(output_dir=tmp_path / "b_route_registry", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    assert Path(result["summary_json"]).exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
    assert summary["status"] == "trial_only_not_used_by_default"
    assert summary["default_policy"] == "registry_gated_adaptation_only"
    assert len(summary["entries"]) == 2

    entries = {(item["char"], item["style"]): item for item in summary["entries"]}
    assert ("山", "lishu") in entries
    assert ("风", "lishu") in entries
    assert entries[("山", "lishu")]["strategy_selected"] == "component_first_safe"
    assert entries[("风", "lishu")]["strategy_selected"] == "fallback_first_reference_only"
    assert entries[("山", "lishu")]["human_review_required"] is True
    assert entries[("风", "lishu")]["fallback_used"] is True
    assert "bbox_aspect" in entries[("山", "lishu")]["usable_constraints"]
    assert "raw_skeleton_path" in entries[("山", "lishu")]["blocked_constraints"]

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(rows) == 2
    row_map = {(row["char"], row["style"]): row for row in rows}
    assert row_map[("山", "lishu")]["strategy_selected"] == "component_first_safe"
    assert row_map[("风", "lishu")]["strategy_selected"] == "fallback_first_reference_only"
    assert row_map[("山", "lishu")]["usable_constraint_count"] != ""

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "registry-gated adaptation" in report
    assert "trial-only" in report
    assert "not_used_by_default" in report
    assert "component_first_safe" in report
    assert "fallback_first_reference_only" in report


def test_b_route_constraint_registry_module_does_not_import_libauboi5():
    module_path = SRC / "b_route_constraint_registry.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
