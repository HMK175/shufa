from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC = EXP_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_execution_csv(path: Path, *, style: str, with_connector: bool = True) -> None:
    fields = [
        "segment_id",
        "stroke_id",
        "point_id",
        "y",
        "x",
        "z",
        "speed",
        "pressure",
        "width",
        "pen_down",
        "is_connector",
        "segment_type",
        "connection_preference",
    ]
    rows = [
        [1, 1, 0, 10, 10, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
        [1, 1, 1, 20, 20, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
    ]
    if with_connector:
        rows.extend(
            [
                [2, 2, 0, 20, 20, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
                [2, 2, 1, 24, 24, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
                [3, 2, 0, 24, 24, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
                [3, 2, 1, 34, 34, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
                [4, 3, 0, 34, 34, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
                [4, 3, 1, 190, 190, 0, 1.3, 0.35, 4, 1, 1, "connector", "weak"],
                [5, 3, 0, 190, 190, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
                [5, 3, 1, 210, 210, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
            ]
        )
    else:
        rows.extend(
            [
                [2, 2, 0, 20, 20, 8, 1.6, 0, 0, 0, 0, "pen_up_move", "weak"],
                [2, 2, 1, 50, 50, 8, 1.6, 0, 0, 0, 0, "pen_up_move", "weak"],
                [3, 2, 0, 50, 50, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
                [3, 2, 1, 70, 70, 0, 1, 1, 9, 1, 0, "stroke", "weak"],
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        writer.writerows(rows)


def _write_fake_inputs(tmp_path: Path) -> tuple[Path, Path]:
    summary_fields = [
        "char",
        "style",
        "success",
        "output_dir",
        "execution_trajectory_csv",
        "connection_count",
        "connector_draw_length",
        "path_length",
    ]
    rows = []
    for char, style, with_connector in [
        ("国", "xingkai", True),
        ("人", "kaishu", False),
        ("人", "lishu", True),
    ]:
        out_dir = tmp_path / f"u{ord(char):04x}_{style}_sample"
        _write_execution_csv(out_dir / "execution_trajectory.csv", style=style, with_connector=with_connector)
        rows.append(
            {
                "char": char,
                "style": style,
                "success": "True",
                "output_dir": str(out_dir),
                "execution_trajectory_csv": str(out_dir / "execution_trajectory.csv"),
                "connection_count": "2" if with_connector else "0",
                "connector_draw_length": "200" if with_connector else "0",
                "path_length": "300",
            }
        )
    summary_csv = tmp_path / "style_diagnostic_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(rows)

    candidates_csv = tmp_path / "visual_audit_candidates.csv"
    with candidates_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["char", "style", "output_dir", "priority"])
        writer.writeheader()
        writer.writerow({"char": "国", "style": "xingkai", "output_dir": rows[0]["output_dir"], "priority": "1"})
        writer.writerow({"char": "缺", "style": "xingkai", "output_dir": str(tmp_path / "missing"), "priority": "1"})
    return summary_csv, candidates_csv


def test_validation_selects_samples_writes_outputs_and_failures(tmp_path):
    from execution_refinement_validation import run_execution_refinement_validation

    summary_csv, candidates_csv = _write_fake_inputs(tmp_path)
    result = run_execution_refinement_validation(
        summary_csv=summary_csv,
        candidates_csv=candidates_csv,
        output_dir=tmp_path / "out",
        target_pairs=[("国", "xingkai"), ("人", "kaishu"), ("人", "lishu"), ("缺", "xingkai")],
        copy_to_paper=False,
    )

    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()
    assert Path(result["failures_csv"]).exists()
    assert result["success_count"] == 3
    assert result["failure_count"] == 1

    with Path(result["summary_csv"]).open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    by_key = {(row["char"], row["style"]): row for row in rows}
    assert int(by_key[("国", "xingkai")]["after_connection_count"]) <= int(
        by_key[("国", "xingkai")]["before_connection_count"]
    )
    assert float(by_key[("国", "xingkai")]["after_stroke_width_range"]) > 0
    assert by_key[("人", "kaishu")]["kaishu_lishu_connector_violation"] == "False"
    assert by_key[("人", "lishu")]["kaishu_lishu_connector_violation"] == "False"

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "人工看图" in report
    assert "不继续调参" in report
    assert "candidate_default_v1 不是全局默认" in report


def test_validation_loads_candidate_default_v1_from_config():
    from execution_refinement_validation import load_candidate_default

    candidate = load_candidate_default()

    assert candidate["connector_rule_name"] == "conservative"
    assert candidate["stroke_width_profile_name"] == "simple_taper"
    assert candidate["status"] == "accepted_for_next_round_candidate"


def test_validation_flags_kaishu_lishu_connector_violation_when_after_has_connector(tmp_path):
    from execution_refinement_validation import _row_for_sample

    baseline = tmp_path / "baseline.csv"
    refined = tmp_path / "refined.csv"
    before_after = tmp_path / "before_after.png"
    overlay = tmp_path / "overlay.png"
    width_pressure = tmp_path / "width_pressure.png"
    before_rows = [
        {
            "segment_id": 1,
            "stroke_id": 1,
            "point_id": 0,
            "y": 0,
            "x": 0,
            "z": 0,
            "speed": 1,
            "pressure": 1,
            "width": 9,
            "pen_down": 1,
            "is_connector": 0,
            "segment_type": "stroke",
            "connection_preference": "weak",
        }
    ]
    after_rows = before_rows + [
        {
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 0,
            "y": 0,
            "x": 0,
            "z": 0,
            "speed": 1,
            "pressure": 0.3,
            "width": 4,
            "pen_down": 1,
            "is_connector": 1,
            "segment_type": "connector",
            "connection_preference": "weak",
        },
        {
            "segment_id": 2,
            "stroke_id": 2,
            "point_id": 1,
            "y": 10,
            "x": 10,
            "z": 0,
            "speed": 1,
            "pressure": 0.3,
            "width": 4,
            "pen_down": 1,
            "is_connector": 1,
            "segment_type": "connector",
            "connection_preference": "weak",
        },
    ]

    row = _row_for_sample(
        sample={"char": "人", "style": "lishu", "output_dir": str(tmp_path)},
        before_rows=before_rows,
        after_rows=after_rows,
        baseline_csv=baseline,
        refined_csv=refined,
        before_after_png=before_after,
        connector_overlay_png=overlay,
        width_pressure_png=width_pressure,
    )

    assert row["kaishu_lishu_connector_violation"] is True


def test_execution_refinement_validation_does_not_import_libauboi5():
    module_path = SRC / "execution_refinement_validation.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or "libpyauboi5" not in text
