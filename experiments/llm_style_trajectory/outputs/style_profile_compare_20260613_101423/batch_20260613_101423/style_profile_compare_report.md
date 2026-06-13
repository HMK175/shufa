# 三字体基础风格对比实验

## 实验目的

固定同一批汉字，对比 `kaishu`、`xingkai`、`lishu` 三种基础 style profile 在 trajectory、execution、workspace 三层上的参数化效果差异。

## 输出目录

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_compare_20260613_101423\batch_20260613_101423`

## 每字三风格生成状态

| char | kaishu | xingkai | lishu |
|---|---|---|---|
| 山 | ok | ok | ok |
| 中 | ok | ok | ok |
| 永 | ok | ok | ok |
| 福 | ok | ok | ok |
| 明 | ok | ok | ok |

## 三种风格平均指标

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 0.920111 | 772.899 | 0.0 | 0.0 | 9.0 | 602.907 | 0 |
| xingkai | 0.96655 | 863.159 | 5.6 | 90.279 | 8.991667 | 404.606 | 0 |
| lishu | 1.322317 | 758.556 | 0.0 | 0.0 | 10.0 | 588.24 | 0 |

## 观察结论

- `lishu` 的 `aspect_ratio` 平均值最高，说明当前参数化 profile 的宽扁倾向能够在几何指标上体现。
- `xingkai` 默认允许弱连接，因此更容易出现 connector，`connector_draw_length` 与 `connection_count` 高于 kaishu / lishu。
- `kaishu` 保持无跨笔连接，整体更保守，适合作为结构轨迹的基准风格。

## 边界说明

当前比较的是参数化 style profile 的效果，不是完整真实书法风格学习。LLM/mock planner 只输出结构化计划，CSV 和所有轨迹点仍由本地确定性工具生成。
