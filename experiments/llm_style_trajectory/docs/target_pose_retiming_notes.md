# 目标位姿 Retiming 说明

该层在任何真实 IK 或机器人 SDK 接入之前，将 `robot_target_poses.csv` 离线后处理为
`robot_target_poses_smoothed.csv`。它只是一个离线 dry-run 准备步骤。

## 目的

上一轮 motion-continuity 检查发现，默认 weak 行楷“山”样例的 target-pose 序列存在重复边界时间戳，并且在保守阈值下出现加速度/jerk 超限：

| metric | before retiming |
|---|---:|
| `dt_nonpositive_count` | 4 |
| `max_accel_m_s2` | 0.533536284 |
| `max_jerk_m_s3` | 11.386446091 |
| `recommended_for_coppeliasim_playback` | false |
| `recommended_for_ik_dry_run` | false |

retiming 层会删除相邻静止重复位姿，并用保守的 segment-aware 目标速度重写严格递增的时间戳。除零长度重复点外，它保持原始几何书写路径不变。

## 处理规则

- 保留输入位姿顺序。
- 当相邻点的 3D 距离小于等于 duplicate epsilon 时，删除相邻静止重复点。
- 如果点的时间相同但位置不同，不删除，而是重新分配时间戳。
- 根据 3D 距离、`segment_type` 和保守速度重新计算 `t_s`。
- 除删除零长度重复点外，保持 `X_m`、`Y_m`、`Z_m`、quaternion、`pen_down` 和
  `segment_type` 不变。
- 复用 `motion_continuity_check.py` 的 gate；如果未通过，就迭代放大时间，直到通过或达到迭代上限。

默认保守速度：

| segment_type | speed |
|---|---:|
| `stroke` | 0.035 m/s |
| `connector` | 0.025 m/s |
| `pen_up_move` | 0.060 m/s |

这些值只是 dry-run 时间规划选择，不是 AUBO i5 认证限制。

## 默认样例

输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses_smoothed.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_points.csv
```

关键结果：

| metric | before | after |
|---|---:|---:|
| `point_count` | 275 | 271 |
| `removed_duplicate_count` | 0 | 4 |
| `duration_s` | 13.0528205 | 22.039876274 |
| `dt_nonpositive_count` | 4 | 0 |
| `max_speed_m_s` | 0.04 | 0.01792 |
| `max_accel_m_s2` | 0.533536284 | 0.274132141 |
| `max_jerk_m_s3` | 11.386446091 | 4.193553547 |
| `recommended_for_coppeliasim_playback` | false | true |
| `recommended_for_ik_dry_run` | false | true |

几何路径长度保持不变：

```text
geometry_path_length_before_m = 0.359530546527
geometry_path_length_after_m  = 0.359530546527
path_length_delta_m           = 0.0
```

## 命令

```powershell
python experiments\llm_style_trajectory\src\target_pose_retiming.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses.csv
```

## 边界

该层不是真实机器人动力学优化，不做 IK，不做关节空间规划，不检查关节速度/加速度/力矩，不 import 或执行 AUBO SDK，不连接 AUBO i5，也不发送机器人命令。它只是未来 CoppeliaSim playback、IK dry-run 或低速空跑准备前的保守离线 gate。
