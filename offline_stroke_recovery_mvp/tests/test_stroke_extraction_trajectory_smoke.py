from pathlib import Path
import importlib.util
import json

import numpy as np
from PIL import Image


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "stroke_extraction_trajectory_smoke.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stroke_extraction_trajectory_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_arg_parser_defaults_to_small_safe_run():
    module = _load_module()

    args = module.build_arg_parser().parse_args([])

    assert args.batch_size == 2
    assert args.max_steps == 2
    assert args.samples_per_split == 2
    assert args.mask_quantile == 0.7
    assert args.output_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_trajectory_smoke"
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
    assert args.extractnet_checkpoint == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_extractnet_smoke"
        / "model"
        / "model_extract.pth"
    )


def test_combine_predicted_masks_merges_foreground_without_holes():
    module = _load_module()

    mask_a = np.array([[False, True], [False, False]])
    mask_b = np.array([[True, False], [False, False]])

    combined = module.combine_predicted_masks([mask_a, mask_b], shape=(2, 2))

    assert combined.dtype == np.bool_
    assert combined.tolist() == [[True, True], [False, False]]


def test_plan_trajectory_samples_round_robins_train_and_test():
    module = _load_module()

    assert module.plan_trajectory_samples(
        train_count=2,
        test_count=2,
        samples_per_split=2,
        max_steps=2,
    ) == [("train", 1), ("test", 1)]
    assert module.plan_trajectory_samples(
        train_count=2,
        test_count=2,
        samples_per_split=2,
        max_steps=3,
    ) == [("train", 1), ("test", 1), ("train", 2)]


def test_save_binary_mask_png_writes_black_foreground(tmp_path: Path):
    module = _load_module()
    path = tmp_path / "mask.png"
    mask = np.array([[True, False], [False, True]])

    module.save_binary_mask_png(path, mask)

    image = Image.open(path).convert("L")
    assert image.size == (2, 2)
    assert image.getpixel((0, 0)) == 0
    assert image.getpixel((1, 1)) == 0
    assert image.getpixel((1, 0)) == 255
    assert image.getpixel((0, 1)) == 255


def test_refine_predicted_mask_drops_border_components():
    module = _load_module()
    mask = np.zeros((6, 6), dtype=bool)
    mask[0, :] = True
    mask[3:5, 3:5] = True

    refined = module.refine_predicted_mask(mask, min_component_pixels=1)

    assert refined[0].sum() == 0
    assert refined[3:5, 3:5].all()
    assert refined.sum() == 4


def test_run_trajectory_smoke_reports_missing_required_paths(tmp_path: Path):
    module = _load_module()

    payload = module.run_trajectory_smoke(
        tmp_path / "missing_repo",
        dataset_dir=tmp_path / "missing_dataset",
        segnet_checkpoint=tmp_path / "missing_segnet.pth",
        extractnet_checkpoint=tmp_path / "missing_extractnet.pth",
        output_dir=tmp_path / "out",
        batch_size=2,
        max_steps=2,
        samples_per_split=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "missing_required_paths"
    assert payload["stage"] == "trajectory_recovery_smoke"
    assert str(tmp_path / "missing_repo") in payload["missing"]


def test_run_trajectory_smoke_rejects_output_dir_outside_mvp_outputs(tmp_path: Path):
    module = _load_module()
    repo_dir = tmp_path / "StrokeExtraction"
    (repo_dir / "model").mkdir(parents=True)
    dataset_dir = tmp_path / "dataset_forSegNet_ExtractNet_RHSEDB_smoke"
    (dataset_dir / "train").mkdir(parents=True)
    (dataset_dir / "test").mkdir(parents=True)
    segnet_checkpoint = tmp_path / "model.pth"
    segnet_checkpoint.write_bytes(b"")
    extractnet_checkpoint = tmp_path / "model_extract.pth"
    extractnet_checkpoint.write_bytes(b"")

    payload = module.run_trajectory_smoke(
        repo_dir,
        dataset_dir=dataset_dir,
        segnet_checkpoint=segnet_checkpoint,
        extractnet_checkpoint=extractnet_checkpoint,
        output_dir=tmp_path / "outside_mvp",
        batch_size=2,
        max_steps=2,
        samples_per_split=2,
        learning_rate=0.0001,
        seed=123,
    )

    assert payload["status"] == "invalid_output_dir"
    assert payload["allowed_root"].endswith("offline_stroke_recovery_mvp\\outputs")


def test_write_report_writes_json(tmp_path: Path):
    module = _load_module()
    report_path = tmp_path / "trajectory_smoke_report.json"

    module.write_report(report_path, {"status": "ok", "completed_samples": 2})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "status": "ok",
        "completed_samples": 2,
    }
