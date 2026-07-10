# Execution Refinement Experiment

## 用户问题回顾

- connector 过多：旧执行层在行楷允许连接时容易把所有相邻笔画首尾依次相连。
- stroke 内部粗细恒定：上一轮 width/pressure 渐变图显示 16 个样本的 stroke width nearly constant。
- 浅色接近白底看不清：旧渐变图的浅色端对 connector 不够友好。
- lishu 横向拉宽问题本轮暂不解决，只记录为后续真实风格来源问题。

## 本轮改动

- conservative connector gate：用距离、角度和 connect_every_n 收紧行楷 connector 触发。
- simple stroke taper：只对 stroke 段施加起笔 / 中段 / 收笔 width 和 pressure 曲线。
- non-white light color visualization：浅色端改为可见浅蓝和棕灰，背景为浅暖灰。
- connector gate 参数：`{"connect_every_n": 2, "max_connector_distance_abs": 160.0, "max_connector_distance_ratio": 0.45, "max_turn_angle_deg": 150.0, "min_stroke_endpoint_distance": 5.0, "mode": "distance_angle_gate", "skip_if_crosses_bbox_center": false}`。
- `skip_if_crosses_bbox_center` 已在代码中实现，但本轮实验配置为 false；在当前样本上开启它会让 connector 几乎清零，不利于人工比较。

本轮不是最终参数，本轮不是真实笔刷模型，本轮颜色只为可读性；仍需人工看图确认。

## 人工反馈归档

用户人工看图反馈：

- 行楷连笔确实变自然了，但现在基本只有一两笔连笔，略显偏少；暂时先接受。
- stroke 粗细变化可以看出来，效果不错。
- 隶书一共两张图，没有出现连笔。
- `人/lishu connector_draw_length: 0.0 -> 3.3998` 看起来可疑，需要核查。

本轮决策：将当前 `conservative connector + simple_taper` 标记为 `candidate_default_v1`，但暂不作为全局默认。后续可以设计介于当前 conservative 和旧 all-adjacent 之间的 `balanced` connector 档位；本轮不继续调参数。

## 可疑字段核查

核查 `人/lishu` refined execution：

- `segment_type=connector` 行数：0。
- `is_connector=1` 行数：0。
- summary 中 `before_connector_draw_length = 0.0`。
- summary 中 `after_connector_draw_length = 0.0`。
- summary 中 `after_stroke_width_range = 3.3998`。

结论：`3.3998` 是 `after_stroke_width_range`，不是 connector_draw_length。当前 summary/report 字段未发现错位，lishu 没有误连笔。

## 输出目录

`experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837`

## 可视化颜色设置

- background_color: `#f7f7f2`
- stroke_light_color: `#6baed6`
- connector_light_color: `#b07d62`
- stroke_light_distance_from_white: `0.680886`
- connector_light_distance_from_white: `0.857291`
- min_alpha: `0.55`
- min_visible_linewidth: `1.2`

## 总体 before/after

- sample_count: `8`
- style_counts: `{'xingkai': 6, 'kaishu': 1, 'lishu': 1}`
- total_connection_count_before/after: `44` / `5`

## 指标表

| char | style | conn before | conn after | connector length before | connector length after | stroke width range before | stroke width range after | figure |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 国 | xingkai | 7 | 1 | 810.946 | 106.146 | 0.0 | 3.23 | `before_after_connector_u56fd_xingkai.png` |
| 德 | xingkai | 14 | 1 | 878.276 | 45.035 | 0.0 | 3.23 | `before_after_connector_u5fb7_xingkai.png` |
| 福 | xingkai | 12 | 1 | 886.416 | 96.856 | 0.0 | 3.229996 | `before_after_connector_u798f_xingkai.png` |
| 人 | xingkai | 1 | 0 | 131.331 | 0.0 | 0.0 | 3.226268 | `before_after_connector_u4eba_xingkai.png` |
| 中 | xingkai | 3 | 0 | 310.785 | 0.0 | 0.0 | 3.229764 | `before_after_connector_u4e2d_xingkai.png` |
| 和 | xingkai | 7 | 2 | 531.324 | 101.215 | 0.0 | 3.229996 | `before_after_connector_u548c_xingkai.png` |
| 人 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.054751 | `before_after_connector_u4eba_kaishu.png` |
| 人 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.3998 | `before_after_connector_u4eba_lishu.png` |

## 需要人工看图的图

- 国 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u56fd_xingkai.png`
- 国 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u56fd_xingkai.png`
- 德 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u5fb7_xingkai.png`
- 德 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u5fb7_xingkai.png`
- 福 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u798f_xingkai.png`
- 福 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u798f_xingkai.png`
- 人 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u4eba_xingkai.png`
- 人 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u4eba_xingkai.png`
- 中 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u4e2d_xingkai.png`
- 中 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u4e2d_xingkai.png`
- 和 / xingkai: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u548c_xingkai.png`
- 和 / xingkai width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\width_pressure_refined_u548c_xingkai.png`
- 人 / kaishu: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u4eba_kaishu.png`
- 人 / kaishu width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\stroke_taper_u4eba_kaishu.png`
- 人 / lishu: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\before_after_connector_u4eba_lishu.png`
- 人 / lishu width/pressure: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837\figures\stroke_taper_u4eba_lishu.png`

## 初步结论

- 如果 after connector 数量下降，说明 conservative gate 已经减轻“每笔必连”的问题。
- 如果 after stroke width range 大于 before，说明 simple taper 已经让 stroke 内部粗细可见变化进入执行层。
- connector 是否自然、stroke taper 是否像书写效果，仍必须人工看图判断；不能只看指标。

## 边界

- 本轮不是最终行楷规则。
- 本轮不是真实笔刷模型。
- 本轮不解决 lishu 的真实风格来源问题。
- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。
