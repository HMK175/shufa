# CoppeliaSim 最小工作空间路径播放

该目录包含当前 `experiments/llm_style_trajectory` 主线的最小 CoppeliaSim bridge。项目内不包含、不复制 CoppeliaSim 软件本体。

## 范围

- 输入：`robot_workspace_trajectory_resampled.csv`
- CoppeliaSim 中的输出：纸面 plane、pen-tip sphere，以及按 segment 类型着色的路径段。
- 当前状态：只做 pen-tip 路径播放。
- 暂不包含：真实机械臂模型、逆运动学、夹爪/工具标定、碰撞检查或控制器调参。

## CoppeliaSim 位置

CoppeliaSim Edu 应放在本仓库之外。本机曾检测到的位置：

```text
D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
```

如果你的路径不同，请从自己的本地安装目录启动 CoppeliaSim。

## 启动 CoppeliaSim

1. 打开 `D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\coppeliaSim.exe`。
2. 保持 CoppeliaSim 运行，场景可以为空。
3. 确认该 CoppeliaSim 安装中有 ZeroMQ remote API add-on。较新的 CoppeliaSim Edu 通常已内置。

## Python 环境

将 CoppeliaSim 的 ZeroMQ remote API client 暴露给当前 PowerShell 会话：

```powershell
$env:PYTHONPATH="D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\programming\zmqRemoteApi\clients\python\src;$env:PYTHONPATH"
```

本地 Python 环境还需要 ZeroMQ 序列化依赖：

```powershell
python -m pip install pyzmq cbor
```

快速 import 检查：

```powershell
python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient; print('ok')"
```

## 离线 Dry Run

dry-run 不连接 CoppeliaSim，只检查 CSV 并打印摘要：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --dry-run
```

dry-run 默认也会在 CSV 所在目录写入单次 playback 结果：

```text
coppeliasim_playback_result.json
coppeliasim_playback_result.md
```

## 真实播放

先启动 CoppeliaSim，再运行：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0
```

低负载播放选项：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0 `
  --display-stride 5

python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --no-path-objects `
  --auto-stop
```

- `--display-stride N`：只绘制每 N 个 colored path segment，但 pen-tip sphere 仍按完整 CSV 运动。
- `--no-path-objects`：跳过 colored path 绘制，只移动 pen tip，可降低 GUI/GPU 负载。
- `--auto-stop`：播放结束后停止 CoppeliaSim 仿真。

播放完成后会在 stdout 打印 JSON 摘要。如果没有设置 `--auto-stop`，脚本还会在 stderr 打印提醒：

```text
playback finished, but CoppeliaSim simulation may still be running; use --auto-stop to stop it automatically
```

使用 `--auto-stop` 时，结果会在 `simulation_stopped` 中记录 `stopSimulation()` 是否成功调用。

## 标准书写场景

`play_workspace_path.py` 可以在播放前自动创建可复现的标准书写场景：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --scene-setup standard `
  --clear-previous-scene `
  --show-axes `
  --show-boundary `
  --display-stride 5 `
  --auto-stop `
  --speed-scale 1.0
```

标准场景对象统一使用 `llm_style_trajectory_*` 前缀，因此下一次运行可用
`--clear-previous-scene` 清理上一次脚本创建的对象。

- `paper plane`：默认 `120mm x 120mm`，位于 `Z=0`。
- `boundary`：纸面边界框，通过 `--show-boundary` 启用。
- `X/Y/Z axes`：坐标轴，通过 `--show-axes` 启用；X 为红色，Y 为绿色，Z 为蓝色。
- `pen-tip sphere`：半径由 `--pen-tip-radius-mm` 控制，默认 `1.5`。
- `path segments`：除非设置 `--no-path-objects`，否则 stroke、connector、pen-up move 会分别着色。

场景参数：

- `--scene-setup standard`：创建标准 pen-tip 场景。
- `--clear-previous-scene`：清理上一次脚本运行创建的对象。
- `--paper-size-mm 120`：设置方形纸面尺寸，单位为毫米。
- `--pen-tip-radius-mm 1.5`：设置 pen-tip sphere 半径。
- `--show-axes`：绘制 X/Y/Z 坐标轴。
- `--show-boundary`：绘制纸面边界框。

结果 JSON/Markdown 会记录 `scene_setup`、`paper_size_mm`、
`pen_tip_radius_mm`、`axes_enabled`、`boundary_enabled`、
`clear_previous_scene`、`coordinate_mapping`、`workspace_bounds`、
`scene_warnings` 和 `recommended_playback`。dry-run 会使用相同场景参数做边界检查，但不会连接 CoppeliaSim。

2026-06-13 已验证标准场景播放：

```text
CSV: experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv
status: finished
point_count: 275
simulation_stopped: true
paper_size_mm: 120.0
pen_tip_radius_mm: 1.5
axes_enabled: true
boundary_enabled: true
clear_previous_scene: true
recommended_playback: true
max_step_3d_mm: 2.487672
max_xy_step_mm: 2.487672
max_z_step_mm: 0.0
workspace_bounds: XY within +/-60mm, Z within 0..8mm
```

结果文件：

```text
experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\coppeliasim_playback_result.json
experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\coppeliasim_playback_result.md
```

