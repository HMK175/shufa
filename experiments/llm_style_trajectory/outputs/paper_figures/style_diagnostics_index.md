# Style Diagnostics Index

源输出目录：

```text
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `style_diagnostic_report.md` | 多字样本风格诊断报告 |
| `style_diagnostic_style_means.csv` | 三种 style 的平均指标 |
| `style_diagnostic_grid.png` | 12 字 x 3 风格 execution render 总览 |
| `style_metric_bars.png` | 风格区分关键指标柱状图 |

样本统计：

| total_samples | success_count | failure_count | missing_char_count |
|---:|---:|---:|---:|
| 54 | 54 | 0 | 0 |

三风格平均指标：

| style | samples | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.018672 | 786.158 | 0.0 | 0.0 | 9.0 | 614.139 | 0 |
| lishu | 18 | 1.465173 | 783.776 | 0.0 | 0.0 | 10.0 | 612.518 | 0 |
| xingkai | 18 | 1.070791 | 1314.104 | 6.056 | 525.944 | 7.488813 | 615.987 | 0 |

关键诊断：

- `lishu` 的平均 `aspect_ratio=1.465173`，明显高于 `kaishu=1.018672` 和 `xingkai=1.070791`，宽扁风格参数在 18 字样本上稳定可见。
- `xingkai` 的平均 `connection_count=6.056`、`connector_draw_length=525.944`，明显高于 kaishu/lishu 的 0，行楷默认弱连接逻辑稳定。
- `kaishu` 与 `lishu` 都保持 `connection_count=0`，说明基础 profile 的“无跨笔连接”约束仍稳定。
- 三种风格 `out_of_bounds_count=0`，说明当前参数化风格在 120mm 纸面映射和重采样层没有越界。
- 当前诊断也暴露参数仍偏粗：宽扁和连接差异清晰，但笔画级宽度、部件级比例、转折圆滑度仍依赖全局参数，下一步应从字体/图像统计中重新估计这些细粒度参数。

边界说明：本实验不是最终风格学习结果。当前 style profile 仍是参数化 profile + 部分字体统计 + prior；本轮目的是诊断稳定性和失败点，不调用 API、CoppeliaSim、AUBO SDK、真实 IK 或任何机器人控制命令。
