import sys
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from predict_stroke_next_rollout import (
    RolloutState,
    build_rollout_input,
    make_summary_row,
    update_previous_mask,
)


def test_autoregressive_previous_mask_starts_empty_and_accumulates():
    state = RolloutState.empty(image_size=16)
    assert state.previous_mask.shape == (16, 16)
    assert float(state.previous_mask.sum()) == 0.0

    pred1 = np.zeros((16, 16), dtype=np.uint8)
    pred1[2:5, 2:5] = 255
    updated = update_previous_mask(state.previous_mask, pred1, mode="union")
    assert int((updated > 0).sum()) == 9

    pred2 = np.zeros((16, 16), dtype=np.uint8)
    pred2[4:8, 4:8] = 255
    updated2 = update_previous_mask(updated, pred2, mode="union")
    assert int((updated2 > 0).sum()) == 9 + 16 - 1


def test_rollout_input_shape_for_teacher_and_autoregressive_modes():
    full = np.ones((16, 16), dtype=np.float32)
    gt_previous = np.zeros((16, 16), dtype=np.float32)
    gt_previous[:, :4] = 1.0
    pred_previous = np.zeros((16, 16), dtype=np.float32)
    pred_previous[:4, :] = 1.0

    teacher = build_rollout_input(full, gt_previous, pred_previous, 2, 4, mode="teacher_forcing")
    auto = build_rollout_input(full, gt_previous, pred_previous, 2, 4, mode="autoregressive")

    assert teacher.shape == (1, 3, 16, 16)
    assert auto.shape == (1, 3, 16, 16)
    assert torch.equal(teacher[0, 1], torch.from_numpy(gt_previous))
    assert torch.equal(auto[0, 1], torch.from_numpy(pred_previous))
    assert torch.allclose(teacher[0, 2], torch.full((16, 16), 0.5))


def test_rollout_summary_row_contains_expected_fields():
    row = make_summary_row(
        char_id="u4e00",
        stroke_index=1,
        stroke_count=1,
        teacher_dice=0.8,
        autoregressive_dice=0.6,
        pred_fg_ratio=0.1,
        accumulated_coverage=0.2,
        overlap_ratio=0.03,
        overflow_ratio=0.04,
        mask_path="pred.png",
        threshold=0.7,
    )
    expected = {
        "char_id",
        "stroke_index",
        "stroke_count",
        "teacher_dice",
        "autoregressive_dice",
        "dice_drop",
        "pred_fg_ratio",
        "accumulated_previous_coverage",
        "overlap_ratio",
        "overflow_ratio",
        "mask_path",
        "threshold",
    }
    assert expected.issubset(row.keys())
    assert row["dice_drop"] == "0.200000"
