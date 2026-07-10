# 小论文实验对比方案与可执行实验清单

## 建议论文主线

建议题目：

```text
自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法
```

本文适合强调的是“自然语言约束 -> 可解释 style modifiers -> 参数化轨迹 -> execution/workspace/robot dry-run 检查”的完整方法链条。当前不应声称已经完成真实书法风格学习、真实机器人书写、图像到轨迹的风格迁移，或 AUBO i5 真实 IK/实机验证。

## 核心论点边界

- 本方法是参数化控制和执行前检查方法，不是真实书法风格学习模型。
- 基础骨架来自 Make Me a Hanzi median strokes，因此真实风格上限受 median stroke 数据限制。
- 字体轮廓统计只能支持部分全局形态和宽度提示，不能直接提供真实书写轨迹、速度、压力、抬笔高度或机器人动力学参数。
- CoppeliaSim 与 AUBO i5 相关输出目前均为 dry-run 或 pen-tip/tool visual sanity check，不是实机控制结果。
- 数值指标只作为辅助证据。轨迹图、渲染图、风格对比图仍需要人工看图校验。

## 实验组总览

| 组别 | 实验名称 | 对照基线 | 本方法/候选方法 | 核心指标 | 当前状态 |
|---|---|---|---|---|---|
| A | 自然语言 modifier 可控性 | fixed profile / no modifier | modifier-controlled profile | connection_count, connector_draw_length, aspect_ratio, turning/smoothness, stroke_width_range | 部分已有 |
| B | 行楷 connector rule 对比 | all_adjacent baseline | candidate_default_v1 / candidate_default_v2 | connection_count, connector_draw_length, 人工 connector 自然度 | 已有，需人工反馈补表 |
| C | execution width / pressure 对比 | fixed width / flat pressure | simple_taper / xingkai_expressive_taper | stroke_width_range, connector_mean_width, connector_mean_pressure, 粗细可见性 | 已有 |
| D | motion continuity 与 retiming | raw target poses | smoothed target poses | dt_nonpositive_count, max_speed, max_accel, max_jerk, recommended_for_ik_dry_run | 已有 |
| E | robot-interface precheck chain | 仅 2D trajectory | execution -> workspace -> retiming -> command plan -> IK feasibility dry-run | out_of_bounds, max_step, recommended_for_sdk_dry_run, recommended_for_real_ik_check | 已有 |
| F | font outline gap / style profile 数据化 | current profile | Phase 1 readonly estimates / comparison-only profile | font_aspect vs trajectory_aspect, aspect gap, component count, unsupported parameters | 分析已有，适合放方法限制 |

## A. 自然语言 modifier 可控性

**目的：** 证明自然语言中的“不要连笔 / 更连贯 / 宽扁一点 / 更圆滑 / 更保守”等约束，不直接生成轨迹点，而是通过离散 `style_modifiers` 影响本地白名单参数映射。

**对照：**

- baseline: fixed profile / no modifier
- ours: modifier-controlled profile

**建议指标：**

- `connection_count`
- `connector_draw_length`
- `aspect_ratio`
- `bbox_width` / `bbox_height`
- `mean_turning` / `total_turning_angle` / `max_turning_angle`
- `stroke_width_range`

**已有资料：**

- modifier connection/shape/smoothness ablation 输出
- execution ablation 与 paper figures 中对应图

**论文写法：** 该实验支撑“自然语言约束有效性”，但要说明约束效果来自可解释白名单映射，而不是 LLM 直接生成 CSV 或轨迹点。

## B. 行楷 connector rule 对比

**目的：** 证明行楷连笔不是越多越好；从 all-adjacent baseline 到 conservative，再到 balanced，可以形成可解释的候选执行层。

**对照：**

- baseline: all_adjacent
- candidate_default_v1: conservative connector + simple_taper
- candidate_default_v2: balanced connector + slight_curve + xingkai_expressive_taper

**关键已有指标：**

| metric | baseline | conservative v1 | balanced v2 |
|---|---:|---:|---:|
| xingkai connection_count sum | 58 | 5 | 10 |
| xingkai connector_draw_length sum | 4938.116 | 349.252 | 586.339 |
| kaishu/lishu connector violations | 0 | 0 | 0 |

