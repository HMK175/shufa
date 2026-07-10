# AUBO i5 目标位姿说明

日期：2026-06-14

## 范围

该层将 `robot_workspace_trajectory_resampled.csv` 转换为
`robot_target_poses.csv`，也就是通用机器人末端目标位姿序列。

它不会：

- 求逆运动学；
- 连接真实 AUBO i5；
- 发送 `move_joint` 或 `move_line` 命令；
- 控制真实机械臂；
- 假设当前实验室 IP、TCP、工具、夹具或安全状态。

当前输出只是 IK 前的准备产物。

## 输入与输出

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

在同一目录生成：

```text
robot_target_poses.csv
robot_target_pose_report.md
robot_target_pose_summary.json
```

## 位姿约定

坐标从毫米转换为米：

```text
X_m = X_mm / 1000 + origin_x_m
Y_m = Y_mm / 1000 + origin_y_m
Z_m = Z_mm / 1000 + origin_z_m
```

默认工具姿态为竖直向下写字：

```text
roll_deg = 180
pitch_deg = 0
yaw_deg = 0
```

对应 quaternion 写入 `qw/qx/qy/qz`，并检查是否归一化。默认 quaternion 约为：

```text
qw = 0
qx = 1
qy = 0
qz = 0
```

origin 和姿态可通过命令行覆盖：

```powershell
python experiments\llm_style_trajectory\src\robot_target_poses.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --origin-x-m 0 `
  --origin-y-m 0 `
  --origin-z-m 0 `
  --roll-deg 180 `
  --pitch-deg 0 `
  --yaw-deg 0
```

## 字段

`robot_target_poses.csv` 包含：

```text
pose_id
t_s
X_m
Y_m
Z_m
roll_deg
pitch_deg
yaw_deg
qw
qx
qy
qz
pen_down
segment_type
speed_m_s
source_X_mm
source_Y_mm
source_Z_mm
```

如果源 CSV 已有 `t_s`，则复用；否则根据相邻 3D 点距离和 `speed_mm_s` 积分生成时间。

## 检查项

`robot_target_pose_summary.json` 和 `robot_target_pose_report.md` 会记录：

- `point_count`
- `duration_s`
- `path_length_m`
- `max_step_m`
- `max_speed_m_s`
- segment counts
- 源 XY 是否落在 120mm 纸面范围内
- 源 Z 是否落在 `0..8mm` 范围内
- NaN/inf 检查
- 时间单调性检查
- quaternion 归一化检查
- `recommended_for_ik_dry_run`
- `warnings`

当前 weak 行楷“山” target-pose 运行结果：

```text
point_count = 275
duration_s = 13.05282
path_length_m = 0.359531
max_step_m = 0.002488
max_speed_m_s = 0.04
recommended_for_ik_dry_run = true
warnings = []
```

## AUBO i5 后续事项

历史平台资料记录在：

```text
AUBO_I5_PLATFORM_NOTES.md
```

后续 AUBO i5 SDK 或 wrapper 可能用到：

- `inverse_kin`
- `move_joint`
- `move_line`
- `set_tool_kinematics_param`

任何实机测试前都必须重新确认当前机器人 IP、控制器状态、TCP/tool transform、笔夹具、纸面位姿、速度/加速度限制、急停、工作空间边界和人员安全条件。历史 IP 和 SDK 示例只作为资料线索，不能当作安全默认配置。
