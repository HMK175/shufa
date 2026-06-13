import json
import sys
from pathlib import Path
from urllib.error import URLError

import pytest


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from planner import load_style_profiles, plan_task, validate_plan
from run_demo import run_task
import planner as planner_module


GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
PROFILES = EXP_DIR / "configs" / "style_profiles.json"


def _profiles():
    return load_style_profiles(PROFILES)


def test_mock_plan_task_parses_xingkai_shan_schema():
    plan = plan_task("写一个行楷风格的山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["char"] == "山"
    assert plan["style"] == "xingkai"
    assert plan["planner_mode"] == "mock"
    assert plan["source"] == "mock_rule_based"
    assert plan["constraints"]["allow_interstroke_connections"] is True
    assert plan["constraints"]["emphasize_flat_shape"] is False
    assert plan["validation"]["ok"] is True
    assert plan["raw_response"] is None
    for key in [
        "char",
        "style",
        "style_params",
        "constraints",
        "stroke_plan",
        "planner_mode",
        "source",
        "warnings",
        "raw_response",
        "validation",
    ]:
        assert key in plan


def test_mock_plan_task_parses_lishu_no_connection_constraint():
    plan = plan_task("写一个隶书风格的山，不要连笔，整体宽扁一些", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["char"] == "山"
    assert plan["style"] == "lishu"
    assert plan["constraints"]["allow_interstroke_connections"] is False
    assert plan["constraints"]["emphasize_flat_shape"] is True
    assert plan["style_params"]["allow_interstroke_connections"] is False
    assert plan["style_params"]["connection_strength"] == 0
    assert plan["validation"]["ok"] is True


def test_mock_plan_task_ignores_interstroke_constraint_words_when_extracting_char():
    plan = plan_task("写一个隶书的山，笔画之间不要连起来", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["char"] == "山"
    assert plan["style"] == "lishu"
    assert plan["requested_chars_raw"] == "山"
    assert plan["constraints"]["allow_interstroke_connections"] is False
    assert plan["validation"]["ok"] is True


def test_validate_plan_finds_unknown_style_and_missing_char():
    plan = {
        "task": "bad",
        "char": "",
        "style": "unknown_style",
        "style_params": {},
        "constraints": {},
        "stroke_plan": {},
        "planner_mode": "mock",
        "source": "test",
        "warnings": [],
        "raw_response": None,
    }

    validation = validate_plan(plan, style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert validation["ok"] is False
    assert any("char" in error for error in validation["errors"])
    assert any("style" in error for error in validation["errors"])


def test_api_and_local_unconfigured_return_friendly_validation_errors(monkeypatch):
    monkeypatch.delenv("LLM_STYLE_PLANNER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_STYLE_PLANNER_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_STYLE_PLANNER_LOCAL_CMD", raising=False)

    api_plan = plan_task("写一个行楷风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)
    local_plan = plan_task("写一个行楷风格的山", mode="local", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert api_plan["validation"]["ok"] is False
    assert "api planner not configured" in api_plan["warnings"][0]
    assert local_plan["validation"]["ok"] is False
    assert "local planner not configured" in local_plan["warnings"][0]


def test_api_unconfigured_can_fallback_to_mock(monkeypatch):
    monkeypatch.delenv("LLM_STYLE_PLANNER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_STYLE_PLANNER_ENDPOINT", raising=False)

    plan = plan_task(
        "写一个行楷风格的山",
        mode="api",
        style_profiles=_profiles(),
        graphics_path=GRAPHICS,
        fallback_to_mock=True,
    )

    assert plan["planner_mode"] == "mock"
    assert plan["source"] == "mock_rule_based"
    assert plan["validation"]["ok"] is True
    assert any("api planner not configured" in warning for warning in plan["warnings"])


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _configure_api(monkeypatch):
    monkeypatch.setenv("LLM_STYLE_PLANNER_API_KEY", "test-key-not-written")
    monkeypatch.setenv("LLM_STYLE_PLANNER_ENDPOINT", "https://example.invalid/chat/completions")
    monkeypatch.setenv("LLM_STYLE_PLANNER_MODEL", "deepseek-v4-pro")


def test_api_plan_task_accepts_valid_deepseek_json(monkeypatch):
    _configure_api(monkeypatch)
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "char": "山",
                            "style": "xingkai",
                            "constraints": {
                                "allow_interstroke_connections": True,
                                "emphasize_flat_shape": False,
                            },
                            "notes": "parsed by test",
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个行楷风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["planner_mode"] == "api"
    assert plan["source"] == "deepseek_v4_pro"
    assert plan["char"] == "山"
    assert plan["style"] == "xingkai"
    assert plan["validation"]["ok"] is True
    assert "test-key-not-written" not in json.dumps(plan, ensure_ascii=False)


def test_api_plan_task_reports_non_json_content(monkeypatch):
    _configure_api(monkeypatch)
    response = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个行楷风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["validation"]["ok"] is False
    assert "non-JSON" in plan["validation"]["errors"][0]


def test_api_plan_task_removes_forbidden_trajectory_payload(monkeypatch):
    _configure_api(monkeypatch)
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "char": "山",
                            "style": "xingkai",
                            "constraints": {"allow_interstroke_connections": True},
                            "trajectory": [[1, 2], [3, 4]],
                            "csv": "y,x\n1,2\n",
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个行楷风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["validation"]["ok"] is True
    assert "trajectory" not in plan
    assert "csv" not in plan
    assert any("removed forbidden planner field" in warning for warning in plan["warnings"])


def test_api_plan_task_rejects_unsupported_style_even_if_model_maps_to_supported(monkeypatch):
    _configure_api(monkeypatch)
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "char": "山",
                            "style": "xingkai",
                            "constraints": {"allow_interstroke_connections": True},
                            "notes": "helpfully mapped unsupported cursive request",
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个草书风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["request_status"] == "unsupported"
    assert plan["requested_style_raw"] == "草书"
    assert plan["mapped_style"] == "xingkai"
    assert plan["validation"]["ok"] is False
    assert any("unsupported style" in error for error in plan["validation"]["errors"])


def test_api_plan_task_rejects_multi_character_request_even_if_model_truncates(monkeypatch):
    _configure_api(monkeypatch)
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "char": "山",
                            "style": "kaishu",
                            "constraints": {"allow_interstroke_connections": False},
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个山水", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["request_status"] == "invalid"
    assert plan["requested_chars_raw"] == "山水"
    assert plan["validation"]["ok"] is False
    assert any("single target character" in error for error in plan["validation"]["errors"])


def test_api_plan_task_defaults_ambiguous_style_to_kaishu_with_warning(monkeypatch):
    _configure_api(monkeypatch)
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "char": "山",
                            "style": "xingkai",
                            "constraints": {"allow_interstroke_connections": True},
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))

    plan = plan_task("写一个好看一点的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["request_status"] == "ok"
    assert plan["requested_style_raw"] == ""
    assert plan["mapped_style"] == "kaishu"
    assert plan["style"] == "kaishu"
    assert plan["constraints"]["allow_interstroke_connections"] is False
    assert plan["validation"]["ok"] is True
    assert any("defaulted to kaishu" in warning for warning in plan["warnings"])


def test_api_plan_task_reports_network_errors(monkeypatch):
    _configure_api(monkeypatch)

    def raise_url_error(request, timeout=30):
        raise URLError("network down")

    monkeypatch.setattr(planner_module, "urlopen", raise_url_error)

    plan = plan_task("写一个行楷风格的山", mode="api", style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert plan["validation"]["ok"] is False
    assert "api planner request failed" in plan["validation"]["errors"][0]


def test_run_task_with_mock_planner_writes_extended_plan_schema(tmp_path):
    result = run_task(
        task_text="写一个行楷风格的山",
        output_root=tmp_path,
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
        image_size=160,
        planner_mode="mock",
    )

    plan = json.loads(Path(result["plan_json"]).read_text(encoding="utf-8"))

    assert plan["planner_mode"] == "mock"
    assert plan["validation"]["ok"] is True
    assert plan["stroke_plan"]["stroke_count"] == 3
    assert "trajectory" not in plan
    assert "csv" not in plan
    assert "points" not in plan


def test_validate_plan_rejects_direct_csv_or_point_payloads():
    plan = plan_task("写一个行楷风格的山", mode="mock", style_profiles=_profiles(), graphics_path=GRAPHICS)
    plan["trajectory"] = [[1, 2], [3, 4]]
    plan["csv"] = "y,x\n1,2\n"

    validation = validate_plan(plan, style_profiles=_profiles(), graphics_path=GRAPHICS)

    assert validation["ok"] is False
    assert any("direct trajectory" in error for error in validation["errors"])
