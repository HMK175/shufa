# 论文实验图表索引

记录日期：2026-06-13

本目录收集当前 `experiments/llm_style_trajectory` 阶段最适合用于论文或汇报的固定命名图表。源输出仍保留在各自 batch 目录中，本目录只作为论文整理入口。

## 1. 建议论文结构对应关系

| 论文位置 | 建议标题 | 使用图表 |
|---|---|---|
| 第 3 章 系统总体方案 | LLM planner 与本地确定性轨迹工具流程 | 方法流程图可根据 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md` 重画 |
| 第 4 章 风格参数构建 | 三字体基础风格对比、多字诊断、字体轮廓差距分析、数据化升级方案与 Phase 1 只读估计 | `fig_style_profile_compare_grid.png`, `style_diagnostics_index.md`, `style_diagnostic_grid.png`, `style_metric_bars.png`, `font_style_gap_analysis_index.md`, `style_profile_upgrade_plan_index.md`, `style_profile_phase1_estimates_index.md` |
| 第 5 章 自然语言约束驱动的轨迹生成 | style modifier 受控映射 | `fig_modifier_connection_shan.png`, `fig_modifier_shape_zhong.png`, `fig_modifier_smoothness_yong.png` |
| 第 5 章 二维执行层 | 中心线轨迹到执行轨迹 | `fig_execution_ablation_shan.png`, `execution_ablation_table.md` |
| 第 6 章 仿真前检查 | 工作空间映射、重采样与 CoppeliaSim dry-run | `fig_workspace_ablation_shan.png`, `fig_workspace_resampling_shan.png`, `fig_coppeliasim_standard_scene_shan.png` |
| 第 6 章 机器人接口准备 | AUBO i5 离线命令计划、安全检查、IK feasibility、运动连续性前检查与 retiming 后处理 | `aubo_i5_command_adapter_index.md`, `aubo_i5_ik_feasibility_index.md`, `motion_continuity_check_index.md`, `target_pose_retiming_index.md`, `aubo_i5_command_adapter_smoothed_index.md`, `aubo_i5_ik_feasibility_smoothed_index.md` |
| 第 6 章 实验分析 | 基础风格、modifier、执行层、工作空间检查 | 本目录全部图表 |

## 2. 基础 Style Profile 对比

源目录：

```text
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/
```

固定图表：

| 文件 | 内容 |
|---|---|
| `fig_style_profile_compare_grid.png` | 5 字 x 3 风格总览 |
| `fig_style_profile_compare_shan.png` | 山：kaishu / xingkai / lishu |
| `fig_style_profile_compare_zhong.png` | 中：kaishu / xingkai / lishu |
| `fig_style_profile_compare_yong.png` | 永：kaishu / xingkai / lishu |
| `fig_style_profile_compare_fu.png` | 福：kaishu / xingkai / lishu |
| `fig_style_profile_compare_ming.png` | 明：kaishu / xingkai / lishu |

平均指标：

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 0.920111 | 772.899 | 0.000 | 0.000 | 9.000000 | 602.907 | 0 |
| xingkai | 0.966550 | 863.159 | 5.600 | 90.279 | 8.991667 | 404.606 | 0 |
| lishu | 1.322317 | 758.556 | 0.000 | 0.000 | 10.000000 | 588.240 | 0 |

可写结论：

- `lishu` 的平均 aspect ratio 最高，体现宽扁趋势。
- `xingkai` 默认产生弱连接，`avg_connection_count` 与 `avg_connector_draw_length` 均高于 kaishu/lishu。
- `kaishu` 无跨笔连接，表现为保守基础风格。
- 三种风格均未超出工作空间范围。

注意：`path_length` 与 `workspace_path_length_mm` 属于不同坐标层指标，论文中不要混作同一个指标解释。

### 2.1 多字样本风格诊断

源目录：

```text
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `style_diagnostics_index.md` | 多字样本风格诊断索引 |
| `style_diagnostic_report.md` | 多字样本风格诊断报告 |
| `style_diagnostic_style_means.csv` | 三风格平均指标 |
| `style_diagnostic_grid.png` | 12 字 x 3 风格 execution render 总览 |
| `style_metric_bars.png` | 风格区分关键指标柱状图 |

样本统计：

| total_samples | success_count | failure_count | missing_char_count |
|---:|---:|---:|---:|
| 54 | 54 | 0 | 0 |

三风格平均指标：

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 1.018672 | 786.158 | 0.0 | 0.0 | 9.0 | 614.139 | 0 |
| lishu | 1.465173 | 783.776 | 0.0 | 0.0 | 10.0 | 612.518 | 0 |
| xingkai | 1.070791 | 1314.104 | 6.056 | 525.944 | 7.488813 | 615.987 | 0 |

可写结论：18 个常用字、54 个 char × style 样本全部成功生成。`lishu` 继续表现出最高 `aspect_ratio`，宽扁参数稳定；`xingkai` 的 connector 指标显著高于 kaishu/lishu，默认弱连接逻辑稳定；`kaishu` 和 `lishu` 均保持无跨笔连接。该诊断也提示当前风格参数仍偏全局化，下一步应优先重新估计笔画级宽度、部件级比例、转折圆滑度和 connector 规则。

### 2.2 字体轮廓驱动的风格差距诊断

源目录：

```text
experiments/llm_style_trajectory/outputs/font_style_gap_analysis_20260618_144838/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `font_style_gap_analysis_index.md` | 本轮 paper_figures 固定入口 |
| `font_style_gap_report.md` | 字体轮廓与当前轨迹差距诊断报告 |
| `font_style_gap_style_means.csv` | 三风格字体/轨迹均值对照 |
| `font_style_grid.png` | 18 字 × 3 风格真实字体渲染网格 |
| `font_vs_trajectory_aspect_ratio.png` | 字体 vs 当前轨迹 aspect ratio 对照 |
| `lishu_flatness_gap.png` | 隶书宽扁差距图 |
| `xingkai_connectedness_gap.png` | 行楷连通性弱对应差距图 |
| `style_separation_gap.png` | 字体/轨迹风格分离度差距图 |

样本统计：

| total | rendered_success | failures |
|---:|---:|---:|
| 54 | 54 | 0 |

三风格字体/轨迹均值：

| style | samples | mean_font_aspect_ratio | mean_trajectory_aspect_ratio | mean_abs_aspect_ratio_gap | mean_font_components | mean_trajectory_connections | mean_font_stroke_width | mean_trajectory_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.029878 | 1.018672 | 0.058451 | 2.888889 | 0.0 | 6.320909 | 9.0 |
| xingkai | 18 | 0.989059 | 1.070791 | 0.126632 | 1.555556 | 6.055556 | 9.575023 | 7.488813 |
| lishu | 18 | 1.480275 | 1.465173 | 0.110869 | 2.5 | 0.0 | 8.956169 | 10.0 |

可写结论：`lishu` 的全局宽扁比例与字体轮廓均值接近，但这更像是整体横向拉宽/纵向压扁对上了比例，并不能证明当前轨迹已经具备真实隶书笔画结构；`xingkai` 字体 connected component 与当前 connector 只是弱对应，当前 `connection_count` 均值更高，说明 connector prior 仍有明显人工规则成分；`kaishu` 的 aspect gap 最小，符合当前 Make Me a Hanzi median 基底更接近楷书的判断。下一步应优先从字体/图像统计中数据化估计横纵比例、笔画宽度分布、部件比例、投影分布和连接先验。

### 2.3 Style profile 数据化升级方案

源目录：

```text
experiments/llm_style_trajectory/outputs/style_profile_upgrade_plan_20260618_150757/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `style_profile_upgrade_plan_index.md` | 本轮 paper_figures 固定入口 |
| `style_profile_upgrade_plan.md` | 数据化升级方案报告 |
| `style_profile_parameter_matrix.csv` | 23 个参数的层级、来源、阶段、风险矩阵 |
| `style_profile_upgrade_recommendations.json` | 三阶段升级建议 |
| `parameter_source_matrix.png` | 参数来源矩阵图 |
| `upgrade_priority_chart.png` | 分阶段优先级图 |

参数矩阵统计：

| item | value |
|---|---:|
| parameter_count | 23 |
| can_estimate_now_count | 7 |
| phase_1_count | 7 |
| phase_2_count | 5 |
| phase_3_count | 11 |

