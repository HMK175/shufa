import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
SRC_DIR = EXP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from style_diagnostics import load_diagnostic_config, run_style_diagnostics


def _read_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "chars": ["山", "龘"],
                "styles": ["kaishu", "xingkai", "lishu"],
                "planner_mode": "mock",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_style_diagnostic_config_loads_chars_styles_and_mode(tmp_path):
    config_path = tmp_path / "style_diagnostic_chars.json"
    _write_config(config_path)

    config = load_diagnostic_config(config_path)

    assert config["chars"] == ["山", "龘"]
    assert config["styles"] == ["kaishu", "xingkai", "lishu"]
    assert config["planner_mode"] == "mock"


def test_style_diagnostics_batch_generates_summary_failures_means_report_and_figures(tmp_path):
    config_path = tmp_path / "style_diagnostic_chars.json"
    _write_config(config_path)

    result = run_style_diagnostics(
        config_path=config_path,
        output_dir=tmp_path / "diagnostic_out",
        image_size=128,
    )

    summary_path = Path(result["summary_csv"])
    style_means_path = Path(result["style_means_csv"])
    char_means_path = Path(result["char_means_csv"])
    failures_path = Path(result["failures_csv"])
    report_path = Path(result["report_md"])
    grid_path = Path(result["grid_png"])
    metric_path = Path(result["metric_bars_png"])

    assert summary_path.exists()
    assert style_means_path.exists()
    assert char_means_path.exists()
    assert failures_path.exists()
    assert report_path.exists()
    assert grid_path.exists()
    assert metric_path.exists()

    summary_rows = _read_csv(summary_path)
    assert len(summary_rows) == 3
    assert {row["style"] for row in summary_rows} == {"kaishu", "xingkai", "lishu"}
    required_fields = {
        "char",
        "style",
        "success",
        "failure_reason",
        "stroke_count",
        "path_length",
        "aspect_ratio",
        "bbox_width",
        "bbox_height",
        "connection_count",
        "connector_draw_length",
        "pen_up_move_length",
        "mean_width",
        "mean_pressure",
        "workspace_path_length_mm",
        "max_xy_step_mm",
        "max_z_step_mm",
        "resampled_point_count",
        "out_of_bounds",
        "motion_continuity_recommended",
        "retiming_required",
    }
    assert required_fields.issubset(summary_rows[0].keys())

    failures = _read_csv(failures_path)
    assert len(failures) == 3
    assert all(row["char"] == "龘" for row in failures)
    assert all(row["success"] == "False" for row in failures)

    style_means = _read_csv(style_means_path)
    assert {row["style"] for row in style_means} == {"kaishu", "xingkai", "lishu"}

    char_means = _read_csv(char_means_path)
    assert {row["char"] for row in char_means} == {"山"}

    report = report_path.read_text(encoding="utf-8")
    assert "参数化 style profile" in report
    assert "不是最终风格学习结果" in report
    assert "missing_char_count" in report

    assert result["total"] == 6
    assert result["success_count"] == 3
    assert result["failure_count"] == 3
    assert result["missing_char_count"] == 3


def test_style_diagnostics_module_does_not_import_aubo_sdk(tmp_path):
    config_path = tmp_path / "style_diagnostic_chars.json"
    _write_config(config_path)
    sys.modules.pop("libpyauboi5", None)

    run_style_diagnostics(config_path=config_path, output_dir=tmp_path / "diagnostic_out", image_size=128)

    assert "libpyauboi5" not in sys.modules
