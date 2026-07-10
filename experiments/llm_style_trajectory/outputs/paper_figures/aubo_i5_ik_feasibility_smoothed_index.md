# AUBO i5 IK Feasibility Smoothed Index

源任务目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

推荐输入：

```text
robot_target_poses_smoothed.csv
```

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_ik_feasibility_smoothed_summary.json` | 基于 smoothed target poses 的 feasibility summary |
| `aubo_i5_ik_feasibility_smoothed_report.md` | 基于 smoothed target poses 的 feasibility 报告 |
| `target_pose_retiming_summary.json` | 去重、retiming 与时间缩放 summary |
| `motion_continuity_after_retiming_summary.json` | retiming 后 motion-continuity gate 结果 |

关键结果：

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| source_target_pose_csv | `robot_target_poses.csv` | `robot_target_poses_smoothed.csv` |
| point_count | 275 | 271 |
| max_step_m | 0.002488 | 0.002488 |
| max_speed_m_s | 0.04 | 0.01792 |
| radius_range_m | `[0.000756, 0.064444]` | `[0.000756, 0.064444]` |
| time_monotonic | true | true |
| quaternion_normalized | true | true |
| within_conservative_envelope | true | true |
| recommended_for_real_ik_check | true | true |
| warnings | [] | [] |

可写结论：smoothed target poses 在保持相同工作空间范围和保守半径 envelope 的同时，继承 retiming 后更平滑、更严格递增的时间序列。后续进入真实 IK 前的离线 feasibility 检查应优先引用该 smoothed 版本；原始 `robot_target_poses.csv` 仅作为 before-retiming 对照。该层仍不是 AUBO i5 真实 IK，不判断关节限位、碰撞、奇异位形或真实可达性，也不连接 SDK 或实机。