可写结论：Phase 1 只处理现在可从字体轮廓统计中低风险估计的全局比例、宽度分布和投影分布；Phase 2 再做 char/component-level 结构适配；Phase 3 保留 connector、taper、pressure、speed、pen-up 等 process prior，不从静态字体直接估计。`prototype_style_profile_estimates.json` 只作为提示，明确 `prototype_not_used_by_default`，不接入默认生成流程。

### 2.4 Phase 1 font-outline readonly estimates

源目录：

```text
experiments/llm_style_trajectory/outputs/style_profile_phase1_estimates_20260618_152952/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `style_profile_phase1_estimates_index.md` | 本轮 paper_figures 固定入口 |
| `style_profile_phase1_estimate_report.md` | Phase 1 字体轮廓只读估计报告 |
| `style_profile_phase1_parameter_comparison.csv` | current profile vs Phase 1 hints |
| `style_profile_phase1_estimates.json` | 只读候选 estimates JSON |
| `current_vs_phase1_scale.png` | 当前 scale 与 Phase 1 scale hints 对比 |
| `current_vs_phase1_width.png` | Phase 1 base width hints |
| `phase1_projection_summary.png` | 投影 spread summary |

关键状态：

| field | value |
|---|---|
| `_status` | `readonly_estimate_not_used_by_default` |
| `_warning` | `not wired into generation pipeline` |
| `_source` | `font_style_gap_analysis_20260618_144838` |

Current vs Phase 1 关键差异：

| style | parameter | current | phase1_hint | delta | confidence |
|---|---|---:|---:|---:|---|
| kaishu | horizontal_scale | 1.0 | 1.0 | 0.0 | medium |
| kaishu | vertical_scale | 1.0 | 1.0 | 0.0 | medium |
| lishu | horizontal_scale | 1.18 | 1.198887 | 0.018887 | medium |
| lishu | vertical_scale | 0.82 | 0.834107 | 0.014107 | medium |
| xingkai | horizontal_scale | 1.03 | 0.979982 | -0.050018 | low |
| xingkai | vertical_scale | 0.98 | 1.020427 | 0.040427 | low |

可写结论：Phase 1 estimates 只给出横纵比例、base width、stroke width distribution、projection summary 和 lishu flatness 的只读提示；connection、connector、pressure、speed、pen-up、robot dynamics 仍明确不支持从静态字体估计。本轮不生成新轨迹，也不接默认生成流程。

## 3. Style Modifier Ablation

### 3.1 连笔语义：山

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

```text
fig_modifier_connection_shan.png
```

| task | connection_preference | connection_strength | connection_count | path_length | pen_up_count | connector_mean_pressure | connector_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 0 | 578.070 | 2 | 0.000 | 0.000 |
| 默认行楷山 | weak | 0.176 | 2 | 766.999 | 0 | 0.338 | 4.245 |
| 更连贯行楷山 | normal | 0.320 | 2 | 766.999 | 0 | 0.678 | 6.897 |

可写结论：自然语言中的“不要连笔 / 默认 / 更连贯”形成 `none -> weak -> normal` 梯度。修复后，`weak` 与 `normal` 都完整连接上一笔终点和下一笔起点，几何路径不再被 `connection_strength` 截断；二者主要差异体现在连接段压力和宽度上。

### 3.2 宽扁语义：中

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
```

固定图表：

```text
fig_modifier_shape_zhong.png
```

| task | shape_emphasis | horizontal_scale | vertical_scale | bbox_width | bbox_height | aspect_ratio |
|---|---:|---:|---:|---:|---:|---:|
| 隶书中 | normal | 1.1800 | 0.8200 | 175.851 | 176.333 | 0.997268 |
| 宽扁一点隶书中 | flatter | 1.2980 | 0.7544 | 193.446 | 162.226 | 1.192443 |
| 更宽隶书中 | wider | 1.2744 | 0.8200 | 190.540 | 176.333 | 1.080569 |

可写结论：`flatter` 同时增宽并压低高度，aspect ratio 提升最大；`wider` 主要增宽并保留原高度。

### 3.3 圆滑语义：永

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
```

固定图表：

```text
fig_modifier_smoothness_yong.png
```

| task | smoothness_level | smoothness | path_length | mean_turning | total_turning_angle | max_turning_angle | connection_preference | connection_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 楷书永 | medium | 0.180 | 649.156 | 0.099365 | 10.632062 | 0.971813 | weak | 0 |
| 更圆滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更平滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更保守行楷永 | low | 0.231 | 653.408 | 0.081651 | 10.696220 | 1.048066 | none | 0 |

可写结论：`mean_turning` 变化较小，应优先使用 `total_turning_angle` 与 `max_turning_angle` 展示圆滑度变化。

## 4. 二维执行层

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

| 文件 | 内容 |
|---|---|
| `fig_execution_ablation_shan.png` | none / weak / normal 执行层总览 |
| `fig_execution_none_render.png` | 不连笔 render |
| `fig_execution_weak_render.png` | weak connector render |
| `fig_execution_normal_render.png` | normal connector render |
| `fig_execution_none_debug.png` | 不连笔 debug |
| `fig_execution_weak_debug.png` | weak connector debug |
| `fig_execution_normal_debug.png` | normal connector debug |
| `execution_ablation_table.md` | 执行层指标表 |

关键指标：

| task | connection_preference | connector_draw_length | pen_up_move_length | connector_mean_pressure | connector_mean_width | mean_width | mean_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 188.929 | 0.000 | 0.000 | 9.500000 | 1.000000 |
| 默认行楷山 | weak | 188.929 | 0.000 | 0.338 | 4.245 | 8.205479 | 0.836935 |
| 更连贯行楷山 | normal | 188.929 | 0.000 | 0.678 | 6.897 | 8.858823 | 0.920684 |

可写结论：execution layer 比中心线轨迹更能表达连笔差异，因为它显式记录 `pressure`、`width`、`pen_down`、`is_connector` 和 `segment_type`。修复后，连笔几何完整性由 connector 负责，`connection_strength` 主要体现在连接段执行属性上。

## 5. 工作空间映射、重采样与 CoppeliaSim Dry-Run

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

```text
fig_workspace_ablation_shan.png
fig_workspace_resampling_shan.png
fig_coppeliasim_standard_scene_shan.png
coppeliasim_standard_scene_result.md
coppeliasim_standard_scene_result.json
```

CoppeliaSim dry-run 关键指标：

| task | connection_preference | point_count | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | stroke_count | connector_count | pen_up_move_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 258 | 8.000 | 4.749 | 8.000 | 237 | 0 | 21 |
| 默认行楷山 | weak | 275 | 2.488 | 2.488 | 0.000 | 237 | 38 | 0 |
| 更连贯行楷山 | normal | 275 | 2.488 | 2.488 | 0.000 | 237 | 38 | 0 |

可写结论：三组轨迹均未越出纸面工作空间。`none` 的最大 3D 跳变来自 8mm Z 轴抬笔，XY 最大步长仍小于 5mm；`weak/normal` 在修复后不再出现 35mm / 43mm 的 XY 段间跳变，重采样后最大 XY 步长约 2.488mm，满足进入 CoppeliaSim 笔尖路径播放的基本连续性要求。

### 5.1 标准书写场景真实播放结果

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `fig_coppeliasim_standard_scene_shan.png` | 120mm x 120mm 纸面、坐标轴、边界和 weak 行楷山路径示意图 |
| `coppeliasim_standard_scene_result.md` | 真实播放结果表 |
| `coppeliasim_standard_scene_result.json` | 真实播放结果原始 JSON |
| `coppeliasim_standard_scene_index.md` | 标准场景资料索引 |

关键结果：

| status | simulation_stopped | recommended_playback | point_count | max_xy_step_mm | max_z_step_mm | paper_size_mm |
|---|---|---|---:|---:|---:|---:|
| finished | true | true | 275 | 2.487672 | 0.0 | 120.0 |

可写结论：标准 CoppeliaSim 纸面场景已能自动创建并完成 weak 行楷山的真实播放。轨迹位于 `120mm x 120mm` 纸面范围内，播放结束后自动停止仿真。当前仍是 pen-tip/sphere scene，不包含机械臂 IK。

### 5.2 AUBO i5 离线命令计划

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_command_adapter_index.md` | AUBO i5 command adapter 论文索引 |
| `aubo_i5_command_plan.csv` | 离线 SDK command plan |
| `aubo_i5_command_plan.md` | command plan 摘要报告 |
| `aubo_i5_safety_check.json` | safety check 原始 JSON |

