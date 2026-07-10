from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = ROOT / "experiments" / "llm_style_trajectory" / "docs" / "b_route_visual_conclusion_freeze_note.md"
JSON_PATH = ROOT / "experiments" / "llm_style_trajectory" / "configs" / "b_route_visual_conclusion_freeze_note.json"


def test_b_route_visual_conclusion_freeze_note_json_roles_are_fixed():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "visual_conclusion_frozen"
    assert payload["main_candidate"].endswith("hybrid_section_compare_cn.png")
    assert payload["supplementary_candidate"] == [
        "experiments/llm_style_trajectory/outputs/b_route_visuals_cn_20260621_143505/h1_lite_u5c71_kaishu_lishu_contrast_cn.png"
    ]
    assert payload["limitation_or_risk_case"] == [
        "experiments/llm_style_trajectory/outputs/b_route_visuals_cn_20260621_143505/h1_lite_u98ce_lishu_risk_contrast_cn.png"
    ]
    roles = {item["recommended_role"] for item in payload["figures"]}
    assert roles == {"main_candidate", "supplementary_candidate", "limitation_or_risk_case"}


def test_b_route_visual_conclusion_freeze_note_doc_contains_freeze_guidance():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "main_candidate" in text
    assert "supplementary_candidate" in text
    assert "limitation_or_risk_case" in text
    assert "冻结" in text
    assert "不要把 `山/kaishu vs 山/lishu` 写成“明显风格分离”" in text
    assert "不要把 `风/lishu` 风险图写成“复杂隶书也取得良好效果”" in text
    assert "trial-only" in text


def test_b_route_visual_conclusion_freeze_note_does_not_import_libauboi5():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "libpyauboi5" not in text
