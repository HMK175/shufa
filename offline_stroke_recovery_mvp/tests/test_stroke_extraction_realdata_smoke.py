from pathlib import Path
import importlib.util
import json


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_realdata_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_realdata_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_arg_parser_defaults_to_sdnet_only():
    module = _load_module()

    args = module.build_arg_parser().parse_args([])

    assert args.stage == "sdnet"
    assert args.batch_size == 2
    assert args.max_steps == 2


def test_write_report_writes_json(tmp_path: Path):
    module = _load_module()
    report_path = tmp_path / "realdata_report.json"

    module.write_report(report_path, {"status": "ok", "stage": "sdnet"})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "stage": "sdnet",
    }
