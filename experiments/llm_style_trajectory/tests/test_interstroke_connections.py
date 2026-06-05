import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_style_profiles import build_estimated_profiles
from planner import load_style_profiles
from trajectory_tools import build_styled_trajectory, trajectory_metrics


def _two_simple_strokes():
    return [
        np.array([[10.0, 10.0], [20.0, 10.0]], dtype=float),
        np.array([[40.0, 40.0], [50.0, 40.0]], dtype=float),
    ]


def test_missing_allow_interstroke_connections_defaults_to_no_connection():
    profile = {
        "resample_step": 10.0,
        "smoothness": 0.0,
        "corner_rounding": 0.0,
        "connection_strength": 0.8,
    }

    styled = build_styled_trajectory(_two_simple_strokes(), profile, image_size=64)
    metrics = trajectory_metrics(
        styled,
        image_size=64,
        stroke_count=2,
        connection_strength=profile["connection_strength"],
    )

    assert len(styled) == 2
    assert metrics["connection_count"] == 0


def test_connection_requires_allow_flag_and_positive_strength():
    profile = {
        "resample_step": 10.0,
        "smoothness": 0.0,
        "corner_rounding": 0.0,
        "connection_strength": 0.8,
        "allow_interstroke_connections": True,
    }

    styled = build_styled_trajectory(_two_simple_strokes(), profile, image_size=64)
    metrics = trajectory_metrics(
        styled,
        image_size=64,
        stroke_count=2,
        connection_strength=profile["connection_strength"],
        allow_interstroke_connections=profile["allow_interstroke_connections"],
    )

    assert len(styled) == 3
    assert metrics["connection_count"] == 1


def test_kaishu_lishu_profiles_do_not_allow_interstroke_connections():
    profiles = load_style_profiles(EXP_DIR / "configs" / "style_profiles.json")

    assert profiles["kaishu"]["connection_strength"] == 0
    assert profiles["kaishu"]["allow_interstroke_connections"] is False
    assert profiles["lishu"]["connection_strength"] == 0
    assert profiles["lishu"]["allow_interstroke_connections"] is False
    assert profiles["xingkai"]["connection_strength"] > 0
    assert profiles["xingkai"]["allow_interstroke_connections"] is True


def test_estimated_connection_strength_policy_keeps_static_sources_as_prior():
    metrics_rows = [
        {"style": "kaishu", "render_success": True, "aspect_ratio": 1.0, "turning": 0.2, "estimated_stroke_width": 8.0},
        {"style": "xingkai", "render_success": True, "aspect_ratio": 1.0, "turning": 0.2, "estimated_stroke_width": 8.0},
        {"style": "lishu", "render_success": True, "aspect_ratio": 1.2, "turning": 0.2, "estimated_stroke_width": 8.0},
    ]
    manual = json.loads((EXP_DIR / "configs" / "style_profiles.json").read_text(encoding="utf-8"))

    estimated = build_estimated_profiles(metrics_rows, manual)

    assert estimated["kaishu"]["connection_strength"] == {"value": 0.0, "source": "default_prior"}
    assert estimated["lishu"]["connection_strength"] == {"value": 0.0, "source": "default_prior"}
    assert estimated["xingkai"]["connection_strength"]["value"] > 0
    assert estimated["xingkai"]["connection_strength"]["source"] == "default_prior"
    assert estimated["kaishu"]["allow_interstroke_connections"] == {"value": False, "source": "default_prior"}
    assert estimated["lishu"]["allow_interstroke_connections"] == {"value": False, "source": "default_prior"}
    assert estimated["xingkai"]["allow_interstroke_connections"] == {"value": True, "source": "default_prior"}
