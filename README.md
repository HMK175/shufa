# 书法机器人轨迹生成项目

## 当前路线

本项目当前主线位于：

```text
experiments/llm_style_trajectory/
```

当前研究重点是：将自然语言书写意图转换为结构化风格计划，再由本地确定性工具生成可解释的书法机器人轨迹，并逐步映射到 CoppeliaSim、AUBO i5 dry-run 接口准备层与 IK feasibility 前检查层。

核心链路：

```text
自然语言输入
-> LLM/mock planner
-> request boundary validation
-> style_modifiers
-> style profile + 本地白名单映射
-> Make Me a Hanzi median 笔画
-> trajectory.csv
-> execution_trajectory.csv
-> robot_workspace_trajectory.csv
-> robot_workspace_trajectory_resampled.csv
-> CoppeliaSim standard pen-tip/sphere scene playback
-> robot_target_poses.csv
-> AUBO i5 dry-run command plan
-> AUBO i5 IK feasibility dry-run
```

关键原则：LLM 不直接生成 CSV、轨迹点或机器人命令。LLM 只负责自然语言解析、风格选择、约束和 modifier 规划；轨迹和机器人接口准备均由本地确定性工具生成。

当前 AUBO i5 相关结果仍是离线 dry-run：不连接真实机械臂，不调用 SDK 运动命令，不求真实 IK，不判断关节限位、碰撞或奇异位形。

## 新对话入口

切换新对话或新代码线程时，先读：

```text
CURRENT_PROJECT_GUIDE.md
experiments/llm_style_trajectory/README.md
experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md
```

## 当前可信记录

| 文件 | 用途 |
|---|---|
| `CURRENT_PROJECT_GUIDE.md` | 当前路线接手指南 |
| `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md` | 阶段总结与论文定位 |
| `PROJECT_LOG.md` | 项目进展日志 |
| `EXPERIMENT_RECORD.md` | 实验记录 |
| `AUBO_I5_PLATFORM_NOTES.md` | AUBO i5 平台资料 |
| `ROBOT_TEST_PLAN.md` | 机器人测试计划 |
| `THESIS_FRAMEWORK_2026.md` | 论文结构框架 |

## 旧路线归档

早期“图像骨架提取 + 强化学习局部优化”路线文档已归档到：

```text
docs/legacy_image_skeleton_rl_route/
```

旧路线代码已归档到：

```text
code/legacy_image_skeleton_rl_route/
```

`code/data/makemeahanzi/` 保留在 `code/` 下，作为当前路线仍可能读取的共享数据。
这些文件保留为历史资料，不作为当前实验主线的优先依据。

## 常用验证

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
Test-Path code\legacy_image_skeleton_rl_route\scripts\stroke.py
Test-Path code\legacy_image_skeleton_rl_route\scripts\pipeline.py
Test-Path code\data\makemeahanzi\graphics.txt
```
