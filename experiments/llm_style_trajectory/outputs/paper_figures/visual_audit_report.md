# 风格诊断 v2：异常样本定位与人工看图校验包

## 本轮目的

本轮从数据诊断转向人工视觉校验准备：自动挑出最值得人工看图的样本和最需要后续调参的问题。
本轮没有替用户完成视觉判断，也没有调整 style profile 参数。不能只看指标判断最终视觉效果。

## 输入诊断目录

`experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746`

## 候选样本统计

- candidate_count: `18`

| case_type | count |
|---|---:|
| `high_aspect_spread` | 5 |
| `high_lishu_aspect` | 3 |
| `long_xingkai_connector` | 3 |
| `low_aspect_spread` | 3 |
| `representative` | 4 |

## Top Cases

| char | style | case_type | priority | reason |
|---|---|---|---:|---|
| 人 | kaishu | `high_aspect_spread` | 1 | 人 的三风格 aspect_ratio 差异较强，spread=0.621 |
| 人 | lishu | `high_aspect_spread` | 1 | 人 的三风格 aspect_ratio 差异较强，spread=0.621 |
| 人 | xingkai | `high_aspect_spread` | 1 | 人 的三风格 aspect_ratio 差异较强，spread=0.621 |
| 好 | kaishu | `high_aspect_spread` | 1 | 好 的三风格 aspect_ratio 差异较强，spread=0.531 |
| 好 | lishu | `high_aspect_spread` | 1 | 好 的三风格 aspect_ratio 差异较强，spread=0.531 |
| 国 | xingkai | `long_xingkai_connector` | 1 | 行楷 connector_draw_length 较长：810.947 |
| 德 | xingkai | `long_xingkai_connector` | 1 | 行楷 connector_draw_length 较长：878.275 |
| 福 | xingkai | `long_xingkai_connector` | 1 | 行楷 connector_draw_length 较长：886.413 |
| 人 | lishu | `high_lishu_aspect` | 2 | 隶书 aspect_ratio 较高：2.036 |
| 好 | lishu | `high_lishu_aspect` | 2 | 隶书 aspect_ratio 较高：1.745 |

## 问题解释

- lishu 宽扁是否过度：优先看 `high_lishu_aspect` 与 `high_aspect_spread` 样本，判断是否只是横向拉宽。
- xingkai 连接是否过长/不自然：优先看 `long_xingkai_connector` 与 `strong_xingkai_connector` 样本。
- kaishu 是否只是保守但缺少笔画风格：看 `representative` 与 `low_aspect_spread` 中的楷书样本。
- 三风格是否在部分字上肉眼难分：看 `low_aspect_spread` 与 `weak_xingkai_connector` 样本。

## 人工校验说明

本轮只是生成候选包和校验清单，没有替用户完成视觉判断。请打开 `selected_images/` 或 `visual_audit_image_manifest.csv` 中的图，按 `visual_audit_checklist.md` 记录人工反馈。
后续是否调参，应等待人工看图反馈后再决定。

## 下一步建议

- 对每个候选样本标注：可接受 / 连接过长 / 宽扁过度 / 风格难分 / 过于机械。
- 根据标注结果再决定是否重新估计 style profile 中的宽扁、连接、笔画宽度或转折圆滑参数。