import sys
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from predict_stroke_next_rollout import apply_remaining_constraint
from stroke_next_model import (
    StrokeNextUNet,
    compute_remaining_mask,
    overlap_penalty_loss,
)


def test_remaining_mask_subtracts_previous_from_full():
    full = np.zeros((8, 8), dtype=np.float32)
    full[1:7, 1:7] = 1.0
    previous = np.zeros((8, 8), dtype=np.float32)
    previous[2:4, 2:4] = 1.0

    remaining = compute_remaining_mask(full, previous)
    assert remaining.shape == full.shape
    assert float(remaining[2:4, 2:4].sum()) == 0.0
    assert float(remaining.sum()) == float(full.sum() - previous.sum())


def test_constrained_prediction_removes_previous_overlap():
    full = np.ones((8, 8), dtype=np.float32)
    previous = np.zeros((8, 8), dtype=np.float32)
    previous[:, :4] = 1.0
    pred = np.ones((8, 8), dtype=np.uint8) * 255

    constrained = apply_remaining_constraint(pred, full, previous, previous_dilate=0)
    assert int((constrained[:, :4] > 0).sum()) == 0
    assert int((constrained[:, 4:] > 0).sum()) == 32


def test_four_channel_next_model_forward_shape():
    model = StrokeNextUNet(in_channels=4, base_channels=4)
    logits = model(torch.zeros((2, 4, 32, 32)))
    assert logits.shape == (2, 1, 32, 32)


def test_overlap_penalty_is_larger_for_overlapping_predictions():
    previous = torch.zeros((1, 1, 8, 8))
    previous[:, :, 2:6, 2:6] = 1.0
    overlap_logits = torch.full((1, 1, 8, 8), -4.0)
    overlap_logits[:, :, 2:6, 2:6] = 4.0
    clear_logits = torch.full((1, 1, 8, 8), -4.0)
    clear_logits[:, :, :2, :2] = 4.0

    assert overlap_penalty_loss(overlap_logits, previous) > overlap_penalty_loss(clear_logits, previous)
