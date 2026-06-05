import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from knowledge import MakeMeAHanziKnowledge
from planner import RuleBasedPlanner, load_style_profiles
from run_demo import run_batch, run_task


def test_planner_parses_xingkai_shan_task():
    profiles = load_style_profiles(EXP_DIR / "configs" / "style_profiles.json")
    planner = RuleBasedPlanner(profiles)
    plan = planner.plan("写一个行楷风格的山")

    assert plan["char"] == "山"
    assert plan["style"] == "xingkai"
    assert plan["style_params"]["connection_strength"] > profiles["kaishu"]["connection_strength"]
    assert plan["stroke_plan"]["source"] == "makemeahanzi"


def test_knowledge_finds_shan_three_strokes():
    graphics = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
    knowledge = MakeMeAHanziKnowledge(graphics)
    glyph = knowledge.get_glyph("山")

    assert glyph.char == "山"
    assert glyph.stroke_count == 3
    assert len(glyph.medians) == 3
    assert all(len(points) >= 2 for points in glyph.medians)


def test_style_profiles_have_executable_numeric_params():
    profiles = load_style_profiles(EXP_DIR / "configs" / "style_profiles.json")
    for name in ["kaishu", "xingkai", "lishu"]:
        assert name in profiles
        for key in [
            "smoothness",
            "resample_step",
            "horizontal_scale",
            "vertical_scale",
            "corner_rounding",
            "connection_strength",
            "speed_scale",
            "pen_up_height",
        ]:
            assert isinstance(profiles[name][key], (int, float))


def test_demo_tasks_cover_three_styles_for_three_chars():
    tasks = json.loads((EXP_DIR / "configs" / "demo_tasks.json").read_text(encoding="utf-8"))
    task_texts = [item["task"] for item in tasks]
    for char in ["山", "中", "永"]:
        for style_text in ["楷书", "行楷", "隶书"]:
            assert any(char in task and style_text in task for task in task_texts)


def test_run_task_writes_csv_preview_and_summary(tmp_path):
    result = run_task(
        task_text="写一个行楷风格的山",
        output_root=tmp_path,
        graphics_path=ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt",
        style_profiles_path=EXP_DIR / "configs" / "style_profiles.json",
        image_size=160,
    )

    csv_path = Path(result["trajectory_csv"])
    preview_path = Path(result["preview_png"])
    summary_path = Path(result["summary_json"])
    plan_path = Path(result["plan_json"])

    assert csv_path.exists()
    assert preview_path.exists()
    assert summary_path.exists()
    assert plan_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert ["nan", "nan"] in rows

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["char"] == "山"
    assert summary["stroke_count"] == 3
    assert summary["style"] == "xingkai"
    for key in [
        "point_count",
        "pen_up_count",
        "bounding_box_width",
        "bounding_box_height",
        "aspect_ratio",
        "mean_turning",
        "connection_count",
        "out_of_bounds",
    ]:
        assert key in summary


def test_batch_demo_writes_summary_and_compare_images(tmp_path):
    tasks = [
        "写一个楷书风格的山",
        "写一个行楷风格的山",
        "写一个隶书风格的山",
        "写一个楷书风格的中",
        "写一个行楷风格的中",
        "写一个隶书风格的中",
        "写一个楷书风格的永",
        "写一个行楷风格的永",
        "写一个隶书风格的永",
    ]
    result = run_batch(
        tasks=tasks,
        output_root=tmp_path,
        graphics_path=ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt",
        style_profiles_path=EXP_DIR / "configs" / "style_profiles.json",
        image_size=160,
    )

    batch_dir = Path(result["batch_dir"])
    summary_csv = Path(result["batch_summary_csv"])
    assert batch_dir.exists()
    assert summary_csv.exists()
    assert (batch_dir / "compare_u5c71.png").exists()
    assert (batch_dir / "compare_u4e2d.png").exists()
    assert (batch_dir / "compare_u6c38.png").exists()

    with summary_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(tasks)
    expected_fields = {
        "char",
        "style",
        "stroke_count",
        "point_count",
        "path_length",
        "pen_up_count",
        "bounding_box_width",
        "bounding_box_height",
        "aspect_ratio",
        "mean_turning",
        "connection_count",
        "out_of_bounds",
    }
    assert expected_fields.issubset(rows[0].keys())
    shan_rows = [row for row in rows if row["char"] == "山"]
    assert len({row["aspect_ratio"] for row in shan_rows}) > 1
