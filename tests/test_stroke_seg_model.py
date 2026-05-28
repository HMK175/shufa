import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from predict_stroke_seg_model import resolve_threshold
from stroke_seg_model import (
    StrokeSegAugmentConfig,
    StrokeSegDataset,
    StrokeSegUNet,
    augment_stroke_seg_arrays,
    infer_max_strokes,
    load_manifest,
    soft_dice_loss,
)
from train_stroke_seg_model import _split_samples, foreground_ratios, snapshot_state_dict, threshold_sweep, weighted_bce_loss


def _write_sample_dataset(root: Path) -> Path:
    for sub in ["images", "masks/u4e00", "masks/u5341", "medians/u4e00", "medians/u5341", "preview"]:
        (root / sub).mkdir(parents=True, exist_ok=True)

    image = np.full((64, 64), 255, dtype=np.uint8)
    cv2.line(image, (8, 32), (56, 32), 0, 3)
    cv2.imwrite(str(root / "images" / "u4e00.png"), image)
    mask = np.zeros((64, 64), dtype=np.uint8)
    cv2.line(mask, (8, 32), (56, 32), 255, 3)
    cv2.imwrite(str(root / "masks" / "u4e00" / "01.png"), mask)
    (root / "medians" / "u4e00" / "01.csv").write_text("y,x\n32,8\n32,56\n", encoding="utf-8")
    cv2.imwrite(str(root / "preview" / "u4e00_preview.png"), image)

    image2 = np.full((64, 64), 255, dtype=np.uint8)
    cv2.line(image2, (8, 32), (56, 32), 0, 3)
    cv2.line(image2, (32, 8), (32, 56), 0, 3)
    cv2.imwrite(str(root / "images" / "u5341.png"), image2)
    mask_h = np.zeros((64, 64), dtype=np.uint8)
    mask_v = np.zeros((64, 64), dtype=np.uint8)
    cv2.line(mask_h, (8, 32), (56, 32), 255, 3)
    cv2.line(mask_v, (32, 8), (32, 56), 255, 3)
    cv2.imwrite(str(root / "masks" / "u5341" / "01.png"), mask_h)
    cv2.imwrite(str(root / "masks" / "u5341" / "02.png"), mask_v)
    (root / "medians" / "u5341" / "01.csv").write_text("y,x\n32,8\n32,56\n", encoding="utf-8")
    (root / "medians" / "u5341" / "02.csv").write_text("y,x\n8,32\n56,32\n", encoding="utf-8")
    cv2.imwrite(str(root / "preview" / "u5341_preview.png"), image2)

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
                "char": "一",
                "split": "train",
                "image_path": "images/u4e00.png",
                "mask_dir": "masks/u4e00",
                "median_dir": "medians/u4e00",
                "stroke_count": "1",
                "width": "64",
                "height": "64",
                "source": "test",
            }
        )
        writer.writerow(
            {
                "char_id": "u5341",
                "char": "十",
                "split": "val",
                "image_path": "images/u5341.png",
                "mask_dir": "masks/u5341",
                "median_dir": "medians/u5341",
                "stroke_count": "2",
                "width": "64",
                "height": "64",
                "source": "test",
            }
        )
    return manifest


def test_stroke_seg_dataset_loader_and_forward_shape(tmp_path):
    manifest = _write_sample_dataset(tmp_path)
    samples = load_manifest(manifest)
    max_strokes = infer_max_strokes(samples)
    dataset = StrokeSegDataset(samples, max_strokes=max_strokes, image_size=64)

    item = dataset[1]
    assert item["image"].shape == (1, 64, 64)
    assert item["masks"].shape == (2, 64, 64)
    assert int(item["masks"][0].sum()) > 0
    assert int(item["masks"][1].sum()) > 0

    model = StrokeSegUNet(max_strokes=max_strokes, base_channels=4)
    logits = model(item["image"].unsqueeze(0))
    assert logits.shape == (1, 2, 64, 64)


def test_stroke_seg_model_one_training_step(tmp_path):
    manifest = _write_sample_dataset(tmp_path)
    samples = load_manifest(manifest)
    dataset = StrokeSegDataset(samples, max_strokes=2, image_size=64)
    model = StrokeSegUNet(max_strokes=2, base_channels=4)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    batch = [dataset[0], dataset[1]]
    images = torch.stack([item["image"] for item in batch])
    masks = torch.stack([item["masks"] for item in batch])
    logits = model(images)
    loss = F.binary_cross_entropy_with_logits(logits, masks) + 0.5 * soft_dice_loss(logits, masks)
    loss.backward()
    optimizer.step()

    assert torch.isfinite(loss)


def test_stroke_seg_debug_metrics_and_overfit_selection(tmp_path):
    manifest = _write_sample_dataset(tmp_path)
    samples = load_manifest(manifest)
    train_samples = _split_samples(samples, "train")
    overfit_samples = train_samples[:1]
    assert len(overfit_samples) == 1
    assert overfit_samples[0].split == "train"

    dataset = StrokeSegDataset(samples, max_strokes=2, image_size=64)
    batch = [dataset[0], dataset[1]]
    masks = torch.stack([item["masks"] for item in batch])
    logits = torch.full_like(masks, -4.0)
    logits[:, 0] = masks[:, 0] * 8.0 - 4.0

    ratios = foreground_ratios(masks)
    assert ratios.shape == (2,)
    assert torch.all(ratios > 0)

    sweep = threshold_sweep(logits, masks, thresholds=[0.3, 0.5, 0.6])
    assert set(sweep) == {0.3, 0.5, 0.6}
    assert sweep[0.5] >= 0.0

    loss = weighted_bce_loss(logits, masks, pos_weight=4.0, empty_channel_weight=0.2)
    assert torch.isfinite(loss)


def test_stroke_seg_augmentation_keeps_image_and_masks_aligned():
    image = np.zeros((64, 64), dtype=np.float32)
    masks = np.zeros((2, 64, 64), dtype=np.float32)
    cv2.line(image, (8, 32), (56, 32), 1.0, 3)
    cv2.line(masks[0], (8, 32), (56, 32), 1.0, 3)
    cv2.line(image, (32, 8), (32, 56), 1.0, 3)
    cv2.line(masks[1], (32, 8), (32, 56), 1.0, 3)

    config = StrokeSegAugmentConfig(rotation_deg=5.0, scale_jitter=0.04, translate_frac=0.05, morph_prob=0.0)
    aug_image, aug_masks = augment_stroke_seg_arrays(image, masks, np.random.default_rng(7), config)

    assert aug_image.shape == image.shape
    assert aug_masks.shape == masks.shape
    union = aug_masks.max(axis=0) > 0.5
    image_fg = aug_image > 0.5
    overlap = np.logical_and(union, image_fg).sum() / max(1, np.logical_or(union, image_fg).sum())
    assert overlap > 0.95


def test_prediction_threshold_uses_checkpoint_best_threshold_by_default():
    assert resolve_threshold(None, {"best_threshold": 0.6}) == 0.6
    assert resolve_threshold(0.4, {"best_threshold": 0.6}) == 0.4
    assert resolve_threshold(None, {}) == 0.5


def test_snapshot_state_dict_is_detached_from_future_model_updates():
    model = StrokeSegUNet(max_strokes=1, base_channels=4)
    snapshot = snapshot_state_dict(model)
    first_key = next(iter(snapshot))
    before = snapshot[first_key].clone()

    with torch.no_grad():
        for param in model.parameters():
            param.add_(1.0)

    assert torch.equal(snapshot[first_key], before)
    assert not torch.equal(snapshot[first_key], model.state_dict()[first_key])
