"""One-shot refresh entrypoint for the offline CalliRewrite hybrid route."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from callirewrite_adapter import convert_callirewrite_npz_to_outputs
from callirewrite_hybrid import run_callirewrite_hybrid_probe
from exporters import write_summary_json


def run_callirewrite_refresh_probe(
    *,
    seq_data_dir: Path,
    converted_dir: Path,
    input_dir: Path,
    output_dir: Path,
    samples: Sequence[str] | None = None,
) -> dict[str, Any]:
    seq_data_dir = Path(seq_data_dir)
    converted_dir = Path(converted_dir)
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not seq_data_dir.exists():
        return {
            "status": "missing_seq_data_dir",
            "stage": "callirewrite_refresh_probe",
            "seq_data_dir": str(seq_data_dir),
        }
    if not input_dir.exists():
        return {
            "status": "missing_input_dir",
            "stage": "callirewrite_refresh_probe",
            "input_dir": str(input_dir),
        }

    normalized_samples = _normalized_samples(samples)
    if normalized_samples:
        npz_paths = []
        missing_samples: list[str] = []
        for sample in normalized_samples:
            npz_path = seq_data_dir / f"{sample}.npz"
            if npz_path.exists():
                npz_paths.append(npz_path)
            else:
                missing_samples.append(sample)
        if missing_samples:
            return {
                "status": "missing_seq_data_samples",
                "stage": "callirewrite_refresh_probe",
                "seq_data_dir": str(seq_data_dir),
                "missing_samples": missing_samples,
            }
    else:
        npz_paths = sorted(seq_data_dir.glob("*.npz"))
        normalized_samples = [path.stem for path in npz_paths]

    if not npz_paths:
        return {
            "status": "no_seq_data_files",
            "stage": "callirewrite_refresh_probe",
            "seq_data_dir": str(seq_data_dir),
        }

    converted_dir.mkdir(parents=True, exist_ok=True)
    converted_summaries = [
        convert_callirewrite_npz_to_outputs(npz_path, converted_dir / npz_path.stem)
        for npz_path in npz_paths
    ]

    hybrid_payload = run_callirewrite_hybrid_probe(
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=normalized_samples,
    )

    payload = {
        "status": hybrid_payload.get("status", "failed"),
        "stage": "callirewrite_refresh_probe",
        "seq_data_dir": str(seq_data_dir),
        "converted_dir": str(converted_dir),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "converted_count": len(converted_summaries),
        "converted_samples": normalized_samples,
        "converted_summaries": [str(path) for path in converted_summaries],
        "hybrid_batch_dir": hybrid_payload.get("batch_dir", ""),
        "visual_audit_contact_sheet": hybrid_payload.get("visual_audit_contact_sheet", ""),
        "manual_audit_sheet": hybrid_payload.get("manual_audit_sheet", ""),
        "hybrid_report_path": hybrid_payload.get("report_path", ""),
        "boundary_note": (
            "Refreshes CalliRewrite seq_extract .npz conversions before running the local "
            "offline hybrid visual probe; still not connected to robot execution."
        ),
    }

    batch_dir = hybrid_payload.get("batch_dir", "")
    if batch_dir:
        refresh_report_path = Path(batch_dir) / "callirewrite_refresh_probe_report.json"
        write_summary_json(refresh_report_path, payload)
        payload["refresh_report_path"] = str(refresh_report_path)
    else:
        payload["refresh_report_path"] = ""
    return payload


def _normalized_samples(samples: Sequence[str] | None) -> list[str]:
    if not samples:
        return []
    return [sample.strip() for sample in samples if str(sample).strip()]
