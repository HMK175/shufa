# AUBO i5 Command Adapter Dry-Run Plan

This is an offline AUBO i5 command adapter dry-run.

It does not run IK, does not connect to a real AUBO i5, does not import or execute `libpyauboi5`, and does not call `move_joint` or `move_line`. The command rows are a future SDK-call plan only.

Historical AUBO IP addresses, ports, and SDK paths are documentation clues only. They are not defaults and are not used by this script.

## Outputs

- command_plan_csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\aubo_i5_command_plan_smoothed.csv`
- safety_check_json: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\aubo_i5_safety_check_smoothed.json`
- source_target_pose_csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv`
- source_retiming_summary: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json`
- source_retimming_summary: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json`
- source_motion_continuity_after_retiming: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\motion_continuity_after_retiming_summary.json`

This result is based on the listed target-pose CSV. When `source_target_pose_kind` is `smoothed`, it uses target poses that already passed the conservative motion-continuity after-retiming gate.

## Future SDK Hints

- `move_joint_approach`: future adapter may call `inverse_kin` followed by `move_joint`.
- `move_line`: future adapter may call `move_line` for target-pose following.
- `move_line_retract`: future adapter may call `move_line` to leave the paper safely.

## Safety Summary

| Field | Value |
|---|---|
| `point_count` | `271` |
| `command_count` | `273` |
| `max_step_m` | `0.002488` |
| `max_speed_m_s` | `0.01792` |
| `max_accel_m_s2_estimate` | `0.080525` |
| `xy_range_m` | `{"x": [-0.049057, 0.048721], "y": [-0.049392, 0.049392]}` |
| `z_range_m` | `[0.0, 0.0]` |
| `quaternion_normalized` | `True` |
| `time_monotonic` | `True` |
| `has_nan_or_inf` | `False` |
| `recommended_for_sdk_dry_run` | `True` |
| `source_target_pose_csv` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv` |
| `source_target_pose_kind` | `smoothed` |
| `source_retiming_summary` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json` |
| `source_retimming_summary` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\target_pose_retiming_summary.json` |
| `source_motion_continuity_after_retiming` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\motion_continuity_after_retiming_summary.json` |
| `warnings` | `[]` |
| `scope` | `AUBO i5 dry-run command plan only; no IK, no SDK import, no connection, no real robot control` |

Before any real AUBO i5 experiment, confirm robot IP, emergency stop, tool TCP, fixture, paper coordinate frame, speed and acceleration limits, reachability, collision margins, and on-site safety.

Dry-run thresholds: max_step_m <= `0.015`, max_speed_m_s <= `0.1`, max_accel_m_s2 <= `0.5`.
