# 小论文图注草稿

以下图注用于 `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/` 中的固定图表包。所有文字仍是草稿，后续应根据人工看图评价进一步收紧或替换。

## Figure 1. 系统流程

**文件：** `fig1_system_pipeline.png`

**图注草稿：** 自然语言约束驱动的参数化轨迹生成与执行前检查流程。用户输入先由 mock/API/local planner 解析为结构化计划，并经过请求边界校验；随后离散 `style_modifiers` 通过本地白名单映射影响 style profile 和执行参数。轨迹点、CSV 和机器人前检查数据均由本地确定性工具生成，LLM 不直接生成轨迹点、CSV 或机器人命令。后续链路包括二维执行层、工作空间映射、target pose retiming 以及机器人接口前 dry-run 检查。

## Figure 2a. 连笔 modifier 可控性

**文件：** `fig2_modifier_control_connection.png`

**图注草稿：** 自然语言连笔约束对行楷“山”执行轨迹的影响。`不要连笔` 触发 `connection_preference=none`，保留抬笔移动；默认行楷使用 weak connector；`更连贯` 使用 normal connector。修复后的 connector 几何路径完整连接相邻笔画端点，weak/normal 的差异主要体现在连接段压力、宽度和速度等执行属性上。该图只说明受控 modifier 的可解释影响，不代表真实行楷连笔学习。

## Figure 2b. 宽扁 modifier 可控性

**文件：** `fig2_modifier_control_shape.png`

**图注草稿：** 自然语言形态约束对隶书“中”的宽扁比例控制。子图标题按 `shape_emphasis` 标注为 `normal / flatter / wider`，不是 `connection_preference`。`宽扁一点` 同时增大横向尺度并压缩纵向尺度，`更宽` 主要增大横向尺度。该图展示了参数化 profile 对整体外形的控制能力，但不能证明真实隶书结构已经被学习；隶书仍可能表现为 Make Me a Hanzi 基础骨架的横向拉宽和纵向压扁。

## Figure 2c. 圆滑 modifier 可控性

**文件：** `fig2_modifier_control_smoothness.png`

**图注草稿：** 自然语言圆滑度约束对轨迹转折的影响。`更圆滑` 和 `更平滑` 提高 smoothness level，降低部分转折强度；`更保守` 同时降低 smoothness 并抑制跨笔连接。由于 `mean_turning` 对局部视觉变化不总是敏感，本文同时参考 `total_turning_angle`、`max_turning_angle` 和人工看图判断。

## Figure 3a. 国 / 行楷 connector rule 对比

**文件：** `fig3_xingkai_connector_levels_u56fd.png`

**图注草稿：** 行楷“国”的 connector 规则消融。all-adjacent baseline 产生较密集的跨笔连接，conservative v1 明显减少连接，balanced v2 在连接数量和自然度之间提供折中候选。balanced v2 仅作为 `candidate_default_v2` 的折中规则，不替换全局默认，也不代表真实行楷书写规则。

## Figure 3b. 德 / 行楷 connector rule 对比

**文件：** `fig3_xingkai_connector_levels_u5fb7.png`

**图注草稿：** 行楷“德”的 connector 规则消融。该字结构较复杂，all-adjacent baseline 容易产生过多连接；conservative v1 连接较少；balanced v2 保留少量曲线 connector，用于观察是否更接近“带过去”的行楷书写感觉。最终是否作为论文主图仍需人工评价 connector 自然度。

## Figure 3c. 明 / 行楷 connector rule 对比

**文件：** `fig3_xingkai_connector_levels_u660e.png`

**图注草稿：** 行楷“明”的 connector 规则消融。balanced v2 相比 conservative v1 恢复少量连接，但没有回到 all-adjacent 的密集连接状态。该结果用于说明规则式 connector 可以形成稀疏到折中的可控梯度，而不是学习得到的真实书写连笔。

## Figure 4. execution width / pressure 可视化

**文件：** `fig4_execution_width_pressure.png`

**图注草稿：** 二维执行层中的宽度和压力可视化。与中心线轨迹不同，`execution_trajectory.csv` 显式记录 `width`、`pressure`、`pen_down`、`is_connector` 和 `segment_type`。该图用于展示 stroke taper、connector thinner 和低压连接等执行属性，说明本方法为后续虚拟书写和机器人接口前检查提供了更丰富的中间表示。该图不应解释为真实笔刷物理模型。

## Table 1. retiming before/after

**文件：** `table1_retiming_before_after.md` / `table1_retiming_before_after.csv`

**表注草稿：** target pose retiming 前后的运动连续性指标对比。原始 target poses 中存在非正时间间隔，并在保守 dry-run gate 下出现 acceleration 和 jerk 超限；去重和 retiming 后，时间戳严格递增，最大加速度和最大 jerk 降至保守阈值内，`recommended_for_ik_dry_run` 由 false 变为 true。该表仅说明离线 target-pose 时间规划改善，不代表真实机器人动力学优化。

## Table 2. robot-interface precheck summary

**文件：** `table2_robot_precheck_summary.md` / `table2_robot_precheck_summary.csv`

**表注草稿：** 机器人接口前检查链条汇总。表中列出 workspace mapping、CoppeliaSim standard scene、AUBO command adapter 和 IK feasibility dry-run 的关键 gate。所有结果均为离线执行前检查或 pen-tip/tool visual sanity check，不连接真实 AUBO i5，不调用 SDK，不发送运动命令，也不等价于真实 IK 验证。

## Table 3. external functional comparison

**文件：** `table3_external_functional_comparison.md` / `table3_external_functional_comparison.csv`

**表注草稿：** 本文方法与几类代表性书写轨迹/风格生成路线的功能性对比。比较维度包括是否需要示教数据、是否支持自然语言输入、是否支持可解释 modifier、是否输出 execution trajectory、是否具备 retiming/motion gate 和 robot-interface dry-run 等。该表只做功能维度对比，不包含外部方法的数值复现结果。

## Supplementary figures. style gap / Phase 1

**文件：** `supplementary/supp_font_style_grid.png`、`supplementary/supp_font_vs_trajectory_aspect_ratio.png`、`supplementary/supp_lishu_flatness_gap.png`、`supplementary/supp_phase1_current_vs_scale.png`

**图注草稿：** 字体轮廓与当前参数化轨迹之间的风格差距诊断。补充图用于说明当前 profile 主要是参数化控制，真实风格学习、部件级结构适配和笔画级风格估计仍是后续方向。Phase 1 readonly estimates 只提供非默认候选提示，不替换当前默认 style profile。
