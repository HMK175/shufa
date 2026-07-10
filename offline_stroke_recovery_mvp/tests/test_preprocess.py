from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from preprocess import ensure_foreground_is_true, crop_to_foreground


def test_ensure_foreground_is_true_converts_dark_pixels_to_true():
    arr = np.array([[255, 0], [255, 255]], dtype=np.uint8)
    mask = ensure_foreground_is_true(arr, threshold=200)
    assert mask.dtype == np.bool_
    assert mask[0, 1]
    assert not mask[0, 0]


def test_crop_to_foreground_returns_tight_bbox():
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 3:5] = True
    cropped, bbox = crop_to_foreground(mask, pad=0)
    assert cropped.shape == (4, 2)
    assert bbox == (2, 3, 5, 4)
