# 小论文实验章节初稿骨架

本文实验章节建议围绕“自然语言约束到执行前检查”的完整链条展开。以下内容是草稿/提纲，不是最终论文正文；写作时应继续保持保守表述。

## 1. 实验设置

**使用图表：**

- Figure 1: `fig1_system_pipeline.png`
- 图表包索引：`mini_paper_figure_index.md`

**想证明什么：**

- 系统输入是自然语言任务，输出是可检查的轨迹和执行前 dry-run 结果。
- LLM/mock planner 只做结构化计划，不直接生成 CSV 或轨迹点。
- 轨迹、执行层、工作空间和 robot precheck 均由本地确定性工具生成。

**当前证据：**

- 已形成 planner -> validation -> modifiers -> style profile -> trajectory -> execution -> workspace -> retiming -> precheck 的链路。
- 图表包中已固定系统流程图和后续实验图表。

**不能过度声称：**

- 不能写成端到端真实机器人书写系统已经完成。
- 不能写成 LLM 自动生成机器人轨迹。

## 2. 自然语言 modifier 可控性实验

**使用图表：**

- Figure 2a: `fig2_modifier_control_connection.png`
- Figure 2b: `fig2_modifier_control_shape.png`
- Figure 2c: `fig2_modifier_control_smoothness.png`

**想证明什么：**

- 自然语言中的“不要连笔 / 更连贯 / 宽扁一点 / 更圆滑”等约束能映射为离散 style modifiers。
- modifiers 通过白名单规则影响本地参数，不让 LLM 直接输出任意数值或轨迹点。

**当前证据：**

- 连笔、宽扁、圆滑三类约束已经形成可量化差异。
- connection/shape/smoothness 三组图可作为正文展示。

**不能过度声称：**

- 不能写成模型学会了真实书法风格。
- 隶书宽扁图只能说明整体比例控制，不能证明真实隶书笔画结构。

## 3. 行楷 connector rule 消融实验

**使用图表：**

- Figure 3a: `fig3_xingkai_connector_levels_u56fd.png`
- Figure 3b: `fig3_xingkai_connector_levels_u5fb7.png`
- Figure 3c: `fig3_xingkai_connector_levels_u660e.png`
- 决策文档：`docs/xingkai_balanced_decision.md`

**想证明什么：**

- all-adjacent baseline 容易过度连笔。
- conservative v1 过于保守。
- balanced v2 在二者之间提供一个可接受的折中候选。

**当前证据：**

- baseline connection_count 总和 58，conservative 为 5，balanced 为 10。
- baseline connector_draw_length 总和 4938.116，conservative 为 349.252，balanced 为 586.339。
- 用户反馈认为 balanced 变化不激进，曲线 connector 更像“带过去”，可作为下一轮候选。

**不能过度声称：**

- `candidate_default_v2` 不能写成全局默认。
- balanced connector 是规则生成，不是真实行楷书写学习。
- 仍需要更多样本人工看图评价。

## 4. 执行层 width/pressure 可视化实验

**使用图表：**

- Figure 4: `fig4_execution_width_pressure.png`
- `width_pressure_visualization_index.md`
- `execution_refinement_index.md`

**想证明什么：**

- execution layer 比中心线轨迹包含更丰富的执行状态。
- `width`、`pressure`、`pen_down`、`is_connector` 和 `segment_type` 能支持虚拟书写与机器人前检查。

**当前证据：**

- execution_trajectory.csv 已记录 pressure/width/speed/connector/pen-up 状态。
- stroke taper 和 connector thinner 已能在可视化中体现。

**不能过度声称：**

- 当前不是物理笔刷模型。
- stroke taper 是执行层参数化效果，不是真实毛笔动力学。

## 5. 运动连续性与 retiming 检查

**使用图表：**

- Table 1: `table1_retiming_before_after.md/.csv`
- `motion_continuity_check_index.md`
- `target_pose_retiming_index.md`

**想证明什么：**

- 原始 target poses 可以通过离线检查发现时间和 jerk 风险。
- retiming/smoothing 后，保守 dry-run gate 能重新通过。

**当前证据：**

- `dt_nonpositive_count` 从 4 降为 0。
- `max_accel_m_s2` 从 0.533536284 降为 0.274132141。
- `max_jerk_m_s3` 从 11.386446091 降为 4.193553547。
- `recommended_for_ik_dry_run` 从 false 变为 true。

**不能过度声称：**

- 这不是关节空间轨迹规划。
- 这不保证真实 AUBO i5 动力学可执行。

## 6. 机器人接口前检查 dry-run

**使用图表：**

- Table 2: `table2_robot_precheck_summary.md/.csv`
- `coppeliasim_tool_model_index.md`
- `aubo_i5_command_adapter_smoothed_index.md`
- `aubo_i5_ik_feasibility_smoothed_index.md`

**想证明什么：**

- 系统已不止输出 2D 图，还能进入 workspace、CoppeliaSim pen-tip/tool 可视化、AUBO command adapter 和 IK feasibility dry-run 的前检查链条。
- 这些层可以在不连接实机的情况下发现格式、边界和连续性问题。

**当前证据：**

- workspace / CoppeliaSim / command adapter / IK feasibility 已有固定 dry-run 结果。
- smoothed target poses 是后续机器人接口准备推荐输入。

**不能过度声称：**

- 不能写真实 AUBO i5 实验完成。
- 不能写真实 IK、碰撞检测、关节限位或动力学仿真已经完成。

## 7. 与已有方法的功能性对比

**使用图表：**

- Table 3: `table3_external_functional_comparison.md/.csv`

**想证明什么：**

- 本文方法的特点是自然语言入口、可解释 modifiers、execution trajectory、retiming/motion gate 和 robot-interface dry-run 的组合。
- 该组合与传统骨架提取、示教轨迹学习、RL 局部优化和字体/图像风格迁移路线有功能侧重点差异。

**当前证据：**

- 表格只列功能维度，不列外部方法数值。

**不能过度声称：**

- 不能把该表写成性能优于外部方法的数值证明。
- 不能在没有复现实验的情况下宣称准确率、误差或效率优势。

## 8. 局限性与未来工作

**使用图表：**

- supplementary figures:
  - `supplementary/supp_font_style_grid.png`
  - `supplementary/supp_font_vs_trajectory_aspect_ratio.png`
  - `supplementary/supp_lishu_flatness_gap.png`
  - `supplementary/supp_phase1_current_vs_scale.png`
- `style_profile_phase1_estimates_index.md`
- `phase1_profile_comparison_index.md`

**想说明什么：**

- 当前风格变化仍然是参数化控制。
- 隶书仍可能偏“压扁楷书”。
- 行楷 connector 是规则生成，不是真实书写学习。
- 字体轮廓只能支持部分全局形态估计，真实风格学习需要 component/stroke-level 数据化。

**当前证据：**

- font gap analysis 和 Phase 1 readonly estimates 已经指出全局比例改进空间有限。
- connector/taper/pressure/speed/pen-up 仍不能从静态字体直接可靠估计。

**不能过度声称：**

- 不能写 style profile 已经由真实字体完整学习得到。
- 不能写 Phase 1 estimates 已经替换默认 style profile。

## 章节写作优先级

1. 先完成第 1-4 节，构成方法核心和主要视觉证据。
2. 再写第 5-6 节，展示执行前检查链条。
3. 第 7 节只做功能性对比，不做数值竞赛。
4. 第 8 节要主动承认边界，避免把参数化控制包装成真实风格学习。
