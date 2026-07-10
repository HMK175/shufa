import csv
import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from a_route_showcase_pack import (  # noqa: E402
    build_a_route_showcase_pack,
    compose_showcase_task_specs,
    load_showcase_config,
)


CONFIG = EXP_DIR / "configs" / "a_route_showcase_chars.json"


def _make_png(path: Path, size: tuple[int, int] = (48, 36), color: tuple[int, int, int] = (240, 240, 240)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(path)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_fake_sample(batch_dir: Path, char: str, style: str, task: str) -> Path:
    sample_dir = batch_dir / f"u{ord(char):04x}_{style}_fake"
    sample_dir.mkdir(parents=True, exist_ok=True)
    preview_png = sample_dir / "preview.png"
    execution_render_png = sample_dir / "execution_render.png"
    execution_debug_png = sample_dir / "execution_debug.png"
    compare_png = sample_dir / "compare.png"
    modifier_ablation_png = sample_dir / "modifier_ablation.png"
    modifier_shape_png = sample_dir / "modifier_ablation_shape.png"
    modifier_smoothness_png = sample_dir / "modifier_ablation_smoothness.png"
    for index, path in enumerate(
        [
            preview_png,
            execution_render_png,
            execution_debug_png,
            compare_png,
            modifier_ablation_png,
            modifier_shape_png,
            modifier_smoothness_png,
        ]
    ):
        _make_png(path, color=(230 - index * 8, 238 - index * 5, 242 - index * 3))
    summary = {
        "task": task,
        "char": char,
        "style": style,
        "output_dir": str(sample_dir),
        "preview_png": str(preview_png),
        "execution_render_png": str(execution_render_png),
        "execution_debug_png": str(execution_debug_png),
        "compare_png": str(compare_png),
        "modifier_ablation_png": str(modifier_ablation_png),
        "modifier_shape_png": str(modifier_shape_png),
        "modifier_smoothness_png": str(modifier_smoothness_png),
        "connection_count": 2 if style == "xingkai" else 0,
        "connector_draw_length": 188.929 if style == "xingkai" else 0.0,
        "pen_up_move_length": 0.0 if style == "xingkai" else 188.929,
        "connector_mean_pressure": 0.678 if style == "xingkai" else 0.0,
        "connector_mean_width": 6.897 if style == "xingkai" else 0.0,
        "mean_width": 8.4,
        "mean_pressure": 0.9,
        "bbox_width": 100.0,
        "bbox_height": 80.0,
        "aspect_ratio": 1.25,
        "style_modifiers": {
            "connection_preference": "weak" if style == "xingkai" else "none",
            "shape_emphasis": "normal",
            "smoothness_level": "medium",
            "stroke_width_level": "normal",
        },
    }
    _write_json(sample_dir / "summary.json", summary)
    _write_json(
        sample_dir / "plan.json",
        {"task": task, "char": char, "style": style, "style_modifiers": summary["style_modifiers"]},
    )
    return sample_dir


def test_showcase_config_has_balanced_char_sets():
    config = load_showcase_config(CONFIG)

    assert len(config["simple_chars"]) >= 6
    assert len(config["medium_chars"]) >= 6
    assert len(config["complex_chars"]) >= 4
    assert len(config["style_overview_chars"]) >= 18
    assert 6 <= len(config["style_overview_grid_chars"]) <= 9
    assert {"国", "德", "福", "和"}.issubset(set(config["connection_control_chars"]))
    assert "抬笔过渡" in config["behavior_control_labels_cn"]
    assert "连续带笔过渡" in config["behavior_control_labels_cn"]


def test_showcase_task_specs_cover_style_modifier_and_execution_display():
    config = load_showcase_config(CONFIG)
    specs = compose_showcase_task_specs(config)

    categories = {spec["category"] for spec in specs}
    assert {"style_overview", "connection_control", "shape_control", "smoothness_control"}.issubset(categories)
    assert any(spec["label_cn"] == "抬笔过渡" for spec in specs)
    assert any(spec["label_cn"] == "宽扁" for spec in specs)
    assert any(spec["label_cn"] == "更圆滑" for spec in specs)


def test_showcase_pack_builds_manifest_checklist_and_cn_figures(tmp_path):
    config = load_showcase_config(CONFIG)
    specs = compose_showcase_task_specs(config)
    batch_dir = tmp_path / "fake_batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        _create_fake_sample(batch_dir, spec["char"], spec["style"], spec["task"])

    result = build_a_route_showcase_pack(
        output_root=tmp_path,
        config_path=CONFIG,
        source_batch_dir=batch_dir,
        run_generation=False,
        paper_figures_dir=tmp_path / "paper_figures",
    )

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    for name in [
        "a_route_showcase_report.md",
        "a_route_showcase_manifest.csv",
        "a_route_visual_audit_checklist.md",
        "a_route_style_overview_grid.png",
        "a_route_modifier_control_overview.png",
        "a_route_execution_display_grid.png",
        "a_route_behavior_control_compare.png",
        "a_route_smoothness_supplementary.png",
    ]:
        assert (out_dir / name).exists()
    assert (out_dir / "paper_index.md").exists()
    assert (out_dir / "selected_images").exists()

    manifest_rows = list(csv.DictReader((out_dir / "a_route_showcase_manifest.csv").open(encoding="utf-8-sig")))
    assert len(manifest_rows) >= 12
    assert {"main_paper_candidate", "supplementary_candidate", "boundary_risk"}.issubset(
        {row["role"] for row in manifest_rows}
    )
    report = (out_dir / "a_route_showcase_report.md").read_text(encoding="utf-8")
    assert "跨笔过渡控制" in report
    assert "execution" in report
    assert "真行楷" in report
