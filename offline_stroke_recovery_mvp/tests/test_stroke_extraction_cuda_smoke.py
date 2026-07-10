from pathlib import Path
import importlib.util
import json


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_cuda_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_cuda_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_batch_sizes_accepts_comma_list():
    module = _load_module()

    assert module.parse_batch_sizes("1,2,4") == [1, 2, 4]
    assert module.parse_batch_sizes(" 1 , 3 ") == [1, 3]


def test_parse_batch_sizes_rejects_non_positive_values():
    module = _load_module()

    try:
        module.parse_batch_sizes("1,0")
    except ValueError as error:
        assert "positive integers" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_write_report_writes_json(tmp_path: Path):
    module = _load_module()
    report_path = tmp_path / "report.json"
    payload = {
        "status": "cuda_unavailable",
        "batch_results": [],
    }

    module.write_report(report_path, payload)

    assert json.loads(report_path.read_text(encoding="utf-8")) == payload


def test_find_missing_modules_reports_absent_dependency_names():
    module = _load_module()

    missing = module.find_missing_modules(["json", "definitely_missing_stroke_module"])

    assert "json" not in missing
    assert "definitely_missing_stroke_module" in missing


def test_default_probe_mode_is_eval_forward():
    module = _load_module()
    parser = module.build_arg_parser()

    args = parser.parse_args([])

    assert args.backward is False


def test_backward_flag_enables_training_style_probe():
    module = _load_module()
    parser = module.build_arg_parser()

    args = parser.parse_args(["--backward"])

    assert args.backward is True
