import csv
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from build_predicted_previous_cache import cache_metadata_fields, write_cache_metadata
from stroke_next_model import PredPreviousCache, StrokeNextDataset, build_next_stroke_samples
from stroke_seg_model import load_manifest
from test_stroke_next_model import _write_next_dataset


def _write_predprev_cache(root: Path) -> Path:
    cache_dir = root / "cache"
    (cache_dir / "u4e00").mkdir(parents=True, exist_ok=True)
    (cache_dir / "u5341").mkdir(parents=True, exist_ok=True)

    empty = np.zeros((32, 32), dtype=np.uint8)
    cv2.imwrite(str(cache_dir / "u4e00" / "prev_01.png"), empty)
    cv2.imwrite(str(cache_dir / "u5341" / "prev_01.png"), empty)
    previous = np.zeros((32, 32), dtype=np.uint8)
    cv2.line(previous, (4, 16), (28, 16), 255, 3)
    cv2.imwrite(str(cache_dir / "u5341" / "prev_02.png"), previous)

    rows = [
        {
            "char_id": "u4e00",
            "split": "train",
            "stroke_index": 1,
            "stroke_count": 1,
            "pred_previous_path": str(cache_dir / "u4e00" / "prev_01.png"),
            "target_mask_path": str(root / "masks" / "u4e00" / "01.png"),
        },
        {
            "char_id": "u5341",
            "split": "val",
            "stroke_index": 1,
            "stroke_count": 2,
            "pred_previous_path": str(cache_dir / "u5341" / "prev_01.png"),
            "target_mask_path": str(root / "masks" / "u5341" / "01.png"),
        },
        {
            "char_id": "u5341",
            "split": "val",
            "stroke_index": 2,
            "stroke_count": 2,
            "pred_previous_path": str(cache_dir / "u5341" / "prev_02.png"),
            "target_mask_path": str(root / "masks" / "u5341" / "02.png"),
        },
    ]
    metadata = cache_dir / "metadata.csv"
    write_cache_metadata(rows, metadata)
    return metadata


def test_cache_metadata_fields_are_complete(tmp_path):
    manifest = _write_next_dataset(tmp_path)
    metadata = _write_predprev_cache(tmp_path)
    assert manifest.exists()

    with metadata.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == cache_metadata_fields()
        rows = list(reader)

    assert len(rows) == 3
    assert rows[0]["stroke_index"] == "1"
    assert Path(rows[0]["pred_previous_path"]).exists()


def test_pred_previous_cache_loader_shape_and_prob_control(tmp_path):
    manifest = _write_next_dataset(tmp_path)
    metadata = _write_predprev_cache(tmp_path)
    samples = build_next_stroke_samples(load_manifest(manifest))
    cache = PredPreviousCache.from_csv(metadata)

    gt_dataset = StrokeNextDataset(samples, image_size=32, pred_previous_cache=cache, pred_previous_prob=0.0)
    cached_dataset = StrokeNextDataset(samples, image_size=32, pred_previous_cache=cache, pred_previous_prob=1.0)

    gt_second = gt_dataset[2]["input"][1].numpy()
    cached_second = cached_dataset[2]["input"][1].numpy()

    assert gt_second.shape == (32, 32)
    assert cached_second.shape == (32, 32)
    assert int(gt_second.sum()) > 0
    assert int(cached_second.sum()) > 0
    assert np.array_equal(gt_second, cached_second)


def test_pred_previous_cache_first_step_is_empty(tmp_path):
    manifest = _write_next_dataset(tmp_path)
    metadata = _write_predprev_cache(tmp_path)
    samples = build_next_stroke_samples(load_manifest(manifest))
    cache = PredPreviousCache.from_csv(metadata)
    dataset = StrokeNextDataset(samples, image_size=32, pred_previous_cache=cache, pred_previous_prob=1.0)

    first = dataset[0]["input"][1].numpy()
    assert first.shape == (32, 32)
    assert float(first.sum()) == 0.0
