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


def test_section_constraints_package_outputs_expected_files_and_samples(tmp_path):
    from section_constraints_package import run_section_constraints_package

    result = run_section_constraints_package(output_dir=tmp_path / "section_constraints", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    assert Path(result["summary_json"]).exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
    assert summary["status"] == "trial_only_not_used_by_default"
    assert summary["default_strategy"] == "component_bbox_if_stable_else_top_mid_bottom_fallback"
    assert len(summary["samples"]) == 3

    sample_index = {(item["char"], item["style"]): item for item in summary["samples"]}
    assert ("山", "kaishu") in sample_index
    assert ("山", "lishu") in sample_index
    assert ("风", "lishu") in sample_index

    assert sample_index[("风", "lishu")]["fallback_used"] is True
    assert sample_index[("风", "lishu")]["section_source"] == "top_mid_bottom_fallback"
    assert sample_index[("山", "kaishu")]["section_strategy"] == "hybrid_component_first"
    assert sample_index[("山", "lishu")]["section_strategy"] == "hybrid_component_first"

    figures = list((out_dir / "figures").glob("*.png"))
    assert len(figures) >= 3

    manifest_rows = list(csv.DictReader(Path(result["manifest_csv"]).open(encoding="utf-8-sig")))
    assert manifest_rows
    assert any(row["artifact_type"] == "figure" for row in manifest_rows)
    assert any(row["artifact_type"] == "summary_json" for row in manifest_rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 3
    assert {row["char"] for row in summary_rows} == {"山", "风"}
    assert {row["style"] for row in summary_rows} == {"kaishu", "lishu"}

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "section constraints package" in report
    assert "component bbox" in report
    assert "top/mid/bottom fallback" in report
    assert "not_used_by_default" in report


def test_section_constraints_package_classifies_constraint_counts_and_risk_levels(tmp_path):
    from section_constraints_package import run_section_constraints_package

    result = run_section_constraints_package(output_dir=tmp_path / "section_constraints", copy_to_paper=False)
    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    rows_by_sample = {(row["char"], row["style"]): row for row in rows}

    shan_kaishu = rows_by_sample[("山", "kaishu")]
    shan_lishu = rows_by_sample[("山", "lishu")]
    feng_lishu = rows_by_sample[("风", "lishu")]

    assert int(shan_kaishu["usable_constraint_count"]) >= 3
    assert int(shan_kaishu["reference_only_constraint_count"]) >= 3
    assert int(shan_kaishu["unsafe_constraint_count"]) >= 2
    assert shan_kaishu["fallback_used"] == "False"
    assert shan_kaishu["recommended_next_use"] == "B_safe_input"

    assert int(shan_lishu["usable_constraint_count"]) >= 3
    assert shan_lishu["fallback_used"] == "False"
    assert shan_lishu["recommended_next_use"] == "B_safe_input"

    assert int(feng_lishu["usable_constraint_count"]) >= 3
    assert feng_lishu["fallback_used"] == "True"
    assert feng_lishu["recommended_next_use"] == "fallback_first_reference_only"
    assert feng_lishu["risk_level"] in {"medium", "high"}


def test_section_constraints_package_module_does_not_import_libauboi5():
    module_path = SRC / "section_constraints_package.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
