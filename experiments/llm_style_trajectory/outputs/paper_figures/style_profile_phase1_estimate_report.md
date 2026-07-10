# Phase 1 font-outline style profile readonly estimator

## 本轮目的

本轮只读输入数据，产出候选 estimates 和报告；不接默认 style profile，不改变 `run_demo.py` 默认行为，本轮不生成新轨迹。

## 输入文件

- font gap dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_style_gap_analysis_20260618_144838`
- `font_style_gap_summary.csv`
- `font_style_gap_style_means.csv`
- `style_profiles.json`

## 输出文件

- estimates: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_phase1_estimates_20260618_152952\style_profile_phase1_estimates.json`
- comparison: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_phase1_estimates_20260618_152952\style_profile_phase1_parameter_comparison.csv`
- warnings: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_phase1_estimates_20260618_152952\style_profile_phase1_estimate_warnings.csv`
- figures: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_phase1_estimates_20260618_152952\figures`

## 估计参数列表

- `horizontal_scale_hint` / `vertical_scale_hint`
- `base_width_hint`
- `stroke_width_distribution`
- `projection_summary`
- `lishu_flatness`

## Current vs Phase 1 关键差异

| style | parameter | current | phase1_hint | delta | confidence |
|---|---|---:|---:|---:|---|
| kaishu | horizontal_scale | 1.0 | 1.0 | 0.0 | medium |
| kaishu | vertical_scale | 1.0 | 1.0 | 0.0 | medium |
| lishu | horizontal_scale | 1.18 | 1.198887 | 0.018887 | medium |
| lishu | vertical_scale | 0.82 | 0.834107 | 0.014107 | medium |
| xingkai | horizontal_scale | 1.03 | 0.979982 | -0.050018 | low |
| xingkai | vertical_scale | 0.98 | 1.020427 | 0.040427 | low |
| kaishu | base_width |  | 6.320909 |  | medium |
| lishu | base_width |  | 8.956169 |  | medium |
| xingkai | base_width |  | 9.575023 |  | medium |

## Lishu 结论

flatness 可以从字体 aspect 统计中给出低风险提示；但当前 lishu 接近字体 aspect 只说明整体宽扁比例接近，真实隶书结构仍需要 component-level / 笔画级数据。

## Xingkai 结论

connectedness 不能直接等价为 connector 数量。connector_trigger、connector_shape 和 connector_width_scale 仍需要人工看图、轨迹数据或执行层反馈。

## 不支持从静态字体估计的参数

- `connection_strength`
- `allow_interstroke_connections`
- `connector_trigger`
- `connector_shape`
- `pressure_curve`
- `speed_scale`
- `pen_up_height`
- `real_robot_dynamics`

## 下一步建议

- 用 phase1 estimates 生成一批非默认对比图。
- 人工看图后再决定是否升级 style profile。
- 先验证全局比例和宽度，再进入 component-level 结构适配。

## 边界

- 字体轮廓不等于真实书写轨迹。
- 静态字体无法给真实速度/压力/抬笔。
- 本轮不生成新轨迹。
- 本轮不接默认，不替换 `style_profiles.json`，不调用 API，不连接 CoppeliaSim/AUBO i5。
