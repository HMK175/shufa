from pathlib import Path
import importlib.util
import json


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_extractnet_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_extractnet_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_arg_parser_defaults_to_small_safe_run():
    module = _load_module()

    args = module.build_arg_parser().parse_args([])

    assert args.batch_size == 2
    assert args.max_steps == 2
    assert args.learning_rate == 0.0001
    assert args.output_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_extractnet_smoke"
    )
    assert args.dataset_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_training_smoke"
        / "dataset_forSegNet_ExtractNet_RHSEDB_smoke"
    )
    assert args.segnet_checkpoint == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_segnet_smoke"
        / "model"
        / "model.pth"
    )


def test_run_extractnet_smoke_reports_missing_required_paths(tmp_path: Path):
    module = _load_module()

    payload = module.run_extractnet_smoke(
        tmp_path / "missing_repo",
        dataset_dir=tmp_path / "missing_dataset",
        segnet_checkpoint=tmp_path / "missing_segnet.pth",
        output_dir=tmp_path / "out",
        batch_size=2,
        max_steps=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "missing_required_paths"
    assert payload["stage"] == "extractnet_training_smoke"
    assert str(tmp_path / "missing_repo") in payload["missing"]


def test_run_extractnet_smoke_rejects_output_dir_outside_mvp_outputs(tmp_path: Path):
    module = _load_module()
    repo_dir = tmp_path / "StrokeExtraction"
    (repo_dir / "model").mkdir(parents=True)
    dataset_dir = tmp_path / "dataset_forSegNet_ExtractNet_RHSEDB_smoke"
    (dataset_dir / "train").mkdir(parents=True)
    (dataset_dir / "test").mkdir(parents=True)
    segnet_checkpoint = tmp_path / "model.pth"
    segnet_checkpoint.write_bytes(b"")

    payload = module.run_extractnet_smoke(
        repo_dir,
        dataset_dir=dataset_dir,
        segnet_checkpoint=segnet_checkpoint,
        output_dir=tmp_path / "outside_mvp",
        batch_size=2,
        max_steps=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "invalid_output_dir"
    assert payload["allowed_root"].endswith("offline_stroke_recovery_mvp\\outputs")


def test_write_report_writes_json(tmp_path: Path):
    module = _load_module()
    report_path = tmp_path / "extractnet_smoke_report.json"

    module.write_report(report_path, {"status": "ok", "completed_steps": 2})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "completed_steps": 2,
    }
