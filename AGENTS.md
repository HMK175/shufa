# 书法机器人项目接手说明

## 当前主线

当前项目默认主线已经从早期的“图像骨架提取 + 强化学习局部优化”切换到：

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

主线代码位于：

```text
experiments/llm_style_trajectory/
```

## 新对话优先阅读

切换新对话或新代码线程时，优先阅读：

1. `CURRENT_PROJECT_GUIDE.md`
2. `experiments/llm_style_trajectory/README.md`
3. `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`
4. `AUBO_I5_PLATFORM_NOTES.md`
5. `ROBOT_TEST_PLAN.md`

如需追溯完整实验过程，再读：

```text
LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
PROJECT_LOG.md
EXPERIMENT_RECORD.md
```

## 旧路线归档

早期路线文档已经归档到：

```text
docs/legacy_image_skeleton_rl_route/
```

这些文档记录旧的“图像骨架提取 + RL 优化”思路。除非要追溯项目早期方案，否则不要把它们作为当前路线依据。

旧路线代码也已归档到：

```text
code/legacy_image_skeleton_rl_route/
```

`code/data/makemeahanzi/` 是当前路线仍可能使用的共享数据，不要移动。

## 图像到笔画路线边界

图像到笔画 / 书写行为恢复路线目前**不是这个默认主线线程的推进方向**。

在当前默认主线线程里，它只用于：

- 后续结果对比
- 图像 / 指标复核
- 论文中的相关讨论、局限性或未来工作说明

但这条限制**只约束当前默认主线线程**。  
如果未来明确开设“图像到笔画 / 书写行为恢复”的独立专责线程，则该线程可以把它作为独立研究路线推进，不受本条限制。

换句话说：

- 当前线程：不要把它混入 A-route / B-route 的默认开发决策
- 独立图像线程：可以单独负责这条路线

## 人工看图规则

对于轨迹图、渲染图、风格对比图、CoppeliaSim 截图等结果，不能只看指标就默认效果好。  
如果数据层看起来正常，但图像直观效果可能不佳，请明确提示用户进行人工目检。

风格差异、连笔外观、笔画宽度、布局自然度这类判断，优先以图像直观效果和人工校验为准，数值指标只作为辅助证据。

## 工作边界

- 默认不要修改 `code/legacy_image_skeleton_rl_route/scripts/stroke.py` /
  `code/legacy_image_skeleton_rl_route/scripts/pipeline.py`
- 默认不要在 `code/` 根目录新增新实验脚本
- 当前实验新增内容优先放在 `experiments/llm_style_trajectory/`
- LLM/API planner 不直接生成 CSV、轨迹点或机器人命令
- AUBO i5 相关工作当前只做到 dry-run command plan 和 IK feasibility dry-run；不要连接真实机械臂，不要求真实 IK，不要调用 SDK 运动命令
- 不要打印、记录或提交 API key

## 常用验证

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
Test-Path code\legacy_image_skeleton_rl_route\scripts\stroke.py
Test-Path code\legacy_image_skeleton_rl_route\scripts\pipeline.py
Test-Path code\data\makemeahanzi\graphics.txt
```
