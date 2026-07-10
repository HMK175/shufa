# Target Pose Retiming / Smoothing Index

源任务目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `target_pose_retiming_summary.json` | target pose 去重、retiming 与时间缩放 summary |
| `target_pose_retiming_report.md` | before/after 人工可读报告 |
| `motion_continuity_after_retiming_summary.json` | retiming 后复用 motion continuity gate 的 summary |
| `motion_continuity_after_retiming_report.md` | retiming 后连续性检查报告 |

关键结果：

| metric | before | after |
|---|---:|---:|
| point_count | 275 | 271 |
| removed_duplicate_count | 0 | 4 |
| duration_s | 13.0528205 | 22.039876274 |
| dt_nonpositive_count | 4 | 0 |
| max_speed_m_s | 0.04 | 0.01792 |
| max_accel_m_s2 | 0.533536284 | 0.274132141 |
| max_jerk_m_s3 | 11.386446091 | 4.193553547 |
| recommended_for_coppeliasim_playback | false | true |
| recommended_for_ik_dry_run | false | true |

几何保持：

| field | value |
|---|---:|
| geometry_path_length_before_m | 0.359530546527 |
| geometry_path_length_after_m | 0.359530546527 |
| path_length_delta_m | 0.0 |
| iterations_used | 3 |
| final_time_scale | 1.953125 |

可写结论：target pose retiming 层在不改变字形几何路径的前提下，删除 4 个零长度重复点，并通过 segment-aware retiming 与整体时间缩放，使默认 weak 行楷山样例重新通过 conservative motion-continuity gate。该层仍不是 AUBO i5 真实动力学优化，不做真实 IK、不连接 SDK、不发送机器人命令，也不保证关节空间可达。
