import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from stroke_next_model import (
    PreviousMaskNoiseConfig,
    StrokeNextDataset,
    StrokeNextUNet,
    apply_previous_mask_noise,
    build_next_stroke_samples,
    next_threshold_sweep,
    resolve_next_threshold,
)
from stroke_seg_model import load_manifest


def _write_next_dataset(root: Path) -> Path:
    for sub in ["images", "masks/u4e00", "masks/u5341", "medians/u4e00", "medians/u5341"]:
        (root / sub).mkdir(parents=True, exist_ok=True)

    image = np.full((32, 32), 255, dtype=np.uint8)
    cv2.line(image, (4, 16), (28, 16), 0, 3)
    cv2.imwrite(str(root / "images" / "u4e00.png"), image)
    mask = np.zeros((32, 32), dtype=np.uint8)
    cv2.line(mask, (4, 16), (28, 16), 255, 3)
    cv2.imwrite(str(root / "masks" / "u4e00" / "01.png"), mask)

    image2 = np.full((32, 32), 255, dtype=np.uint8)
    cv2.line(image2, (4, 16), (28, 16), 0, 3)
    cv2.line(image2, (16, 4), (16, 28), 0, 3)
    cv2.imwrite(str(root / "images" / "u5341.png"), image2)
    mask1 = np.zeros((32, 32), dtype=np.uint8)
    mask2 = np.zeros((32, 32), dtype=np.uint8)
    cv2.line(mask1, (4, 16), (28, 16), 255, 3)
    cv2.line(mask2, (16, 4), (16, 28), 255, 3)
    cv2.imwrite(str(root / "masks" / "u5341" / "01.png"), mask1)
    cv2.imwrite(str(root / "masks" / "u5341" / "02.png"), mask2)

    manifest = root / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "char_id",
                "char",
                "split",
                "image_path",
                "mask_dir",
                "median_dir",
                "stroke_count",
                "width",
                "height",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "char_id": "u4e00",
                "char": "one",
                "split": "train",
                "image_path": "images/u4e00.png",
                "mask_dir": "masks/u4e00",
                "median_dir": "medians/u4e00",
                "stroke_count": "1",
                "width": "32",
                "height": "32",
                "source": "test",
            }
        )
        writer.writerow(
            {
                "char_id": "u5341",
                "char": "ten",
                "split": "val",
                "image_path": "images/u5341.png",
                "mask_dir": "masks/u5341",
                "median_dir": "medians/u5341",
                "stroke_count": "2",
                "width": "32",
                "height": "32",
                "source": "test",
            }
        )
    return manifest


def test_next_stroke_samples_expand_to_total_stroke_count(tmp_path):
    manifest = _write_next_dataset(tmp_path)
    samples = load_manifest(manifest)
    next_samples = build_next_stroke_samples(samples)

    assert len(next_samples) == 3
    assert [sample.stroke_index for sample in next_samples] == [1, 1, 2]
    assert next_samples[-1].target_mask_path.name == "02.png"


def test_next_stroke_dataset_previous_mask_and_step_map(tmp_path):
    manifest = _write_next_dataset(tmp_path)
    samples = load_manifest(manifest)
    next_samples = build_next_stroke_samples(samples)
    dataset = StrokeNextDataset(next_samples, image_size=32)

    first = dataset[0]
    assert first["input"].shape == (3, 32, 32)
    assert first["target"].shape == (1, 32, 32)
    assert float(first["input"][1].sum()) == 0.0
    assert torch.allclose(first["input"][2], torch.full((32, 32), 1.0))

    second_stroke = dataset[2]
    assert int(second_stroke["input"][1].sum()) > 0
    assert torch.allclose(second_stroke["input"][2], torch.full((32, 32), 1.0))


def test_next_stroke_model_forward_shape_and_threshold_helpers():
    model = StrokeNextUNet(base_channels=4)
    logits = model(torch.zeros((2, 3, 32, 32)))
    targets = torch.zeros((2, 1, 32, 32))
    targets[:, :, 10:14, 10:14] = 1.0

    assert logits.shape == (2, 1, 32, 32)
    sweep = next_threshold_sweep(logits, targets, thresholds=[0.3, 0.5])
    assert set(sweep) == {0.3, 0.5}
    assert resolve_next_threshold(None, {"best_threshold": 0.7}) == 0.7
    assert resolve_next_threshold(0.4, {"best_threshold": 0.7}) == 0.4


def test_previous_mask_noise_can_dropout_and_add_false_positives():
    previous = np.zeros((16, 16), dtype=np.float32)
    previous[4:8, 4:8] = 1.0

    dropped = apply_previous_mask_noise(
        previous,
        PreviousMaskNoiseConfig(dropout_prob=1.0),
        rng=np.random.default_rng(123),
    )
    assert float(dropped.sum()) == 0.0

    noisy = apply_previous_mask_noise(
        previous,
        PreviousMaskNoiseConfig(false_positive_prob=1.0, false_positive_ratio=0.02),
        rng=np.random.default_rng(123),
    )
    assert noisy.shape == previous.shape
    assert float(noisy.sum()) > float(previous.sum())


def test_previous_mask_noise_apply_prob_can_keep_gt_previous_mask():
    previous = np.zeros((16, 16), dtype=np.float32)
    previous[4:8, 4:8] = 1.0
    unchanged = apply_previous_mask_noise(
        previous,
        PreviousMaskNoiseConfig(apply_prob=0.0, dropout_prob=1.0, false_positive_prob=1.0),
        rng=np.random.default_rng(123),
    )
    assert np.array_equal(unchanged, previous)