关键结果：

| point_count | command_count | max_step_m | max_speed_m_s | max_accel_m_s2_estimate | recommended_for_sdk_dry_run | warnings |
|---:|---:|---:|---:|---:|---|---|
| 275 | 277 | 0.002488 | 0.04 | 0.0 | true | [] |

command plan 类型：

| command_type | count | 说明 |
|---|---:|---|
| `move_joint_approach` | 1 | 安全接近位姿，仅作为 future SDK hint |
| `move_line` | 275 | 沿末端目标位姿序列跟随 |
| `move_line_retract` | 1 | 结束后安全撤离，仅作为 future SDK hint |

可写结论：当前系统已经把 `robot_target_poses.csv` 推进到 AUBO i5 SDK dry-run command plan，形成“接近、线性跟随、撤离”的离线接口准备结果，并通过步长、速度、加速度估计、时间单调性和四元数归一化检查。当前仍不做 IK、不连接真实 AUBO i5、不调用 `move_joint` / `move_line`、不发送真实控制命令。

### 5.3 AUBO i5 IK feasibility dry-run

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_ik_feasibility_index.md` | AUBO i5 IK feasibility dry-run 论文索引 |
| `aubo_i5_ik_feasibility_summary.json` | feasibility summary 原始 JSON |
| `aubo_i5_ik_feasibility_report.md` | feasibility 人工可读报告 |
| `aubo_i5_ik_feasibility_points.csv` | 每个 target pose 的前检查标记 |

关键结果：

| point_count | max_step_m | max_speed_m_s | radius_range_m | recommended_for_real_ik_check | warnings |
|---:|---:|---:|---|---|---|
| 275 | 0.002488 | 0.04 | `[0.000756, 0.064444]` | true | [] |

可写结论：当前系统已完成进入真实 IK 前的离线 feasibility gate。该层检查目标位姿字段、纸面范围、Z 范围、点距、速度、时间单调性、四元数归一化、NaN/inf 和保守半径 envelope。它仍不是 AUBO i5 真实 IK，不判断关节限位、碰撞、奇异位形或真实可达性，也不连接 SDK 或实机。

### 5.4 Motion continuity dry-run

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `motion_continuity_check_index.md` | 速度、加速度、jerk 与时间连续性前检查索引 |
| `motion_continuity_summary.json` | motion continuity summary 原始 JSON |
| `motion_continuity_report.md` | motion continuity 可读报告 |

关键结果：

| point_count | max_speed_m_s | max_accel_m_s2 | max_jerk_m_s3 | dt_nonpositive_count | recommended_for_ik_dry_run |
|---:|---:|---:|---:|---:|---|
| 275 | 0.04 | 0.533536 | 11.386446 | 4 | false |

可写结论：当前 target pose 序列在几何与速度上仍较安全，但更严格的运动连续性 gate 检出了 4 个零时长边界点，以及保守阈值下的 acceleration / jerk 超限。因此进入真实 IK dry-run 或低速空跑准备前，应先做 target pose 去重、retiming 与速度曲线平滑。该层仍不是真实机器人动力学、不是 IK、也不判断关节空间速度、加速度或力矩。

### 5.5 Target pose retiming / smoothing dry-run

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `target_pose_retiming_index.md` | target pose 去重、retiming 与速度平滑后处理索引 |
| `target_pose_retiming_summary.json` | before/after summary 原始 JSON |
| `target_pose_retiming_report.md` | retiming 人工可读报告 |
| `motion_continuity_after_retiming_summary.json` | retiming 后复用 continuity gate 的 summary |
| `motion_continuity_after_retiming_report.md` | retiming 后连续性检查报告 |

关键结果：

| metric | before | after |
|---|---:|---:|
| point_count | 275 | 271 |
| duration_s | 13.0528205 | 22.039876274 |
| dt_nonpositive_count | 4 | 0 |
| max_speed_m_s | 0.04 | 0.01792 |
| max_accel_m_s2 | 0.533536 | 0.274132 |
| max_jerk_m_s3 | 11.386446 | 4.193554 |
| recommended_for_coppeliasim_playback | false | true |
| recommended_for_ik_dry_run | false | true |

可写结论：target pose retiming 层删除 4 个相邻静止重复点，并在不改变几何路径长度的前提下重写严格递增时间戳。默认 weak 行楷山样例的 acceleration / jerk 已回到保守 dry-run gate 内，可重新进入 CoppeliaSim playback 或真实 IK 前的离线检查准备。该层仍不是关节空间轨迹规划、真实机器人动力学优化或 AUBO i5 实机控制。

### 5.6 AUBO i5 smoothed command adapter dry-run

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_command_adapter_smoothed_index.md` | 基于 smoothed target poses 的 command adapter 索引 |
| `aubo_i5_command_plan_smoothed.md` | smoothed command plan 报告 |
| `aubo_i5_safety_check_smoothed.json` | smoothed safety check JSON |

关键结果：

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| point_count | 275 | 271 |
| command_count | 277 | 273 |
| max_step_m | 0.002488 | 0.002488 |
| max_speed_m_s | 0.04 | 0.01792 |
| recommended_for_sdk_dry_run | true | true |
| warnings | [] | [] |

可写结论：原始 `robot_target_poses.csv` 保留为 before-retiming 对照；后续 AUBO command adapter 推荐输入为 `robot_target_poses_smoothed.csv`。该结果基于已通过 conservative motion-continuity gate 的 target poses，仍只是 SDK dry-run command plan，不调用 AUBO SDK、不连接实机、不发送运动命令。

### 5.7 AUBO i5 smoothed IK feasibility dry-run

固定资料：

| 文件 | 内容 |
|---|---|
| `aubo_i5_ik_feasibility_smoothed_index.md` | 基于 smoothed target poses 的 IK feasibility 索引 |
| `aubo_i5_ik_feasibility_smoothed_summary.json` | smoothed feasibility summary |
| `aubo_i5_ik_feasibility_smoothed_report.md` | smoothed feasibility 报告 |

关键结果：

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| point_count | 275 | 271 |
| max_step_m | 0.002488 | 0.002488 |
| max_speed_m_s | 0.04 | 0.01792 |
| radius_range_m | `[0.000756, 0.064444]` | `[0.000756, 0.064444]` |
| recommended_for_real_ik_check | true | true |
| warnings | [] | [] |

可写结论：smoothed IK feasibility 结果继承 retiming 后更稳定的时间序列，并保持相同工作空间和保守半径 envelope。后续真实 IK 前离线检查应优先引用该 smoothed 版本；该层仍不是真实 AUBO i5 IK，不判断关节限位、碰撞、奇异位形或真实可达性。

## 6. 当前推荐使用顺序

论文或汇报中建议按以下顺序展示：

