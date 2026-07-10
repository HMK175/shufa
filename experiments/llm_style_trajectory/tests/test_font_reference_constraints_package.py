import json
from pathlib import Path

from experiments.llm_style_trajectory.src.font_reference_constraints_package import (
    DEFAULT_SAMPLES,
    classify_constraint,
    run_font_reference_constraints_package,
)


def test_font_reference_constraints_package_outputs_expected_files_without_trajectories(tmp_path):
    out_dir = tmp_path / "font_reference_constraints"
    result = run_font_reference_constraints_package(
        output_dir=out_dir,
        samples=[("山", "kaishu"), ("山", "lishu")],
        copy_to_paper=False,
        skeleton_method="ridge",
    )

    assert Path(result["output_dir"]) == out_dir
    constraints_csv = out_dir / "font_reference_constraints.csv"
    constraints_json = out_dir / "font_reference_constraints.json"
    summary_csv = out_dir / "font_reference_constraints_summary.csv"
    report_md = out_dir / "font_reference_constraints_report.md"
    manifest_csv = out_dir / "font_reference_constraints_manifest.csv"

    for path in [constraints_csv, constraints_json, summary_csv, report_md, manifest_csv]:
        assert path.exists(), path

    payload = json.loads(constraints_json.read_text(encoding="utf-8"))
    assert payload["status"] == "reference_constraints_only_not_used_by_default"
    assert payload["default_pipeline_integration"] is False
    assert payload["adapted_trajectory_generated"] is False
    assert len(payload["samples"]) == 2

    for sample in payload["samples"]:
        constraints = sample["constraints"]
        assert "bbox_aspect" in constraints
        assert "lower_half_width_ratio" in constraints
        assert "skeleton_complexity_score" in constraints
        assert constraints["bbox_aspect"]["recommended_use"] in {
            "usable_for_adaptation",
            "visual_reference_only",
            "unsafe_for_direct_use",
        }

    figures = sorted((out_dir / "figures").glob("constraint_reference_*.png"))
    assert len(figures) == 2

    forbidden_names = {
        "trajectory.csv",
        "execution_trajectory.csv",
        "robot_workspace_trajectory.csv",
        "robot_workspace_trajectory_resampled.csv",
    }
    generated_names = {path.name for path in out_dir.rglob("*") if path.is_file()}
    assert not (generated_names & forbidden_names)
    assert not any(name.startswith("adapted_trial") for name in generated_names)

    report_text = report_md.read_text(encoding="utf-8")
    assert "H2" in report_text
    assert "not used by default" in report_text
    assert "不移动轨迹点" in report_text


def test_default_samples_are_kaishu_lishu_only_and_exclude_xingkai():
    assert len(DEFAULT_SAMPLES) == 7
    assert {style for _, style in DEFAULT_SAMPLES} == {"kaishu", "lishu"}
    assert ("山", "kaishu") in DEFAULT_SAMPLES
    assert ("风", "lishu") in DEFAULT_SAMPLES


def test_constraint_classification_marks_complex_skeleton_as_unsafe():
    result = classify_constraint(
        "raw_skeleton_path",
        value=1.0,
        style="lishu",
        component_count=4,
        endpoint_count=20,
        branch_count=40,
        complexity_score=0.9,
    )

    assert result["recommended_use"] == "unsafe_for_direct_use"
    assert result["risk_level"] == "high"


def test_module_does_not_import_libauboi5():
    module_path = Path("experiments/llm_style_trajectory/src/font_reference_constraints_package.py")
    if module_path.exists():
        assert "libpyauboi5" not in module_path.read_text(encoding="utf-8")
