"""Sequence-style current-stroke segmentation dataset and model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset
import csv

from stroke_seg_model import ConvBlock, StrokeSegSample, UpBlock


THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]


@dataclass
class StrokeNextSample:
    char_id: str
    char: str
    split: str
    stroke_index: int
    stroke_count: int
    image_path: Path
    mask_dir: Path
    target_mask_path: Path


@dataclass
class PreviousMaskNoiseConfig:
    """Optional training-only corruption for the previous-strokes channel."""

    apply_prob: float = 1.0
    dropout_prob: float = 0.0
    morph_prob: float = 0.0
    false_positive_prob: float = 0.0
    false_positive_ratio: float = 0.002


class PredPreviousCache:
    """Lookup for offline autoregressive previous-mask snapshots."""

    def __init__(self, rows: dict[tuple[str, int], Path]):
        self.rows = dict(rows)

    @classmethod
    def from_csv(cls, path: Path | str) -> "PredPreviousCache":
        metadata = Path(path)
        rows: dict[tuple[str, int], Path] = {}
        with metadata.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows[(row["char_id"], int(row["stroke_index"]))] = Path(row["pred_previous_path"])
        return cls(rows)

    def get(self, sample: StrokeNextSample) -> Path | None:
        return self.rows.get((sample.char_id, sample.stroke_index))


def build_next_stroke_samples(samples: Sequence[StrokeSegSample]) -> list[StrokeNextSample]:
    rows: list[StrokeNextSample] = []
    for sample in samples:
        for stroke_index in range(1, sample.stroke_count + 1):
            rows.append(
                StrokeNextSample(
                    char_id=sample.char_id,
                    char=sample.char,
                    split=sample.split,
                    stroke_index=stroke_index,
                    stroke_count=sample.stroke_count,
                    image_path=sample.image_path,
                    mask_dir=sample.mask_dir,
                    target_mask_path=sample.mask_dir / f"{stroke_index:02d}.png",
                )
            )
    return rows


def split_next_samples(samples: Sequence[StrokeNextSample], split: str) -> list[StrokeNextSample]:
    return [sample for sample in samples if sample.split == split]


def _read_foreground(path: Path, image_size: int, nearest: bool = False) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"image not readable: {path}")
    if image.shape != (image_size, image_size):
        interpolation = cv2.INTER_NEAREST if nearest else cv2.INTER_AREA
        image = cv2.resize(image, (image_size, image_size), interpolation=interpolation)
    if nearest:
        return (image > 127).astype(np.float32)
    return 1.0 - image.astype(np.float32) / 255.0


def apply_previous_mask_noise(
    previous: np.ndarray,
    config: PreviousMaskNoiseConfig | None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Corrupt a GT previous mask to prepare for autoregressive rollout drift."""

    if config is None:
        return previous
    rng = rng or np.random.default_rng()
    if config.apply_prob <= 0 or rng.random() >= float(config.apply_prob):
        return previous
    noisy = previous.astype(np.float32).copy()

    if config.dropout_prob > 0:
        keep = rng.random(noisy.shape) >= float(config.dropout_prob)
        noisy = noisy * keep.astype(np.float32)

    if config.morph_prob > 0 and rng.random() < float(config.morph_prob):
        kernel = np.ones((3, 3), dtype=np.uint8)
        binary = (noisy > 0.5).astype(np.uint8)
        if rng.random() < 0.5:
            binary = cv2.erode(binary, kernel, iterations=1)
        else:
            binary = cv2.dilate(binary, kernel, iterations=1)
        noisy = binary.astype(np.float32)

    if config.false_positive_prob > 0 and rng.random() < float(config.false_positive_prob):
        h, w = noisy.shape
        count = max(1, int(h * w * max(0.0, float(config.false_positive_ratio))))
        ys = rng.integers(0, h, size=count)
        xs = rng.integers(0, w, size=count)
        false_points = np.zeros_like(noisy, dtype=np.uint8)
        false_points[ys, xs] = 1
        false_points = cv2.dilate(false_points, np.ones((3, 3), dtype=np.uint8), iterations=1)
        noisy = np.maximum(noisy, false_points.astype(np.float32))

    return np.clip(noisy, 0.0, 1.0).astype(np.float32)


def compute_remaining_mask(full: np.ndarray, previous: np.ndarray, previous_dilate: int = 0) -> np.ndarray:
    """Return full glyph foreground after removing already written previous strokes."""

    prev = (previous > 0.5).astype(np.uint8)
    if previous_dilate > 0:
        kernel = np.ones((3, 3), dtype=np.uint8)
        prev = cv2.dilate(prev, kernel, iterations=int(previous_dilate))
    remaining = np.where(prev > 0, 0.0, full.astype(np.float32))
    return np.clip(remaining, 0.0, 1.0).astype(np.float32)


