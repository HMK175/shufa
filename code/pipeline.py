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
from skeleton import skeletonize
from trajectory import trace_skeleton, trace_skeleton_dfs, smooth_bspline, smooth_strokes, save_trajectory_csv, save_stroke_csv
from stroke import get_stroke_list, prune_skeleton

# ============================================================
# 可调参数：直接修改这里的值，然后点 ▶ 运行
# ============================================================
TRACE_MODE = "stroke"  # 轨迹追踪: "stroke"(笔画感知) / "dfs"(简单DFS)
SMOOTH = 2.0           # B样条平滑强度 (0=不平滑, 越大越平滑)
SAMPLE = 300           # 平滑后采样点数 (0=保持原始点数)
USE_RL = True          # 是否使用 RL 微调轨迹
RL_EPISODES = 200      # RL 每笔画训练轮数
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_images():
    """返回 code/ 下所有用户图片（排除生成的结果图）。"""
    imgs = []
    for f in sorted(glob.glob(os.path.join(SCRIPT_DIR, "*.jpg")) +
                    glob.glob(os.path.join(SCRIPT_DIR, "*.jpeg")) +
                    glob.glob(os.path.join(SCRIPT_DIR, "*.jfif")) +
                    glob.glob(os.path.join(SCRIPT_DIR, "*.png"))):
        base = os.path.basename(f)
        if "pipeline" in base or "test" in base:
            continue
        imgs.append(f)
    return imgs


def process_one(image_path, output_csv, output_img, smooth, sample, trace_mode,
                use_rl=None, rl_episodes=None):
    """处理单张图片，返回是否成功。"""
    print(f"\n{'='*50}")
    print(f"Processing: {os.path.basename(image_path)}  [trace={trace_mode}]")

    img = load_image(image_path)
    print(f"[1/5] Loaded: {img.shape}")

    binary = preprocess(img)
    print(f"[2/5] Binary (fg: {np.sum(binary > 0)})")

    skeleton = skeletonize(binary)
    n_sk = np.sum(skeleton > 0)
    print(f"[3/5] Skeleton (px: {n_sk})")
    if n_sk == 0:
        print("  -> SKIP: empty skeleton", file=sys.stderr)
        return False

    # 骨架剪枝（移除毛刺）
    skeleton = prune_skeleton(skeleton)
    n_pruned = np.sum(skeleton > 0)
    print(f"      Pruned: {n_sk} → {n_pruned} px ({n_sk - n_pruned} removed)")

    # 选择追踪方法
    if trace_mode == "dfs":
        trajectory = trace_skeleton_dfs(skeleton)
        strokes = None
    else:
        trajectory = trace_skeleton(skeleton)
        strokes = get_stroke_list(skeleton)

    print(f"[4/5] Trajectory ({len(trajectory)} pts, {len(strokes) if strokes else 0} strokes)")

    # 平滑：如果有笔画列表则逐笔画平滑（笔画间抬笔），否则整条平滑
    rl_strokes = None
    display_strokes = None
    if strokes and len(strokes) > 0:
        if smooth > 0 or sample > 0:
            smoothed_strokes = smooth_strokes(strokes, total_points=sample if sample > 0 else 300, s=smooth)
            print(f"[5/5] Smoothed by stroke ({sum(len(s) for s in smoothed_strokes)} total pts)")
        else:
            smoothed_strokes = [s.copy() for s in strokes]

        # RL 微调（可选）
        if use_rl:
            from rl_optimizer import optimize_trajectory_rl
            print(f"[RL] Optimizing with DDPG ({rl_episodes} eps/stroke)...")
            rl_strokes, rl_noisy_strokes, rl_stats = optimize_trajectory_rl(
                binary, skeleton, smoothed_strokes,
                episodes_per_stroke=rl_episodes,
                verbose=True,
            )
            total_pts = sum(len(s) for s in rl_strokes)
            avg_init = sum(rl_stats["init_chamfer"]) / len(rl_stats["init_chamfer"])
            avg_noisy = sum(rl_stats["noisy_chamfer"]) / len(rl_stats["noisy_chamfer"])
            avg_final = sum(rl_stats["final_chamfer"]) / len(rl_stats["final_chamfer"])
            print(f"[RL] Done: {total_pts} total pts, "
                  f"Chamfer: init={avg_init:.1f} → noisy={avg_noisy:.1f} → RL={avg_final:.1f}px")

            # 保存 RL 结果和加噪对比
            rl_csv = output_csv.replace(".csv", "_rl.csv")
            save_stroke_csv(rl_strokes, rl_csv)
            print(f"  -> {rl_csv}")

        save_stroke_csv(rl_strokes if rl_strokes else smoothed_strokes, output_csv)
        display_strokes = rl_strokes if rl_strokes else smoothed_strokes
        all_smoothed = np.vstack(display_strokes)
    elif smooth > 0 or sample > 0:
        num_pts = sample if sample > 0 else len(trajectory)
        all_smoothed = smooth_bspline(trajectory, num_points=num_pts, s=smooth)
        print(f"[5/5] Smoothed ({len(all_smoothed)} pts)")
        save_trajectory_csv(all_smoothed, output_csv)
    else:
        all_smoothed = trajectory
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

    if display_strokes is not None and len(display_strokes) > 1:
        # 按笔画着色
        colors = plt.cm.tab10(np.linspace(0, 1, len(display_strokes)))
        for i, s in enumerate(display_strokes):
            axes[3].plot(s[:, 1], s[:, 0], "-", color=colors[i],
                         linewidth=1.2, label=f"S{i+1}")
        title = f"Trajectory ({trace_mode}"
        if rl_strokes is not None:
            title += " + RL"
        title += ")"
        axes[3].set_title(title)
        axes[3].legend(fontsize=7)
    elif len(trajectory) > 0:
        axes[3].plot(trajectory[:, 1], trajectory[:, 0], "c-", linewidth=0.8, alpha=0.5, label="Raw")
        axes[3].set_title(f"Trajectory ({trace_mode})")
    if smooth > 0 and strokes is None and len(all_smoothed) > 0:
        axes[3].plot(all_smoothed[:, 1], all_smoothed[:, 0], "r-", linewidth=1.0, label="Smoothed")
    axes[3].invert_yaxis()
    axes[3].set_aspect("equal")
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
    parser.add_argument("--trace", choices=["stroke", "dfs"], default=TRACE_MODE,
                        help=f"Trace method (default: {TRACE_MODE})")
    parser.add_argument("--smooth", type=float, default=SMOOTH)
    parser.add_argument("--sample", type=int, default=SAMPLE)
    parser.add_argument("--rl", action="store_true", default=USE_RL,
                        help="Apply DDPG RL trajectory optimization")
    parser.add_argument("--rl-episodes", type=int, default=RL_EPISODES,
                        help=f"RL episodes per stroke (default: {RL_EPISODES})")
    args = parser.parse_args()

    if args.image:
        # 单张模式
        out_csv = args.output or "trajectory.csv"
        out_img = args.output_img or "pipeline_result.png"
        process_one(args.image, out_csv, out_img, args.smooth, args.sample, args.trace,
                    use_rl=args.rl, rl_episodes=args.rl_episodes)
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
            if process_one(img_path, out_csv, out_img, args.smooth, args.sample, args.trace):
                ok += 1
        print(f"\nDone: {ok}/{len(images)} succeeded.")


if __name__ == "__main__":
    main()
