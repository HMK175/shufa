# Execution Ablation: Xingkai 山

Source batch: `experiments/llm_style_trajectory/outputs/batch_20260613_154131/`

| task | connection_preference | connection_strength | connector_draw_length | pen_up_move_length | connector_mean_pressure | connector_mean_width | mean_width | mean_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 写一个不要连笔的行楷山 | none | 0.000 | 0.000 | 188.929 | 0.000 | 0.000 | 9.500000 | 1.000000 |
| 写一个行楷风格的山 | weak | 0.176 | 188.929 | 0.000 | 0.338 | 4.244600 | 8.205479 | 0.836935 |
| 写一个更连贯的行楷山 | normal | 0.320 | 188.929 | 0.000 | 0.678 | 6.897000 | 8.858823 | 0.920684 |

说明：修复后，`weak` 和 `normal` 的 connector 几何都完整连接上一笔终点和下一笔起点，不再用 `connection_strength` 截断连接路径。`connection_strength` 只影响连接段的 `pressure`、`width` 和速度等执行属性。因此，二维 execution layer 的差异不再表现为“连到一半/连得更远”，而是表现为低压细连接与更高压力、更宽连接之间的执行差异。