**人工反馈摘要：**

- v1: connector 更自然但偏保守，stroke taper 可见，lishu 未观察到误连笔。
- v2: 每个字基本只多一笔连笔，变化不激进；`福` 的连笔数量仍为 1 但位置变化；曲线 connector 更像“带过去”；当前可接受但不直接进入仿真书写。

**已有资料：**

- `experiments/llm_style_trajectory/docs/execution_refinement_decision.md`
- `experiments/llm_style_trajectory/docs/xingkai_balanced_decision.md`
- `experiments/llm_style_trajectory/outputs/xingkai_balanced_experiment_20260618_141424/`
- `experiments/llm_style_trajectory/outputs/paper_figures/xingkai_balanced_experiment_index.md`

## C. execution width / pressure 对比

**目的：** 说明 execution layer 比中心线轨迹更能表达书写执行状态，包括宽度、压力、connector 强弱和 pen-up move。

**对照：**

- baseline: fixed width / flat pressure
- ours: simple_taper / xingkai_expressive_taper

**建议指标：**

- `stroke_width_range`
- `mean_width`
- `mean_pressure`
- `connector_mean_width`
- `connector_mean_pressure`
- `connector_draw_length`

**已有资料：**

- `experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md`
- `experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/`

**论文写法：** 强调 execution_trajectory.csv 是为虚拟书写和后续机器人仿真准备的执行层，不破坏旧 `trajectory.csv` 中心线格式。

## D. motion continuity 与 retiming

**目的：** 证明从 raw target poses 到 smoothed target poses 后，时间单调性、加速度和 jerk 的保守 dry-run gate 得到修复。

**对照：**

- baseline: raw `robot_target_poses.csv`
- ours: `robot_target_poses_smoothed.csv`

**已有关键结果：**

| metric | raw target poses | smoothed target poses |
|---|---:|---:|
| dt_nonpositive_count | 4 | 0 |
| max_accel_m_s2 | 0.533536284 | 0.274132141 |
| max_jerk_m_s3 | 11.386446091 | 4.193553547 |
| recommended_for_coppeliasim_playback | false | true |
| recommended_for_ik_dry_run | false | true |

**已有资料：**

- `experiments/llm_style_trajectory/docs/motion_continuity_check_notes.md`
- `experiments/llm_style_trajectory/docs/target_pose_retiming_notes.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md`

## E. robot-interface precheck chain

**目的：** 展示方法不是停在 2D 图像或中心线，而是形成了进入机器人接口前的离线检查链条。

**对照：**

- baseline: only 2D trajectory
- ours: execution -> workspace mapping -> resampling -> target poses -> retiming -> AUBO command plan dry-run -> IK feasibility dry-run

**建议指标：**

- `out_of_bounds`
- `max_step_mm` / `max_xy_step_mm` / `max_z_step_mm`
- `recommended_for_sdk_dry_run`
- `recommended_for_real_ik_check`
- `warnings`

**已有资料：**

- `experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md`

**论文写法：** 只能写“执行前检查”和“dry-run 适配层”，不能写成真实 IK、真实 AUBO i5 控制或真实机器人书写。

## F. font outline gap / style profile 数据化

**目的：** 说明当前 style profile 的风格真实性上限，并为后续数据化升级提供证据。

**对照：**

- baseline: current profile
- analysis: font style gap / Phase 1 readonly estimates / comparison-only profile

**建议指标：**

- `font_aspect`
- `trajectory_aspect`
- `aspect_gap`
- component count / contour count
- unsupported parameter list

**已有资料：**

- `experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/style_profile_upgrade_plan_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md`

**论文写法：** 更适合作为“方法限制与后续工作”或“profile 数据化诊断”，不建议作为主结果强行宣称风格学习成功。

## 外部方法功能对比表

该表只做功能性比较，不编造外部方法的数值结果。

