import csv
import json
import sys
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import planner as planner_module
from evaluate_planner_robustness import run_robustness


GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
PROFILES = EXP_DIR / "configs" / "style_profiles.json"


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _chat_response(content):
    return {"choices": [{"message": {"content": content}}]}


def _write_tasks(tmp_path, tasks):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _configure_api(monkeypatch):
    monkeypatch.setenv("LLM_STYLE_PLANNER_API_KEY", "test-key-not-written")
    monkeypatch.setenv("LLM_STYLE_PLANNER_ENDPOINT", "https://example.invalid/chat/completions")
    monkeypatch.setenv("LLM_STYLE_PLANNER_MODEL", "deepseek-v4-pro")


def test_robustness_summary_and_report_are_generated_with_fake_api(tmp_path, monkeypatch):
    _configure_api(monkeypatch)
    payloads = [
        _chat_response(json.dumps({"char": "山", "style": "xingkai", "constraints": {"allow_interstroke_connections": True}}, ensure_ascii=False)),
        _chat_response(json.dumps({"char": "山", "style": "caoshu", "constraints": {"allow_interstroke_connections": False}}, ensure_ascii=False)),
        _chat_response(json.dumps({"char": "山", "style": "xingkai", "trajectory": [[1, 2]], "csv": "y,x\n1,2\n"}, ensure_ascii=False)),
        _chat_response("not json"),
    ]

    def fake_urlopen(request, timeout=30):
        return _FakeResponse(payloads.pop(0))

    monkeypatch.setattr(planner_module, "urlopen", fake_urlopen)
    tasks_path = _write_tasks(
        tmp_path,
        [
            {
                "id": "valid",
                "task": "写一个行楷风格的山",
                "expected_char": "山",
                "expected_style": "xingkai",
                "expected_allow_interstroke_connections": True,
                "expected_validation_ok": True,
            },
            {
                "id": "invalid_style",
                "task": "写一个草书风格的山",
                "expected_char": "山",
                "expected_style": "caoshu",
                "expected_allow_interstroke_connections": False,
                "expected_validation_ok": False,
            },
            {
                "id": "dangerous",
                "task": "不要输出CSV，只给计划",
                "expected_char": "山",
                "expected_style": "xingkai",
                "expected_allow_interstroke_connections": True,
                "expected_validation_ok": True,
            },
            {
                "id": "non_json",
                "task": "写一个行楷风格的山",
                "expected_char": "山",
                "expected_style": "xingkai",
                "expected_allow_interstroke_connections": True,
                "expected_validation_ok": False,
            },
        ],
    )

    result = run_robustness(
        planner_mode="api",
        tasks_path=tasks_path,
        out_dir=tmp_path / "out",
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
    )

    summary_path = Path(result["summary_csv"])
    report_path = Path(result["report_md"])
    assert summary_path.exists()
    assert report_path.exists()
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8", newline="")))
    assert len(rows) == 4
    assert result["metrics"]["total"] == 4
    assert result["metrics"]["expected_invalid_rejected_count"] == 2
    assert result["metrics"]["dangerous_output_count"] == 1
    assert result["metrics"]["json_parse_success_count"] == 3
    assert "validation_ok_count" in report_path.read_text(encoding="utf-8")


def test_robustness_api_single_failure_does_not_stop_batch(tmp_path, monkeypatch):
    _configure_api(monkeypatch)
    calls = {"count": 0}

    def fake_urlopen(request, timeout=30):
        calls["count"] += 1
        if calls["count"] == 2:
            raise URLError("temporary outage")
        return _FakeResponse(
            _chat_response(json.dumps({"char": "山", "style": "xingkai", "constraints": {"allow_interstroke_connections": True}}, ensure_ascii=False))
        )

    monkeypatch.setattr(planner_module, "urlopen", fake_urlopen)
    tasks_path = _write_tasks(
        tmp_path,
        [
            {"id": "a", "task": "写一个行楷风格的山", "expected_char": "山", "expected_style": "xingkai", "expected_allow_interstroke_connections": True, "expected_validation_ok": True},
            {"id": "b", "task": "写一个行楷风格的山", "expected_char": "山", "expected_style": "xingkai", "expected_allow_interstroke_connections": True, "expected_validation_ok": False},
            {"id": "c", "task": "写一个行楷风格的山", "expected_char": "山", "expected_style": "xingkai", "expected_allow_interstroke_connections": True, "expected_validation_ok": True},
        ],
    )

    result = run_robustness(
        planner_mode="api",
        tasks_path=tasks_path,
        out_dir=tmp_path / "out",
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
    )

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8", newline="")))
    assert len(rows) == 3
    assert rows[1]["validation_ok"] == "False"
    assert "api planner request failed" in rows[1]["error"]
    assert result["metrics"]["total"] == 3


def test_robustness_summary_records_request_boundary_rejections(tmp_path, monkeypatch):
    _configure_api(monkeypatch)
    response = _chat_response(
        json.dumps(
            {
                "char": "山",
                "style": "xingkai",
                "constraints": {"allow_interstroke_connections": True},
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr(planner_module, "urlopen", lambda request, timeout=30: _FakeResponse(response))
    tasks_path = _write_tasks(
        tmp_path,
        [
            {
                "id": "unsupported_mapped",
                "task": "写一个草书风格的山",
                "expected_char": "山",
                "expected_style": "caoshu",
                "expected_allow_interstroke_connections": False,
                "expected_validation_ok": False,
            }
        ],
    )

    result = run_robustness(
        planner_mode="api",
        tasks_path=tasks_path,
        out_dir=tmp_path / "out",
        graphics_path=GRAPHICS,
        style_profiles_path=PROFILES,
    )

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8", newline="")))
    assert rows[0]["validation_ok"] == "False"
    assert rows[0]["expected_invalid_rejected"] == "True"
    assert rows[0]["request_status"] == "unsupported"
    assert rows[0]["requested_style_raw"] == "草书"
    assert rows[0]["mapped_style"] == "xingkai"
    assert "unsupported style" in rows[0]["error"]
    assert result["metrics"]["expected_invalid_rejected_count"] == 1