1. `fig_style_profile_compare_grid.png`：先证明三种基础风格不同。
2. `style_diagnostics_index.md`：扩展到 18 个字，诊断基础 style profile 在更多结构上的稳定性。
3. `fig_modifier_connection_shan.png`：证明自然语言可控制连笔。
4. `fig_modifier_shape_zhong.png`：证明自然语言可控制宽扁。
5. `fig_modifier_smoothness_yong.png`：证明自然语言可控制圆滑。
6. `fig_execution_ablation_shan.png`：证明 execution layer 能表达笔压/笔宽/抬笔状态。
7. `fig_workspace_ablation_shan.png`：证明轨迹已能映射到机器人纸面坐标。
8. `fig_workspace_resampling_shan.png`：证明重采样与 playback dry-run 能发现并消除段间跳变风险。
9. `fig_coppeliasim_standard_scene_shan.png`：证明轨迹进入固定 CoppeliaSim 书写工作空间并完成标准场景播放。
10. `aubo_i5_command_adapter_index.md`：证明轨迹已进一步整理成 AUBO i5 SDK dry-run command plan。
11. `aubo_i5_ik_feasibility_index.md`：证明目标位姿已通过进入真实 IK 前的离线 feasibility gate。
12. `motion_continuity_check_index.md`：展示更严格的速度、加速度、jerk 与时间连续性 gate；原始默认样例未通过该 gate，提示需要 retiming/smoothing。
13. `target_pose_retiming_index.md`：展示 retiming 后 `dt_nonpositive_count=0`，acceleration/jerk 回到保守阈值内，默认样例重新通过 CoppeliaSim playback 与 IK dry-run 前检查。
14. `aubo_i5_command_adapter_smoothed_index.md`：展示基于 smoothed target poses 的 AUBO command adapter 结果。
15. `aubo_i5_ik_feasibility_smoothed_index.md`：展示基于 smoothed target poses 的 IK feasibility 前检查结果。
16. `style_visual_audit_index.md`：展示多字样本风格诊断后的异常样本定位与人工看图校验包，提醒数值诊断不能替代视觉判断。
17. `connector_brush_visual_diagnostics_index.md`：进一步把 connector、pen-up move、stroke width 和 pressure 拆开显示，解释旧图灰线、宽度不明显和 lishu 横向拉伸等人工看图问题。
18. `width_pressure_visualization_index.md`：用颜色深浅和适度线宽编码 execution 层的 width / pressure，区分 global 与 per-image normalization，用于判断 connector 是否确实更细/低压，以及主体 stroke 内部是否几乎恒定。
19. `execution_refinement_index.md`：基于人工反馈进行第一轮 execution refinement 实验，收紧行楷 connector 触发、加入简单 stroke taper，并改用非白浅色端提升 width/pressure 渐变图可读性。
20. `experiments/llm_style_trajectory/docs/execution_refinement_decision.md`：归档用户人工看图反馈，并把 conservative connector + simple_taper 标记为 `candidate_default_v1`。该标记只是下一轮候选默认，不是全局默认。
21. `execution_refinement_validation_index.md`：对 `candidate_default_v1` 做 18 个样本 before/after 验证，输出人工看图包和指标汇总；该轮仍不调参、不切全局默认。
22. `xingkai_balanced_experiment_index.md`：新增 balanced connector、slight curved connector 和行楷 expressive taper，对比 baseline / conservative / balanced 三档；用于判断是否可作为下一轮 `candidate_default_v2` 候选。
23. `experiments/llm_style_trajectory/docs/xingkai_balanced_decision.md`：归档 balanced 人工反馈，并将 balanced + slight_curve + xingkai_expressive_taper 标记为 `candidate_default_v2`；该标记不是全局默认。
24. `font_style_gap_analysis_index.md`：从真实字体轮廓统计反查当前 style profile 与轨迹指标的差距，说明下一步应优先数据化升级风格参数，而不是继续盲调 connector/taper。
25. `style_profile_upgrade_plan_index.md`：把 style profile 参数分成 style / component / process_prior 三类，并形成 Phase 1-3 数据化升级路线；prototype estimates 不接入默认流程。
26. `style_profile_phase1_estimates_index.md`：把 Phase 1 可从字体轮廓估计的低风险参数产出为 readonly estimates；不替换默认 profile，不生成新轨迹。

## 7. 边界说明

- 当前图表展示的是参数化 style profile 与受控 modifier 的效果。
- 当前尚不是完整真实书法风格学习。
- 当前已完成 CoppeliaSim pen-tip/sphere 最小路径播放、dry-run 检查、AUBO i5 离线 command plan、IK feasibility dry-run、motion continuity dry-run、target pose retiming 后处理，以及基于 smoothed target poses 重新生成的 command/IK dry-run 结果，但尚未接入真实机械臂模型、真实 IK、真实动力学或控制器。
- LLM/API planner 不直接输出 CSV 或轨迹点，仍由本地确定性工具生成。

## 8. Execution refinement：connector 收紧与 stroke taper

源输出目录：

```text
experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `execution_refinement_index.md` | 本轮 paper_figures 固定入口 |
| `execution_refinement_report.md` | before/after 实验报告 |
| `execution_refinement_summary.csv` | 关键指标汇总 |
| `execution_refinement_before_after_connector_u56fd_xingkai.png` | 国 / 行楷 connector before/after |
| `execution_refinement_before_after_connector_u5fb7_xingkai.png` | 德 / 行楷 connector before/after |
| `execution_refinement_before_after_connector_u798f_xingkai.png` | 福 / 行楷 connector before/after |

关键结果：

| char | style | connection_count | connector_draw_length | stroke_width_range |
|---|---|---:|---:|---:|
| 国 | xingkai | 7 -> 1 | 810.946 -> 106.146 | 0.0 -> 3.23 |
| 德 | xingkai | 14 -> 1 | 878.276 -> 45.035 | 0.0 -> 3.23 |
| 福 | xingkai | 12 -> 1 | 886.416 -> 96.856 | 0.0 -> 3.229996 |
| 和 | xingkai | 7 -> 2 | 531.324 -> 101.215 | 0.0 -> 3.229996 |

可写结论：本轮 conservative connector gate 已经缓解“所有相邻笔画必连”的问题，simple taper 让 stroke 内部 width/pressure 出现可量化变化，且浅色端不再接近白色。但这些仍是实验性执行层参数，不是真实行楷规则或真实笔刷模型，后续需要人工看图反馈后再决定是否继续收紧 connector 或设计更细的笔画级宽度模型。

人工反馈收口：

- `candidate_default_v1` 已记录到 `execution_refinement_profiles.json`，指向 `conservative` + `simple_taper`。
- 用户反馈：connector 自然度改善但略偏保守；stroke taper 可见且效果不错；lishu 未观察到误连笔。
- `人/lishu` 可疑字段已核查：`after_connector_draw_length=0.0`，`3.3998` 是 `after_stroke_width_range`。
- 后续可考虑增加 `balanced` connector 档位，但不是当前轮次。

## 9. candidate_default_v1 多样本验证

源输出目录：

```text
experiments/llm_style_trajectory/outputs/execution_refinement_validation_20260618_120238/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `execution_refinement_validation_index.md` | 本轮 paper_figures 固定入口 |
| `execution_refinement_validation_report.md` | 多样本 before/after 验证报告 |
| `execution_refinement_validation_summary.csv` | 18 个样本的指标汇总 |
| `execution_refinement_validation_before_after_u56fd_xingkai.png` | 国 / 行楷 before/after 图 |
| `execution_refinement_validation_before_after_u5fb7_xingkai.png` | 德 / 行楷 before/after 图 |
| `execution_refinement_validation_before_after_u798f_xingkai.png` | 福 / 行楷 before/after 图 |
| `execution_refinement_validation_before_after_u548c_xingkai.png` | 和 / 行楷 before/after 图 |
| `execution_refinement_validation_before_after_u4e2d_xingkai.png` | 中 / 行楷 before/after 图 |

关键结果：

| metric | value |
|---|---:|
| selected_count | 18 |
| success_count | 18 |
| failure_count | 0 |
| xingkai_samples | 8 |
| xingkai connection_count sum | 58 -> 5 |
| xingkai connector_draw_length sum | 4938.116 -> 349.252 |
| xingkai retained connector samples | 4 / 8 |
| kaishu/lishu connector violations | 0 |
| mean after stroke_width_range | 3.2295 |

可写结论：`candidate_default_v1` 在多样本中继续满足“行楷 connector 明显收敛、楷书/隶书不误连、stroke taper 可见”的基本要求；
但 `中/人/明/林` 行楷 after connector 清零，说明它可能偏保守，仍需要人工看图判断是否进入默认执行层，或之后设计 `balanced` 档位。

## 10. balanced connector + 行楷局部风格增强

源输出目录：

