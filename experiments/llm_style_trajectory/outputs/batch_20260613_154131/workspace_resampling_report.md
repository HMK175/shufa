# Workspace Resampling Report

- tasks: `5`
- out_of_bounds_count: `0`

| task | segment_counts | original_max_step_mm | resampled_max_step_mm | stroke_max_step_mm | connector_max_step_mm | pen_up_move_max_step_mm | estimated_duration_s |
|---|---|---:|---:|---:|---:|---:|---:|
| 写一个不要连笔的行楷山 | `{"pen_up_move": 2, "stroke": 3}` | 52.241 | 4.749 | 1.888 | 0.0 | 4.749 | 12.103962 |
| 写一个行楷风格的山 | `{"connector": 2, "stroke": 3}` | 52.241 | 2.488 | 1.888 | 2.488 | 0.0 | 13.05282 |
| 写一个更连贯的行楷山 | `{"connector": 2, "stroke": 3}` | 52.241 | 2.488 | 1.888 | 2.488 | 0.0 | 13.606321 |
| 写一个更保守的行楷永 | `{"pen_up_move": 4, "stroke": 5}` | 97.4 | 4.87 | 1.903 | 0.0 | 4.87 | 14.885315 |
| 写一个更圆滑的行楷永 | `{"connector": 4, "stroke": 5}` | 97.4 | 2.497 | 1.989 | 2.497 | 0.0 | 16.786986 |
