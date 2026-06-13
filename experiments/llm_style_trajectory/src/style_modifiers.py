"""Controlled style modifier parsing and local whitelist mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STYLE_MODIFIERS = {
    "connection_preference": "weak",
    "shape_emphasis": "normal",
    "smoothness_level": "medium",
    "stroke_width_level": "normal",
}

MODIFIER_CHOICES = {
    "connection_preference": {"none", "weak", "normal"},
    "shape_emphasis": {"normal", "flatter", "wider"},
    "smoothness_level": {"low", "medium", "high"},
    "stroke_width_level": {"thin", "normal", "thick"},
}

BRUSH_KEYS = [
    "base_width",
    "min_width",
    "max_width",
    "start_taper",
    "end_taper",
    "turn_width_gain",
    "horizontal_width_gain",
    "vertical_width_gain",
    "antialias_scale",
]


def normalize_style_modifiers(raw: Any | None) -> dict[str, str]:
    """Keep only supported modifier enum values and fill stable defaults."""
    out = dict(DEFAULT_STYLE_MODIFIERS)
    if not isinstance(raw, dict):
        return out
    for key, choices in MODIFIER_CHOICES.items():
        value = str(raw.get(key, out[key])).strip().lower()
        if value in choices:
            out[key] = value
    return out


def parse_style_modifiers_from_text(task_text: str) -> dict[str, str]:
    modifiers = dict(DEFAULT_STYLE_MODIFIERS)
    text = task_text.lower()

    if any(token in task_text for token in ["不要连笔", "不连笔", "不要连接", "不连接", "不要连起来", "不连起来"]):
        modifiers["connection_preference"] = "none"
    elif any(token in task_text for token in ["轻微连笔", "弱连笔", "稍微连贯", "略连贯"]):
        modifiers["connection_preference"] = "weak"
    elif any(token in task_text for token in ["更连贯", "连笔", "连起来", "连接"]):
        modifiers["connection_preference"] = "normal"

    if any(token in task_text for token in ["宽扁", "扁一些", "扁一点", "更扁", "横向舒展"]):
        modifiers["shape_emphasis"] = "flatter"
    elif any(token in task_text for token in ["宽一些", "宽一点", "更宽"]):
        modifiers["shape_emphasis"] = "wider"

    if any(token in task_text for token in ["圆滑", "更圆滑", "平滑", "更平滑", "圆润", "更圆润"]):
        modifiers["smoothness_level"] = "high"
    if any(token in task_text for token in ["保守", "规整", "規整"]):
        modifiers["smoothness_level"] = "low"
        modifiers["connection_preference"] = "none"

    if any(token in task_text for token in ["粗一点", "粗一些", "更粗", "粗笔"]):
        modifiers["stroke_width_level"] = "thick"
    elif any(token in task_text for token in ["细一点", "细一些", "更细", "细笔"]):
        modifiers["stroke_width_level"] = "thin"

    if "thin" in text:
        modifiers["stroke_width_level"] = "thin"
    elif "thick" in text:
        modifiers["stroke_width_level"] = "thick"

    return modifiers


def merge_text_and_model_modifiers(task_text: str, raw_model_modifiers: Any | None) -> dict[str, str]:
    """Normalize model modifiers, then let explicit user text win."""
    merged = normalize_style_modifiers(raw_model_modifiers)
    parsed = parse_style_modifiers_from_text(task_text)
    for key, parsed_value in parsed.items():
        if parsed_value != DEFAULT_STYLE_MODIFIERS[key]:
            merged[key] = parsed_value
    return normalize_style_modifiers(merged)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_number(value: float | bool) -> float | bool:
    if isinstance(value, bool):
        return value
    return round(float(value), 4)


def apply_style_modifiers_to_style_params(
    base_params: dict[str, Any],
    modifiers: dict[str, str] | None,
) -> dict[str, float | bool]:
    """Map whitelisted modifiers onto trusted local style params."""
    mods = normalize_style_modifiers(modifiers)
    out: dict[str, float | bool] = dict(base_params)
    profile_allows_connections = bool(base_params.get("allow_interstroke_connections", False))
    base_strength = float(base_params.get("connection_strength", 0.0))

    if mods["connection_preference"] == "none" or not profile_allows_connections:
        out["allow_interstroke_connections"] = False
        out["connection_strength"] = 0.0
    elif mods["connection_preference"] == "weak":
        out["allow_interstroke_connections"] = True
        out["connection_strength"] = round(max(0.08, min(base_strength * 0.55, 0.18)), 4)
    else:
        out["allow_interstroke_connections"] = True
        out["connection_strength"] = round(max(base_strength, 0.2), 4)

    h_scale = float(out.get("horizontal_scale", 1.0))
    v_scale = float(out.get("vertical_scale", 1.0))
    if mods["shape_emphasis"] == "flatter":
        out["horizontal_scale"] = round(min(1.38, h_scale * 1.1), 4)
        out["vertical_scale"] = round(max(0.7, v_scale * 0.92), 4)
    elif mods["shape_emphasis"] == "wider":
        out["horizontal_scale"] = round(min(1.35, h_scale * 1.08), 4)

    smoothness = float(out.get("smoothness", 0.0))
    corner = float(out.get("corner_rounding", 0.0))
    if mods["smoothness_level"] == "high":
        out["smoothness"] = round(min(0.9, smoothness * 1.25 + 0.08), 4)
        out["corner_rounding"] = round(min(0.9, corner * 1.2 + 0.06), 4)
    elif mods["smoothness_level"] == "low":
        out["smoothness"] = round(max(0.02, smoothness * 0.55), 4)
        out["corner_rounding"] = round(max(0.02, corner * 0.55), 4)

    return {key: _round_number(value) for key, value in out.items()}


def apply_style_modifiers_to_brush_params(
    base_brush: dict[str, Any],
    modifiers: dict[str, str] | None,
) -> dict[str, float]:
    mods = normalize_style_modifiers(modifiers)
    out = {key: float(value) for key, value in base_brush.items() if key in BRUSH_KEYS}
    if not out:
        out = {
            "base_width": 8.0,
            "min_width": 3.0,
            "max_width": 14.0,
            "start_taper": 0.12,
            "end_taper": 0.12,
            "turn_width_gain": 0.22,
            "horizontal_width_gain": 0.0,
            "vertical_width_gain": 0.0,
            "antialias_scale": 3.0,
        }

    if mods["stroke_width_level"] == "thick":
        out["base_width"] *= 1.22
        out["min_width"] *= 1.08
        out["max_width"] *= 1.08
    elif mods["stroke_width_level"] == "thin":
        out["base_width"] *= 0.78
        out["min_width"] *= 0.9

    if mods["smoothness_level"] == "high":
        out["turn_width_gain"] *= 0.92
    elif mods["smoothness_level"] == "low":
        out["turn_width_gain"] *= 1.08

    if mods["shape_emphasis"] in {"flatter", "wider"}:
        out["horizontal_width_gain"] = out.get("horizontal_width_gain", 0.0) + 0.04

    min_w = max(1.0, float(out.get("min_width", 3.0)))
    max_w = max(min_w + 0.5, float(out.get("max_width", 14.0)))
    base_w = _clamp(float(out.get("base_width", 8.0)), min_w, max_w)
    out["min_width"] = round(min_w, 4)
    out["max_width"] = round(max_w, 4)
    out["base_width"] = round(base_w, 4)
    return {key: round(float(value), 4) for key, value in out.items() if key in BRUSH_KEYS}


def load_brush_profiles(path: Path | str) -> dict[str, dict[str, float]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    profiles: dict[str, dict[str, float]] = {}
    for style, params in data.items():
        if isinstance(params, dict):
            profiles[style] = {key: float(params[key]) for key in BRUSH_KEYS if key in params}
    if "default" not in profiles:
        profiles["default"] = apply_style_modifiers_to_brush_params({}, DEFAULT_STYLE_MODIFIERS)
    return profiles