```text
experiments/llm_style_trajectory/outputs/xingkai_balanced_experiment_20260618_141424/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `xingkai_balanced_experiment_index.md` | 本轮 paper_figures 固定入口 |
| `xingkai_balanced_report.md` | balanced 实验报告 |
| `xingkai_balanced_summary.csv` | baseline / conservative / balanced 指标汇总 |
| `xingkai_balanced_compare_connector_levels_u56fd_xingkai.png` | 国 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u5fb7_xingkai.png` | 德 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u798f_xingkai.png` | 福 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u548c_xingkai.png` | 和 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u4e2d_xingkai.png` | 中 / 行楷三档对比图 |

关键结果：

| metric | baseline | conservative | balanced |
|---|---:|---:|---:|
| xingkai connection_count sum | 58 | 5 | 10 |
| xingkai connector_draw_length sum | 4938.116 | 349.252 | 586.339 |
| kaishu/lishu connector violations | 0 | 0 | 0 |

可写结论：balanced 没有回到 baseline 全连，也比 conservative 多保留了一些行楷 connector；
`国/德/明/林` 是最值得先看的改善样本，`中/人` 仍清零，可能仍偏保守。
本轮只是诊断实验，不是最终行楷模型，也不进入仿真书写。

人工反馈收口：

- 用户反馈 balanced 每个字基本只多一笔，变化不激进；`福` 仍为一笔连笔但位置变化。
- 曲线 connector 更像“带过去”，当前效果可接受。
- `candidate_default_v2` 已记录到 `execution_refinement_profiles.json`，指向 `balanced` + `slight_curve` + `xingkai_expressive_taper`。
- `candidate_default_v2` 暂不替换全局默认，也不直接进入仿真书写。
- `candidate_default_v1` 继续保留为 conservative refined baseline。

## 11. CoppeliaSim simple pen/tool coordinate calibration

源任务目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `coppeliasim_tool_model_index.md` | simple pen/tool 坐标系校准层索引 |
| `coppeliasim_tool_model_result.json` | dry-run 原始结果 |
| `coppeliasim_tool_model_result.md` | dry-run 可读报告 |

关键结果：

| field | value |
|---|---:|
| status | dry_run |
| point_count | 275 |
| tool_model | simple-pen |
| show_tool_frame | true |
| tool_length_mm | 120.0 |
| tool_radius_mm | 4.0 |
| tcp_offset_mm | 0.0 |
| max_xy_step_mm | 2.487672 |
| recommended_for_coordinate_calibration | true |
| warnings | [] |

可写结论：该层把 CoppeliaSim standard pen-tip scene 推进到
paper/workspace/tool TCP frame 的可复查说明，并提供 simple pen cylinder 与
TCP frame 可视化参数。当前仍只是 tool visual sanity check，不是 AUBO i5
真实机器人模型，不是真实 IK，不是动力学仿真，也不是实机控制。
## Phase 1 readonly estimates 非默认对比图验证

源输出目录：

```text
experiments/llm_style_trajectory/outputs/phase1_profile_comparison_20260618_155353/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md
```

固定资料：

| 文件 | 内容 |
|---|---|
| `phase1_profile_comparison_index.md` | 本轮 paper_figures 入口 |
| `phase1_profile_comparison_report.md` | current profile vs phase1 candidate 对比报告 |
| `phase1_profile_comparison_summary.csv` | 指标对比表 |
| `style_profile_phase1_candidate.json` | `_status=comparison_only_not_default` 的临时候选 profile |
| `compare_current_phase1_u4eba_all_styles.png` | “人”三风格 current/phase1 对比 |
| `compare_current_phase1_u4e2d_all_styles.png` | “中”三风格 current/phase1 对比 |
| `compare_current_phase1_u597d_lishu.png` | “好”隶书对比 |
| `compare_current_phase1_u98ce_lishu.png` | “风”隶书对比 |
| `compare_current_phase1_u56fd_xingkai.png` | “国”行楷对比 |

关键结果：

| style | samples | mean_abs_aspect_ratio_delta | mean_abs_path_length_delta | mean_abs_mean_width_delta |
|---|---:|---:|---:|---:|
| kaishu | 3 | 0.000000 | 0.000 | 0.000000 |
| lishu | 4 | 0.001680 | 10.368 | 0.000000 |
| xingkai | 5 | 0.090515 | 7.508 | 0.006537 |

可写结论：Phase 1 全局字体轮廓估计对 kaishu/lishu 的视觉和指标改变有限；xingkai 的 aspect 变化来自全局 scale，但 connector 规则保持原样，因此不能靠 Phase 1 解决行楷味问题。本轮结果只用于非默认对比和人工看图，不替换 `style_profiles.json`，不改变 `run_demo.py`，也不进入机器人接口链路。下一步应转向 Phase 2 component/stroke-level style modeling。
## Mini-paper experiment comparison plan

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_experiment_plan_index.md
experiments/llm_style_trajectory/docs/mini_paper_experiment_plan.md
experiments/llm_style_trajectory/configs/mini_paper_experiment_matrix.json
```

建议论文主线：

```text
自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法
```

推荐正文主实验：

| id | 实验 | 当前状态 |
|---|---|---|
| A | 自然语言 modifier 可控性 | 部分已有，需固定论文图 |
| B | 行楷 connector rule baseline / conservative / balanced 对比 | 已有，需补人工评价表 |
| C | execution width / pressure 对比 | 已有 |
| D | motion continuity 与 retiming | 已有 |
| E | robot-interface precheck chain | 已有，限 dry-run 表述 |
| F | font outline gap / style profile 数据化诊断 | 分析已有，建议放限制与未来工作 |

边界：本方案只整理已有结果和下一步可执行实验清单，不新增算法、不替换全局默认 style profile、不调用 API、不连接 CoppeliaSim/AUBO i5、不做真实 IK 或机器人控制。
## Mini-paper fixed figure/table pack

固定目录：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/
```

核心索引：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/mini_paper_figure_index.md
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/mini_paper_figure_manifest.csv
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/mini_paper_table_manifest.csv
```

图表包统计：

| item | count |
|---|---:|
| figure / supplementary figure entries | 12 |
| table entries | 3 |
| missing sources | 0 |

正文候选图表：

| 编号 | 文件 | 内容 |
|---|---|---|
| Figure 1 | `fig1_system_pipeline.png` | 自然语言到 deterministic trajectory 和 dry-run precheck 的系统流程 |
| Figure 2a | `fig2_modifier_control_connection.png` | 连笔 modifier 可控性 |
| Figure 2b | `fig2_modifier_control_shape.png` | 宽扁 modifier 可控性；子图标题按 `shape_emphasis` 显示为 `normal / flatter / wider` |
| Figure 2c | `fig2_modifier_control_smoothness.png` | 圆滑 modifier 可控性 |
| Figure 3a | `fig3_xingkai_connector_levels_u56fd.png` | 国 / 行楷 connector baseline-v1-v2 对比 |
| Figure 3b | `fig3_xingkai_connector_levels_u5fb7.png` | 德 / 行楷 connector baseline-v1-v2 对比 |
| Figure 3c | `fig3_xingkai_connector_levels_u660e.png` | 明 / 行楷 connector baseline-v1-v2 对比 |
| Figure 4 | `fig4_execution_width_pressure.png` | execution width / pressure 可视化 |
| Table 1 | `table1_retiming_before_after.md/.csv` | target pose retiming before/after |
| Table 2 | `table2_robot_precheck_summary.md/.csv` | robot-interface precheck chain |
| Table 3 | `table3_external_functional_comparison.md/.csv` | 外部方法功能对比 |

补充材料位于 `mini_paper_figures/supplementary/`，用于 style gap / Phase 1 readonly estimates 的限制说明。该包只整理已有结果和一张方法流程示意图，不新增算法、不替换默认 profile、不调用 API、不连接 CoppeliaSim/AUBO i5、不做真实 IK 或机器人控制。

### Mini-paper visual evaluation and captions draft

新增写作材料：

```text
experiments/llm_style_trajectory/docs/mini_paper_visual_evaluation_template.md
experiments/llm_style_trajectory/docs/mini_paper_figure_captions_draft.md
experiments/llm_style_trajectory/docs/mini_paper_experiment_section_outline.md
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/human_visual_evaluation_template.csv
```

用途：为固定图表包提供人工看图评分表、中文图注草稿和实验章节提纲。该材料明确当前结果仍是参数化控制，不是真实书法风格学习；隶书仍可能偏“压扁楷书”；行楷 connector 是规则生成；CoppeliaSim/AUBO 只写 dry-run/precheck。

## 2026-06-19 Font-outline-derived trajectory basis feasibility

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_feasibility_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `font_outline_basis_report.md` | MakeMeAHanzi median 与字体轮廓 skeleton candidate 的可行性诊断报告 |
| `font_outline_basis_summary.csv` | 每个 char/style 的 mask、skeleton、bbox/aspect、endpoint/branch 指标 |
| `font_outline_basis_manifest.csv` | 每个字的对比图 manifest |
| `font_outline_basis_feasibility/basis_compare_uXXXX.png` | 10 个字的 median vs kaishu/xingkai/lishu skeleton 对比图 |

可写结论：字体轮廓 skeleton candidate 在 `山`、`德`、`福` 等样本上比 MakeMeAHanzi median 更能直观呈现行楷/隶书差异，说明下一阶段值得探索 font-outline-derived trajectory basis。但复杂字 skeleton 端点和分叉较多，本轮不替换默认 pipeline，不承诺直接可用于轨迹生成；后续必须做人工看图、骨架去噪、断裂修复和笔画顺序恢复。

