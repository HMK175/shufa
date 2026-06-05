"""Rule-based planner for the LLM-style trajectory experiment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


STYLE_ALIASES = {
    "楷书": "kaishu",
    "正楷": "kaishu",
    "kaishu": "kaishu",
    "行楷": "xingkai",
    "xingkai": "xingkai",
    "行书": "xingkai",
    "隶书": "lishu",
    "lishu": "lishu"
}


def _coerce_profile_value(value: Any) -> float | bool:
    if isinstance(value, bool):
        return value
    return float(value)


def load_style_profiles(path: Path | str) -> dict[str, dict[str, float | bool]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        name: {key: _coerce_profile_value(value) for key, value in params.items()}
        for name, params in data.items()
        if isinstance(params, dict) and not name.startswith("_")
    }


def _extract_style(task_text: str, profiles: dict[str, dict[str, float]]) -> str:
    for key, value in STYLE_ALIASES.items():
        if key in task_text and value in profiles:
            return value
    return "kaishu"


def _extract_char(task_text: str) -> str:
    match = re.search(r"的([\u4e00-\u9fff])", task_text)
    if match:
        return match.group(1)
    chars = re.findall(r"[\u4e00-\u9fff]", task_text)
    if chars:
        return chars[-1]
    raise ValueError(f"Cannot find a Chinese character in task: {task_text}")


class RuleBasedPlanner:
    """Small deterministic planner that can later be replaced by a real LLM."""

    def __init__(self, style_profiles: dict[str, dict[str, float]]):
        self.style_profiles = style_profiles

    def plan(self, task_text: str) -> dict[str, Any]:
        style = _extract_style(task_text, self.style_profiles)
        char = _extract_char(task_text)
        return {
            "task": task_text,
            "char": char,
            "style": style,
            "style_params": dict(self.style_profiles[style]),
            "stroke_plan": {
                "source": "makemeahanzi",
                "order": "source_order",
                "trajectory_generator": "deterministic_style_profile"
            }
        }
