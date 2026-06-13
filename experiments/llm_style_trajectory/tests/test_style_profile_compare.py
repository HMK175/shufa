import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from style_profile_compare import load_compare_tasks, run_style_profile_compare


CONFIG = EXP_DIR / "configs" / "style_profile_compare_tasks.json"


def _read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_style_profile_compare_config_loads_expected_tasks():
    tasks = load_compare_tasks(CONFIG)

    assert len(tasks) == 15
    chars = {task["char"] for task in tasks}
    assert chars == {"山", "中", "永", "福", "明"}
    for char in chars:
        assert {task["style"] for task in tasks if task["char"] == char} == {"kaishu", "xingkai", "lishu"}


def test_style_profile_compare_batch_outputs_summary_report_and_grid(tmp_path):
    result = run_style_profile_compare(
        output_root=tmp_path,
        tasks_path=CONFIG,
        image_size=160,
    )

    summary_path = Path(result["summary_csv"])
    report_path = Path(result["report_md"])
    grid_path = Path(result["grid_png"])

    assert summary_path.exists()
    assert report_path.exists()
    assert grid_path.exists()

    rows = _read_csv(summary_path)
    assert len(rows) == 15
    for char in {"山", "中", "永", "福", "明"}:
        char_rows = [row for row in rows if row["char"] == char]
        assert {row["style"] for row in char_rows} == {"kaishu", "xingkai", "lishu"}
        assert Path(result["style_compare_images"][f"u{ord(char):04x}"]).exists()

    required_fields = {
        "char",
        "style",
        "task",
        "stroke_count",
        "path_length",
        "mean_turning",
        "total_turning_angle",
        "max_turning_angle",
        "bbox_width",
        "bbox_height",
        "aspect_ratio",
        "connection_count",
        "connector_draw_length",
        "pen_up_move_length",
        "mean_width",
        "mean_pressure",
        "connector_mean_width",
        "connector_mean_pressure",
        "workspace_path_length_mm",
        "max_step_mm",
        "out_of_bounds",
        "z_min",
        "z_max",
    }
    assert required_fields.issubset(rows[0].keys())

    report = report_path.read_text(encoding="utf-8")
    assert "三字体基础风格对比" in report
    assert "参数化 style profile" in report
