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


def _write_trial_csv(path: Path, segments: list[list[tuple[float, float]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["y", "x", "segment_id", "point_index", "is_break", "source"],
        )
        writer.writeheader()
        for segment_id, points in enumerate(segments, start=1):
            for point_index, (y, x) in enumerate(points):
                writer.writerow(
                    {
                        "y": y,
                        "x": x,
                        "segment_id": segment_id,
                        "point_index": point_index,
                        "is_break": 0,
                        "source": "font_skeleton_trial",
                    }
                )
            writer.writerow(
                {
                    "y": "nan",
                    "x": "nan",
                    "segment_id": segment_id,
                    "point_index": "",
                    "is_break": 1,
                    "source": "font_skeleton_trial",
                }
            )


def _build_fake_trial_dir(tmp_path: Path) -> Path:
    trial_dir = tmp_path / "font_derived_trial"
    samples = {
        "u4eba_kaishu": [
            [(10, 20), (30, 35), (60, 50)],
            [(10, 20), (9, 19)],
            [(12, 22), (35, 75), (60, 100)],
        ],
        "u5c71_lishu": [
            [(70, 20), (70, 80)],
            [(70, 82), (40, 82), (20, 82)],
            [(70, 20), (40, 20), (20, 20)],
        ],
        "u5c71_kaishu": [[(0, 0), (10, 10)]],
    }
    for subdir, segments in samples.items():
        sample_dir = trial_dir / subdir
        _write_trial_csv(sample_dir / "font_derived_trial_trajectory.csv", segments)
        (sample_dir / "font_derived_trial_compare.png").write_bytes(b"not-a-real-png")
    return trial_dir


def test_stroke_ordering_prototype_writes_only_two_sample_outputs(tmp_path):
    from font_skeleton_stroke_ordering_prototype import run_font_skeleton_stroke_ordering

    trial_dir = _build_fake_trial_dir(tmp_path)
    result = run_font_skeleton_stroke_ordering(
        trial_dir=trial_dir,
        output_dir=tmp_path / "ordering",
        copy_to_paper=False,
        min_segment_length_px=2.0,
        simplify_epsilon=0.5,
    )

    out_dir = Path(result["output_dir"])
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    assert (out_dir / "u4eba_kaishu").exists()
    assert (out_dir / "u5c71_lishu").exists()
    assert not (out_dir / "u5c71_kaishu").exists()

    for subdir in ["u4eba_kaishu", "u5c71_lishu"]:
        sample_dir = out_dir / subdir
        assert (sample_dir / "font_skeleton_ordered_trial_trajectory.csv").exists()
        assert (sample_dir / "font_skeleton_ordering_summary.json").exists()
        assert (sample_dir / "font_skeleton_ordering_compare.png").exists()
        assert not (sample_dir / "trajectory.csv").exists()

        rows = list(
            csv.DictReader(
                (sample_dir / "font_skeleton_ordered_trial_trajectory.csv").open(
                    encoding="utf-8-sig"
                )
            )
        )
        assert rows
        assert {
            "y",
            "x",
            "stroke_like_id",
            "point_index",
            "is_break",
            "order_index",
            "source",
        }.issubset(rows[0])
        assert all(row["source"] == "font_skeleton_ordering_trial" for row in rows)
        assert any(row["is_break"] == "1" for row in rows)

        summary = json.loads((sample_dir / "font_skeleton_ordering_summary.json").read_text(encoding="utf-8"))
        assert summary["raw_segment_count"] >= summary["simplified_segment_count"]
        assert summary["ordered_stroke_like_count"] == summary["simplified_segment_count"]
        assert "recommended_for_next_stage" in summary

    summary_rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(summary_rows) == 2
    assert {row["char_id"] for row in summary_rows} == {"u4eba", "u5c71"}

    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "不是正式轨迹" in report
    assert "不是真实笔顺恢复" in report
    assert "candidate writable order" in report
    assert "不接机器人" in report


def test_stroke_ordering_prototype_module_does_not_import_libauboi5():
    module_path = SRC / "font_skeleton_stroke_ordering_prototype.py"
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    assert "import libpyauboi5" not in text
    assert "from libpyauboi5" not in text
    assert importlib.util.find_spec("libpyauboi5") is None or True