| 方法类型 | 需要示教数据 | 支持自然语言输入 | 支持可解释 modifiers | 输出 execution trajectory | workspace mapping | retiming / motion gate | robot dry-run | 风格真实性上限 | 实现复杂度 / 数据依赖 |
|---|---|---|---|---|---|---|---|---|---|
| 传统图像骨架提取 | 否 | 否 | 否 | 通常否 | 通常否 | 否 | 否 | 受输入图像和骨架质量限制 | 中等，依赖图像处理 |
| 示教轨迹学习 | 是 | 否 | 通常否 | 是 | 可扩展 | 可扩展 | 可扩展 | 受示教数据覆盖范围限制 | 高，依赖采集轨迹 |
| 强化学习局部优化 | 可选 | 否 | 通常否 | 可输出 | 可扩展 | 需额外设计 | 可扩展 | 受奖励函数和初始轨迹限制 | 高，调参和训练成本高 |
| 字体/图像风格迁移 | 否或弱 | 否 | 通常否 | 通常否 | 否 | 否 | 否 | 静态视觉风格强，书写过程弱 | 中高，依赖图像/字体数据 |
| 本方法 | 否 | 是 | 是 | 是 | 是 | 是 | dry-run | 受 Make Me a Hanzi median 与参数化 profile 限制 | 中等，依赖本地数据和规则映射 |

## 现有结果路径索引

| 方向 | 固定入口 |
|---|---|
| modifier / execution / workspace 早期图表 | `experiments/llm_style_trajectory/outputs/paper_figures/` |
| style diagnostics | `experiments/llm_style_trajectory/outputs/paper_figures/style_diagnostics_index.md` |
| visual audit | `experiments/llm_style_trajectory/outputs/paper_figures/style_visual_audit_index.md` |
| connector / brush visual diagnostics | `experiments/llm_style_trajectory/outputs/paper_figures/connector_brush_visual_diagnostics_index.md` |
| width / pressure visualization | `experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md` |
| execution refinement v1 | `experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md` |
| xingkai balanced v2 | `experiments/llm_style_trajectory/outputs/paper_figures/xingkai_balanced_experiment_index.md` |
| motion continuity | `experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md` |
| target pose retiming | `experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md` |
| CoppeliaSim tool model | `experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md` |
| AUBO command adapter smoothed | `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md` |
| AUBO IK feasibility smoothed | `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md` |
| font style gap | `experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md` |
| style profile upgrade plan | `experiments/llm_style_trajectory/outputs/paper_figures/style_profile_upgrade_plan_index.md` |
| Phase 1 estimates | `experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md` |
| Phase 1 comparison | `experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md` |

## 最小可执行论文实验清单

1. 整理 modifier connection / shape / smoothness 三组图，形成“自然语言约束有效性”主图。
2. 整理 xingkai baseline / conservative / balanced 对比图和人工反馈表，形成“连笔规则 ablation”主图。
3. 整理 width / pressure 与 execution refinement 图，形成“执行层比中心线更丰富”的证据。
4. 整理 raw target poses vs smoothed target poses 表，形成“motion continuity gate 修复”的证据。
5. 整理 workspace / CoppeliaSim / AUBO dry-run 结果，形成“机器人接口前检查链条”的流程图和表。
6. 将 font gap / Phase 1 readonly estimates 放入限制与未来工作，不把它写成已经替换默认 profile 的结果。
7. 补一张人工评价表：connector naturalness、style distinguishability、stroke width visibility、layout naturalness。该表需要用户人工看图后填写。

## 暂不建议作为主实验的内容

- 真实 DeepSeek API planner 鲁棒性：可作为附录或系统入口验证，不建议压过方法核心。
- Phase 1 readonly estimates：适合证明“当前风格真实性还有数据化升级空间”，不建议作为主结果。
- AUBO i5 command/IK dry-run：适合说明工程闭环，不可写成真实机器人实验。

## 下一步建议

优先固定 4 张论文图和 3 张表：

- 图 1：系统流程图，覆盖 planner -> modifier -> trajectory -> execution -> workspace -> robot dry-run。
- 图 2：modifier controllability 三联图。
- 图 3：xingkai connector rule baseline / v1 / v2 对比图。
- 图 4：motion continuity before/after retiming 表图。
- 表 1：外部方法功能对比表。
- 表 2：核心 ablation 指标表。
- 表 3：人工看图评价表。

完成这些以后，再决定是否补充 API planner 鲁棒性或 Phase 1 profile comparison 作为附录。