该层仍只是标准 pen-tip/sphere 场景，不包含机械臂模型、IK、动力学、碰撞检查或真实控制器。

## 简单笔工具模型

在真实 IK 工作之前，可让播放脚本在 pen-tip 场景上增加一个可视化 simple pen tool，用于坐标系 sanity check：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --scene-setup standard `
  --tool-model simple-pen `
  --show-tool-frame `
  --tool-length-mm 120 `
  --tool-radius-mm 4 `
  --tcp-offset-mm 0 `
  --base-frame-origin-mm 0,0,0 `
  --display-stride 5 `
  --auto-stop
```

dry-run 也支持该配置，且不会连接 CoppeliaSim：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --tool-model simple-pen `
  --show-tool-frame `
  --dry-run
```

使用 `--tool-model simple-pen` 或 `--show-tool-frame` 时，单次运行结果写入：

```text
coppeliasim_tool_model_result.json
coppeliasim_tool_model_result.md
```

结果会记录 `tool_model`、`tool_length_mm`、`tool_radius_mm`、
`tcp_offset_mm`、`base_frame_origin_mm`、`coordinate_frames`、
`paper_frame`、`workspace_frame`、`tcp_convention` 和
`recommended_for_coordinate_calibration`。

坐标系约定：

- `paper_frame`：位于方形纸面中心，`Z=0`。
- `workspace_frame`：当前与 `paper_frame` 重合；可选的
  `base_frame_origin_mm` 只作为标定元数据记录。
- `tool_tcp_frame`：CSV 点被视为书写 TCP / 笔尖目标。
- `simple-pen`：仅为可视化 cylinder，从笔尖沿 `+Z` 方向绘制。

该层仍只是 simple pen/tool 视觉 sanity check。它不是 AUBO i5 机器人模型，不做逆运动学，不做动力学仿真，不做碰撞检查，也不控制真实机器人。

## 单次播放结果

每次 dry-run 或真实播放都会写入单次结果记录：

```text
coppeliasim_playback_result.json
coppeliasim_playback_result.md
```

默认写到 CSV 所在目录。若要写到其他目录：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --display-stride 5 `
  --auto-stop `
  --result-out-dir experiments\llm_style_trajectory\outputs\playback_results `
  --dry-run
```

结果包含 `status`、`point_count`、`segment_type_counts`、
`duration_estimate_s`、`speed_scale`、`display_stride`、
`path_objects_enabled`、`auto_stop`、`simulation_stopped`、`dry_run`、
`max_step_3d_mm`、`max_xy_step_mm`、`max_z_step_mm` 和 XYZ 范围。

当前范围仍是 `pen-tip/sphere playback only, no robot IK`。

如果缺少 Python ZeroMQ client，请安装依赖或把 CoppeliaSim remote API client 暴露给本地 Python 环境。脚本会返回友好的配置错误，不会直接给出很长 traceback。

## 批量 Dry Run

batch dry-run 会在不连接 CoppeliaSim 的情况下，汇总 batch 目录中所有
`robot_workspace_trajectory_resampled.csv`：

```powershell
python experiments\llm_style_trajectory\coppeliasim\evaluate_playback_batch.py `
  --batch-dir experiments\llm_style_trajectory\outputs\batch_20260613_092733
```

输出：

```text
experiments\llm_style_trajectory\outputs\batch_20260613_092733\coppeliasim_playback_summary.csv
experiments\llm_style_trajectory\outputs\batch_20260613_092733\coppeliasim_playback_report.md
```

报告会把点间跳变拆成 `max_step_3d_mm`、`max_xy_step_mm` 和
`max_z_step_mm`，避免把抬笔高度变化误认为 XY 平面跳变。

## 已验证的手动播放

2026-06-13 验证配置：

```text
CoppeliaSim: D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
CSV: experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv
```

dry-run 摘要：

```json
{
  "point_count": 258,
  "segment_type_counts": {
    "pen_up_move": 21,
    "stroke": 237
  },
  "x_mm_range": [-49.057031, 48.721406],
  "y_mm_range": [-49.392188, 49.392188],
  "z_mm_range": [0.0, 8.0],
  "duration_estimate_s": 12.972534,
  "path_length_mm": 391.530547,
  "max_step_mm": 8.0,
  "max_step_3d_mm": 8.0,
  "max_xy_step_mm": 4.749192,
  "max_z_step_mm": 8.0,
  "status": "dry_run",
  "dry_run": true
}
```

设置 `PYTHONPATH` 并安装 `pyzmq` / `cbor` 后，真实播放命令已验证可运行。当前范围仍只是 pen-tip 或 sphere 路径播放：还没有机械臂模型、逆运动学、末端标定、碰撞检查或控制器调参。

说明：`max_step_mm` 作为兼容字段保留，等价于 `max_step_3d_mm`。新报告应优先使用
`max_step_3d_mm`、`max_xy_step_mm` 和 `max_z_step_mm`。

## 坐标

CSV 使用毫米，CoppeliaSim 使用米：

```text
X_m = X_mm / 1000
Y_m = Y_mm / 1000
Z_m = Z_mm / 1000
```

默认纸面为 `120mm x 120mm`，在 CoppeliaSim 中表示为 `0.12m x 0.12m`。
