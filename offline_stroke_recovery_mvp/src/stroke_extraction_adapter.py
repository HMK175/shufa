"""Adapter helpers for trying StrokeExtraction as an external candidate.

This module does not vendor or execute StrokeExtraction. It checks an external
checkout, writes a reproducibility report, and prepares a conservative manual
probe command shape for later use when the upstream repository and weights are
available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from exporters import write_summary_json


STROKE_EXTRACTION_REPO_URL = "https://github.com/MengLi-l1/StrokeExtraction"
EXPECTED_ROLE = "stroke_instance_segmentation_candidate"

ENVIRONMENT_CANDIDATES = (
    "requirements.txt",
    "environment.yml",
    "environment.yaml",
    "env.yml",
    "ReadMe.md",
    "README.md",
)
ENTRYPOINT_CANDIDATES = (
    "extraction_stroke_application_for_single_character_.py",
    "test.py",
    "demo.py",
    "inference.py",
    "infer.py",
    "predict.py",
    "tools/test.py",
    "tools/demo.py",
    "scripts/test.py",
    "scripts/demo.py",
)
WEIGHT_SUFFIXES = (".pth", ".pt", ".ckpt", ".pkl")


def inspect_stroke_extraction_checkout(checkout_dir: Path) -> dict[str, Any]:
    """Inspect whether an external StrokeExtraction checkout is probe-ready."""

    checkout_dir = Path(checkout_dir)
    missing: list[str] = []
    warnings: list[str] = []

    if not checkout_dir.exists():
        missing.append("checkout_dir")
        status = "missing_checkout"
        environment_spec = None
        entrypoint = None
        weight_candidates: list[str] = []
    else:
        readme = checkout_dir / "README.md"
        if not readme.exists():
            warnings.append("missing: README.md")

        environment_spec = _first_existing(checkout_dir, ENVIRONMENT_CANDIDATES)
        entrypoint = _first_existing(checkout_dir, ENTRYPOINT_CANDIDATES)
        weight_candidates = _find_weight_candidates(checkout_dir)

        if environment_spec is None:
            missing.append("requirements.txt or environment.yml")
        elif environment_spec.name.lower() == "readme.md":
            warnings.append("no explicit environment file found; using README requirements note")
        if entrypoint is None:
            missing.append("inference/test entrypoint")
        if not weight_candidates:
            warnings.append("no local checkpoint candidate found (*.pth, *.pt, *.ckpt, *.pkl)")

        if missing:
            status = "missing_entrypoint"
        elif weight_candidates:
            status = "ready_for_manual_probe"
        else:
            status = "needs_weights"

    return {
        "ready": status == "ready_for_manual_probe",
        "status": status,
        "repo_url": STROKE_EXTRACTION_REPO_URL,
        "checkout_dir": str(checkout_dir),
        "expected_role": EXPECTED_ROLE,
        "missing": missing,
        "warnings": warnings,
        "recommended_next_action": _recommended_next_action(status),
        "stages": {
            "environment": {
                "spec": "" if environment_spec is None else str(environment_spec),
                "candidates_checked": [str(checkout_dir / name) for name in ENVIRONMENT_CANDIDATES],
            },
            "inference": {
                "entrypoint": "" if entrypoint is None else str(entrypoint),
                "candidates_checked": [str(checkout_dir / name) for name in ENTRYPOINT_CANDIDATES],
            },
            "weights": {
                "candidates": weight_candidates,
                "suffixes_checked": list(WEIGHT_SUFFIXES),
            },
        },
    }


def build_stroke_extraction_probe_command(
    checkout_dir: Path,
    input_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Return a conservative StrokeExtraction probe command without executing it."""

    checkout_dir = Path(checkout_dir)
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    entrypoint = _first_existing(checkout_dir, ENTRYPOINT_CANDIDATES)
    entrypoint_arg = str(entrypoint.relative_to(checkout_dir)) if entrypoint else "UPSTREAM_ENTRYPOINT.py"
    argv = [
        "python",
        entrypoint_arg,
        "--input",
        str(input_dir),
        "--output",
        str(output_dir),
    ]
    return {
        "cwd": str(checkout_dir),
        "argv": argv,
        "powershell": " ".join(_quote_arg(arg) for arg in argv),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "note": (
            "Suggested shape only; external code is not executed by this adapter. "
            "Adjust flags to match the upstream README after inspecting the checkout."
        ),
    }


