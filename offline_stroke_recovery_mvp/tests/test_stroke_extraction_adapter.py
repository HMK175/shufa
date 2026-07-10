from pathlib import Path
import json
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stroke_extraction_adapter import (
    STROKE_EXTRACTION_REPO_URL,
    build_stroke_extraction_probe_command,
    inspect_stroke_extraction_checkout,
    write_stroke_extraction_feasibility_report,
)


def test_inspect_stroke_extraction_checkout_reports_missing_repo(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"

    status = inspect_stroke_extraction_checkout(checkout_dir)

    assert status["ready"] is False
    assert status["status"] == "missing_checkout"
    assert status["repo_url"] == STROKE_EXTRACTION_REPO_URL
    assert status["checkout_dir"] == str(checkout_dir)
    assert "checkout_dir" in status["missing"]
    assert status["expected_role"] == "stroke_instance_segmentation_candidate"


def test_inspect_stroke_extraction_checkout_reports_missing_core_files(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"
    checkout_dir.mkdir()
    (checkout_dir / "README.md").write_text("# StrokeExtraction\n", encoding="utf-8")

    status = inspect_stroke_extraction_checkout(checkout_dir)

    assert status["ready"] is False
    assert status["status"] == "missing_entrypoint"
    assert "inference/test entrypoint" in status["missing"]
    assert "no explicit environment file found; using README requirements note" in status["warnings"]
    assert status["recommended_next_action"] == "inspect_upstream_readme_and_download_required_weights"


def test_inspect_stroke_extraction_checkout_detects_candidate_entrypoint(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"
    checkout_dir.mkdir()
    (checkout_dir / "README.md").write_text("# StrokeExtraction\n", encoding="utf-8")
    (checkout_dir / "requirements.txt").write_text("torch==1.9.0\n", encoding="utf-8")
    (checkout_dir / "test.py").write_text("print('test')\n", encoding="utf-8")
    (checkout_dir / "model.pth").write_bytes(b"weights")

    status = inspect_stroke_extraction_checkout(checkout_dir)

    assert status["ready"] is True
    assert status["status"] == "ready_for_manual_probe"
    assert status["stages"]["inference"]["entrypoint"].endswith("test.py")
    assert status["stages"]["environment"]["spec"].endswith("requirements.txt")
    assert status["stages"]["weights"]["candidates"] == [str(checkout_dir / "model.pth")]


def test_inspect_stroke_extraction_checkout_detects_upstream_readme_and_application_script(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"
    checkout_dir.mkdir()
    (checkout_dir / "ReadMe.md").write_text(
        "## Requirements\n\n    pytorch=1.9\n    python=3.8\n",
        encoding="utf-8",
    )
    (checkout_dir / "extraction_stroke_application_for_single_character_.py").write_text(
        "print('application')\n",
        encoding="utf-8",
    )

    status = inspect_stroke_extraction_checkout(checkout_dir)

    assert status["ready"] is False
    assert status["status"] == "needs_weights"
    assert status["stages"]["environment"]["spec"].endswith("ReadMe.md")
    assert status["stages"]["inference"]["entrypoint"].endswith(
        "extraction_stroke_application_for_single_character_.py"
    )
    assert "no explicit environment file found; using README requirements note" in status["warnings"]
    assert status["recommended_next_action"] == "inspect_upstream_readme_and_download_required_weights"


def test_build_stroke_extraction_probe_command_is_non_executing(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"

    command = build_stroke_extraction_probe_command(checkout_dir, input_dir, output_dir)

    assert command["cwd"] == str(checkout_dir)
    assert command["argv"][0] == "python"
    assert command["input_dir"] == str(input_dir)
    assert command["output_dir"] == str(output_dir)
    assert "external code is not executed by this adapter" in command["note"]


def test_write_stroke_extraction_feasibility_report_records_no_go_when_repo_missing(tmp_path: Path):
    checkout_dir = tmp_path / "StrokeExtraction"
    input_dir = tmp_path / "inputs"
    report_dir = tmp_path / "report"

    report_path = write_stroke_extraction_feasibility_report(
        checkout_dir,
        input_dir,
        report_dir,
    )

    assert report_path == report_dir / "stroke_extraction_feasibility_report.md"
    report = report_path.read_text(encoding="utf-8")
    assert "StrokeExtraction Feasibility Report" in report
    assert "missing_checkout" in report
    assert "not connected to robot execution" in report

    payload = json.loads((report_dir / "stroke_extraction_feasibility.json").read_text(encoding="utf-8"))
    assert payload["inspection"]["status"] == "missing_checkout"
    assert payload["recommended_decision"] == "no_go_until_external_checkout_is_ready"
