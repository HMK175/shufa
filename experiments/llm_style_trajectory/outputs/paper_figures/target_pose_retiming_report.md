# Target Pose Retiming Report

Scope: offline target-pose retiming only. This is not real robot dynamics optimization, not joint-space planning, not IK, and not AUBO i5 control.

- source_csv: `experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses.csv`
- smoothed_csv: `experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses_smoothed.csv`

## Before / After

| metric | before | after |
|---|---:|---:|
| `point_count` | `275` | `271` |
| `duration_s` | `13.0528205` | `22.039876274` |
| `dt_nonpositive_count` | `4` | `0` |
| `max_speed_m_s` | `0.04` | `0.01792` |
| `max_accel_m_s2` | `0.533536284` | `0.274132141` |
| `max_jerk_m_s3` | `11.386446091` | `4.193553547` |
| `recommended_for_coppeliasim_playback` | `False` | `True` |
| `recommended_for_ik_dry_run` | `False` | `True` |

## Retiming Summary

| field | value |
|---|---|
| `original_point_count` | `275` |
| `retimed_point_count` | `271` |
| `removed_duplicate_count` | `4` |
| `geometry_path_length_before_m` | `0.359530546527` |
| `geometry_path_length_after_m` | `0.359530546527` |
| `path_length_delta_m` | `0.0` |
| `iterations_used` | `3` |
| `final_time_scale` | `1.953125` |
| `retiming_success` | `True` |
| `failure_reasons` | `[]` |

Only adjacent static duplicate points may be removed. The remaining `X_m/Y_m/Z_m` coordinates and quaternion fields are preserved; this layer rewrites time and speed fields only.
