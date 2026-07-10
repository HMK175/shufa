from pathlib import Path
import csv
import json
import sys

from PIL import Image, ImageDraw


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from run_pipeline import run_batch
from exporters import write_batch_report
from smoke_benchmark import (
    collect_batch_summaries,
    create_smoke_benchmark_report,
    write_manual_audit_sheet,
    write_visual_audit_contact_sheet,
)


EXPECTED_AUDIT_COLUMNS = [
    "sample",
    "status",
    "audit_status",
    "failure_reason",
    "mask_ok",
    "skeleton_ok",
    "segments_ok",
    "order_ok",
    "trajectory_ok",
    "failure_type",
    "notes",
    "summary_path",
    "candidate_order_image",
    "final_trajectory_image",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_simple_glyph(path: Path) -> None:
    image = Image.new("L", (32, 32), 255)
    draw = ImageDraw.Draw(image)
    draw.line((8, 16, 24, 16), fill=0, width=5)
    draw.line((16, 8, 16, 24), fill=0, width=5)
    image.save(path)


def _write_panel(path: Path, color: tuple[int, int, int], *, size: tuple[int, int] = (24, 16)) -> None:
    image = Image.new("RGB", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _row_by_sample(rows: list[dict[str, str]], sample: str) -> dict[str, str]:
    matches = [row for row in rows if row["sample"] == sample]
    assert len(matches) == 1
    return matches[0]


def test_collect_batch_summaries_returns_sample_rows_with_artifact_paths(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    ok_dir = batch_dir / "ok_sample"
    fail_dir = batch_dir / "failed_sample"
    _write_json(
        ok_dir / "recovery_summary.json",
        {
            "status": "ok",
            "audit_status": "promising",
            "sample_dir": str(ok_dir),
        },
    )
    (ok_dir / "candidate_order.png").write_bytes(b"fake-png")
    (ok_dir / "final_trajectory.png").write_bytes(b"fake-png")
    _write_json(
        fail_dir / "recovery_summary.json",
        {
            "status": "failed",
            "audit_status": "failed",
            "failure_reason": "no_foreground_pixels",
            "sample_dir": str(fail_dir),
        },
    )

    rows = collect_batch_summaries(batch_dir)

    assert [row["sample"] for row in rows] == ["failed_sample", "ok_sample"]
    failed, ok = rows
    assert failed["status"] == "failed"
    assert failed["failure_reason"] == "no_foreground_pixels"
    assert failed["candidate_order_image"] == "n/a"
    assert failed["final_trajectory_image"] == "n/a"
    assert failed["summary_path"] == str(fail_dir / "recovery_summary.json")
    assert ok["status"] == "ok"
    assert ok["failure_reason"] == ""
    assert ok["candidate_order_image"] == str(ok_dir / "candidate_order.png")
    assert ok["final_trajectory_image"] == str(ok_dir / "final_trajectory.png")


def test_collect_batch_summaries_reports_missing_and_invalid_summaries(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    missing_dir = batch_dir / "missing_sample"
    invalid_dir = batch_dir / "invalid_sample"
    missing_dir.mkdir(parents=True)
    invalid_dir.mkdir(parents=True)
    (missing_dir / "candidate_order.png").write_bytes(b"fake-png")
    (invalid_dir / "recovery_summary.json").write_text("{not json", encoding="utf-8")
    (invalid_dir / "final_trajectory.png").write_bytes(b"fake-png")

    rows = collect_batch_summaries(batch_dir)

    assert [row["sample"] for row in rows] == ["invalid_sample", "missing_sample"]
    invalid_row = _row_by_sample(rows, "invalid_sample")
    assert invalid_row["status"] == "failed"
    assert invalid_row["audit_status"] == "failed"
    assert invalid_row["failure_reason"] == "invalid_summary"
    assert invalid_row["summary_path"] == str(invalid_dir / "recovery_summary.json")
    assert invalid_row["candidate_order_image"] == "n/a"
    assert invalid_row["final_trajectory_image"] == str(invalid_dir / "final_trajectory.png")
    assert invalid_row["mask_ok"] == ""
    assert invalid_row["notes"] == ""

    missing_row = _row_by_sample(rows, "missing_sample")
    assert missing_row["status"] == "failed"
    assert missing_row["audit_status"] == "failed"
    assert missing_row["failure_reason"] == "missing_summary"
    assert missing_row["summary_path"] == "n/a"
    assert missing_row["candidate_order_image"] == str(missing_dir / "candidate_order.png")
    assert missing_row["final_trajectory_image"] == "n/a"
    assert missing_row["segments_ok"] == ""
    assert missing_row["failure_type"] == ""


def test_collect_batch_summaries_uses_current_sample_dir_for_artifacts(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    sample_dir = batch_dir / "moved_sample"
    stale_dir = tmp_path / "old_location" / "moved_sample"
    _write_json(
        sample_dir / "recovery_summary.json",
        {
            "sample": "moved_sample",
            "status": "ok",
            "audit_status": "promising",
            "sample_dir": str(stale_dir),
        },
    )
    (sample_dir / "candidate_order.png").write_bytes(b"fake-png")
    (sample_dir / "final_trajectory.png").write_bytes(b"fake-png")

    rows = collect_batch_summaries(batch_dir)

    row = rows[0]
    assert row["candidate_order_image"] == str(sample_dir / "candidate_order.png")
    assert row["final_trajectory_image"] == str(sample_dir / "final_trajectory.png")


def test_write_manual_audit_sheet_uses_blank_manual_fields(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    sample_dir = batch_dir / "sample_a"
    _write_json(
        sample_dir / "recovery_summary.json",
        {
            "status": "ok",
            "audit_status": "risky_needs_manual_check",
            "sample_dir": str(sample_dir),
        },
    )

    output_path = write_manual_audit_sheet(batch_dir)

    assert output_path == batch_dir / "manual_audit_sheet.csv"
    rows = _read_csv_rows(output_path)
    assert list(rows[0]) == EXPECTED_AUDIT_COLUMNS
    for field in [
        "mask_ok",
        "skeleton_ok",
        "segments_ok",
        "order_ok",
        "trajectory_ok",
        "failure_type",
        "notes",
    ]:
        assert rows[0][field] == ""


def test_write_visual_audit_contact_sheet_creates_nonempty_png(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    alpha_dir = batch_dir / "alpha"
    beta_dir = batch_dir / "beta"
    _write_json(
        alpha_dir / "recovery_summary.json",
        {
            "sample": "alpha",
            "status": "ok",
            "audit_status": "promising",
            "sample_dir": str(alpha_dir),
        },
    )
    _write_json(
        beta_dir / "recovery_summary.json",
        {
            "sample": "beta",
            "status": "ok",
            "audit_status": "risky_needs_manual_check",
            "sample_dir": str(beta_dir),
        },
    )
    for sample_dir, color in [(alpha_dir, (220, 80, 80)), (beta_dir, (80, 80, 220))]:
        _write_panel(sample_dir / "input_image.png", color)
        _write_panel(sample_dir / "clean_skeleton.png", tuple(max(channel - 40, 0) for channel in color))
        _write_panel(sample_dir / "final_trajectory.png", tuple(min(channel + 20, 255) for channel in color))

    output_path = write_visual_audit_contact_sheet(batch_dir)

    assert output_path == batch_dir / "visual_audit_contact_sheet.png"
    image = Image.open(output_path).convert("RGB")
    assert image.width > image.height
    assert image.getbbox() is not None


def test_write_visual_audit_contact_sheet_tolerates_missing_panels(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    sample_dir = batch_dir / "gamma"
    _write_json(
        sample_dir / "recovery_summary.json",
        {
            "sample": "gamma",
            "status": "failed",
            "audit_status": "failed",
            "sample_dir": str(sample_dir),
        },
    )
    _write_panel(sample_dir / "input_image.png", (30, 30, 30))

    output_path = write_visual_audit_contact_sheet(batch_dir)

    image = Image.open(output_path).convert("RGB")
    assert image.size[0] > 0
    assert image.size[1] > 0


def test_create_smoke_benchmark_report_counts_statuses(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    for sample, status, audit_status in [
        ("ok_sample", "ok", "promising"),
        ("risky_sample", "ok", "risky_needs_manual_check"),
        ("failed_sample", "failed", "failed"),
    ]:
        _write_json(
            batch_dir / sample / "recovery_summary.json",
            {
                "status": status,
                "audit_status": audit_status,
                "sample_dir": str(batch_dir / sample),
            },
        )

    report = create_smoke_benchmark_report(batch_dir)

    assert report["batch_dir"] == str(batch_dir)
    assert report["total_samples"] == 3
    assert report["status_counts"] == {"failed": 1, "ok": 2}
    assert report["audit_status_counts"] == {
        "failed": 1,
        "promising": 1,
        "risky_needs_manual_check": 1,
    }
    assert report["manual_audit_sheet"] == str(batch_dir / "manual_audit_sheet.csv")


def test_run_batch_uses_unique_sample_names_for_duplicate_stems(tmp_path: Path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_path = first_dir / "foo.png"
    second_path = second_dir / "foo.png"
    _make_simple_glyph(first_path)
    _make_simple_glyph(second_path)

    batch_dir = run_batch([first_path, second_path], tmp_path / "batch_outputs")

    audit_rows = _read_csv_rows(batch_dir / "manual_audit_sheet.csv")
    assert [row["sample"] for row in audit_rows] == ["foo", "foo_2"]
    first_summary = json.loads((batch_dir / "foo" / "recovery_summary.json").read_text(encoding="utf-8"))
    second_summary = json.loads((batch_dir / "foo_2" / "recovery_summary.json").read_text(encoding="utf-8"))
    assert first_summary["sample"] == "foo"
    assert second_summary["sample"] == "foo_2"

    report = (batch_dir / "batch_report.md").read_text(encoding="utf-8")
    assert report.count("| foo |") == 2
    assert report.count("| foo_2 |") == 2


def test_run_batch_writes_manual_audit_sheet_and_mentions_it_in_report(tmp_path: Path):
    simple_path = tmp_path / "simple_glyph.png"
    blank_path = tmp_path / "blank_sample.png"
    _make_simple_glyph(simple_path)
    Image.new("L", (16, 16), 255).save(blank_path)

    batch_dir = run_batch([simple_path, blank_path], tmp_path / "batch_outputs")

    audit_path = batch_dir / "manual_audit_sheet.csv"
    assert audit_path.exists()
    rows = _read_csv_rows(audit_path)
    assert [row["sample"] for row in rows] == ["blank_sample", "simple_glyph"]
    blank_row = rows[0]
    assert blank_row["status"] == "failed"
    assert blank_row["failure_reason"] == "no_foreground_pixels"
    assert blank_row["candidate_order_image"] == "n/a"
    assert blank_row["final_trajectory_image"] == "n/a"
    assert blank_row["mask_ok"] == ""
    assert blank_row["trajectory_ok"] == ""

    report = (batch_dir / "batch_report.md").read_text(encoding="utf-8")
    assert "manual_audit_sheet.csv" in report
    assert str(audit_path) in report


def test_batch_report_escapes_newlines_in_markdown_cells(tmp_path: Path):
    report_path = tmp_path / "batch_report.md"

    write_batch_report(
        report_path,
        [
            {
                "sample": "sample\none",
                "status": "failed",
                "failure_reason": "bad\r\nline|pipe",
                "audit_status": "failed",
                "component_count": "n/a",
                "branch_point_count": "n/a",
                "max_pen_up_jump_px": "n/a",
                "trajectory_point_count": "n/a",
                "sample_dir": "dir\nname",
                "summary_path": "n/a",
                "trajectory_path": "n/a",
                "final_trajectory_image": "n/a",
            }
        ],
    )

    report = report_path.read_text(encoding="utf-8")
    assert "sample<br>one" in report
    assert "bad<br>line\\|pipe" in report
    assert "dir<br>name" in report
    assert "\none |" not in report
    assert "bad\r" not in report
