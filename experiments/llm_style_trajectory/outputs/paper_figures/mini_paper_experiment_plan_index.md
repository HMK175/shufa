# Mini-paper experiment plan index

## 固定入口

| 文件 | 内容 |
|---|---|
| `experiments/llm_style_trajectory/docs/mini_paper_experiment_plan.md` | 小论文实验对比方案、外部功能对比表、最小实验清单 |
| `experiments/llm_style_trajectory/configs/mini_paper_experiment_matrix.json` | 可机器读取的实验矩阵与论文图表清单 |

## 建议论文主线

```text
自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法
```

当前可写成“自然语言约束 + 可解释 style modifiers + 参数化轨迹 + execution/workspace/robot dry-run 检查链条”。不要写成真实书法风格学习、真实机器人书写或真实 AUBO i5 IK 已完成。

## 推荐主实验

| id | 实验 | 状态 | 优先级 |
|---|---|---|---:|
| A | 自然语言 modifier 可控性 | 部分已有，需固定论文图 | 1 |
| B | 行楷 connector rule baseline / conservative / balanced 对比 | 已有，需补人工评价表 | 1 |
| C | execution width / pressure 对比 | 已有 | 2 |
| D | motion continuity 与 retiming | 已有 | 1 |
| E | robot-interface precheck chain | 已有，限 dry-run 表述 | 2 |
| F | font outline gap / style profile 数据化诊断 | 分析已有，建议放限制与未来工作 | 3 |

## 已有关联入口

| 方向 | 入口 |
|---|---|
| 行楷 balanced v2 | `experiments/llm_style_trajectory/outputs/paper_figures/xingkai_balanced_experiment_index.md` |
| width / pressure | `experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md` |
| execution refinement | `experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md` |
| motion continuity | `experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md` |
| target pose retiming | `experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md` |
| CoppeliaSim tool model | `experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md` |
| AUBO command adapter smoothed | `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md` |
| AUBO IK feasibility smoothed | `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md` |
| font style gap | `experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md` |
| Phase 1 readonly estimates | `experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md` |
| Phase 1 comparison | `experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md` |

## 最小下一步

1. 固定 modifier controllability 三联图。
2. 固定 xingkai connector baseline / candidate_default_v1 / candidate_default_v2 对比图和人工评价表。
3. 固定 execution width/pressure 图。
4. 固定 raw vs smoothed target poses 指标表。
5. 固定外部方法功能对比表。

## 边界说明

本索引用于小论文实验方案整理，不新增算法，不替换全局默认 style profile，不调用 API，不连接 CoppeliaSim/AUBO i5，不做真实 IK 或机器人控制。
