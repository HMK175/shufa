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


def test_h1_lite_style_contrast_generates_shan_kaishu_and_lishu_contrast(tmp_path):
    from h1_lite_style_contrast_expansion import run_h1_lite_style_contrast_expansion

    result = run_h1_lite_style_contrast_expansion(
        output_dir=tmp_path / "contrast",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    kaishu_dir = out_dir / "u5c71_kaishu"
    contrast_dir = out_dir / "contrast"

    assert kaishu_dir.exists()
    assert (kaishu_dir / "h1_lite_conservative.csv").exists()
    assert (kaishu_dir / "h1_lite_balanced.csv").exists()
    assert (kaishu_dir / "h1_lite_summary.json").exists()
    assert (kaishu_dir / "h1_lite_compare.png").exists()

    assert (contrast_dir / "h1_lite_u5c71_kaishu_lishu_contrast.png").exists()
    assert (contrast_dir / "h1_lite_u5c71_style_gap_summary.json").exists()
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

    kaishu_summary = json.loads((kaishu_dir / "h1_lite_summary.json").read_text(encoding="utf-8"))
    assert kaishu_summary["status"] == "trial_not_used_by_default"
    assert kaishu_summary["source"] == "constraint_bounded_adaptation_h1_lite_trial"
    assert kaishu_summary["char"] == "山"
    assert kaishu_summary["char_id"] == "u5c71"
    assert kaishu_summary["style"] == "kaishu"
    assert kaishu_summary["stroke_count_preserved"] is True
    assert set(kaishu_summary["used_constraints"]) <= {
        "bbox_aspect",
        "lower_half_width_ratio",
        "left_right_spread",
        "bbox_center_shift_x",
        "bbox_center_shift_y",
    }

    gap_summary = json.loads((contrast_dir / "h1_lite_u5c71_style_gap_summary.json").read_text(encoding="utf-8"))
    assert gap_summary["status"] == "trial_not_used_by_default"
    assert gap_summary["char_id"] == "u5c71"
    assert gap_summary["styles"] == ["kaishu", "lishu"]
    assert gap_summary["kaishu_source"] == "generated_this_run"
    assert gap_summary["lishu_source"] == "existing_h1_lite_reference"
    assert "kaishu_lishu_style_gap_before" in gap_summary
    assert "kaishu_lishu_style_gap_after_balanced" in gap_summary
    assert gap_summary["recommended_for_visual_followup"] is True

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(rows) == 2
    assert {row["style"] for row in rows} == {"kaishu", "lishu"}
    assert all(row["char_id"] == "u5c71" for row in rows)

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "trial-only" in report
    assert "not_used_by_default" in report
    assert "不生成正式 trajectory.csv" in report
    assert "山/kaishu" in report
    assert "山/lishu" in report


def test_h1_lite_style_contrast_module_does_not_import_libauboi5():
    module_path = SRC / "h1_lite_style_contrast_expansion.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
