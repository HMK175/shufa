"""Lightweight ordered stroke-mask segmentation model and dataset helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset


@dataclass
class StrokeSegSample:
    char_id: str
    char: str
    split: str
    image_path: Path
    mask_dir: Path
    median_dir: Path
    stroke_count: int
    width: int
    height: int
    source: str


@dataclass
class StrokeSegAugmentConfig:
    rotation_deg: float = 6.0
    scale_jitter: float = 0.06
    translate_frac: float = 0.05
    morph_prob: float = 0.25
    morph_kernel: int = 3


def load_manifest(manifest: Path) -> List[StrokeSegSample]:
    data_dir = manifest.parent
    samples: List[StrokeSegSample] = []
    with manifest.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(
                StrokeSegSample(
                    char_id=row["char_id"],
                    char=row["char"],
                    split=row["split"],
                    image_path=data_dir / row["image_path"],
                    mask_dir=data_dir / row["mask_dir"],
                    median_dir=data_dir / row["median_dir"],
                    stroke_count=int(row["stroke_count"]),
                    width=int(row["width"]),
                    height=int(row["height"]),
                    source=row["source"],
                )
            )
    return samples


def infer_max_strokes(samples: Sequence[StrokeSegSample]) -> int:
    return max((sample.stroke_count for sample in samples), default=0)


def augment_stroke_seg_arrays(
    image: np.ndarray,
    masks: np.ndarray,
    rng: np.random.Generator,
    config: StrokeSegAugmentConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply one synchronized light affine/morph transform to image and masks.

    Arrays use foreground-positive convention, so constant border is zero.
    """
    config = config or StrokeSegAugmentConfig()
    h, w = image.shape
    angle = float(rng.uniform(-config.rotation_deg, config.rotation_deg))
    scale = float(1.0 + rng.uniform(-config.scale_jitter, config.scale_jitter))
    tx = float(rng.uniform(-config.translate_frac, config.translate_frac) * w)
    ty = float(rng.uniform(-config.translate_frac, config.translate_frac) * h)
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, scale)
    matrix[0, 2] += tx
    matrix[1, 2] += ty

    aug_image = cv2.warpAffine(
        image.astype(np.float32),
        matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )
    aug_masks = np.zeros_like(masks, dtype=np.float32)
    for idx, mask in enumerate(masks):
        aug_masks[idx] = cv2.warpAffine(
            mask.astype(np.float32),
            matrix,
            (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        )
    aug_masks = (aug_masks > 0.5).astype(np.float32)

    if config.morph_prob > 0 and rng.random() < config.morph_prob:
        kernel_size = max(1, int(config.morph_kernel))
        kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        op = cv2.MORPH_DILATE if rng.random() < 0.5 else cv2.MORPH_ERODE
        for idx in range(aug_masks.shape[0]):
            if aug_masks[idx].max() <= 0:
                continue
            morphed = cv2.morphologyEx((aug_masks[idx] > 0.5).astype(np.uint8), op, kernel)
            aug_masks[idx] = morphed.astype(np.float32)
        aug_image = aug_masks.max(axis=0).astype(np.float32)

    return np.clip(aug_image, 0.0, 1.0).astype(np.float32), aug_masks.astype(np.float32)


class StrokeSegDataset(Dataset):
    """Dataset returning a glyph image and fixed-K ordered stroke mask tensor."""

    def __init__(
        self,
        samples: Sequence[StrokeSegSample],
        max_strokes: int,
        image_size: int = 256,
        augment: bool = False,
        augment_config: StrokeSegAugmentConfig | None = None,
    ):
        self.samples = list(samples)
        self.max_strokes = int(max_strokes)
        self.image_size = int(image_size)
        self.augment = bool(augment)
        self.augment_config = augment_config or StrokeSegAugmentConfig()

    def __len__(self) -> int:
        return len(self.samples)

    def _read_image(self, path: Path) -> torch.Tensor:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"image not readable: {path}")
        if image.shape != (self.image_size, self.image_size):
            image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        # Use foreground-positive convention: black strokes -> 1, white background -> 0.
        image = 1.0 - image.astype(np.float32) / 255.0
        return torch.from_numpy(image).unsqueeze(0)

    def _read_masks(self, sample: StrokeSegSample) -> torch.Tensor:
        masks = np.zeros((self.max_strokes, self.image_size, self.image_size), dtype=np.float32)
        for idx in range(min(sample.stroke_count, self.max_strokes)):
            mask_path = sample.mask_dir / f"{idx + 1:02d}.png"
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise RuntimeError(f"mask not readable: {mask_path}")
            if mask.shape != (self.image_size, self.image_size):
                mask = cv2.resize(mask, (self.image_size, self.image_size), interpolation=cv2.INTER_NEAREST)
            masks[idx] = (mask > 127).astype(np.float32)
        return torch.from_numpy(masks)

    def __getitem__(self, index: int) -> Dict[str, object]:
        sample = self.samples[index]
        image = self._read_image(sample.image_path)
        masks = self._read_masks(sample)
        if self.augment:
            image_np, masks_np = augment_stroke_seg_arrays(
                image.squeeze(0).numpy(),
                masks.numpy(),
                np.random.default_rng(),
                self.augment_config,
            )
            image = torch.from_numpy(image_np).unsqueeze(0)
            masks = torch.from_numpy(masks_np)
        return {
            "image": image,
            "masks": masks,
            "stroke_count": sample.stroke_count,
            "char_id": sample.char_id,
            "char": sample.char,
            "image_path": str(sample.image_path),
        }


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class UpBlock(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, out_channels, kernel_size=2, stride=2)
        self.conv = ConvBlock(out_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        if x.shape[-2:] != skip.shape[-2:]:
            x = nn.functional.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([x, skip], dim=1))


class StrokeSegUNet(nn.Module):
    def __init__(self, max_strokes: int, in_channels: int = 1, base_channels: int = 16):
        super().__init__()
        self.max_strokes = int(max_strokes)
        self.enc1 = ConvBlock(in_channels, base_channels)
        self.enc2 = ConvBlock(base_channels, base_channels * 2)
        self.enc3 = ConvBlock(base_channels * 2, base_channels * 4)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(base_channels * 4, base_channels * 8)
        self.up3 = UpBlock(base_channels * 8, base_channels * 4, base_channels * 4)
        self.up2 = UpBlock(base_channels * 4, base_channels * 2, base_channels * 2)
        self.up1 = UpBlock(base_channels * 2, base_channels, base_channels)
        self.head = nn.Conv2d(base_channels, self.max_strokes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        b = self.bottleneck(self.pool(e3))
        d3 = self.up3(b, e3)
        d2 = self.up2(d3, e2)
        d1 = self.up1(d2, e1)
        return self.head(d1)


def dice_score_per_channel(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-6):
    probs = torch.sigmoid(logits)
    preds = (probs >= threshold).float()
    dims = (0, 2, 3)
    intersection = (preds * targets).sum(dim=dims)
    pred_sum = preds.sum(dim=dims)
    target_sum = targets.sum(dim=dims)
    dice = (2.0 * intersection + eps) / (pred_sum + target_sum + eps)
    valid = target_sum > 0
    return dice, valid


def soft_dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    dims = (0, 2, 3)
    intersection = (probs * targets).sum(dim=dims)
    denom = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2.0 * intersection + eps) / (denom + eps)
    valid = targets.sum(dim=dims) > 0
    if valid.any():
        return 1.0 - dice[valid].mean()
    return logits.new_tensor(0.0)
