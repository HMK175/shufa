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
from skeleton import skeletonize, smooth_junctions, straighten_junctions
from trajectory import trace_skeleton, trace_skeleton_dfs, trace_skeleton_curvature, smooth_bspline, smooth_strokes, save_trajectory_csv, save_stroke_csv
from stroke import get_stroke_list, prune_skeleton

# ============================================================
# 可调参数：直接修改这里的值，然后点 ▶ 运行
# ============================================================
TRACE_MODE = "stroke"  # 轨迹追踪: "stroke"(笔画感知) / "curvature"(曲率分割) / "dfs"(简单DFS)
SMOOTH = 5.0           # B样条平滑强度 (0=不平滑, 越大越平滑)
BLUR_KSIZE = 5         # 二值化前高斯核大小 (0=关闭, 3-7推荐)
SAMPLE = 300           # 平滑后采样点数 (0=保持原始点数)
USE_RL = True          # 是否使用 RL 微调轨迹
RL_EPISODES = 200      # RL 每笔画训练轮数

# ── 新增：骨架方法 & 轨迹优化 ──────────────────────────────────
SKELETON_METHOD = "thin"    # 骨架: "thin"(形态学细化) / "wu2024"(轮廓中点)
ENHANCED_SMOOTH = False     # 启用增强平滑（savgol/adaptive_bspline）
SMOOTH_METHOD = "savgol"    # 平滑方法: "savgol" / "adaptive_bspline" / "both"
APPLY_ARC_LENGTH = True     # 弧长均匀重采样
APPLY_VELOCITY_PLAN = False # 时间参数化轨迹（速度规划）
APPLY_CURVATURE_OPT = False # 局部曲率约束优化
APPLY_WORKSPACE_MAP = False # 映射到机器人工作空间
WORKSPACE_ORIGIN = (0.0, 0.0, 0.05)  # (X,Y,Z) 米
WORKSPACE_SCALE = (0.15, 0.15)       # (scale_x, scale_y) 米
V_MAX = 1.0                         # 最大速度
CURV_ALPHA = 1.0                    # 曲率灵敏度
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
                use_rl=None, rl_episodes=None,
                skeleton_method=None, enhanced_smooth=None,
                smooth_method=None, apply_arc_length=None,
                apply_velocity_plan=None, apply_curvature_opt=None,
                apply_workspace_map=None):
    """处理单张图片，返回是否成功。"""
    print(f"\n{'='*50}")
    print(f"Processing: {os.path.basename(image_path)}  [trace={trace_mode}]")

    img = load_image(image_path)
    print(f"[1/5] Loaded: {img.shape}")

    binary = preprocess(img, blur_ksize=BLUR_KSIZE)
    print(f"[2/5] Binary (fg: {np.sum(binary > 0)})")

    # 骨架提取：按方法分发
    if skeleton_method == "wu2024":
        from wu2024_skeleton import wu2024_skeletonize, get_wu2024_stroke_list
        skeleton = wu2024_skeletonize(binary)
        n_sk = np.sum(skeleton > 0)
        print(f"[3/5] Skeleton (px: {n_sk}, method: wu2024)")
        if n_sk == 0:
            print("  -> SKIP: empty skeleton", file=sys.stderr)
            return False
        # wu2024 自带笔画组装，不需额外 prune
        if trace_mode == "dfs":
            trajectory = trace_skeleton_dfs(skeleton)
            strokes = None
        elif trace_mode == "curvature":
            strokes_raw = trace_skeleton_curvature(skeleton, angle_threshold=50.0)
            strokes = [s for s in strokes_raw if len(s) >= 5]
            trajectory = np.vstack(strokes) if strokes else np.empty((0, 2))
        else:
            strokes = get_wu2024_stroke_list(skeleton)
            trajectory = np.vstack(strokes) if strokes else np.empty((0, 2))
    else:
        skeleton = skeletonize(binary)
        n_sk = np.sum(skeleton > 0)
        print(f"[3/5] Skeleton (px: {n_sk})")
        if n_sk == 0:
            print("  -> SKIP: empty skeleton", file=sys.stderr)
            return False
        skeleton = prune_skeleton(skeleton)
        n_pruned = np.sum(skeleton > 0)
        print(f"      Pruned: {n_sk} → {n_pruned} px ({n_sk - n_pruned} removed)")
        skeleton = straighten_junctions(skeleton)
        n_straight = np.sum(skeleton > 0)
        print(f"      Junction fix: {n_pruned} → {n_straight} px")

        if trace_mode == "dfs":
            trajectory = trace_skeleton_dfs(skeleton)
            strokes = None
        elif trace_mode == "curvature":
            strokes_raw = trace_skeleton_curvature(skeleton, angle_threshold=50.0)
            strokes = [s for s in strokes_raw if len(s) >= 5]
            trajectory = np.vstack(strokes) if strokes else np.empty((0, 2))
        else:
            trajectory = trace_skeleton(skeleton)
            strokes = get_stroke_list(skeleton)

    print(f"[4/5] Trajectory ({len(trajectory)} pts, {len(strokes) if strokes else 0} strokes)")

    # 平滑：如果有笔画列表则逐笔画平滑（笔画间抬笔），否则整条平滑
    rl_strokes = None
    display_strokes = None
    timed_data = None
    if strokes and len(strokes) > 0:
        if enhanced_smooth:
            from trajectory_optimizer import optimize_trajectory, save_timed_csv
            opt_result = optimize_trajectory(
                strokes, binary,
                smooth_method=smooth_method,
                apply_arc_length=apply_arc_length,
                apply_velocity_plan=apply_velocity_plan,
                apply_curvature_opt=apply_curvature_opt,
                apply_workspace_map=apply_workspace_map,
                bspline_s=smooth,
            )
            smoothed_strokes = opt_result['strokes']
            timed_data = opt_result
            n_pts = sum(len(s) for s in smoothed_strokes)
            print(f"[5/5] Enhanced smooth ({smooth_method}, {n_pts} pts, "
                  f"Chamfer={opt_result['chamfer']:.1f}px)")
        else:
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
                noise_std=2.0,
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

        # 附加输出：时间参数化 / 工作空间
        if timed_data and timed_data.get('timestamps') and apply_velocity_plan:
            timed_csv = output_csv.replace(".csv", "_timed.csv")
            from trajectory_optimizer import save_timed_csv as _save_timed
            for si, stk in enumerate(display_strokes):
                if si < len(timed_data['timestamps']) and timed_data['timestamps'][si] is not None:
                    _save_timed(stk, timed_data['velocities'][si],
                               timed_data['timestamps'][si],
                               timed_csv if len(display_strokes) == 1
                               else timed_csv.replace(".csv", f"_s{si+1}.csv"))
            print(f"  -> {timed_csv}")
        if timed_data and timed_data.get('workspace') and apply_workspace_map:
            ws_csv = output_csv.replace(".csv", "_workspace.csv")
            from trajectory_optimizer import workspace_to_csv
            all_ws = [w for w in timed_data['workspace'] if w is not None]
            if all_ws:
                workspace_to_csv(np.vstack(all_ws), ws_csv)
                print(f"  -> {ws_csv}")
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
    parser.add_argument("--trace", choices=["stroke", "dfs", "curvature"], default=TRACE_MODE,
                        help=f"Trace method (default: {TRACE_MODE})")
    parser.add_argument("--smooth", type=float, default=SMOOTH)
    parser.add_argument("--sample", type=int, default=SAMPLE)
    parser.add_argument("--rl", action="store_true", default=USE_RL,
                        help="Apply DDPG RL trajectory optimization")
    parser.add_argument("--no-rl", action="store_false", dest="rl",
                        help="Disable RL optimization")
    parser.add_argument("--rl-episodes", type=int, default=RL_EPISODES,
                        help=f"RL episodes per stroke (default: {RL_EPISODES})")
    parser.add_argument("--skeleton", choices=["thin", "wu2024"], default=SKELETON_METHOD,
                        help=f"Skeleton method (default: {SKELETON_METHOD})")
    parser.add_argument("--enhanced-smooth", action="store_true", default=ENHANCED_SMOOTH,
                        help="Enable enhanced smoothing (savgol/adaptive_bspline)")
    parser.add_argument("--smooth-method", choices=["savgol", "adaptive_bspline", "both"],
                        default=SMOOTH_METHOD,
                        help=f"Smoothing method (default: {SMOOTH_METHOD})")
    parser.add_argument("--no-arc-length", action="store_false", dest="apply_arc_length",
                        default=APPLY_ARC_LENGTH,
                        help="Disable arc-length reparameterization")
    parser.add_argument("--velocity-plan", action="store_true", default=APPLY_VELOCITY_PLAN,
                        help="Enable time-parameterized velocity planning")
    parser.add_argument("--curvature-opt", action="store_true", default=APPLY_CURVATURE_OPT,
                        help="Enable local curvature optimization")
    parser.add_argument("--workspace-map", action="store_true", default=APPLY_WORKSPACE_MAP,
                        help="Enable workspace mapping (pixels → meters)")
    args = parser.parse_args()

    if args.image:
        # 单张模式
        out_csv = args.output or "trajectory.csv"
        out_img = args.output_img or "pipeline_result.png"
        process_one(args.image, out_csv, out_img, args.smooth, args.sample, args.trace,
                    use_rl=args.rl, rl_episodes=args.rl_episodes,
                    skeleton_method=args.skeleton,
                    enhanced_smooth=args.enhanced_smooth,
                    smooth_method=args.smooth_method,
                    apply_arc_length=args.apply_arc_length,
                    apply_velocity_plan=args.velocity_plan,
                    apply_curvature_opt=args.curvature_opt,
                    apply_workspace_map=args.workspace_map)
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
            if process_one(img_path, out_csv, out_img, args.smooth, args.sample, args.trace,
                          use_rl=args.rl, rl_episodes=args.rl_episodes,
                          skeleton_method=args.skeleton,
                          enhanced_smooth=args.enhanced_smooth,
                          smooth_method=args.smooth_method,
                          apply_arc_length=args.apply_arc_length,
                          apply_velocity_plan=args.velocity_plan,
                          apply_curvature_opt=args.curvature_opt,
                          apply_workspace_map=args.workspace_map):
                ok += 1
        print(f"\nDone: {ok}/{len(images)} succeeded.")


if __name__ == "__main__":
    main()
