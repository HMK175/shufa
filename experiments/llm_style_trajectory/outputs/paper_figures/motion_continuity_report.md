# Motion Continuity Dry-Run Report

Scope: motion continuity dry-run only; not real robot dynamics, not IK, not joint-space velocity/acceleration/torque checking, and not real robot control.

- input: `experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_target_poses.csv`
- input_kind: `target_pose`
- time_source: `provided`

## Summary

| Field | Value |
|---|---|
| `point_count` | `275` |
| `duration_s` | `13.0528205` |
| `path_length_m` | `0.359530547` |
| `dt_min_s` | `0.0` |
| `dt_max_s` | `0.075515783` |
| `dt_mean_s` | `0.047638031` |
| `dt_nonpositive_count` | `4` |
| `max_step_3d_m` | `0.002487672` |
| `max_speed_m_s` | `0.04` |
| `max_speed_jump_m_s` | `0.025` |
| `max_accel_m_s2` | `0.533536284` |
| `max_jerk_m_s3` | `11.386446091` |
| `jerk_peak_count` | `6` |
| `quaternion_norm_min` | `1.0` |
| `quaternion_norm_max` | `1.0` |
| `quaternion_normalized` | `True` |
| `orientation_fixed_or_smooth` | `True` |
| `segment_counts` | `{"connector": 38, "stroke": 237}` |
| `segment_stats` | `{"connector": {"max_accel_m_s2": 0.247804265, "max_jerk_m_s3": 4.093798811, "max_speed_m_s": 0.04, "point_count": 38}, "stroke": {"max_accel_m_s2": 0.533536284, "max_jerk_m_s3": 11.386446091, "max_speed_m_s": 0.04, "point_count": 237}}` |
| `recommended_for_coppeliasim_playback` | `False` |
| `recommended_for_ik_dry_run` | `False` |
| `warnings` | `[]` |
| `failure_reasons` | `["time is not strictly increasing or contains dt <= 0", "max_accel_m_s2 0.533536 exceeds threshold 0.500000", "max_jerk_m_s3 11.386446 exceeds threshold 5.000000"]` |

## Boundary

These thresholds are conservative dry-run gates for simulation and future IK preparation. They are not claimed to be real AUBO i5 controller limits. This report does not check joint-space velocity, joint acceleration, torque, collision, singularity, or true reachability.
