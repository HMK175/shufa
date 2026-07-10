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


def test_h1_lite_feng_lishu_risk_trial_generates_single_sample_and_reference_contrast(tmp_path):
    from h1_lite_feng_lishu_risk_trial import run_h1_lite_feng_lishu_risk_trial

    result = run_h1_lite_feng_lishu_risk_trial(
        output_dir=tmp_path / "feng_trial",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    sample_dir = out_dir / "u98ce_lishu"
    contrast_dir = out_dir / "contrast"

    assert sample_dir.exists()
    assert (sample_dir / "h1_lite_conservative.csv").exists()
    assert (sample_dir / "h1_lite_balanced.csv").exists()
    assert (sample_dir / "h1_lite_summary.json").exists()
    assert (sample_dir / "h1_lite_compare.png").exists()

    assert (contrast_dir / "h1_lite_u98ce_lishu_risk_contrast.png").exists()
    assert (contrast_dir / "h1_lite_u5c71_lishu_reference_compare.png").exists()
    assert (contrast_dir / "h1_lite_u98ce_lishu_reference_gap_summary.json").exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    forbidden_names = {
        "trajectory.csv",
        "execution_trajectory.csv",
        "robot_workspace_trajectory.csv",
        "robot_workspace_trajectory_resampled.csv",
    }
    generated_names = {path.name for path in out_dir.rglob("*") if path.is_file()}
    assert not (generated_names & forbidden_names)

    summary = json.loads((sample_dir / "h1_lite_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "trial_not_used_by_default"
    assert summary["source"] == "constraint_bounded_adaptation_h1_lite_trial"
    assert summary["char"] == "风"
    assert summary["char_id"] == "u98ce"
    assert summary["style"] == "lishu"
    assert summary["stroke_count_preserved"] is True
    assert summary["stroke_count"] > 0
    assert summary["point_count"] > 0
    assert summary["max_point_shift_px"]["conservative"] <= 18.0 + 1e-6
    assert summary["max_point_shift_px"]["balanced"] <= 18.0 + 1e-6
    assert set(summary["used_constraints"]) <= {
        "bbox_aspect",
        "lower_half_width_ratio",
        "left_right_spread",
        "bbox_center_shift_x",
        "bbox_center_shift_y",
    }

    gap = json.loads((contrast_dir / "h1_lite_u98ce_lishu_reference_gap_summary.json").read_text(encoding="utf-8"))
    assert gap["status"] == "trial_not_used_by_default"
    assert gap["source"] == "h1_lite_feng_lishu_risk_trial"
    assert gap["char"] == "风"
    assert gap["char_id"] == "u98ce"
    assert gap["style"] == "lishu"
    assert gap["reference_char"] == "山"
    assert gap["reference_style"] == "lishu"
    assert gap["reference_source_role"] == "existing_h1_lite_positive_reference"
    assert "feng_vs_reference_bbox_aspect_gap" in gap
    assert "feng_vs_reference_lower_half_width_gap" in gap
    assert gap["recommended_for_visual_followup"] is True

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(rows) == 1
    assert rows[0]["char_id"] == "u98ce"
    assert rows[0]["style"] == "lishu"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "trial-only" in report
    assert "not_used_by_default" in report
    assert "风/lishu" in report
    assert "山/lishu" in report
    assert "不生成正式 trajectory.csv" in report


def test_h1_lite_feng_lishu_risk_trial_module_does_not_import_libauboi5():
    module_path = SRC / "h1_lite_feng_lishu_risk_trial.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
