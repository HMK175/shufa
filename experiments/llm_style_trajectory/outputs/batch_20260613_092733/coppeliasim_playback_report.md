# CoppeliaSim playback dry-run report

- Batch directory: `experiments\llm_style_trajectory\outputs\batch_20260613_092733`
- CSV files checked: 5
- Out-of-workspace rows: 0
- Max 3D step: 80.2581 mm
- Max XY step: 80.2581 mm
- Max Z step: 8 mm

## Focus: xingkai shan connection ablation

| task_dir | connection | points | max_3d | max_xy | max_z | duration_s | stroke | connector | pen_up |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| u5c71_xingkai_20260613_092733_979792 | none | 258 | 8.0 | 4.749192 | 8.0 | 12.972534 | 237 | 0 | 21 |
| u5c71_xingkai_20260613_092734_183421 | weak | 246 | 43.046802 | 43.046802 | 0.0 | 14.147425 | 237 | 9 | 0 |
| u5c71_xingkai_20260613_092734_359476 | normal | 251 | 35.523756 | 35.523756 | 0.0 | 14.133252 | 237 | 14 | 0 |

## Notes

- This report is dry-run only: no GUI, no CoppeliaSim connection, no robot IK.
- `stroke_count`, `connector_count`, and `pen_up_move_count` are point counts by segment type.
- `max_step_3d_mm`, `max_xy_step_mm`, and `max_z_step_mm` split the playback jump check.
- GUI load during live playback can be reduced with `--display-stride N` or `--no-path-objects`.
