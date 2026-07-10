"""Check the per-stroke mask dataset and create overlay previews."""

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PREVIEW_DIR = SCRIPT_DIR / "output" / "dataset_preview"
MASK_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def _resolve_path(path_text: str, base_dir: Path) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _read_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        print(f"Dataset manifest not found: {path}")
        print("Create it first, or use code/dataset/manifest.csv as the template.")
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    return rows


def _mask_files(mask_dir: Path) -> List[Path]:
    if not mask_dir.exists():
        return []
    return sorted(p for p in mask_dir.iterdir() if p.suffix.lower() in MASK_EXTS)


def _color_overlay(gray: np.ndarray, masks: List[np.ndarray]) -> np.ndarray:
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    colors = [
        (230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200),
        (245, 130, 48), (145, 30, 180), (70, 240, 240), (240, 50, 230),
        (210, 245, 60), (250, 190, 190), (0, 128, 128), (230, 190, 255),
        (170, 110, 40), (255, 250, 200), (128, 0, 0), (170, 255, 195),
    ]
    overlay = base.copy()
    for i, mask in enumerate(masks):
        fg = mask > 0
        if not np.any(fg):
            continue
        color = np.array(colors[i % len(colors)], dtype=np.uint8)
        overlay[fg] = (0.45 * overlay[fg] + 0.55 * color).astype(np.uint8)
    return overlay


def check_dataset(manifest: Path, preview_dir: Path) -> int:
    rows = _read_manifest(manifest)
    if not rows:
        print("No dataset samples found in manifest.")
        print("Expected columns: char_id,char,image_path,mask_dir,stroke_count,split,note")
        return 0

    preview_dir.mkdir(parents=True, exist_ok=True)
    base_dir = manifest.parent
    errors = 0
    total = 0

    for row in rows:
        total += 1
        char_id = (row.get("char_id") or "").strip()
        image_path = _resolve_path(row.get("image_path", ""), base_dir)
        mask_dir = _resolve_path(row.get("mask_dir", ""), base_dir)
        stroke_count_text = (row.get("stroke_count") or "").strip()
        try:
            stroke_count = int(stroke_count_text)
        except ValueError:
            stroke_count = -1
            print(f"[ERROR] {char_id or '<missing>'}: invalid stroke_count={stroke_count_text!r}")
            errors += 1

        sample_errors = []
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            sample_errors.append(f"image not readable: {image_path}")

        mask_paths = _mask_files(mask_dir)
        if not mask_dir.exists():
            sample_errors.append(f"mask_dir not found: {mask_dir}")
        elif stroke_count >= 0 and len(mask_paths) != stroke_count:
            sample_errors.append(f"mask count {len(mask_paths)} != stroke_count {stroke_count}")

        masks = []
        coverage_parts = []
        if image is not None:
            image_area = image.shape[0] * image.shape[1]
            for mask_path in mask_paths:
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is None:
                    sample_errors.append(f"mask not readable: {mask_path}")
                    continue
                if mask.shape != image.shape:
                    sample_errors.append(
                        f"mask size mismatch: {mask_path.name} {mask.shape} != image {image.shape}"
                    )
                    continue
                masks.append(mask)
                coverage = float(np.count_nonzero(mask > 0)) / float(image_area)
                coverage_parts.append(f"{mask_path.stem}:{coverage:.4f}")

        if image is not None and masks:
            overlay = _color_overlay(image, masks)
            out_path = preview_dir / f"{char_id or image_path.stem}_overlay.png"
            cv2.imwrite(str(out_path), overlay)
            preview_msg = f" preview={out_path}"
        else:
            preview_msg = ""

        if sample_errors:
            errors += len(sample_errors)
            print(f"[ERROR] {char_id or image_path.stem}: " + "; ".join(sample_errors))
        else:
            print(f"[OK] {char_id}: masks={len(masks)} coverage=[{', '.join(coverage_parts)}]{preview_msg}")

    print(f"Checked {total} sample(s), errors={errors}.")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a stroke mask dataset manifest")
    parser.add_argument("--manifest", default=str(SCRIPT_DIR / "dataset" / "manifest.csv"))
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    args = parser.parse_args()

    code = check_dataset(Path(args.manifest).resolve(), Path(args.preview_dir).resolve())
    raise SystemExit(code)


if __name__ == "__main__":
    main()
