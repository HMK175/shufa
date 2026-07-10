# AUBO i5 IK Feasibility Dry-Run Report

This report is an IK feasibility dry-run. It is not real IK, does not connect to a real robot arm, does not import or call the AUBO SDK, and does not send robot control commands.

It also does not check joint limits, collisions, singular configurations, dynamics, or calibrated AUBO i5 reachability. The radius envelope is only a conservative pre-check hint.

## Outputs

- points_csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\aubo_i5_ik_feasibility_smoothed_points.csv`
- source_target_pose_csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv`
- source_retiming_summary: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json`
- source_retimming_summary: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json`
- source_motion_continuity_after_retiming: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\motion_continuity_after_retiming_summary.json`

When `source_target_pose_kind` is `smoothed`, this report is based on target poses that already passed the conservative motion-continuity after-retiming gate.

## Config

- paper_half_width_m: `0.06`
- paper_half_height_m: `0.06`
- z_range_m: `0.0..0.008`
- max_step_m: `0.015`
- max_speed_m_s: `0.1`
- conservative_radius_envelope_m: `0.0..0.9`

## Summary

| Field | Value |
|---|---|
| `point_count` | `271` |
| `source_csv` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv` |
| `source_target_pose_csv` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv` |
| `source_target_pose_kind` | `smoothed` |
| `source_retiming_summary` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json` |
| `source_retimming_summary` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json` |
| `source_motion_continuity_after_retiming` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\motion_continuity_after_retiming_summary.json` |
| `xy_range_m` | `{"x": [-0.049057, 0.048721], "y": [-0.049392, 0.049392]}` |
| `z_range_m` | `[0.0, 0.0]` |
| `radius_range_m` | `[0.000756, 0.064444]` |
| `max_step_m` | `0.002488` |
| `max_speed_m_s` | `0.01792` |
| `time_monotonic` | `True` |
| `quaternion_normalized` | `True` |
| `has_nan_or_inf` | `False` |
| `required_fields_present` | `True` |
| `within_conservative_envelope` | `True` |
| `recommended_for_real_ik_check` | `True` |
| `warnings` | `[]` |
| `scope` | `AUBO i5 IK feasibility dry-run only; not real IK, not SDK, not robot control` |

Next step before true IK: confirm TCP, base coordinate frame, paper pose, robot IP, emergency stop, workspace safety boundary, tool fixture, speed limits, and on-site supervision.
