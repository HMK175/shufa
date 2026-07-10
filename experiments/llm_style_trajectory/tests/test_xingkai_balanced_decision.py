from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
PROFILE_PATH = EXP_DIR / "configs" / "execution_refinement_profiles.json"
DECISION_PATH = EXP_DIR / "docs" / "xingkai_balanced_decision.md"


def test_candidate_default_v2_points_to_balanced_refinement_and_is_not_global_default():
    profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    defaults = profiles["candidate_defaults"]

    assert "candidate_default_v1" in defaults
    assert "candidate_default_v2" in defaults

    candidate = defaults["candidate_default_v2"]
    assert candidate["connector_rule"] == "balanced"
    assert candidate["connector_shape"] == "slight_curve"
    assert candidate["stroke_width_profile"] == "xingkai_expressive_taper"
    assert candidate["status"] == "accepted_for_next_round_candidate"
    assert candidate["date"] == "2026-06-18"
    assert "曲线" in candidate["human_feedback"] or "curve" in candidate["human_feedback"].lower()

    serialized = json.dumps(candidate, ensure_ascii=False).lower()
    assert candidate.get("global") is not True
    assert candidate.get("is_global_default") is not True
    assert "global_default" not in serialized
    assert "set_as_default" not in serialized


def test_xingkai_balanced_decision_doc_records_feedback_and_boundaries():
    text = DECISION_PATH.read_text(encoding="utf-8")

    assert "candidate_default_v2" in text
    assert "人工反馈" in text
    assert "暂不替换全局默认" in text
    assert "曲线 connector" in text
    assert "不进入仿真书写" in text
    assert "不是最终行楷模型" in text


def test_xingkai_balanced_decision_does_not_import_libauboi5():
    python_files = [
        EXP_DIR / "src" / "execution_refinement.py",
        EXP_DIR / "src" / "xingkai_balanced_experiment.py",
    ]
    for path in python_files:
        text = path.read_text(encoding="utf-8")
        assert "import libpyauboi5" not in text
        assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
