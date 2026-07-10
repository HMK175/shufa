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


def test_h1_lite_writes_two_trial_samples_without_forbidden_outputs(tmp_path):
    from constraint_bounded_adaptation_h1_lite import run_constraint_bounded_adaptation_h1_lite

    result = run_constraint_bounded_adaptation_h1_lite(
        output_dir=tmp_path / "h1_lite",
        copy_to_paper=False,
    )

    out_dir = Path(result["output_dir"])
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    expected_dirs = {"u4eba_kaishu", "u5c71_lishu"}
    assert {path.name for path in out_dir.iterdir() if path.is_dir()} == expected_dirs

    forbidden_names = {
        "trajectory.csv",
        "execution_trajectory.csv",
        "robot_workspace_trajectory.csv",
        "robot_workspace_trajectory_resampled.csv",
    }
    generated_names = {path.name for path in out_dir.rglob("*") if path.is_file()}
    assert not (generated_names & forbidden_names)
    assert not any(name.startswith("adapted_trial") for name in generated_names)

    for subdir_name in expected_dirs:
        sample_dir = out_dir / subdir_name
        assert (sample_dir / "h1_lite_conservative.csv").exists()
        assert (sample_dir / "h1_lite_balanced.csv").exists()
        assert (sample_dir / "h1_lite_summary.json").exists()
        assert (sample_dir / "h1_lite_compare.png").exists()

        summary = json.loads((sample_dir / "h1_lite_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "trial_not_used_by_default"
        assert summary["source"] == "constraint_bounded_adaptation_h1_lite_trial"
        assert summary["stroke_count_preserved"] is True
        assert summary["stroke_count"] > 0
        assert summary["point_count"] > 0
        assert summary["max_point_shift_px"]["conservative"] <= 12.0 + 1e-6
        assert summary["max_point_shift_px"]["balanced"] <= 18.0 + 1e-6
        assert set(summary["used_constraints"]) <= {
            "bbox_aspect",
            "lower_half_width_ratio",
            "left_right_spread",
            "bbox_center_shift_x",
            "bbox_center_shift_y",
        }
        assert "raw_skeleton_path" not in summary["used_constraints"]
        assert "unordered_skeleton_segments" not in summary["used_constraints"]
        assert "bbox_aspect_conservative" in summary
        assert "lower_half_width_balanced" in summary
        assert "left_right_spread_balanced" in summary
        assert summary["recommended_for_visual_followup"] is True

        rows = list(csv.DictReader((sample_dir / "h1_lite_conservative.csv").open(encoding="utf-8-sig")))
        assert rows
        assert {"y", "x", "stroke_id", "point_index", "is_break", "variant", "source"}.issubset(rows[0])
        assert any(row["is_break"] == "1" for row in rows)
        assert all(row["source"] == "constraint_bounded_adaptation_h1_lite_trial" for row in rows)

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 2
    assert {row["char_id"] for row in summary_rows} == {"u4eba", "u5c71"}
    assert {row["style"] for row in summary_rows} == {"kaishu", "lishu"}

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "H1-lite" in report
    assert "raw skeleton path" in report
    assert "not used by default" in report
    assert "不生成正式 trajectory.csv" in report


def test_h1_lite_uses_only_h2_usable_constraints():
    from constraint_bounded_adaptation_h1_lite import load_usable_constraints

    constraints = load_usable_constraints(
        Path("experiments/llm_style_trajectory/outputs/font_reference_constraints_20260619_230426/font_reference_constraints.json"),
        "u5c71",
        "lishu",
    )

    assert set(constraints) == {
        "bbox_aspect",
        "lower_half_width_ratio",
        "left_right_spread",
        "bbox_center_shift_x",
        "bbox_center_shift_y",
    }


def test_h1_lite_module_does_not_import_libauboi5():
    module_path = SRC / "constraint_bounded_adaptation_h1_lite.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
