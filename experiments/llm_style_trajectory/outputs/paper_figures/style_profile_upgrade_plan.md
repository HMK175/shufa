# Style profile 数据化升级方案设计与参数分层表

## 本轮目的

本轮不是直接替换生成算法，而是基于 font style gap analysis 建立参数分层、数据来源、估计方法和后续实现计划。
本轮不调 connector/taper，不替换默认 style profile，不改变 `run_demo.py` 默认行为。

## 为什么不能继续只靠 MakeMeAHanzi + 全局参数细调

- 当前行楷容易表现为“楷书骨架 + connector”。
- 当前隶书容易表现为“楷书骨架 + 横向拉宽/纵向压扁”。
- stroke taper 是 execution 层的视觉效果，不是真实字体风格来源。
- font gap analysis 已提示：下一步应从字体/图像统计中系统估计风格参数，而不是继续盲调 connector/taper。

## 输入依据

- font gap dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_style_gap_analysis_20260618_144838`
- `font_style_gap_summary.csv`
- `font_style_gap_style_means.csv`
- `style_profiles.json`
- `style_sources.json`
- `execution_refinement_profiles.json`

## 参数分层概览

- total parameters: `23`
- can_estimate_now: `7`
- component: `2`
- process_prior: `11`
- style: `10`

## 实现阶段概览

- phase_1: `7`
- phase_2: `5`
- phase_3: `11`

## 参数来源矩阵

完整表见 `style_profile_parameter_matrix.csv`。核心字段包括：parameter、level、current_source、proposed_source、can_estimate_now、required_inputs、priority、implementation_phase、risk、notes。

## 三阶段升级路线

### Phase 1：现在就能做、风险较低

目标：font-outline-derived global and width parameters。
- `horizontal_scale`
- `vertical_scale`
- `base_width`
- `stroke_width_distribution`
- `horizontal_projection_distribution`
- `vertical_projection_distribution`
- `lishu_flatness`

### Phase 2：中等复杂度，需要设计映射

- `smoothness`
- `corner_rounding`
- `component_width_ratio`
- `component_height_ratio`
- `xingkai_connectedness_prior`

### Phase 3：静态字体难直接估计，需要轨迹或人工反馈

- `speed_scale`
- `connection_strength`
- `allow_interstroke_connections`
- `pen_up_height`
- `stroke_start_width_scale`
- `stroke_mid_width_scale`
- `stroke_end_width_scale`
- `pressure_curve`
- `connector_trigger`
- `connector_shape`
- `connector_width_scale`

## 本轮不要再盲调的参数

- `connector_trigger`
- `connector_shape`
- `connector_width_scale`
- `stroke_start_width_scale`
- `stroke_mid_width_scale`
- `stroke_end_width_scale`

## 不能从静态字体直接估计

- `allow_interstroke_connections`
- `pen_up_height`
- `pressure_curve`
- `real_robot_dynamics`
- `speed_scale`

## Prototype estimates

`prototype_style_profile_estimates.json` 只给出 style-level hints，例如 aspect ratio、stroke width 和 connectedness 的弱提示。
prototype 不接入默认流程，不会被 `run_demo.py` 或当前生成链路读取。
- status: `prototype_not_used_by_default`
- warning: `not wired into generation pipeline`

## 人工看图参与点

- Phase 1 的全局比例和宽度估计需要配合字体网格图、gap 图人工看图确认。
- Phase 2 的 component/char-level 参数必须经过代表样本和异常样本人工校验。
- Phase 3 的 connector/taper/pressure/speed 不应只靠数值表，需要继续保留人工看图和执行层诊断。

## 边界

- 字体轮廓不等于真实书写轨迹。
- 静态字体不能直接给速度、抬笔高度、真实压力或机器人动态控制。
- prototype 不接入默认流程。
- 本轮不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人命令。
