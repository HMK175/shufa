"""Evaluate text-planner robustness on a small natural-language task suite."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from planner import DANGEROUS_DIRECT_OUTPUT_KEYS, load_style_profiles, plan_task


EXP_DIR = Path(__file__).resolve().parents[1]
ROOT = EXP_DIR.parents[1]
DEFAULT_TASKS = EXP_DIR / "configs" / "planner_robustness_tasks.json"
DEFAULT_GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_PROFILES = EXP_DIR / "configs" / "style_profiles.json"
DEFAULT_OUTPUT_ROOT = EXP_DIR / "outputs"
SUMMARY_FIELDS = [
    "id",
    "task",
    "planner_mode",
    "source",
    "request_status",
    "requested_style_raw",
    "requested_chars_raw",
    "mapped_style",
    "rejection_reason",
    "expected_char",
    "actual_char",
    "char_correct",
    "expected_style",
    "actual_style",
    "style_correct",
    "expected_allow_interstroke_connections",
    "actual_allow_interstroke_connections",
    "connection_constraint_correct",
    "expected_validation_ok",
    "validation_ok",
    "expected_invalid_rejected",
    "dangerous_output",
    "json_parse_success",
    "latency_sec",
    "error",
    "warnings",
    "plan_path",
]


def _timestamped_output_dir(root: Path | str) -> Path:
    return Path(root) / f"planner_robustness_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def load_tasks(path: Path | str) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("planner robustness tasks must be a JSON list")
    return [dict(item) for item in data]


def _safe_id(text: str, index: int) -> str:
    raw = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text.strip())
    raw = raw.strip("_") or f"task_{index:02d}"
    return f"{index:02d}_{raw[:48]}"


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _validation_ok(plan: dict[str, Any]) -> bool:
    return bool(plan.get("validation", {}).get("ok", False))


def _error_text(plan: dict[str, Any]) -> str:
    errors = plan.get("validation", {}).get("errors", [])
    if isinstance(errors, list):
        return "; ".join(str(item) for item in errors)
    return str(errors or "")


def _warning_text(plan: dict[str, Any]) -> str:
    warnings = list(plan.get("warnings", []) or [])
    validation_warnings = plan.get("validation", {}).get("warnings", [])
    if isinstance(validation_warnings, list):
        warnings.extend(validation_warnings)
    return "; ".join(str(item) for item in warnings if item)


def _dangerous_output(plan: dict[str, Any]) -> bool:
    if any(key in plan for key in DANGEROUS_DIRECT_OUTPUT_KEYS):
        return True
    text = _warning_text(plan).lower() + " " + _error_text(plan).lower()
    return "forbidden planner field" in text or "direct trajectory" in text


def _json_parse_success(plan: dict[str, Any]) -> bool:
    text = _error_text(plan).lower()
    failure_markers = [
        "not configured",
        "non-json",
        "planner unavailable",
        "response body was not json",
        "missing choices",
        "request failed",
    ]
    return not any(marker in text for marker in failure_markers)


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


def _compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    latency_vals = [float(row["latency_sec"]) for row in rows if row.get("latency_sec") not in ("", None)]
    return {
        "total": total,
        "validation_ok_count": sum(row.get("validation_ok") is True for row in rows),
        "char_correct_count": sum(row.get("char_correct") is True for row in rows),
        "style_correct_count": sum(row.get("style_correct") is True for row in rows),
        "connection_constraint_correct_count": sum(row.get("connection_constraint_correct") is True for row in rows),
        "expected_invalid_rejected_count": sum(row.get("expected_invalid_rejected") is True for row in rows),
        "dangerous_output_count": sum(row.get("dangerous_output") is True for row in rows),
        "json_parse_success_count": sum(row.get("json_parse_success") is True for row in rows),
        "average_latency": round(sum(latency_vals) / len(latency_vals), 4) if latency_vals else math.nan,
    }


def _write_report(metrics: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    total = max(int(metrics["total"]), 1)
    success_rows = [row for row in rows if row.get("validation_ok") is True]
    failure_rows = [row for row in rows if row.get("validation_ok") is not True]
    lines = [
        "# Planner Robustness Report",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        if key.endswith("_count"):
            lines.append(f"- {key}: {value}/{total}")
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Typical Success",
            "",
        ]
    )
    if success_rows:
        row = success_rows[0]
        lines.append(f"- `{row['id']}`: {row['task']} -> char={row['actual_char']}, style={row['actual_style']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Typical Failure", ""])
    if failure_rows:
        row = failure_rows[0]
        lines.append(f"- `{row['id']}`: {row['task']} -> {row['error'] or 'validation failed'}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- API keys are read from environment variables and are not written to this report.",
            "- LLM output is validated before local trajectory generation.",
            "- Dangerous trajectory/CSV/point fields are either removed with warnings or rejected by validation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _evaluate_one(
    item: dict[str, Any],
    index: int,
    output_dir: Path,
    planner_mode: str,
    style_profiles: dict[str, dict[str, float | bool]],
    graphics_path: Path | str,
    fallback_to_mock: bool,
) -> dict[str, Any]:
    task_id = str(item.get("id") or _safe_id(str(item.get("task", "")), index))
    task_text = str(item.get("task", ""))
    plan_path = output_dir / f"{_safe_id(task_id, index)}_plan.json"
    start = time.perf_counter()
    try:
        plan = plan_task(
            task_text,
            mode=planner_mode,
            style_profiles=style_profiles,
            graphics_path=graphics_path,
            fallback_to_mock=fallback_to_mock,
        )
    except Exception as exc:  # noqa: BLE001 - batch evaluation should continue
        plan = {
            "task": task_text,
            "char": "",
            "style": "",
            "style_params": {},
            "constraints": {},
            "stroke_plan": {},
            "planner_mode": planner_mode,
            "source": "exception",
            "warnings": [],
            "raw_response": None,
            "validation": {"ok": False, "errors": [str(exc)], "warnings": []},
        }
    latency = round(time.perf_counter() - start, 4)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    expected_validation_ok = _as_bool(item.get("expected_validation_ok", item.get("expected_valid")))
    expected_char = item.get("expected_char", "")
    expected_style = item.get("expected_style", "")
    expected_allow = _as_bool(item.get("expected_allow_interstroke_connections"))
    actual_allow = _as_bool(plan.get("constraints", {}).get("allow_interstroke_connections"))
    validation_ok = _validation_ok(plan)

    row = {
        "id": task_id,
        "task": task_text,
        "planner_mode": plan.get("planner_mode", planner_mode),
        "source": plan.get("source", ""),
        "request_status": plan.get("request_status", ""),
        "requested_style_raw": plan.get("requested_style_raw", ""),
        "requested_chars_raw": plan.get("requested_chars_raw", ""),
        "mapped_style": plan.get("mapped_style", ""),
        "rejection_reason": plan.get("rejection_reason", ""),
        "expected_char": expected_char,
        "actual_char": plan.get("char", ""),
        "char_correct": (plan.get("char", "") == expected_char) if expected_char else "",
        "expected_style": expected_style,
        "actual_style": plan.get("style", ""),
        "style_correct": (plan.get("style", "") == expected_style) if expected_style else "",
        "expected_allow_interstroke_connections": expected_allow,
        "actual_allow_interstroke_connections": actual_allow,
        "connection_constraint_correct": (actual_allow == expected_allow) if expected_allow is not None else "",
        "expected_validation_ok": expected_validation_ok,
        "validation_ok": validation_ok,
        "expected_invalid_rejected": (expected_validation_ok is False and validation_ok is False),
        "dangerous_output": _dangerous_output(plan),
        "json_parse_success": _json_parse_success(plan),
        "latency_sec": latency,
        "error": _error_text(plan),
        "warnings": _warning_text(plan),
        "plan_path": str(plan_path),
    }
    return row


def run_robustness(
    planner_mode: str,
    tasks_path: Path | str = DEFAULT_TASKS,
    out_dir: Path | str | None = None,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    fallback_to_mock: bool = False,
) -> dict[str, Any]:
    output_dir = Path(out_dir) if out_dir is not None else _timestamped_output_dir(DEFAULT_OUTPUT_ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(tasks_path)
    style_profiles = load_style_profiles(style_profiles_path)

    rows = [
        _evaluate_one(
            item=item,
            index=index,
            output_dir=output_dir,
            planner_mode=planner_mode,
            style_profiles=style_profiles,
            graphics_path=graphics_path,
            fallback_to_mock=fallback_to_mock,
        )
        for index, item in enumerate(tasks, start=1)
    ]
    metrics = _compute_metrics(rows)
    summary_csv = output_dir / "planner_robustness_summary.csv"
    report_md = output_dir / "planner_robustness_report.md"
    _write_csv(rows, summary_csv)
    _write_report(metrics, rows, report_md)
    result = {
        "output_dir": str(output_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "metrics": metrics,
    }
    (output_dir / "planner_robustness_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LLM-style planner robustness.")
    parser.add_argument("--planner-mode", choices=["api", "mock", "local"], default="api")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--style-profile", default=str(DEFAULT_PROFILES))
    parser.add_argument("--fallback-to-mock", action="store_true")
    args = parser.parse_args()

    result = run_robustness(
        planner_mode=args.planner_mode,
        tasks_path=args.tasks,
        out_dir=args.out_dir,
        graphics_path=args.graphics,
        style_profiles_path=args.style_profile,
        fallback_to_mock=args.fallback_to_mock,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
