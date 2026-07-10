# 多字样本风格区分度与参数诊断实验

## 实验目的

扩充多字样本，诊断当前 `kaishu` / `xingkai` / `lishu` 参数化 style profile 与受控 modifier 在更多结构汉字上的稳定性和可区分性。

## 输出目录

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746`

## 总览

- total_samples: `54`
- success_count: `54`
- failure_count: `0`
- missing_char_count: `0`

## 三风格平均指标

| style | samples | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.018672 | 786.158 | 0.0 | 0.0 | 9.0 | 614.139 | 0 |
| lishu | 18 | 1.465173 | 783.776 | 0.0 | 0.0 | 10.0 | 612.518 | 0 |
| xingkai | 18 | 1.070791 | 1314.104 | 6.056 | 525.944 | 7.488813 | 615.987 | 0 |

## 诊断结论

- `lishu` 是否更宽扁主要看 `aspect_ratio / bbox_width / bbox_height`；若平均 `aspect_ratio` 明显高于 kaishu/xingkai，则当前宽扁参数仍有效。
- `xingkai` 是否更连贯主要看 `connection_count / connector_draw_length`；若这些指标高于 kaishu/lishu，则默认弱连接逻辑仍稳定。
- `kaishu` 的保守性主要看 `connection_count` 低和 connector 指标接近 0。

## 失败与异常案例

- 无失败样本。

## 风格差异不明显提示

- 未发现简单阈值下的明显不稳定提示。

## 参数诊断建议

- 当前较有效参数：`horizontal_scale / vertical_scale`、`allow_interstroke_connections`、`connection_strength`、execution 层 `width / pressure`。
- 当前较粗参数：全字统一缩放和平滑，难以表达部件级、笔画级差异。
- 下一步应优先从字体/图像统计中重新估计：笔画级宽度分布、部件级横纵比例、起收笔宽度变化、转折圆滑度和风格相关 connector 规则。

## 边界说明

这不是最终风格学习结果。当前 style profile 仍是参数化 profile + 部分字体统计 + prior；本轮目的是诊断稳定性和失败点，不追求最终书写效果。没有调用 API、CoppeliaSim、AUBO SDK、真实 IK 或任何机器人控制命令。
