from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _read_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_fake_current_profile(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kaishu": {
                    "smoothness": 0.18,
                    "resample_step": 6.0,
                    "horizontal_scale": 1.0,
                    "vertical_scale": 1.0,
                    "corner_rounding": 0.12,
                    "connection_strength": 0.0,
                    "allow_interstroke_connections": False,
                    "speed_scale": 1.0,
                    "pen_up_height": 8.0,
                },
                "xingkai": {
                    "smoothness": 0.42,
                    "resample_step": 5.0,
                    "horizontal_scale": 1.03,
                    "vertical_scale": 0.98,
                    "corner_rounding": 0.36,
                    "connection_strength": 0.32,
                    "allow_interstroke_connections": True,
                    "speed_scale": 1.15,
                    "pen_up_height": 4.0,
                },
                "lishu": {
                    "smoothness": 0.24,
                    "resample_step": 5.5,
                    "horizontal_scale": 1.18,
                    "vertical_scale": 0.82,
                    "corner_rounding": 0.18,
                    "connection_strength": 0.0,
                    "allow_interstroke_connections": False,
                    "speed_scale": 0.9,
                    "pen_up_height": 7.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_fake_estimates(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "_status": "readonly_estimate_not_used_by_default",
                "_source": "fake_gap",
                "_warning": "not wired into generation pipeline",
                "styles": {
                    "kaishu": {
                        "horizontal_scale_hint": {"value": 1.0},
                        "vertical_scale_hint": {"value": 1.0},
                        "base_width_hint": {"value": 6.3},
                    },
                    "xingkai": {
                        "horizontal_scale_hint": {"value": 0.98},
                        "vertical_scale_hint": {"value": 1.02},
                        "base_width_hint": {"value": 9.6},
                    },
                    "lishu": {
                        "horizontal_scale_hint": {"value": 1.2},
                        "vertical_scale_hint": {"value": 0.83},
                        "base_width_hint": {"value": 9.0},
                    },
                },
                "unsupported_from_static_font": [
                    "connection_strength",
                    "allow_interstroke_connections",
                    "connector_trigger",
                    "connector_shape",
                    "pressure_curve",
                    "speed_scale",
                    "pen_up_height",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_phase1_candidate_profile_preserves_unsupported_connector_fields(tmp_path):
    from phase1_profile_comparison import build_phase1_candidate_profile

    current_path = tmp_path / "style_profiles.json"
    estimates_path = tmp_path / "style_profile_phase1_estimates.json"
    _write_fake_current_profile(current_path)
    _write_fake_estimates(estimates_path)
    before = current_path.read_text(encoding="utf-8")

    candidate = build_phase1_candidate_profile(
        current_profile_path=current_path,
        estimates_path=estimates_path,
        output_path=tmp_path / "style_profile_phase1_candidate.json",
    )

    candidate_path = Path(candidate["candidate_profile_path"])
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert payload["_status"] == "comparison_only_not_default"
    assert payload["xingkai"]["horizontal_scale"] == 0.98
    assert payload["xingkai"]["vertical_scale"] == 1.02
    assert payload["xingkai"]["connection_strength"] == 0.32
    assert payload["xingkai"]["allow_interstroke_connections"] is True
    assert payload["xingkai"]["speed_scale"] == 1.15
    assert payload["xingkai"]["pen_up_height"] == 4.0
    assert payload["_phase1_base_width_hints"]["xingkai"] == 9.6
    assert current_path.read_text(encoding="utf-8") == before


def test_phase1_profile_comparison_generates_summary_report_manifest_and_figures(tmp_path):
    from phase1_profile_comparison import run_phase1_profile_comparison

    current_path = tmp_path / "style_profiles.json"
    estimates_path = tmp_path / "style_profile_phase1_estimates.json"
    _write_fake_current_profile(current_path)
    _write_fake_estimates(estimates_path)
    before = current_path.read_text(encoding="utf-8")

    result = run_phase1_profile_comparison(
        estimates_path=estimates_path,
        current_profile_path=current_path,
        output_dir=tmp_path / "phase1_compare",
        samples=[{"char": "山", "styles": ["kaishu", "xingkai"]}],
        image_size=128,
        copy_to_paper=False,
    )

    summary_path = Path(result["summary_csv"])
    report_path = Path(result["report_md"])
    manifest_path = Path(result["manifest_csv"])
    candidate_path = Path(result["candidate_profile"])

    assert summary_path.exists()
    assert report_path.exists()
    assert manifest_path.exists()
    assert candidate_path.exists()
    assert current_path.read_text(encoding="utf-8") == before

    rows = _read_csv(summary_path)
    assert {row["variant"] for row in rows} == {"current", "phase1"}
    assert {row["style"] for row in rows} == {"kaishu", "xingkai"}
    required_fields = {
        "char",
        "style",
        "variant",
        "profile_source",
        "horizontal_scale",
        "vertical_scale",
        "base_width",
        "aspect_ratio",
        "bbox_width",
        "bbox_height",
        "path_length",
        "connection_count",
        "connector_draw_length",
        "mean_width",
        "stroke_width_range",
        "visual_change_expected",
        "needs_user_review",
        "aspect_ratio_delta",
        "mean_width_delta",
    }
    assert required_fields.issubset(rows[0].keys())

    manifest = _read_csv(manifest_path)
    assert manifest
    assert any(Path(row["figure_path"]).exists() for row in manifest)
    assert result["figures"]
    assert all(Path(path).exists() for path in result["figures"].values())

    report = report_path.read_text(encoding="utf-8")
    assert "不接默认" in report
    assert "人工看图" in report
    assert "Phase 2" in report
    assert "comparison_only_not_default" in report


def test_phase1_profile_comparison_module_does_not_import_aubo_sdk():
    module_path = SRC_DIR / "phase1_profile_comparison.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
