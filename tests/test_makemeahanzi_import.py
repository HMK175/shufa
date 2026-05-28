import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from check_stroke_cls_dataset import check_dataset
from import_makemeahanzi import classify_stroke, import_graphics, parse_graphics_line
from rebuild_stroke_cls_dataset import rebuild_dataset


def test_parse_graphics_line_reads_character_strokes_and_medians():
    row = {
        "character": "山",
        "strokes": ["M 10 10 L 40 10"],
        "medians": [[[10, 10], [40, 10]]],
    }

    parsed = parse_graphics_line(json.dumps(row, ensure_ascii=False))

    assert parsed["character"] == "山"
    assert parsed["strokes"] == ["M 10 10 L 40 10"]
    assert parsed["medians"] == [[[10, 10], [40, 10]]]


def test_classify_basic_median_shapes_uses_six_plus_one_classes():
    assert classify_stroke([[0, 0], [80, 4]]) == "heng"
    assert classify_stroke([[0, 0], [2, 90]]) == "shu"
    assert classify_stroke([[90, 80], [10, 0]]) == "pie"
    assert classify_stroke([[10, 80], [90, 0]]) == "na"
    assert classify_stroke([[10, 10], [40, 10], [40, 60]]) == "zhe"
    assert classify_stroke([[0, 0], [8, 8]]) == "dian"


def test_import_graphics_writes_review_images_and_new_metadata_schema(tmp_path):
    graphics = tmp_path / "graphics.txt"
    graphics.write_text(
        json.dumps(
            {
                "character": "一",
                "strokes": ["M 100 500 L 900 500"],
                "medians": [[[100, 500], [900, 500]]],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "stroke_cls_dataset"

    summary = import_graphics(graphics, out_dir, limit=1, chars=None, image_size=64)

    assert summary["total_samples"] == 1
    metadata = out_dir / "metadata.csv"
    assert metadata.exists()
    with metadata.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["auto_class"] == "heng"
    assert rows[0]["class_name"] == "heng"
    assert (out_dir / rows[0]["image_path"]).exists()
    assert (out_dir / rows[0]["review_path"]).exists()


def test_rebuild_uses_manual_class_name_and_maps_gou_to_zhe(tmp_path):
    data_dir = tmp_path / "stroke_cls_dataset"
    image_dir = data_dir / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "s1.png").write_bytes(b"not an image")
    metadata = data_dir / "metadata.csv"
    with metadata.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id",
                "char",
                "stroke_index",
                "auto_class",
                "class_name",
                "image_path",
                "review_path",
                "median_points",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "s1",
                "char": "乙",
                "stroke_index": "1",
                "auto_class": "gou",
                "class_name": "gou",
                "image_path": "images/s1.png",
                "review_path": "review/s1_review.png",
                "median_points": "[]",
                "source": "test",
            }
        )

    counts = rebuild_dataset(metadata, data_dir, clear=True)

    assert counts["zhe"] == 1
    assert (data_dir / "zhe" / "s1.png").exists()


def test_review_rendering_keeps_makemeahanzi_glyph_upright(tmp_path):
    graphics = tmp_path / "graphics.txt"
    graphics.write_text(
        json.dumps(
            {
                "character": "山",
                "strokes": [
                    "M 536 209 Q 546 407 552 587 Q 556 633 562 664 Q 569 691 574 710 Q 578 723 554 740 Q 512 762 484 767 Q 465 771 456 760 Q 447 751 457 734 Q 488 688 489 655 Q 499 444 488 200 C 487 170 534 179 536 209 Z",
                    "M 796 244 Q 657 232 536 209 L 488 200 Q 379 182 284 155 Q 256 148 263 180 Q 267 253 272 329 Q 275 357 263 373 Q 220 416 190 409 Q 178 403 188 382 Q 224 309 215 236 Q 211 166 182 133 Q 161 112 170 96 Q 183 78 203 66 Q 219 57 230 67 Q 243 83 283 99 Q 440 151 606 182 Q 757 210 789 197 C 819 193 826 247 796 244 Z",
                    "M 789 197 Q 783 166 774 145 Q 756 118 785 55 Q 795 36 809 49 Q 837 73 846 173 Q 868 386 890 427 Q 900 443 889 460 Q 867 479 831 501 Q 816 510 802 503 Q 793 499 796 484 Q 823 435 796 244 L 789 197 Z",
                ],
                "medians": [
                    [[472, 748], [525, 700], [514, 235], [493, 208]],
                    [[196, 398], [217, 379], [239, 340], [243, 263], [233, 126], [282, 127], [380, 155], [575, 197], [710, 218], [772, 221], [788, 237]],
                    [[810, 490], [826, 477], [849, 433], [798, 57]],
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "stroke_cls_dataset"

    import_graphics(graphics, out_dir, limit=1, chars=None, image_size=64)

    review = cv2.imread(str(out_dir / "review" / "u5c71_01_review.png"))
    assert review is not None
    # The first stroke of "山" starts near the top in upright rendering. In the
    # full-glyph review panel (left side), the red highlight should therefore
    # occupy more pixels in the upper half than the lower half.
    full_panel = review[:, : int(review.shape[1] * 0.55)]
    red = (
        (full_panel[:, :, 2] > 150)
        & (full_panel[:, :, 1] < 90)
        & (full_panel[:, :, 0] < 90)
    )
    ys = np.where(red)[0]
    assert len(ys) > 0
    assert np.median(ys) < full_panel.shape[0] * 0.52


def test_check_stroke_cls_dataset_handles_missing_metadata(tmp_path, capsys):
    code = check_dataset(tmp_path)
    captured = capsys.readouterr()

    assert code == 0
    assert "metadata.csv not found" in captured.out
