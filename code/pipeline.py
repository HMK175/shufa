"""最小管线：输入字形图片 → 二值化 → 骨架提取 → 初始轨迹 → 平滑轨迹 → 输出CSV。

点击 VS Code ▶ 直接运行：批量处理 code/ 目录下所有 jpg/png 图片。
命令行: python pipeline.py <图片路径> [选项]       处理单张
命令行: python pipeline.py                        批量处理
"""

import argparse
import glob
import os
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from utils import load_image, preprocess
from skeleton import zhang_suen
from trajectory import trace_skeleton, smooth_bspline, save_trajectory_csv

# ============================================================
# 可调参数：直接修改这里的值，然后点 ▶ 运行
# ============================================================
SMOOTH = 2.0   # B样条平滑强度 (0=不平滑, 越大越平滑)
SAMPLE = 300   # 平滑后采样点数 (0=保持原始点数)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_images():
    """返回 code/ 下所有用户图片（排除生成的结果图）。"""
    imgs = []
    for f in sorted(glob.glob(os.path.join(SCRIPT_DIR, "*.jpg")) +
                    glob.glob(os.path.join(SCRIPT_DIR, "*.jpeg")) +
                    glob.glob(os.path.join(SCRIPT_DIR, "*.png"))):
        base = os.path.basename(f)
        if "pipeline" in base or "test_char" in base:
            continue
        imgs.append(f)
    return imgs


def process_one(image_path, output_csv, output_img, smooth, sample):
    """处理单张图片，返回是否成功。"""
    print(f"\n{'='*50}")
    print(f"Processing: {os.path.basename(image_path)}")

    img = load_image(image_path)
    print(f"[1/5] Loaded: {img.shape}")

    binary = preprocess(img)
    print(f"[2/5] Binary (fg: {np.sum(binary > 0)})")

    skeleton = zhang_suen(binary)
    n_sk = np.sum(skeleton > 0)
    print(f"[3/5] Skeleton (px: {n_sk})")
    if n_sk == 0:
        print("  -> SKIP: empty skeleton", file=sys.stderr)
        return False

    trajectory = trace_skeleton(skeleton)
    print(f"[4/5] Trajectory ({len(trajectory)} pts)")

    if smooth > 0 or sample > 0:
        num_pts = sample if sample > 0 else len(trajectory)
        smoothed = smooth_bspline(trajectory, num_points=num_pts, s=smooth)
        print(f"[5/5] Smoothed ({len(smoothed)} pts)")
        save_trajectory_csv(smoothed, output_csv)
    else:
        smoothed = trajectory
        save_trajectory_csv(trajectory, output_csv)

    print(f"  -> {output_csv}")

    # 可视化
    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Original")
    axes[1].imshow(binary, cmap="gray")
    axes[1].set_title("Binary")
    axes[2].imshow(skeleton, cmap="gray")
    axes[2].set_title("Skeleton")
    axes[3].set_facecolor("black")
    if len(trajectory) > 0:
        axes[3].plot(trajectory[:, 1], trajectory[:, 0], "c-", linewidth=0.8, alpha=0.5, label="Raw")
    if smooth > 0 and len(smoothed) > 0:
        axes[3].plot(smoothed[:, 1], smoothed[:, 0], "r-", linewidth=1.0, label="Smoothed")
    axes[3].invert_yaxis()
    axes[3].set_aspect("equal")
    axes[3].set_title("Trajectory")
    if smooth > 0:
        axes[3].legend(fontsize=7)
    for ax in axes:
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_img, dpi=150)
    plt.close()
    print(f"  -> {output_img}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Glyph image → skeleton → trajectory → CSV")
    parser.add_argument("image", nargs="?", default=None)
    parser.add_argument("--output", "-o", default=None, help="CSV output (auto-named in batch mode)")
    parser.add_argument("--output-img", default=None, help="Visualization output (auto-named in batch mode)")
    parser.add_argument("--smooth", type=float, default=SMOOTH)
    parser.add_argument("--sample", type=int, default=SAMPLE)
    args = parser.parse_args()

    if args.image:
        # 单张模式
        out_csv = args.output or "trajectory.csv"
        out_img = args.output_img or "pipeline_result.png"
        process_one(args.image, out_csv, out_img, args.smooth, args.sample)
    else:
        # 批量模式
        images = _find_images()
        if not images:
            print("No jpg/png images found in code/", file=sys.stderr)
            sys.exit(1)
        print(f"Batch processing {len(images)} image(s)")
        ok = 0
        for img_path in images:
            name = os.path.splitext(os.path.basename(img_path))[0]
            out_csv = f"{name}_trajectory.csv"
            out_img = f"{name}_pipeline.png"
            if process_one(img_path, out_csv, out_img, args.smooth, args.sample):
                ok += 1
        print(f"\nDone: {ok}/{len(images)} succeeded.")


if __name__ == "__main__":
    main()
