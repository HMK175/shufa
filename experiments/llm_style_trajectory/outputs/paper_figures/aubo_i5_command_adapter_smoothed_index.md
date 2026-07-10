# AUBO i5 Command Adapter Smoothed Index

源任务目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

推荐输入：

```text
robot_target_poses_smoothed.csv
```

对照输入：

```text
robot_target_poses.csv
```

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_command_plan_smoothed.md` | 基于 smoothed target poses 的 dry-run command plan 报告 |
| `aubo_i5_safety_check_smoothed.json` | 基于 smoothed target poses 的 safety check JSON |
| `target_pose_retiming_summary.json` | 去重、retiming 与时间缩放 summary |
| `motion_continuity_after_retiming_summary.json` | retiming 后 motion-continuity gate 结果 |

关键结果：

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| source_target_pose_csv | `robot_target_poses.csv` | `robot_target_poses_smoothed.csv` |
| point_count | 275 | 271 |
| command_count | 277 | 273 |
| max_step_m | 0.002488 | 0.002488 |
| max_speed_m_s | 0.04 | 0.01792 |
| max_accel_m_s2_estimate | 0.0 | 0.080525 |
| recommended_for_sdk_dry_run | true | true |
| warnings | [] | [] |

command type 说明：

| command_type | count |
|---|---:|
| `move_joint_approach` | 1 |
| `move_line` | 271 |
| `move_line_retract` | 1 |

可写结论：原始 `robot_target_poses.csv` 保留为 before-retiming 对照；后续机器人接口准备推荐使用 `robot_target_poses_smoothed.csv`。smoothed command plan 删除了 4 个零长度重复目标点，命令数从 277 降为 273，同时继承 retiming 后已通过 conservative motion-continuity gate 的时间序列。该层仍只是 AUBO i5 SDK dry-run command plan，不做 IK、不连接 SDK 或实机、不调用 `move_joint` / `move_line`，也不发送任何机器人命令。
