from pathlib import Path
import importlib.util
import json


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_training_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_training_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_arg_parser_defaults_to_small_safe_run():
    module = _load_module()

    args = module.build_arg_parser().parse_args([])

    assert args.dataset == "RHSEDB"
    assert args.batch_size == 2
    assert args.sdnet_steps == 2
    assert args.train_intermediate_samples == 2
    assert args.test_intermediate_samples == 2
    assert args.output_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_training_smoke"
    )


def test_run_training_smoke_reports_missing_required_paths(tmp_path: Path):
    module = _load_module()

    payload = module.run_training_smoke(
        tmp_path / "missing_repo",
        output_dir=tmp_path / "out",
        dataset="RHSEDB",
        batch_size=2,
        sdnet_steps=2,
        train_intermediate_samples=2,
        test_intermediate_samples=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "missing_required_paths"
    assert payload["stage"] == "sdnet_training_and_intermediate_generation"
    assert str(tmp_path / "missing_repo") in payload["missing"]


def test_run_training_smoke_rejects_output_dir_outside_mvp_outputs(tmp_path: Path):
    module = _load_module()
    repo_dir = tmp_path / "StrokeExtraction"
    for required_dir in [
        repo_dir / "dataset" / "RHSEDB" / "train",
        repo_dir / "dataset" / "RHSEDB" / "test",
        repo_dir / "content_net_model" / "out",
        repo_dir / "char_recognise" / "out_vgg_bn" / "model",
    ]:
        required_dir.mkdir(parents=True)
    (repo_dir / "content_net_model" / "out" / "model_content.pth").write_bytes(b"")
    (repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.pth").write_bytes(b"")
    (repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.th").write_bytes(b"")

    payload = module.run_training_smoke(
        repo_dir,
        output_dir=tmp_path / "outside_mvp",
        dataset="RHSEDB",
        batch_size=2,
        sdnet_steps=2,
        train_intermediate_samples=2,
        test_intermediate_samples=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "invalid_output_dir"
    assert payload["allowed_root"].endswith("offline_stroke_recovery_mvp\\outputs")


def test_write_report_writes_json(tmp_path: Path):
    module = _load_module()
    report_path = tmp_path / "training_smoke_report.json"

    module.write_report(report_path, {"status": "ok", "completed_steps": 2})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "completed_steps": 2,
    }
