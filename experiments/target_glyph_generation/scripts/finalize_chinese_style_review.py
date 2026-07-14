"""Finalize ChineseStyle OCR review drafts without mutating their source CSV files."""

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.review_finalization import (
    CANDIDATE_FIELDNAMES,
    ISSUE_FIELDNAMES,
    REJECTED_FIELDNAMES,
    candidate_rows,
    finalize_review_drafts,
    issue_rows,
    load_ocr_labels,
    load_review_draft,
    rejected_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize read-only manual review drafts for ChineseStyle OCR labels"
    )
    parser.add_argument("--ocr-labels", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True, action="append")
    parser.add_argument("--resolution-draft", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    labels = load_ocr_labels(arguments.ocr_labels)
    drafts = [load_review_draft(path) for path in arguments.draft]
    resolution_drafts = [
        load_review_draft(path) for path in (arguments.resolution_draft or [])
    ]
    result = finalize_review_drafts(labels, drafts, resolution_drafts=resolution_drafts)
    summary = {
        "candidate_count": len(result.candidates),
        "rejected_count": len(result.rejected),
        "unresolved_count": len(result.unresolved),
        "conflict_count": len(result.conflicts),
        "normalization_count": len(result.normalizations),
        "is_finalizable": result.is_finalizable,
    }
    _write_outputs(arguments.output_dir, result, summary)
    print(json.dumps(summary, ensure_ascii=False))
    if not result.is_finalizable:
        raise SystemExit(1)


def _write_outputs(output_dir: Path, result, summary: dict[str, object]) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "unresolved_rows.csv", ISSUE_FIELDNAMES, issue_rows(result.unresolved))
    _write_csv(output_dir / "conflict_rows.csv", ISSUE_FIELDNAMES, issue_rows(result.conflicts))
    _write_csv(output_dir / "rejected_rows.csv", REJECTED_FIELDNAMES, rejected_rows(result.rejected))
    (output_dir / "normalization_report.json").write_text(
        json.dumps({"normalizations": issue_rows(result.normalizations)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "review_finalization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    candidate_path = output_dir / "candidate_manifest.csv"
    if result.is_finalizable:
        _write_csv(candidate_path, CANDIDATE_FIELDNAMES, candidate_rows(result.candidates))
    elif candidate_path.exists():
        candidate_path.unlink()


def _write_csv(path: Path, fieldnames, rows) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
