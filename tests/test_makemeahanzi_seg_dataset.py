import csv
import json
import sys
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from check_stroke_seg_dataset import check_dataset
from generate_makemeahanzi_seg_dataset import generate_dataset


def _write_sample_graphics(path: Path) -> None:
    rows = [
        {
            "character": "一",
            "strokes": ["M 100 500 L 900 500 Q 920 500 900 520 L 100 520 Z"],
            "medians": [[[100, 510], [900, 510]]],
        },
        {
            "character": "十",
            "strokes": [
                "M 120 480 L 900 480 L 900 520 L 120 520 Z",
                "M 500 120 L 540 120 L 540 900 L 500 900 Z",
            ],
            "medians": [
                [[120, 500], [900, 500]],
                [[520, 120], [520, 900]],
            ],
        },
        {
            "character": "人",
            "strokes": [
                "M 500 120 L 540 150 L 380 900 L 340 880 Z",
                "M 530 300 L 900 880 L 860 900 L 500 330 Z",
            ],
            "medians": [
                [[520, 135], [360, 890]],
                [[515, 315], [880, 890]],
            ],
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_generate_makemeahanzi_seg_dataset_outputs_valid_structure(tmp_path):
    graphics = tmp_path / "graphics.txt"
    chars_file = tmp_path / "chars.txt"
    out_dir = tmp_path / "stroke_seg_dataset"
    _write_sample_graphics(graphics)
    chars_file.write_text("一十人\n", encoding="utf-8")

    summary = generate_dataset(graphics, chars_file, out_dir, image_size=96)

    assert summary["glyphs"] == 3
    assert summary["total_strokes"] == 5
    assert summary["train"] == 2
    assert summary["val"] == 0
    assert summary["test"] == 1

    manifest = out_dir / "manifest.csv"
    assert manifest.exists()
    with manifest.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    for row in rows:
        image = cv2.imread(str(out_dir / row["image_path"]), cv2.IMREAD_GRAYSCALE)
        assert image is not None
        assert image.shape == (96, 96)

        mask_dir = out_dir / row["mask_dir"]
        median_dir = out_dir / row["median_dir"]
        stroke_count = int(row["stroke_count"])
        masks = sorted(mask_dir.glob("*.png"))
        medians = sorted(median_dir.glob("*.csv"))
        assert len(masks) == stroke_count
        assert len(medians) == stroke_count

        for mask_path in masks:
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            assert mask is not None
            assert mask.shape == image.shape
            assert int((mask > 0).sum()) > 0

        for median_path in medians:
            with median_path.open(newline="", encoding="utf-8") as f:
                median_rows = list(csv.DictReader(f))
            assert median_rows
            assert {"y", "x"} <= set(median_rows[0].keys())

        preview = cv2.imread(str(out_dir / "preview" / f"{row['char_id']}_preview.png"))
        assert preview is not None

    assert check_dataset(out_dir) == 0
