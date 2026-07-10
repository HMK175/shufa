from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
PROFILE = EXP_DIR / "configs" / "execution_refinement_profiles.json"
DECISION_DOC = EXP_DIR / "docs" / "execution_refinement_decision.md"
OUTPUT_DIR = EXP_DIR / "outputs" / "execution_refinement_20260618_104837"


def test_candidate_default_v1_points_to_conservative_and_simple_taper():
    data = json.loads(PROFILE.read_text(encoding="utf-8"))
    candidate = data["candidate_defaults"]["candidate_default_v1"]

    assert candidate["connector_rule"] == "conservative"
    assert candidate["stroke_width_profile"] == "simple_taper"
    assert candidate["status"] == "accepted_for_next_round_candidate"
    assert "slightly sparse" in candidate["human_feedback"]


def test_lishu_refined_execution_has_no_connector_and_summary_is_zero():
    refined_csv = OUTPUT_DIR / "cases" / "u4eba_lishu" / "refined_execution_trajectory.csv"
    summary_csv = OUTPUT_DIR / "execution_refinement_summary.csv"

    with refined_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert [row for row in rows if row["segment_type"] == "connector"] == []
    assert [row for row in rows if row["is_connector"] == "1"] == []

    with summary_csv.open(newline="", encoding="utf-8") as fh:
        summary_rows = list(csv.DictReader(fh))
    lishu = next(row for row in summary_rows if row["char"] == "人" and row["style"] == "lishu")
    assert float(lishu["before_connector_draw_length"]) == 0.0
    assert float(lishu["after_connector_draw_length"]) == 0.0
    assert float(lishu["after_stroke_width_range"]) > 0.0


def test_decision_doc_records_human_feedback_and_boundaries():
    text = DECISION_DOC.read_text(encoding="utf-8")

    assert "candidate_default_v1" in text
    assert "人工反馈" in text
    assert "暂不作为全局默认" in text
    assert "本轮不继续调参数" in text
    assert "lishu" in text
    assert "不允许 connector" in text


def test_decision_artifacts_do_not_import_libauboi5():
    for path in [
        EXP_DIR / "src" / "execution_refinement.py",
        EXP_DIR / "src" / "execution_refinement_experiment.py",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in PROFILE.read_text(encoding="utf-8")