## 2026-06-19 Font outline basis manual audit

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_outline_basis_audit_20260619_120211/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_audit_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `font_outline_basis_audit_report.md` | skeleton 问题统计、top 样本和人工看图重点 |
| `font_outline_basis_audit_candidates.csv` | 30 条 char/style 候选，包含空白 `manual_decision` 和 `manual_comment` |
| `font_outline_basis_visual_audit_checklist.md` | 给人工筛选使用的 checklist |
| `font_outline_basis_image_manifest.csv` | selected_images manifest |
| `font_outline_basis_audit/basis_compare_uXXXX.png` | 10 张待人工优先查看的对比图 |

可写结论：audit 包把 skeleton 问题分成 `high_endpoint_count`、`high_branch_count`、`disconnected_skeleton`、`high_aspect_gap`、`complex_skeleton` 和 `promising_candidate`。本轮不做参数调整，也不把 font skeleton 接入默认生成流程；下一步应先由用户人工判断 selected images 中哪些样本值得进入 skeleton 后处理设计。
## 2026-06-19 Font skeleton cleanup prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_cleanup_prototype_20260619_122355/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_cleanup_prototype_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `skeleton_cleanup_report.md` | kaishu / lishu skeleton cleanup before/after 报告和人工看图重点 |
| `skeleton_cleanup_summary.csv` | 每个 char/style 的 raw vs cleaned endpoint/branch/component/pixel 指标 |
| `skeleton_cleanup_manifest.csv` | before/after 对比图 manifest |
| `font_skeleton_cleanup_prototype/cleanup_compare_uXXXX_style.png` | font mask、raw skeleton、cleaned skeleton、overlay 对比图 |

可写结论：轻量 cleanup 对楷书 skeleton 的 endpoint/branch 简化更明显，对隶书较保守；部分样本如 `永` 和 `风` 清理后仍有断裂/多连通分量。该实验只说明 font-outline skeleton 后处理值得继续探索，不代表已经得到正式可写轨迹；后续需人工看图后再进入 path extraction prototype。
## 2026-06-19 Font skeleton path extraction prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_path_extraction_20260619_123527/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_path_extraction_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `skeleton_path_report.md` | very small-sample path extraction 报告和人工看图重点 |
| `skeleton_path_summary.csv` | 每个样本的 component / endpoint / branch / path segment 指标 |
| `skeleton_path_manifest.csv` | path overlay 图 manifest |
| `font_skeleton_path_extraction/path_extraction_uXXXX_style.png` | font mask、raw skeleton、cleaned skeleton、candidate path segments 对比图 |

可写结论：`山/kaishu`、`人/kaishu`、`山/lishu` 是较低风险的 font-derived trajectory trial 候选；`中/kaishu` 分叉较多，`永/lishu` 多连通分量，仍需人工看图确认。该实验不含真实笔顺恢复，不生成正式 `trajectory.csv`，不替换默认 MakeMeAHanzi median pipeline。
## 2026-06-19 Font-derived trajectory trial

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_derived_trajectory_trial_20260619_125428/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_derived_trajectory_trial_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `font_derived_trial_report.md` | 三个低风险样本的 trial 报告和人工看图问题 |
| `font_derived_trial_summary.csv` | segment / point / path length / warning 指标 |
| `font_derived_trial_manifest.csv` | 子目录、trial CSV 和 compare 图索引 |
| `u5c71_kaishu/font_derived_trial_trajectory.csv` | 山/kaishu trial CSV |
| `u4eba_kaishu/font_derived_trial_trajectory.csv` | 人/kaishu trial CSV |
| `u5c71_lishu/font_derived_trial_trajectory.csv` | 山/lishu trial CSV |
| `font_derived_trajectory_trial/*_compare.png` | MakeMeAHanzi median、font mask、raw/clean skeleton、path segments、trial trajectory 对比图 |

可写结论：`人/kaishu` 是最干净的 font-derived trajectory trial 候选，`山/lishu` 显示比 MakeMeAHanzi median 更强的隶书字体轮廓信号，`山/kaishu` 则提示 candidate order 仍不是真实笔顺。该实验只用于判断 font-outline basis 是否值得继续，不生成正式 `trajectory.csv`，不接 execution/robot pipeline。
# 2026-06-19 Font skeleton stroke ordering / simplification prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_stroke_ordering_20260619_132543/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_stroke_ordering_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `font_skeleton_ordering_report.md` | 两个极小样本的 stroke ordering / simplification 报告 |
| `font_skeleton_ordering_summary.csv` | raw -> simplified segment 指标 |
| `font_skeleton_ordering_manifest.csv` | ordered trial CSV 与 compare 图索引 |
| `u4eba_kaishu/font_skeleton_ordered_trial_trajectory.csv` | 人/kaishu candidate writable order CSV |
| `u5c71_lishu/font_skeleton_ordered_trial_trajectory.csv` | 山/lishu candidate writable order CSV |
| `font_skeleton_stroke_ordering_index.md` | 本轮固定入口 |

可写结论：`人/kaishu` 从 4 个 raw trial segments 简化为 2 个 stroke-like candidates，适合作为下一步 font-derived execution mock 的首个低风险候选；`山/lishu` 保持 4 个 stroke-like candidates，更强调保留隶书轮廓风格而不是强行连成一笔。本轮不是真实笔顺恢复，不是正式轨迹，不生成正式 `trajectory.csv`，不接默认 pipeline 或机器人接口。

# 2026-06-19 Median-to-font skeleton alignment / adaptation prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/median_font_alignment_20260619_145307/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/median_font_alignment_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `median_font_alignment_report.md` | B 路线 median + font skeleton adaptation 报告 |
| `median_font_alignment_summary.csv` | alpha=0.25/0.5 projection distance 与 shift 指标 |
| `median_font_alignment_manifest.csv` | trial CSV 与 compare 图索引 |
| `u4eba_kaishu/adapted_trial_alpha_025.csv` | 人/kaishu alpha=0.25 trial CSV |
| `u4eba_kaishu/adapted_trial_alpha_050.csv` | 人/kaishu alpha=0.5 trial CSV |
| `u5c71_lishu/adapted_trial_alpha_025.csv` | 山/lishu alpha=0.25 trial CSV |
| `u5c71_lishu/adapted_trial_alpha_050.csv` | 山/lishu alpha=0.5 trial CSV |

可写结论：`人/kaishu` 保持两笔结构且 projection distance 明显下降，是 B 路线的低风险正例；`山/lishu` projection distance 也下降，但全局 bbox aspect 没有朝 lishu 字体宽底形态靠近，说明最近邻吸附不足以解决隶书结构适配，下一步需要 stroke-level bbox / anchor alignment。该实验不是正式轨迹，不恢复真实笔顺，不接默认 pipeline 或机器人接口。

# 2026-06-19 Median-font adaptation v2 prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/median_font_adaptation_v2_20260619_154351/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/median_font_adaptation_v2_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `median_font_adaptation_v2_report.md` | B 路线 v2：global bbox alignment + stroke-level anchor alignment 报告 |
| `median_font_adaptation_v2_summary.csv` | before / v1 / v2 projection distance、aspect gap、shift、path length ratio 指标 |
| `median_font_adaptation_v2_manifest.csv` | v2 trial CSV 与 compare 图索引 |
| `u4eba_kaishu/adapted_v2_conservative.csv` | 人/kaishu conservative trial CSV |
| `u4eba_kaishu/adapted_v2_stronger.csv` | 人/kaishu stronger trial CSV |
| `u5c71_lishu/adapted_v2_conservative.csv` | 山/lishu conservative trial CSV |
| `u5c71_lishu/adapted_v2_stronger.csv` | 山/lishu stronger trial CSV |

可写结论：`人/kaishu` 在 v2 中 projection distance 与 aspect gap 都较 v1 小幅改善，stroke_count 保持 2；`山/lishu` projection distance 明显下降，但 aspect gap 只是回到接近原 median，没有明显逼近 lishu font aspect，说明 global bbox + anchor alignment 仍不足以解决隶书宽底结构适配。该实验仍是 diagnostic prototype，不生成正式 `trajectory.csv`，不接默认 pipeline 或机器人接口。

