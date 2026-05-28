"""Visualize candidate stroke predictions for one glyph."""

import argparse
import csv
from math import ceil
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _parse_bbox(text: str):
    y0, x0, y1, x1 = [float(v) for v in text.split(";")]
    return y0, x0, y1, x1


def visualize(candidates_csv: Path, predictions_csv: Path) -> Path:
    base_dir = candidates_csv.parent
    candidates = _read_csv(candidates_csv)
    predictions = {row["candidate_id"]: row for row in _read_csv(predictions_csv)}
    if not candidates:
        raise RuntimeError(f"no candidates in {candidates_csv}")

    source_image = Path(candidates[0]["source_image"])
    image = cv2.imread(str(source_image), cv2.IMREAD_GRAYSCALE)
    if image is None:
        image = np.full((256, 256), 255, dtype=np.uint8)

    cols = 3
    rows = ceil(len(candidates) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4.4))
    axes = np.array(axes).reshape(-1)

    for ax, row in zip(axes, candidates):
        pred = predictions.get(row["candidate_id"], {})
        crop = cv2.imread(str(base_dir / row["candidate_image"]), cv2.IMREAD_GRAYSCALE)
        panel = np.full((image.shape[0], image.shape[1] + (crop.shape[1] if crop is not None else 128), 3), 255, dtype=np.uint8)
        gray_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        panel[: image.shape[0], : image.shape[1]] = gray_rgb
        y0, x0, y1, x1 = _parse_bbox(row["bbox"])
        cv2.rectangle(panel, (int(x0), int(y0)), (int(x1), int(y1)), (220, 30, 30), 3)
        if crop is not None:
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            crop_rgb = cv2.resize(crop_rgb, (128, 128), interpolation=cv2.INTER_AREA)
            yoff = max(0, (panel.shape[0] - 128) // 2)
            xoff = image.shape[1]
            panel[yoff : yoff + 128, xoff : xoff + 128] = crop_rgb
        ax.imshow(panel)
        title = (
            f"{row['candidate_id']}  w={float(row['winding']):.2f}\n"
            f"1 {pred.get('top1_class','')} {pred.get('top1_conf','')}  "
            f"2 {pred.get('top2_class','')} {pred.get('top2_conf','')}  "
            f"3 {pred.get('top3_class','')} {pred.get('top3_conf','')}\n"
            f"{pred.get('reliable','')} {pred.get('note','')}"
        )
        ax.set_title(title, fontsize=9)
        ax.axis("off")

    for ax in axes[len(candidates):]:
        ax.axis("off")
    fig.tight_layout()
    out_path = base_dir / "candidate_predictions.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize candidate predictions")
    parser.add_argument("candidates_csv")
    parser.add_argument("predictions_csv")
    args = parser.parse_args()
    visualize(Path(args.candidates_csv).resolve(), Path(args.predictions_csv).resolve())


if __name__ == "__main__":
    main()
