import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from planner import load_style_profiles, plan_task
from run_demo import run_batch
from style_modifiers import (
    DEFAULT_STYLE_MODIFIERS,
    apply_style_modifiers_to_brush_params,
    normalize_style_modifiers,
)


GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
PROFILES = EXP_DIR / "configs" / "style_profiles.json"
BRUSH = EXP_DIR / "configs" / "brush_profiles.json"


def _profiles():
    return load_style_profiles(PROFILES)


def test_style_modifiers_schema_defaults_are_stable():
    modifiers = normalize_style_modifiers({})

    assert modifiers == DEFAULT_STYLE_MODIFIERS
    assert modifiers == {
        "connection_preference": "weak",
        "shape_emphasis": "normal",
        "smoothness_level": "medium",
        "stroke_width_level": "normal",
    }


def test_mock_planner_parses_connection_shape_smoothness_and_width_modifiers():
    no_connection = plan_task("写一个不要连笔的行楷山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    default_xingkai = plan_task("写一个行楷风格的山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    connected = plan_task("写一个更连贯的行楷山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    flat_lishu = plan_task("写一个宽扁一点的隶书中", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    wider_lishu = plan_task("写一个更宽的隶书中", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    smooth = plan_task("写一个更圆滑的楷书永", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    smoother = plan_task("写一个更平滑的楷书永", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    conservative = plan_task("写一个更保守的行楷永", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    thick = plan_task("写一个粗一点的行楷山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    thin = plan_task("写一个细一点的行楷山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert no_connection["style_modifiers"]["connection_preference"] == "none"
    assert no_connection["style_params"]["connection_strength"] == 0
    assert no_connection["style_params"]["allow_interstroke_connections"] is False

    assert default_xingkai["style_modifiers"]["connection_preference"] == "weak"
    assert default_xingkai["style_params"]["allow_interstroke_connections"] is True
    assert 0 < default_xingkai["style_params"]["connection_strength"] < connected["style_params"]["connection_strength"]

    assert connected["style_modifiers"]["connection_preference"] == "normal"
    assert connected["style_params"]["allow_interstroke_connections"] is True
    assert connected["style_params"]["connection_strength"] > 0

    assert flat_lishu["style_modifiers"]["shape_emphasis"] == "flatter"
    assert flat_lishu["style_params"]["horizontal_scale"] > _profiles()["lishu"]["horizontal_scale"]
    assert flat_lishu["style_params"]["vertical_scale"] < _profiles()["lishu"]["vertical_scale"]

    assert wider_lishu["style_modifiers"]["shape_emphasis"] == "wider"
    assert wider_lishu["style_params"]["horizontal_scale"] > _profiles()["lishu"]["horizontal_scale"]
    assert wider_lishu["style_params"]["vertical_scale"] == _profiles()["lishu"]["vertical_scale"]

    assert smooth["style_modifiers"]["smoothness_level"] == "high"
    assert smooth["style_params"]["smoothness"] > _profiles()["kaishu"]["smoothness"]
    assert smooth["style_params"]["allow_interstroke_connections"] is False
    assert smoother["style_modifiers"]["smoothness_level"] == "high"
    assert smoother["style_params"]["smoothness"] == smooth["style_params"]["smoothness"]

    assert conservative["style_modifiers"]["smoothness_level"] == "low"
    assert conservative["style_modifiers"]["connection_preference"] == "none"
    assert conservative["style_params"]["connection_strength"] == 0

    assert thick["style_modifiers"]["stroke_width_level"] == "thick"
    assert thin["style_modifiers"]["stroke_width_level"] == "thin"


def test_modifier_mapping_does_not_enable_illegal_interstroke_connections():
    plan = plan_task("写一个更连贯的隶书山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["style"] == "lishu"
    assert plan["style_modifiers"]["connection_preference"] == "normal"
    assert plan["constraints"]["allow_interstroke_connections"] is False
    assert plan["style_params"]["allow_interstroke_connections"] is False
    assert plan["style_params"]["connection_strength"] == 0
    assert plan["validation"]["ok"] is True


def test_brush_modifier_mapping_is_whitelisted_and_bounded():
    base = {"base_width": 9.0, "min_width": 4.0, "max_width": 14.0}
    thick = apply_style_modifiers_to_brush_params(
        base,
        {"stroke_width_level": "thick", "connection_preference": "normal", "shape_emphasis": "normal", "smoothness_level": "medium"},
    )
    thin = apply_style_modifiers_to_brush_params(
        base,
        {"stroke_width_level": "thin", "connection_preference": "normal", "shape_emphasis": "normal", "smoothness_level": "medium"},
    )
    ignored = normalize_style_modifiers({"stroke_width_level": "huge", "base_width": 999})

    assert thick["base_width"] > base["base_width"]
    assert thin["base_width"] < base["base_width"]
    assert thick["base_width"] <= thick["max_width"]
    assert thin["base_width"] >= thin["min_width"]
    assert "base_width" not in ignored
    assert ignored["stroke_width_level"] == "normal"


def test_modifier_summary_csv_can_be_generated(tmp_path):
    tasks = [
        "写一个行楷风格的山",
        "写一个更连贯的行楷山",
        "写一个不要连笔的行楷山",
        "写一个宽扁一点的隶书中",
        "写一个更圆滑的楷书永",
        "写一个更保守的行楷永",
    ]

    result = run_batch(
        tasks=tasks,
        output_root=tmp_path,
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
        image_size=160,
    )

    modifier_summary = Path(result["modifier_summary_csv"])
    assert modifier_summary.exists()

    with modifier_summary.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == len(tasks)
    expected_fields = {
        "task",
        "char",
        "style",
        "style_modifiers",
        "connection_strength",
        "allow_interstroke_connections",
        "smoothness",
        "horizontal_scale",
        "vertical_scale",
        "bbox_width",
        "bbox_height",
        "brush_base_width",
        "connection_count",
        "pen_up_count",
        "mean_turning",
        "aspect_ratio",
        "path_length",
    }
    assert expected_fields.issubset(rows[0].keys())
    modifiers = [json.loads(row["style_modifiers"]) for row in rows]
    assert any(item["connection_preference"] == "none" for item in modifiers)
    assert any(item["shape_emphasis"] == "flatter" for item in modifiers)


def test_xingkai_connection_ablation_has_gradient_metrics(tmp_path):
    tasks = [
        "写一个不要连笔的行楷山",
        "写一个行楷风格的山",
        "写一个更连贯的行楷山",
    ]

    result = run_batch(
        tasks=tasks,
        output_root=tmp_path,
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
        image_size=160,
    )

    with Path(result["modifier_summary_csv"]).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_pref = {row["connection_preference"]: row for row in rows}
    assert {"none", "weak", "normal"}.issubset(by_pref.keys())
    assert float(by_pref["none"]["connection_strength"]) == 0
    assert float(by_pref["none"]["connection_count"]) == 0
    assert 0 < float(by_pref["weak"]["connection_strength"]) < float(by_pref["normal"]["connection_strength"])
    assert float(by_pref["weak"]["connector_mean_pressure"]) < float(by_pref["normal"]["connector_mean_pressure"])
    assert float(by_pref["weak"]["connector_mean_width"]) < float(by_pref["normal"]["connector_mean_width"])
    assert int(float(by_pref["none"]["pen_up_count"])) > int(float(by_pref["weak"]["pen_up_count"]))
    assert Path(result["ablation_compare_images"]["山"]).exists()


def test_shape_and_smoothness_ablation_outputs_key_fields_and_compare_images(tmp_path):
    tasks = [
        "写一个隶书风格的中",
        "写一个宽扁一点的隶书中",
        "写一个更宽的隶书中",
        "写一个楷书风格的永",
        "写一个更圆滑的楷书永",
        "写一个更平滑的楷书永",
        "写一个更保守的行楷永",
    ]

    result = run_batch(
        tasks=tasks,
        output_root=tmp_path,
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
        image_size=160,
    )

    with Path(result["modifier_summary_csv"]).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    expected_fields = {
        "task",
        "char",
        "style",
        "style_modifiers",
        "horizontal_scale",
        "vertical_scale",
        "smoothness",
        "connection_strength",
        "allow_interstroke_connections",
        "bbox_width",
        "bbox_height",
        "aspect_ratio",
        "path_length",
        "pen_up_count",
        "mean_turning",
        "total_turning_angle",
        "max_turning_angle",
    }
    assert expected_fields.issubset(rows[0].keys())
    assert Path(result["shape_compare_images"]["中"]).exists()
    assert Path(result["smoothness_compare_images"]["永"]).exists()

    zhong_by_shape = {row["shape_emphasis"]: row for row in rows if row["char"] == "中"}
    assert {"normal", "flatter", "wider"}.issubset(zhong_by_shape.keys())
    assert float(zhong_by_shape["flatter"]["horizontal_scale"]) > float(zhong_by_shape["normal"]["horizontal_scale"])
    assert float(zhong_by_shape["flatter"]["vertical_scale"]) < float(zhong_by_shape["normal"]["vertical_scale"])
    assert float(zhong_by_shape["wider"]["horizontal_scale"]) > float(zhong_by_shape["normal"]["horizontal_scale"])
    assert float(zhong_by_shape["wider"]["vertical_scale"]) == float(zhong_by_shape["normal"]["vertical_scale"])

    yong_by_smoothness = {
        (row["style"], row["smoothness_level"], row["connection_preference"]): row
        for row in rows
        if row["char"] == "永"
    }
    default_kaishu = yong_by_smoothness[("kaishu", "medium", "weak")]
    smooth_kaishu = yong_by_smoothness[("kaishu", "high", "weak")]
    conservative_xingkai = yong_by_smoothness[("xingkai", "low", "none")]
    assert float(smooth_kaishu["smoothness"]) > float(default_kaishu["smoothness"])
    assert float(smooth_kaishu["total_turning_angle"]) <= float(default_kaishu["total_turning_angle"])
    assert conservative_xingkai["connection_preference"] == "none"
    assert float(conservative_xingkai["connection_strength"]) == 0