# 2026-06-19 Lishu structure adaptation v3 prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/lishu_structure_adaptation_v3_20260619_155525/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/lishu_structure_adaptation_v3_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `lishu_structure_v3_report.md` | `山/lishu` structure-constrained adaptation v3 报告 |
| `lishu_structure_v3_summary.csv` | v2 stronger vs v3 projection、aspect、lower-half width、shift、path length ratio 指标 |
| `lishu_structure_v3_manifest.csv` | v3 trial CSV 与 compare 图索引 |
| `u5c71_lishu/lishu_structure_v3_conservative.csv` | 山/lishu conservative structure trial CSV |
| `u5c71_lishu/lishu_structure_v3_stronger.csv` | 山/lishu stronger structure trial CSV |
| `u5c71_lishu/lishu_structure_v3_compare.png` | original median / lishu font / v2 / v3 conservative / v3 stronger 对比图 |

可写结论：v3 显式加入下半部横向支撑和左右外展后，`山/lishu` 的 lower-half width 与 bbox aspect 相比 v2 有小幅改善，说明隶书结构适配确实需要 structure-level constraints。但 v3 仍触达 shift cap，aspect 仍远低于字体轮廓，不能直接接默认 pipeline；下一步应人工看图后考虑 component-level alignment。

# 2026-06-19 Lishu component-level alignment prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/lishu_component_alignment_20260619_160805/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/lishu_component_alignment_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `lishu_component_alignment_report.md` | `山/lishu` component-level alignment 报告 |
| `lishu_component_alignment_summary.csv` | v3 vs component conservative / stronger 指标 |
| `lishu_component_alignment_manifest.csv` | component trial CSV 与 compare 图索引 |
| `u5c71_lishu/lishu_component_alignment_conservative.csv` | 山/lishu component conservative trial CSV |
| `u5c71_lishu/lishu_component_alignment_stronger.csv` | 山/lishu component stronger trial CSV |
| `u5c71_lishu/lishu_component_alignment_compare.png` | original median / lishu font / v2 / v3 / component variants 对比图 |

可写结论：component-level alignment 相比 v3 对 bbox aspect 和 lower-half width 有小幅改善，conservative 的 projection distance 也略低于 v3；但 stronger 的 projection distance 反而升高，且两个 component variant 都触达 24px shift cap。该结果说明下一步更值得改进 component group 与字体 target 的定义，而不是继续增大 alpha。本轮仍是 diagnostic prototype，不生成正式 `trajectory.csv`，不接默认 pipeline 或机器人接口。

# 2026-06-19 Trajectory style route decision report

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/trajectory_style_route_decision_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md` | A/B/C 三条轨迹风格路线的证据整理与决策报告 |
| `experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json` | 机器可读路线状态、推荐用途和下一步选项 |

路线状态：

| route | recommended status | decision |
|---|---|---|
| A | stable baseline / robot backbone | 保留为默认系统链路和 dry-run robotics backbone |
| B | safe style adaptation research direction | 作为保留笔顺的有限风格适配研究方向 |
| C | style basis research only | 作为小样本人工筛选的字体风格基底探索，不接默认 pipeline |

可写结论：当前不宜继续盲目调 connector/taper，也不宜直接把 font skeleton derived path 接入默认 pipeline。下一阶段推荐先写 hybrid route design spec：A 提供笔顺、可写性、执行层和机器人 precheck 链路；B 提供有边界的形态适配；C 提供人工筛选的字体轮廓风格参考。该报告只做路线决策整理，不新增算法、不调参数、不接 API/CoppeliaSim/AUBO/SDK。

# 2026-06-19 Hybrid style trajectory design spec

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/hybrid_style_trajectory_design_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md` | hybrid route 架构、模块职责、接口边界和候选 prototype |
| `experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json` | 机器可读模块契约、robot pipeline entry rule 和 H1/H2/H3 方案 |

核心设计：

```text
A: stable median trajectory, stroke order, execution and robot precheck backbone
B: bounded adaptation, trial-only, preserves stroke_count and stroke_order
C: font reference / candidate basis, manually screened, does not directly replace A
Human audit gate: required before visual style claims or prototype promotion
```

推荐下一步：优先做 H2（A median + C font reference constraints only），即先把字体轮廓/骨架证据整理成可审计的约束包，不移动轨迹点、不生成正式 `trajectory.csv`、不接默认 pipeline。H1（A+B bounded adaptation）可在 H2 明确哪些参考可信后再做；H3 适合论文图和限制说明。

边界：该 spec 只做方案设计和接口整理，不新增算法、不调参数、不调用 API、不连接 CoppeliaSim/AUBO/SDK、不生成新轨迹。

# 2026-06-19 H2 font reference constraints package

源输出目录：

```text
experiments/llm_style_trajectory/outputs/font_reference_constraints_20260619_230426/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `font_reference_constraints_report.md` | H2 约束包报告与下一步 B adaptation 建议 |
| `font_reference_constraints.json` | 机器可读字体参考约束包，状态为 `reference_constraints_only_not_used_by_default` |
| `font_reference_constraints.csv` | 每条字体参考约束一行 |
| `font_reference_constraints_summary.csv` | 每个 char/style 样本一行 |
| `font_reference_constraints_manifest.csv` | 约束可视化图 manifest |
| `figures/constraint_reference_uXXXX_style.png` | font mask、skeleton、bbox/lower-half/左右极值约束图 |

处理范围：`山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`中/lishu`、`永/lishu`、`风/lishu`。本轮不处理 xingkai，也不处理德、福、国。

约束统计：

| recommended_use | count |
|---|---:|
| usable_for_adaptation | 25 |
| visual_reference_only | 25 |
| unsafe_for_direct_use | 34 |

可写结论：H2 只整理 C 路线字体参考证据，不移动 A 路线 median 轨迹点。`bbox_aspect`、`lower_half_width_ratio`、`left_right_spread` 和极小幅度的 `bbox_center_shift_x/y` 可作为未来 B adaptation 的 bounded hints；skeleton endpoint/branch/component/complexity 只作为视觉审计信号；raw skeleton path 和 unordered skeleton segments 明确不安全，不能直接驱动轨迹变形。该结果不接默认 pipeline，不生成正式 `trajectory.csv`，不接 execution、workspace、CoppeliaSim 或 AUBO 链路。

# 2026-06-19 H1-lite constraint-bounded median adaptation prototype

源输出目录：

```text
experiments/llm_style_trajectory/outputs/constraint_bounded_adaptation_h1_lite_20260619_231903/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/constraint_bounded_adaptation_h1_lite_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `h1_lite_report.md` | H1-lite 诊断报告 |
| `h1_lite_summary.csv` | 两个样本的 conservative / balanced 指标汇总 |
| `h1_lite_manifest.csv` | trial CSV、summary JSON 和 compare 图索引 |
| `u4eba_kaishu/h1_lite_compare.png` | 人/kaishu original median、H2 reference、conservative、balanced 对比图 |
| `u5c71_lishu/h1_lite_compare.png` | 山/lishu original median、H2 reference、conservative、balanced 对比图 |

处理范围：只处理 `人/kaishu` 与 `山/lishu`。本轮不处理 xingkai、复杂字、execution、workspace、CoppeliaSim 或 AUBO。

关键指标：

| char/style | bbox aspect median -> conservative -> balanced | lower-half width median -> conservative -> balanced | max shift conservative / balanced |
|---|---:|---:|---:|
| 人/kaishu | 1.414861 -> 1.402621 -> 1.392189 | 215.040000 -> 214.046706 -> 213.207647 | 1.056528 / 1.776407 px |
| 山/lishu | 0.945007 -> 0.998870 -> 1.048676 | 187.343097 -> 193.898937 -> 199.553901 | 5.461121 / 9.845336 px |

可写结论：H1-lite 使用 H2 的 `usable_for_adaptation` 约束做 bounded median adaptation，不使用 raw skeleton path、unordered skeleton segments 或最近点 skeleton pulling。`山/lishu` 在未触达 shift cap 的情况下朝字体参考的宽底方向移动，说明 H2 约束可以作为更安全的 B route 输入。该结果仍是 trial-only，不生成正式 `trajectory.csv`，不接默认 pipeline，不接 execution/robot 链路，需要人工看图后再决定是否扩展。

# 2026-06-19 H1-lite style contrast expansion

源输出目录：

```text
experiments/llm_style_trajectory/outputs/h1_lite_style_contrast_20260619_234043/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/h1_lite_style_contrast_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `h1_lite_style_contrast_report.md` | 山/kaishu vs 山/lishu H1-lite 对照报告 |
| `h1_lite_style_contrast_summary.csv` | kaishu / lishu 指标汇总 |
| `h1_lite_style_contrast_manifest.csv` | 样本图、summary 和对照图索引 |
| `u5c71_kaishu/h1_lite_compare.png` | 新增山/kaishu H1-lite compare 图 |
| `contrast/h1_lite_u5c71_kaishu_lishu_contrast.png` | 山/kaishu 与山/lishu 同字不同风格对照图 |
| `contrast/h1_lite_u5c71_style_gap_summary.json` | style gap before/after JSON |