def write_stroke_extraction_feasibility_report(
    checkout_dir: Path,
    input_dir: Path,
    output_dir: Path,
) -> Path:
    """Write a reproducibility report for the external StrokeExtraction trial."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inspection = inspect_stroke_extraction_checkout(checkout_dir)
    command = build_stroke_extraction_probe_command(
        checkout_dir,
        input_dir,
        output_dir / "runtime_outputs",
    )
    decision = (
        "go_attempt_manual_probe"
        if inspection["ready"]
        else "no_go_until_external_checkout_is_ready"
    )
    payload = {
        "inspection": inspection,
        "command": command,
        "recommended_decision": decision,
        "scope": (
            "External StrokeExtraction trial for offline stroke-region recovery only; "
            "no training, CoppeliaSim, AUBO, SDK, or robot execution."
        ),
    }
    write_summary_json(output_dir / "stroke_extraction_feasibility.json", payload)

    missing = ", ".join(inspection["missing"]) if inspection["missing"] else "none"
    warnings = ", ".join(inspection["warnings"]) if inspection["warnings"] else "none"
    lines = [
        "# StrokeExtraction Feasibility Report",
        "",
        "## Scope",
        "",
        (
            "This report checks StrokeExtraction as an external stroke-instance "
            "segmentation candidate. It is not connected to robot execution."
        ),
        "",
        "## Checkout",
        "",
        f"- Repository: {STROKE_EXTRACTION_REPO_URL}",
        f"- Checkout directory: {inspection['checkout_dir']}",
        f"- Expected role: {inspection['expected_role']}",
        f"- Status: {inspection['status']}",
        f"- Missing: {missing}",
        f"- Warnings: {warnings}",
        f"- Recommended next action: {inspection['recommended_next_action']}",
        "",
        "## Suggested manual probe command",
        "",
        f"- Working directory: `{command['cwd']}`",
        f"- Command shape: `{command['powershell']}`",
        f"- Input directory: `{command['input_dir']}`",
        f"- Output directory: `{command['output_dir']}`",
        "",
        "## Decision",
        "",
        f"`{decision}`",
        "",
        "## Boundary",
        "",
        (
            "Use StrokeExtraction only as an offline candidate for visual stroke-region "
            "recovery. Do not run training, CoppeliaSim, AUBO, SDK, or real robot "
            "commands in this thread."
        ),
        "",
    ]
    (output_dir / "stroke_extraction_feasibility_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return output_dir / "stroke_extraction_feasibility_report.md"


def _first_existing(base_dir: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = base_dir / name
        if path.exists():
            return path
    return None


def _find_weight_candidates(checkout_dir: Path) -> list[str]:
    if not checkout_dir.exists():
        return []
    candidates: list[Path] = []
    for suffix in WEIGHT_SUFFIXES:
        candidates.extend(checkout_dir.rglob(f"*{suffix}"))
    return [str(path) for path in sorted(candidates)[:20] if path.is_file()]


def _recommended_next_action(status: str) -> str:
    if status == "missing_checkout":
        return "clone_or_download_external_repo"
    if status in {"missing_entrypoint", "needs_weights"}:
        return "inspect_upstream_readme_and_download_required_weights"
    return "run_manual_probe_on_smoke_inputs"


def _quote_arg(arg: str) -> str:
    if not arg or any(char.isspace() for char in arg):
        return "'" + arg.replace("'", "''") + "'"
    return arg
