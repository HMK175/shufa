# Current Project Guide

记录日期：2026-06-22

## 1. 一句话定位

当前默认主线是 `experiments/llm_style_trajectory`：  
用 LLM/mock planner 解析自然语言书写意图，通过受控 `style_modifiers` 和本地确定性轨迹工具生成参数化书法轨迹，并完成 execution layer、workspace、retiming、CoppeliaSim dry-run 与 AUBO i5 dry-run precheck。

## 2. 新线程优先阅读

新对话或新代码线程请按顺序阅读：

1. `CURRENT_PROJECT_GUIDE.md`
2. `AGENTS.md`
3. `experiments/llm_style_trajectory/README.md`
4. `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`
5. `AUBO_I5_PLATFORM_NOTES.md`
6. `ROBOT_TEST_PLAN.md`

需要完整背景时再读：

```text
LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
PROJECT_LOG.md
EXPERIMENT_RECORD.md
```

## 3. 当前默认主线链路

```text
用户自然语言
-> planner.py
-> request boundary validation
-> style_modifiers.py
-> style profile + brush profile
-> Make Me a Hanzi medians
-> trajectory_tools.py
-> trajectory.csv
-> execution_tools.py
-> execution_trajectory.csv
-> workspace_mapping.py
-> robot_workspace_trajectory.csv
-> workspace_resampling.py
-> robot_workspace_trajectory_resampled.csv
-> coppeliasim/play_workspace_path.py
-> CoppeliaSim standard pen-tip/sphere scene
-> robot_target_poses.py
-> robot_target_poses.csv
-> aubo_i5_command_adapter.py
-> aubo_i5_command_plan.csv / aubo_i5_safety_check.json
-> aubo_i5_ik_feasibility.py
-> aubo_i5_ik_feasibility_summary.json / report.md / points.csv
```

## 4. 当前路线状态

- **A-route**：`MakeMeAHanzi median + style profile`  
  当前稳定主线，也是 execution / robot dry-run backbone。

- **B-route**：`median + font reference / section constraints adaptation`  
  当前为 registry-gated、trial-only、not used by default。

- **C-route**：`font skeleton / font-derived path evidence`  
  当前只作为小样本、人工筛选的风格证据路线，不接默认 pipeline。

## 5. 图像到笔画路线边界

图像到笔画 / 书写行为恢复路线，**当前不是这个默认主线线程的推进方向**。

在当前默认主线线程里，它只用于：

- 后续结果对比
- 图像 / 指标复核
- 论文中的相关讨论、局限性或未来工作说明

但这条边界**只约束当前默认主线线程**，并**不限制未来单独开设的图像到笔画专责线程**。  
如果未来明确开设独立线程专门负责图像到笔画 / 书写行为恢复，那么那个线程可以把它作为独立研究路线推进。

为了避免误导：

- 当前主线线程：不要把这条路线混入 A-route / B-route 的默认开发决策
- 独立图像线程：可以单独推进该路线，不必受本条“comparison-only”限制

对应说明页：

```text
experiments/llm_style_trajectory/docs/image_to_stroke_comparison_only_note.md
```

## 6. 人工看图规则

对于轨迹图、渲染图、风格对比图、CoppeliaSim 截图等结果，不能只看指标就默认效果好。  
如果数据层看起来正常，但图像直观效果可能不佳，请明确提示用户进行人工目检。

尤其是下面这些判断，优先以图像直观效果和人工校验为准：

- 风格差异是否明显
- 连笔是否自然
- 笔画宽度 / 压力变化是否可见
- 布局是否自然

数值指标只作为辅助证据。

## 7. 当前工作边界

- 当前不是完整真实书法风格学习
- 当前不是 LLM 直接生成轨迹
- 当前不处理任意真实书法图像输入进入默认主线
- 当前 CoppeliaSim 仍是 pen-tip/sphere scene，不含真实机械臂 IK
- 当前 AUBO i5 只做到 dry-run command plan 和 IK feasibility dry-run，不连接实机，不调用 SDK 运动命令
- 历史 AUBO IP 只作为线索，不作为默认配置

## 8. `code/` 目录边界

当前 `code/` 已整理为共享数据与旧路线归档：

```text
code/
├── README.md
├── data/
│   └── makemeahanzi/
└── legacy_image_skeleton_rl_route/
    ├── README.md
    ├── scripts/
    ├── models/
    ├── lists/
    └── artifacts/
```

当前主线仍可能读取：

```text
code/data/makemeahanzi/graphics.txt
```

旧的 `stroke.py`、`pipeline.py`、图像骨架 / RL / 训练预测脚本都已归档到：

```text
code/legacy_image_skeleton_rl_route/scripts/
```

默认不要把新实验脚本放到 `code/` 根目录，新实验优先放在：

```text
experiments/llm_style_trajectory/
```

## 9. 旧路线归档

早期“图像骨架提取 + 强化学习局部优化”相关文档已归档到：

```text
docs/legacy_image_skeleton_rl_route/
```

这些内容是历史资料，不再作为当前主线依据。

## 10. 当前重要入口

### Thesis framework

```text
THESIS_FRAMEWORK_2026.md
experiments/llm_style_trajectory/docs/thesis_mini_paper_positioning_note.md
```

当前大论文定稿题目（2026-07-01）：

```text
机器人书写目标字图像生成与轨迹恢复研究
```

注意：

- 上述两份文档记录的是**当前推荐的大论文章节结构与小论文定位**
- 它们不改变本线程的默认开发边界
- 当前默认主线依然是 `experiments/llm_style_trajectory`
- 图像到笔画 / 风格图像生成仍建议由独立线程分别推进

### Route decision

```text
experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md
experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json
experiments/llm_style_trajectory/outputs/paper_figures/trajectory_style_route_decision_index.md
```

### Hybrid route design

```text
experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md
experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json
experiments/llm_style_trajectory/outputs/paper_figures/hybrid_style_trajectory_design_index.md
```

### B-route handoff

```text
experiments/llm_style_trajectory/docs/b_route_handoff_note.md
experiments/llm_style_trajectory/configs/b_route_handoff_note.json
experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md
```

### B-route visual freeze

```text
experiments/llm_style_trajectory/docs/b_route_visual_conclusion_freeze_note.md
experiments/llm_style_trajectory/configs/b_route_visual_conclusion_freeze_note.json
experiments/llm_style_trajectory/outputs/paper_figures/b_route_visual_conclusion_freeze_index.md
```

## 11. 常用验证

运行当前主线测试：

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
```

检查共享数据与旧路线归档：

```powershell
Test-Path code\legacy_image_skeleton_rl_route\scripts\stroke.py
Test-Path code\legacy_image_skeleton_rl_route\scripts\pipeline.py
Test-Path code\data\makemeahanzi\graphics.txt
```

查看论文图表索引：

```text
experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md
```