class StrokeNextDataset(Dataset):
    """Each item asks the model to predict stroke k from glyph + previous strokes."""

    def __init__(
        self,
        samples: Sequence[StrokeNextSample],
        image_size: int = 256,
        previous_noise: PreviousMaskNoiseConfig | None = None,
        pred_previous_cache: PredPreviousCache | None = None,
        pred_previous_prob: float = 0.0,
        use_remaining_channel: bool = False,
        remaining_previous_dilate: int = 0,
    ):
        self.samples = list(samples)
        self.image_size = int(image_size)
        self.previous_noise = previous_noise
        self.pred_previous_cache = pred_previous_cache
        self.pred_previous_prob = float(pred_previous_prob)
        self.use_remaining_channel = bool(use_remaining_channel)
        self.remaining_previous_dilate = int(remaining_previous_dilate)

    def __len__(self) -> int:
        return len(self.samples)

    def _read_previous_mask(self, sample: StrokeNextSample) -> np.ndarray:
        previous = np.zeros((self.image_size, self.image_size), dtype=np.float32)
        for stroke_index in range(1, sample.stroke_index):
            mask_path = sample.mask_dir / f"{stroke_index:02d}.png"
            previous = np.maximum(previous, _read_foreground(mask_path, self.image_size, nearest=True))
        return previous

    def __getitem__(self, index: int) -> Dict[str, object]:
        sample = self.samples[index]
        full = _read_foreground(sample.image_path, self.image_size, nearest=False)
        previous = self._read_previous_mask(sample)
        if self.pred_previous_cache is not None and self.pred_previous_prob > 0:
            if self.pred_previous_prob >= 1.0 or np.random.default_rng().random() < self.pred_previous_prob:
                cached = self.pred_previous_cache.get(sample)
                if cached is not None:
                    previous = _read_foreground(cached, self.image_size, nearest=True)
        previous = apply_previous_mask_noise(previous, self.previous_noise)
        target = _read_foreground(sample.target_mask_path, self.image_size, nearest=True)
        progress = float(sample.stroke_index) / max(1.0, float(sample.stroke_count))
        step_map = np.full((self.image_size, self.image_size), progress, dtype=np.float32)
        channels = [full, previous]
        if self.use_remaining_channel:
            channels.append(compute_remaining_mask(full, previous, self.remaining_previous_dilate))
        channels.append(step_map)
        inputs = np.stack(channels, axis=0).astype(np.float32)
        return {
            "input": torch.from_numpy(inputs),
            "target": torch.from_numpy(target[None, ...].astype(np.float32)),
            "char_id": sample.char_id,
            "char": sample.char,
            "split": sample.split,
            "stroke_index": sample.stroke_index,
            "stroke_count": sample.stroke_count,
            "image_path": str(sample.image_path),
            "target_mask_path": str(sample.target_mask_path),
        }


class StrokeNextUNet(nn.Module):
    def __init__(self, in_channels: int = 3, base_channels: int = 16):
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base_channels)
        self.enc2 = ConvBlock(base_channels, base_channels * 2)
        self.enc3 = ConvBlock(base_channels * 2, base_channels * 4)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(base_channels * 4, base_channels * 8)
        self.up3 = UpBlock(base_channels * 8, base_channels * 4, base_channels * 4)
        self.up2 = UpBlock(base_channels * 4, base_channels * 2, base_channels * 2)
        self.up1 = UpBlock(base_channels * 2, base_channels, base_channels)
        self.head = nn.Conv2d(base_channels, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        b = self.bottleneck(self.pool(e3))
        d3 = self.up3(b, e3)
        d2 = self.up2(d3, e2)
        d1 = self.up1(d2, e1)
        return self.head(d1)


def next_dice_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    preds = (probs >= threshold).float()
    dims = (1, 2, 3)
    intersection = (preds * targets).sum(dim=dims)
    denom = preds.sum(dim=dims) + targets.sum(dim=dims)
    return (2.0 * intersection + eps) / (denom + eps)


def next_soft_dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    dims = (1, 2, 3)
    intersection = (probs * targets).sum(dim=dims)
    denom = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2.0 * intersection + eps) / (denom + eps)
    return 1.0 - dice.mean()


def overlap_penalty_loss(logits: torch.Tensor, previous_masks: torch.Tensor) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    previous = previous_masks.float()
    return (probs * previous).sum() / previous.sum().clamp_min(1.0)


def next_threshold_sweep(logits: torch.Tensor, targets: torch.Tensor, thresholds: Sequence[float] = THRESHOLDS) -> Dict[float, float]:
    return {
        float(threshold): float(next_dice_score(logits.cpu(), targets.cpu(), threshold=threshold).mean().item())
        for threshold in thresholds
    }


def best_threshold_from_metrics(metrics: Dict[str, object]) -> float:
    sweep = metrics.get("threshold_sweep") or {}
    usable = [(float(key), value) for key, value in sweep.items() if value is not None]
    if not usable:
        return 0.5
    return max(usable, key=lambda item: float(item[1]))[0]


def resolve_next_threshold(cli_threshold: float | None, checkpoint: dict) -> float:
    if cli_threshold is not None:
        return float(cli_threshold)
    value = checkpoint.get("best_threshold", 0.5)
    return 0.5 if value is None else float(value)
