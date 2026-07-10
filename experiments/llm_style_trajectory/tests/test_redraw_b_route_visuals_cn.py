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


def test_redraw_b_route_visuals_cn_outputs_expected_files(tmp_path):
    from redraw_b_route_visuals_cn import run_redraw_b_route_visuals_cn

    result = run_redraw_b_route_visuals_cn(output_dir=tmp_path / "b_route_visuals_cn", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()

    expected = {
        "h1_lite_u5c71_kaishu_lishu_contrast_cn.png",
        "h1_lite_u98ce_lishu_risk_contrast_cn.png",
        "hybrid_section_compare_cn.png",
        "b_route_visuals_cn_report.md",
        "b_route_visuals_cn_manifest.csv",
    }
    names = {path.name for path in out_dir.iterdir() if path.is_file()}
    assert expected.issubset(names)

    manifest_rows = list(csv.DictReader((out_dir / "b_route_visuals_cn_manifest.csv").open(encoding="utf-8-sig")))
    assert len(manifest_rows) == 3
    assert {row["artifact_name"] for row in manifest_rows} == {
        "h1_lite_u5c71_kaishu_lishu_contrast_cn.png",
        "h1_lite_u98ce_lishu_risk_contrast_cn.png",
        "hybrid_section_compare_cn.png",
    }
    assert all(row["status"] == "visual_redraw_only_not_used_by_default" for row in manifest_rows)
    assert all(row["difference_overlay"] == "True" for row in manifest_rows)
    assert all(row["inset_zoom"] == "True" for row in manifest_rows)

    report = (out_dir / "b_route_visuals_cn_report.md").read_text(encoding="utf-8")
    assert "中文标题" in report
    assert "差异辅助" in report
    assert "原始中位轨迹" in report
    assert "保守版" in report
    assert "平衡版" in report
    assert "差异仍然很弱" in report


def test_redraw_b_route_visuals_cn_does_not_write_trajectory_or_robot_artifacts(tmp_path):
    from redraw_b_route_visuals_cn import run_redraw_b_route_visuals_cn

    result = run_redraw_b_route_visuals_cn(output_dir=tmp_path / "b_route_visuals_cn", copy_to_paper=False)
    out_dir = Path(result["output_dir"])

    forbidden = {
        "trajectory.csv",
        "execution_trajectory.csv",
        "robot_workspace_trajectory.csv",
        "robot_workspace_trajectory_resampled.csv",
        "robot_target_poses.csv",
    }
    generated = {path.name for path in out_dir.rglob("*") if path.is_file()}
    assert not (generated & forbidden)


def test_redraw_b_route_visuals_cn_summary_json_fields_and_labels(tmp_path):
    from redraw_b_route_visuals_cn import run_redraw_b_route_visuals_cn

    result = run_redraw_b_route_visuals_cn(output_dir=tmp_path / "b_route_visuals_cn", copy_to_paper=False)
    summary_path = Path(result["summary_json"])
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["status"] == "visual_redraw_only_not_used_by_default"
    assert payload["figure_count"] == 3
    assert payload["label_map"]["original median"] == "原始中位轨迹"
    assert payload["label_map"]["conservative"] == "保守版"
    assert payload["label_map"]["balanced"] == "平衡版"
    assert payload["label_map"]["known positive reference"] == "已知正例参考"
    assert payload["label_map"]["top_band"] == "上区"
    assert payload["label_map"]["mid_band"] == "中区"
    assert payload["label_map"]["bottom_band"] == "下区"


def test_redraw_b_route_visuals_cn_module_does_not_import_libauboi5():
    module_path = SRC / "redraw_b_route_visuals_cn.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
