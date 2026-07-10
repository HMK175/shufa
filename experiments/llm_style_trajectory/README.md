# LLM 风格轨迹实验

这是当前主线的独立实验模块。它不修改、不调用已经归档到
`code/legacy_image_skeleton_rl_route/scripts/` 的旧图像骨架流程。

## 阶段总结

最新的中文总览在：

```text
../../LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
```

该文件汇总了当前方法主线、关键输出路径、DeepSeek planner 鲁棒性结果，以及三类 style modifier 消融实验：

- 连笔控制：`none / weak / normal`
- 形态控制：`normal / flatter / wider`
- 圆滑度控制：`medium / high / low`

当前推荐图：

- `outputs/batch_20260611_210502/modifier_ablation_u5c71.png`
- `outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png`
- `outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png`

机器人接口 dry-run 输出的索引：

- `outputs/paper_figures/aubo_i5_command_adapter_index.md`
- `outputs/paper_figures/aubo_i5_ik_feasibility_index.md`
- `outputs/paper_figures/motion_continuity_check_index.md`
- `outputs/paper_figures/target_pose_retiming_index.md`
- `outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md`
- `outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md`

这些都只是离线准备层：不求真实 IK，不连接 AUBO i5，不 import 或执行 SDK，也不发送机器人命令。

target pose 完成 retiming 后，后续机器人接口准备推荐使用
`robot_target_poses_smoothed.csv`。原始 `robot_target_poses.csv` 保留为
before-retiming 对照输入。

对于轨迹图、渲染对比图、CoppeliaSim 截图等图像型结果，不能只靠数值指标判断效果。如果结果数值正常但视觉上可能不自然，需要明确标记为需要人工目检，并记录到实验说明中。

planner 是自然语言入口，只输出结构化 plan。它不生成 CSV 行、轨迹点或机器人命令。轨迹由本地确定性工具生成，输入来源包括：

1. `code/data/makemeahanzi/graphics.txt` 中的 Make Me a Hanzi median 笔画。
2. 数值化 style profile。
3. `trajectory_tools.py`。

## 规划器模式

- `mock`：默认规则 planner。确定性执行，不需要网络。
- `api`：DeepSeek chat-completions planner。读取
  `LLM_STYLE_PLANNER_API_KEY`、`LLM_STYLE_PLANNER_ENDPOINT` 和
  `LLM_STYLE_PLANNER_MODEL`。默认 endpoint 为
  `https://api.deepseek.com/chat/completions`，默认 model 为
  `deepseek-v4-pro`。
- `local`：预留给后续本地模型 planner 的接口。目前只检查
  `LLM_STYLE_PLANNER_LOCAL_CMD`，本实验中不会启动本地模型。

如果选择 `api` 或 `local` 但未配置，planner 会返回友好的 validation error。只有显式传入 `--fallback-to-mock` 时，才会回退到规则 planner。

## 计划结构契约

计划中的 LLM prompt 和 schema 见 `configs/planner_prompt.md`。所有 planner 模式返回同一种 plan 结构：

- `char`
- `style`
- `style_params`
- `constraints`
- `stroke_plan`
- `planner_mode`
- `source`
- `warnings`
- `raw_response`
- `validation`

validation 会拒绝直接输出 trajectory 或 CSV 内容的 payload。LLM 只允许描述任务解析、风格选择、约束和确定性工具计划。

## 运行示例

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode mock
```

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个隶书风格的山，不要连笔" --planner-mode mock
```

批量 demo：

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --tasks-file experiments\llm_style_trajectory\configs\demo_tasks.json --planner-mode mock
```

API/local 占位示例：

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode api --fallback-to-mock
```

DeepSeek API 示例：

```powershell
$env:LLM_STYLE_PLANNER_API_KEY = "<your key>"
$env:LLM_STYLE_PLANNER_ENDPOINT = "https://api.deepseek.com/chat/completions"
$env:LLM_STYLE_PLANNER_MODEL = "deepseek-v4-pro"
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode api
```

API key 不会写入 `plan.json`、`summary.json`、测试输出或日志。自动化测试使用 mock HTTP response，不调用真实 API。
