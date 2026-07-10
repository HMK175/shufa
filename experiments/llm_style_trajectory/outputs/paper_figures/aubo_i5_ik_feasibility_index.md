# AUBO i5 IK Feasibility Dry-Run Index

Source task:

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

Fixed files:

| File | Content |
|---|---|
| `aubo_i5_ik_feasibility_summary.json` | IK feasibility dry-run summary |
| `aubo_i5_ik_feasibility_report.md` | Human-readable feasibility report |
| `aubo_i5_ik_feasibility_points.csv` | Per-target pose feasibility flags |

Key result:

| point_count | max_step_m | max_speed_m_s | radius_range_m | recommended_for_real_ik_check | warnings |
|---:|---:|---:|---|---|---|
| 275 | 0.002488 | 0.04 | `[0.000756, 0.064444]` | true | [] |

Scope:

- offline feasibility dry-run only;
- not real AUBO i5 IK;
- no SDK import;
- no robot connection;
- no real command execution;
- no joint-limit, collision, singularity, or calibrated reachability check.