关键指标：

| style | bbox aspect median -> conservative -> balanced | lower-half width median -> conservative -> balanced | max shift balanced | path ratio balanced |
|---|---:|---:|---:|---:|
| 山/kaishu | 0.945007 -> 0.965779 -> 0.984478 | 187.343097 -> 190.213398 -> 192.664933 | 4.341142 px | 0.996284 |
| 山/lishu | 0.945007 -> 0.998870 -> 1.048676 | 187.343097 -> 193.898937 -> 199.553901 | 9.845336 px | 0.989006 |

Style gap：

| metric | before | after conservative | after balanced |
|---|---:|---:|---:|
| bbox_aspect_gap | 0.000000 | 0.033091 | 0.064198 |
| lower_half_width_gap | 0.000000 | 3.685539 | 6.888968 |

可写结论：新增 `山/kaishu` 后，同字不同风格 gap 被拉开；kaishu 的 H1-lite 变化更保守，lishu 的 H1-lite 变化更明显。该结果支持 H1-lite 作为 bounded hybrid adaptation 的下一步候选，但仍需人工看 `h1_lite_u5c71_kaishu_lishu_contrast.png` 判断楷书是否未被过度拉伸、隶书是否确实更宽底。当前仍是 trial-only，不接默认 pipeline。

# 2026-06-20 Hybrid section refinement v1

源输出目录：

```text
experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/hybrid_section_refinement_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `hybrid_section_refinement_report.md` | `风/lishu` hybrid section refinement 报告 |
| `hybrid_section_refinement_summary.csv` | 单样本 conservative / balanced 指标汇总 |
| `hybrid_section_refinement_manifest.csv` | summary / compare / trial csv 索引 |
| `u98ce_lishu/hybrid_section_compare.png` | original median、font sections、median section labels、conservative、balanced 对比图 |

关键指标：

| sample | section_source | section_names | bbox_aspect median -> conservative -> balanced | lower_half_width median -> conservative -> balanced | max_shift conservative / balanced | path_ratio conservative / balanced |
|---|---|---|---:|---:|---:|---:|
| 风/lishu | `top_mid_bottom_fallback` | `top_band / mid_band / bottom_band` | 1.188427 -> 1.259425 -> 1.306963 | 215.040000 -> 219.856896 -> 223.297536 | 5.543559 / 8.824495 px | 0.982155 / 0.973699 |

可写结论：本轮 hybrid section refinement 没有得到足够稳定的 font component bbox，因此实际使用的是 `top/mid/bottom` fallback。即便如此，它仍在比 H1-lite 更局部的约束下，继续把 `风/lishu` 朝宽底方向轻微推进，同时没有触发高 shift 或明显 path collapse。这说明 section-level refinement 比之前更激进的 v3/component-level 更适合作为复杂 lishu 的下一步整理方向；但由于本轮未真正验证 component-first 收益，下一步更适合先整理 section 约束包，或先在 `山/lishu` 这类稳定样本上复现相同流程，而不是继续扩字。

# 2026-06-21 Section constraints package / fallback guide

源输出目录：

```text
experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/
```

固定入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/section_constraints_package_index.md
```

主要文件：

| 文件 | 内容 |
|---|---|
| `section_constraints_package_report.md` | section 约束封装与 fallback guide |
| `section_constraints_package.json` | machine-readable 约束包 |
| `section_constraints_package.csv` | 每个样本一行的约束汇总 |
| `section_constraints_package_manifest.csv` | 摘要与图路径 manifest |
| `figures/section_constraints_uXXXX_style.png` | 约束示意图 |

关键规则：

- component bbox stable 时：优先 component-first，只做轻量 bbox 对齐和 section anchor 对齐。
- component bbox 不稳定时：回退 `top/mid/bottom` fallback，并记录 `fallback_used=true`。
- usable constraints：`bbox_aspect`、`lower_half_width_ratio`、`left_right_spread`、`bbox_center_shift_x/y`。
- reference-only constraints：`component_count`、`endpoint_count`、`branch_count`。
- unsafe constraints：`raw_skeleton_path`、`unordered_skeleton_segments`。

样本级总结：

| sample | section_source | fallback_used | recommended_next_use |
|---|---|---|---|
| 山/kaishu | component_bbox | False | B_safe_input |
| 山/lishu | component_bbox | False | B_safe_input |
| 风/lishu | top_mid_bottom_fallback | True | fallback_first_reference_only |

可写结论：section constraints package 不是新算法，而是把 section-level 证据整理成可复用约束包，方便后续 B 路线调用。当前最安全的做法是把 `山/kaishu`、`山/lishu` 当作 B 路线的安全输入，把 `风/lishu` 当作 fallback-first 参考样本；不要把不稳定的 component bbox 或 raw skeleton 直接接入默认生成流程。


# 2026-06-21 B-route constraint registry / gated probe

源输出目录：

`	ext
experiments/llm_style_trajectory/outputs/b_route_constraint_registry_20260621_012544/
experiments/llm_style_trajectory/outputs/b_route_registry_probe_20260621_012330/
`

固定入口：

`	ext
experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md
`

可写结论：B route now uses a registry-gated adaptation entry point. H2 font-reference constraints and section constraints are unified into a read-only evidence pack; raw skeleton paths remain blocked. The small probe only covers 山/lishu and 风/lishu, stays trial-only, and is not used by default.



# 2026-06-21 B-route handoff note

- docs: `experiments/llm_style_trajectory/docs/b_route_handoff_note.md`
- json: `experiments/llm_style_trajectory/configs/b_route_handoff_note.json`
- status: B route remains registry-gated, trial-only, and not used by default.

## B-route 中文图与差异辅助

源目录：

```text
experiments/llm_style_trajectory/outputs/b_route_visuals_cn_*/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `b_route_visuals_cn_index.md` | 中文重绘入口 |
| `h1_lite_u5c71_kaishu_lishu_contrast_cn.png` | 山/楷书 vs 山/隶书中文对照 |
| `h1_lite_u98ce_lishu_risk_contrast_cn.png` | 风/隶书风险试验中文图 |
| `hybrid_section_compare_cn.png` | 风/隶书 section refinement 中文图 |
| `b_route_visuals_cn_report.md` | 哪张图差异仍弱、哪张更适合人工判断 |

## B-route visual conclusion freeze

固定资料：

| 文件 | 内容 |
|---|---|
| `b_route_visual_conclusion_freeze_index.md` | 三张关键中文图的冻结定位入口 |
| `b_route_visual_conclusion_freeze_note.md` | 正文候选 / 补充材料 / 风险图的人工结论固定页 |
| `b_route_visual_conclusion_freeze_note.json` | 机器可读的 figure role 冻结摘要 |

## A-route showcase / 跨笔过渡控制展示包

固定资料：

| 文件 | 内容 |
|---|---|
| `a_route_showcase_index.md` | A-route 大样本展示包入口 |
| `a_route_style_overview_grid.png` | kaishu / xingkai / lishu 基础风格总览 |
| `a_route_modifier_control_overview.png` | modifier 控制总览，重点为跨笔过渡和宽扁形态 |
| `a_route_execution_display_grid.png` | width / pressure / connector / pen-up 的 execution layer 展示 |
| `a_route_behavior_control_compare.png` | 抬笔过渡 / 弱连续过渡 / 连续带笔过渡行为对比 |
| `a_route_visual_audit_checklist.md` | 人工目检样本册 |

可写结论：本轮把 connector / 连笔重新定位为自然语言驱动的跨笔过渡控制和 execution 行为控制，不把它作为真实行楷风格迁移成功的证据。
