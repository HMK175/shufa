# balanced connector + 行楷局部风格增强实验

## 用户问题回顾

- 当前 conservative connector 太少。
- 行楷仍像“楷书骨架 + 少量连笔 + taper”。
- 当前不适合直接进入仿真书写展示。

## 本轮方法

- 新增 `balanced` connector gate，位于旧 `baseline/all_adjacent` 与 `candidate_default_v1/conservative` 之间。
- 对行楷 connector 使用 `slight_curve` 二次贝塞尔曲线，避免所有连接段都是直线。
- 对行楷使用 `xingkai_expressive_taper`，略增强起收笔宽度/压力变化。
- 不影响 kaishu / lishu；非行楷仍不允许 connector。

## 输出目录

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424`

## 样本统计

- summary rows: `36`
- failures: `0`
- xingkai balanced samples: `8`
- balanced between baseline/conservative count: `8`
- xingkai balanced zero-connector samples: `2`
- kaishu/lishu connector violations: `0`

## baseline / conservative / balanced 指标对比

| char | style | variant | connection_count | connector_draw_length | stroke_width_range | has_curved_connector |
|---|---|---|---:|---:|---:|---|
| 国 | xingkai | baseline | 7 | 810.946 | 0.0 | False |
| 国 | xingkai | conservative | 1 | 106.146 | 3.23 | False |
| 国 | xingkai | balanced | 2 | 150.731 | 4.18 | True |
| 德 | xingkai | baseline | 14 | 878.276 | 0.0 | False |
| 德 | xingkai | conservative | 1 | 45.035 | 3.23 | False |
| 德 | xingkai | balanced | 3 | 123.149 | 4.18 | True |
| 福 | xingkai | baseline | 12 | 886.416 | 0.0 | False |
| 福 | xingkai | conservative | 1 | 96.856 | 3.229996 | False |
| 福 | xingkai | balanced | 1 | 87.219 | 4.179994 | True |
| 和 | xingkai | baseline | 7 | 531.324 | 0.0 | False |
| 和 | xingkai | conservative | 2 | 101.215 | 3.229996 | False |
| 和 | xingkai | balanced | 2 | 102.119 | 4.179995 | True |
| 中 | xingkai | baseline | 3 | 310.785 | 0.0 | False |
| 中 | xingkai | conservative | 0 | 0.0 | 3.229764 | False |
| 中 | xingkai | balanced | 0 | 0.0 | 4.179694 | False |
| 人 | xingkai | baseline | 1 | 131.331 | 0.0 | False |
| 人 | xingkai | conservative | 0 | 0.0 | 3.226268 | False |
| 人 | xingkai | balanced | 0 | 0.0 | 4.175273 | False |
| 明 | xingkai | baseline | 7 | 785.3 | 0.0 | False |
| 明 | xingkai | conservative | 0 | 0.0 | 3.229995 | False |
| 明 | xingkai | balanced | 1 | 77.414 | 4.179994 | True |
| 林 | xingkai | baseline | 7 | 603.738 | 0.0 | False |
| 林 | xingkai | conservative | 0 | 0.0 | 3.229995 | False |
| 林 | xingkai | balanced | 1 | 45.707 | 4.179994 | True |
| 人 | kaishu | baseline | 0 | 0.0 | 0.0 | False |
| 人 | kaishu | conservative | 0 | 0.0 | 3.054751 | False |
| 人 | kaishu | balanced | 0 | 0.0 | 3.054751 | False |
| 人 | lishu | baseline | 0 | 0.0 | 0.0 | False |
| 人 | lishu | conservative | 0 | 0.0 | 3.3998 | False |
| 人 | lishu | balanced | 0 | 0.0 | 3.3998 | False |
| 中 | kaishu | baseline | 0 | 0.0 | 0.0 | False |
| 中 | kaishu | conservative | 0 | 0.0 | 3.059968 | False |
| 中 | kaishu | balanced | 0 | 0.0 | 3.059968 | False |
| 中 | lishu | baseline | 0 | 0.0 | 0.0 | False |
| 中 | lishu | conservative | 0 | 0.0 | 3.399991 | False |
| 中 | lishu | balanced | 0 | 0.0 | 3.399991 | False |

## 初步判断

- balanced 的目标是避免回到全连，同时比 conservative 更少清零；是否真正更有行楷味，需要人工看图确认。
- 对 `中/人/明/林` 等 conservative 清零样本，报告中已标注 balanced 是否仍清零；若仍清零，说明 gate 仍偏保守。
- 楷书/隶书样本作为安全检查，不应产生 connector。

## 人工看图清单

- 国 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u56fd_xingkai.png`；人工看图：确认 balanced 是否比 conservative 更有行楷味，同时没有回到全连。
- 德 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u5fb7_xingkai.png`；人工看图：确认 balanced 是否比 conservative 更有行楷味，同时没有回到全连。
- 福 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u798f_xingkai.png`；人工看图：balanced 未比 conservative 增加 connector，确认是否仍偏保守。
- 和 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u548c_xingkai.png`；人工看图：balanced 未比 conservative 增加 connector，确认是否仍偏保守。
- 中 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4e2d_xingkai.png`；人工看图：balanced 未比 conservative 增加 connector，确认是否仍偏保守。
- 人 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4eba_xingkai.png`；人工看图：balanced 未比 conservative 增加 connector，确认是否仍偏保守。
- 明 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u660e_xingkai.png`；人工看图：确认 balanced 是否比 conservative 更有行楷味，同时没有回到全连。
- 林 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u6797_xingkai.png`；人工看图：确认 balanced 是否比 conservative 更有行楷味，同时没有回到全连。
- 人 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4eba_kaishu.png`；人工看图：确认非行楷仍无 connector，且 expressive 改动没有误作用。
- 人 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4eba_lishu.png`；人工看图：确认非行楷仍无 connector，且 expressive 改动没有误作用。
- 中 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4e2d_kaishu.png`；人工看图：确认非行楷仍无 connector，且 expressive 改动没有误作用。
- 中 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424\figures\compare_connector_levels_u4e2d_lishu.png`；人工看图：确认非行楷仍无 connector，且 expressive 改动没有误作用。

## 边界

- 本轮不是最终行楷模型。
- 本轮不是真实书法学习。
- 本轮不进入仿真书写，不连接 CoppeliaSim / AUBO i5。
- 本轮不调用 API，不调用 SDK，不发送机器人命令。
- 隶书当前仍主要是参数化横向拉宽问题，本轮不解决隶书真实风格来源问题。

## 下一步建议

- 如果 balanced 仍偏少，再稍放宽 gate。
- 如果 balanced 过多，回到 conservative。
- 如果视觉接受，再考虑作为 `candidate_default_v2`，而不是直接替换全局默认。
