from pathlib import Path
import importlib.util
import json


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_segnet_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_segnet_smoke", SCRIPT_PATH)
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
        / "stroke_extraction_segnet_smoke"
    )


def test_run_segnet_smoke_reports_missing_required_paths(tmp_path: Path):
    module = _load_module()

    payload = module.run_segnet_smoke(
        tmp_path / "missing_repo",
        dataset_dir=tmp_path / "missing_dataset",
        output_dir=tmp_path / "out",
        batch_size=2,
        max_steps=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "missing_required_paths"
    assert payload["stage"] == "segnet_training_smoke"
    assert str(tmp_path / "missing_repo") in payload["missing"]


def test_run_segnet_smoke_rejects_output_dir_outside_mvp_outputs(tmp_path: Path):
    module = _load_module()
    repo_dir = tmp_path / "StrokeExtraction"
    (repo_dir / "model").mkdir(parents=True)
    dataset_dir = tmp_path / "dataset_forSegNet_ExtractNet_RHSEDB_smoke"
    (dataset_dir / "train").mkdir(parents=True)
    (dataset_dir / "test").mkdir(parents=True)

    payload = module.run_segnet_smoke(
        repo_dir,
        dataset_dir=dataset_dir,
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
    report_path = tmp_path / "segnet_smoke_report.json"

    module.write_report(report_path, {"status": "ok", "completed_steps": 2})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "completed_steps": 2,
    }


def test_find_missing_modules_reports_absent_dependency_names():
    module = _load_module()

    missing = module.find_missing_modules(["json", "definitely_missing_segnet_module"])

    assert "json" not in missing
    assert "definitely_missing_segnet_module" in missing


def test_plan_smoke_schedule_repeats_small_dataset_batches():
    module = _load_module()

    assert module.plan_smoke_schedule(full_batches=1, max_steps=2) == [(1, 1), (2, 1)]
    assert module.plan_smoke_schedule(full_batches=2, max_steps=3) == [(1, 1), (2, 2), (3, 1)]
