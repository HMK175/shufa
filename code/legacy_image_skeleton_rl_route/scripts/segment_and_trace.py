"""Segment a glyph into per-stroke masks, skeletonize each mask, and export strokes."""

import argparse
from pathlib import Path
from typing import List

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import torch
except ImportError:  # pragma: no cover - depends on local environment
    torch = None

from skeleton import skeletonize
try:
    from stroke_segmenter import MiniUNet
except ImportError:  # pragma: no cover - depends on local environment
    MiniUNet = None
from trajectory import save_stroke_csv, smooth_strokes, trace_skeleton_dfs


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_segmenter.pt"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output" / "segmenter"


def _load_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    return image


def _predict_masks(image: np.ndarray, model_path: Path, max_strokes: int, image_size: int, threshold: float):
    if torch is None or MiniUNet is None:
        raise RuntimeError("PyTorch is not installed in this environment. Install torch before inference.")
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")

    checkpoint = torch.load(str(model_path), map_location="cpu")
    max_strokes = int(checkpoint.get("max_strokes", max_strokes))
    image_size = int(checkpoint.get("image_size", image_size))
    model = MiniUNet(max_strokes=max_strokes)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    resized = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
    tensor = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        probs = torch.sigmoid(model(tensor))[0].cpu().numpy()

    masks = []
    for channel in probs:
        mask = (channel >= threshold).astype(np.uint8) * 255
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        masks.append(mask)
    return masks


def _trace_masks(masks: List[np.ndarray], min_area: int, smooth_points: int, smooth_s: float) -> List[np.ndarray]:
    strokes = []
    for mask in masks:
        if int(np.count_nonzero(mask > 0)) < min_area:
            continue
        skel = skeletonize(mask)
        path = trace_skeleton_dfs(skel)
        if len(path) < 2:
            continue
        strokes.append(path.astype(float))
    if smooth_points > 0 and strokes:
        return smooth_strokes(strokes, total_points=smooth_points, s=smooth_s)
    return strokes


def _save_mask_preview(image: np.ndarray, masks: List[np.ndarray], out_path: Path) -> None:
    base = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    colors = plt.cm.tab20(np.linspace(0, 1, max(len(masks), 1)))[:, :3]
    overlay = base.astype(float) / 255.0
    for i, mask in enumerate(masks):
        fg = mask > 0
        if np.any(fg):
            overlay[fg] = 0.45 * overlay[fg] + 0.55 * colors[i]
    plt.figure(figsize=(6, 6))
    plt.imshow(np.clip(overlay, 0, 1))
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def _save_trace_preview(image: np.ndarray, masks: List[np.ndarray], strokes: List[np.ndarray], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].imshow(image, cmap="gray")
    axes[0].set_title("Input")
    axes[1].set_facecolor("black")
    colors = plt.cm.tab20(np.linspace(0, 1, max(len(strokes), 1)))
    for i, stroke in enumerate(strokes):
        axes[1].plot(stroke[:, 1], stroke[:, 0], "-", color=colors[i], linewidth=1.4)
    axes[1].invert_yaxis()
    axes[1].set_aspect("equal")
    axes[1].set_title(f"Segmented strokes ({len(strokes)})")
    for ax in axes:
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def run(args) -> int:
    image_path = Path(args.image).resolve()
    model_path = Path(args.model).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image = _load_gray(image_path)

    try:
        masks = _predict_masks(image, model_path, args.max_strokes, args.image_size, args.threshold)
    except (FileNotFoundError, RuntimeError, KeyError) as exc:
        print(f"Inference cannot run: {exc}")
        return 0

    stem = image_path.stem
    mask_dir = output_dir / f"{stem}_masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    for i, mask in enumerate(masks, start=1):
        cv2.imwrite(str(mask_dir / f"{i:02d}.png"), mask)

    strokes = _trace_masks(masks, args.min_area, args.smooth_points, args.smooth)
    csv_path = Path(args.output_csv).resolve() if args.output_csv else output_dir / f"{stem}_segmented.csv"
    save_stroke_csv(strokes, str(csv_path))
    mask_preview = output_dir / f"{stem}_mask_preview.png"
    trace_preview = output_dir / f"{stem}_trace_preview.png"
    _save_mask_preview(image, masks, mask_preview)
    _save_trace_preview(image, masks, strokes, trace_preview)

    print(f"Saved masks: {mask_dir}")
    print(f"Saved trajectory CSV: {csv_path}")
    print(f"Saved mask preview: {mask_preview}")
    print(f"Saved trace preview: {trace_preview}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment a glyph and trace per-stroke masks")
    parser.add_argument("image")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--max-strokes", type=int, default=12)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--min-area", type=int, default=20)
    parser.add_argument("--smooth-points", type=int, default=300)
    parser.add_argument("--smooth", type=float, default=8.0)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output-csv", default=None)
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
