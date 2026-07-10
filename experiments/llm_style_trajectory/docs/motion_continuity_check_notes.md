# 运动连续性 dry-run 检查说明

该层用于在后续 CoppeliaSim playback、IK dry-run 或低速空跑准备之前，离线检查重采样 workspace 轨迹或机器人 target pose 序列。

## 范围

- 输入：`robot_workspace_trajectory_resampled.csv` 或 `robot_target_poses.csv`。
- 输出：`motion_continuity_summary.json`、`motion_continuity_report.md` 和
  `motion_continuity_points.csv`。
- 这只是离线 dry-run 检查。
- 它不是真实机器人动力学检查，不做逆运动学，不检查关节空间速度/加速度/力矩，不做碰撞检测，也不控制真实机器人。

## 检查项

- workspace 或 target-pose 输入所需字段。
- 时间连续性：`dt_min`、`dt_max`、`dt_mean` 和 `dt <= 0`。
- 相邻点 3D 距离和由此计算的笛卡尔速度。
- 相邻区间速度跳变。
- 笛卡尔加速度估计。
- 笛卡尔 jerk 估计。
- target pose 的 quaternion 范数，以及姿态是否固定或平滑。
- `stroke`、`connector`、`pen_up_move` 的分段统计。

## 保守阈值

默认阈值只是 dry-run gate，不是已确认的 AUBO i5 控制器限制：

| threshold | value |
|---|---:|
| max_speed_m_s | 0.10 |
| max_accel_m_s2 | 0.50 |
| max_jerk_m_s3 | 5.0 |
| max_speed_jump_m_s | 0.05 |

## 默认样例结果

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_points.csv
```

关键结果：

| field | value |
|---|---:|
| point_count | 275 |
| duration_s | 13.0528205 |
| path_length_m | 0.359530547 |
| max_speed_m_s | 0.04 |
| max_speed_jump_m_s | 0.025 |
| max_accel_m_s2 | 0.533536284 |
| max_jerk_m_s3 | 11.386446091 |
| dt_nonpositive_count | 4 |
| quaternion_normalized | true |
| recommended_for_coppeliasim_playback | false |
| recommended_for_ik_dry_run | false |

该样例在几何上仍适合之前的 pen-tip playback，但 motion-continuity gate 检出了重复的零时间边界点，以及保守加速度/jerk 阈值超限。进入真实 IK 或低速空跑准备之前，应先对 target pose 序列做去重、retiming 和速度平滑。
