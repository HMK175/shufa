# CoppeliaSim playback dry-run report

- Batch directory: `experiments\llm_style_trajectory\outputs\batch_20260613_154131`
- CSV files checked: 5
- Out-of-workspace rows: 0
- Max 3D step: 8 mm
- Max XY step: 4.87001 mm
- Max Z step: 8 mm

## Focus: xingkai shan connection ablation

| task_dir | connection | points | max_3d | max_xy | max_z | duration_s | stroke | connector | pen_up |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| u5c71_xingkai_20260613_154131_804149 | none | 258 | 8.0 | 4.749192 | 8.0 | 12.972534 | 237 | 0 | 21 |
| u5c71_xingkai_20260613_154132_009898 | weak | 275 | 2.487672 | 2.487672 | 0.0 | 13.05282 | 237 | 38 | 0 |
| u5c71_xingkai_20260613_154132_190216 | normal | 275 | 2.487672 | 2.487672 | 0.0 | 13.606321 | 237 | 38 | 0 |

## Notes

- This report is dry-run only: no GUI, no CoppeliaSim connection, no robot IK.
- `stroke_count`, `connector_count`, and `pen_up_move_count` are point counts by segment type.
- `max_step_3d_mm`, `max_xy_step_mm`, and `max_z_step_mm` split the playback jump check.
- GUI load during live playback can be reduced with `--display-stride N` or `--no-path-objects`.
