# 机器人测试计划

## 实验条件说明

- 潜在可用设备：AUBO i5 / 遨博 i5 协作机械臂（来自师兄视觉抓取实验资料线索）
- 末端形式：夹爪或末端工具夹持书写笔，具体夹具与 TCP 需现场确认
- 不做毛笔书法（不需要笔压、笔锋、墨迹扩散）
- 重点验证：**轨迹规划是否合理**，而非真正毛笔书法艺术效果

## 已确认的平台资料线索

师兄资料文件夹：

```text
D:\edge download\视觉抓取26.04.27
```

关键信息：

- `遨博机器人运动控制实验记录.docx` 中明确写到实验目标为与 `AUBO i5` 机械臂通讯并进行运动控制。
- SDK 目录包含 `Aubo_CPlusPlus_SDK_CHN.pdf`、`Aubo_C_SDK_CHN.pdf`、`SDK-Python_Manual_CHN_V1.0.pdf`。
- Python SDK 目录包含 `auboi5-sdk-for-windows-python3.7-x64-v1.5.2`、`libpyauboi5.pyd`、`pyauboi51.dll`。
- 视觉抓取程序中使用 `Auboi5Robot`，并封装 `connect`、`inverse_kin`、`move_joint`、`move_line` 等接口。
- 历史网络配置出现过 `192.168.174.29`、`192.168.174.129`、`192.168.94.130` 和端口 `8899`。这些只作为历史线索，实机前需按现场示教器和控制柜重新确认。

详细记录见：

```text
AUBO_I5_PLATFORM_NOTES.md
```

## 测试目标

验证算法生成的轨迹能够被机械臂执行，并完成简单字形书写。

## 测试流程

### 第一阶段：纯仿真验证
1. 输入自然语言书写任务，例如“写一个行楷风格的山”
2. 由 planner 生成结构化 plan 和受控 style modifiers
3. 本地确定性工具生成 `trajectory.csv`、`execution_trajectory.csv`
4. 在二维平面和 CoppeliaSim standard pen-tip/sphere scene 中验证轨迹
5. 计算风格差异、连接段、工作空间边界和重采样步长等指标

### 第二阶段：运动学映射
1. 将二维轨迹点映射到机械臂工作空间坐标系
2. 将 `robot_workspace_trajectory_resampled.csv` 转换为 AUBO i5 末端目标位姿序列
3. 固定书写笔工具姿态和 TCP 参数，生成 `robot_target_poses.csv`
4. 生成 AUBO i5 dry-run command plan 和 safety check
5. 运行 IK feasibility dry-run 前检查，但不求真实 IK、不连接实机
6. 运行 motion continuity dry-run，检查 target pose / workspace 轨迹的时间连续性、速度、加速度和 jerk
7. 对未通过连续性 gate 的目标位姿做去重、retiming 和速度平滑，生成 `robot_target_poses_smoothed.csv`
8. 基于 `robot_target_poses_smoothed.csv` 重新生成 AUBO command adapter 和 IK feasibility dry-run 结果
9. 在仿真环境中验证机械臂运动范围、速度、加速度和轨迹连续性

### 第三阶段：实物书写实验（如有条件）
1. 3-5条已平滑的轨迹，不现场生成
2. AUBO i5 末端夹爪或工具夹持书写笔
3. 先低速、离纸面安全高度空跑轨迹
4. 再执行简单落笔轨迹跟踪
5. 拍摄书写结果并与目标字形对比

## 论文中描述方式

- 不强调"毛笔书法效果"，而说"末端轨迹跟踪实验"
- 实验采用仿真与实物验证相结合的方式
- 首先在二维平面中验证轨迹生成与优化效果
- 随后将优化轨迹映射到机械臂工作空间，通过末端夹爪夹持书写笔完成简单字形轨迹跟踪实验

## 最低验证标准

1. 能输入自然语言书写任务 ✓
2. 能输出 `trajectory.csv`、`execution_trajectory.csv` 和工作空间轨迹 ✓
3. 能展示三种基础字体风格差异 ✓
4. 能展示连笔、宽扁、圆滑等 modifier ablation ✓
5. 能映射到机械臂纸面工作空间 ✓
6. 能完成 CoppeliaSim standard pen-tip/sphere scene 播放 ✓
7. 能生成 AUBO i5 target poses、dry-run command plan 和 IK feasibility 前检查 ✓
8. 能生成 motion continuity dry-run 报告，发现速度/加速度/jerk 与时间连续性问题 ✓
9. 能生成 target pose retiming / smoothing 后处理结果，并让默认样例重新通过 conservative continuity gate ✓
10. 能让后续 command adapter / IK feasibility 默认基于 smoothed target poses 重新生成 dry-run 结果 ✓
11. 论文能解释当前边界：尚未真实 IK、尚未实机控制 ✓

## 实机安全边界

- 不直接运行师兄遗留控制程序控制真实机械臂。
- 不直接复用历史 IP，必须现场确认控制柜、示教器、电脑网段和急停状态。
- 真实 AUBO i5 实验前必须先完成：
  1. `robot_target_poses.csv` 离线检查
  2. IK feasibility dry-run 前检查
  3. 速度/加速度/jerk dry-run 检查
  4. 离纸面空跑
  5. 低速小范围落笔测试

当前 `motion_continuity_check.py` 已完成离线检查层。默认 weak 行楷山样例原始 target pose 速度未超阈值，但存在 4 个零时长重复边界点，并在保守阈值下出现 acceleration / jerk 超限。`target_pose_retiming.py` 已完成后处理：删除 4 个相邻静止重复点，保持几何路径长度不变，并生成 `robot_target_poses_smoothed.csv`。后处理后 `dt_nonpositive_count=0`，`max_accel_m_s2=0.274132141`，`max_jerk_m_s3=4.193553547`，`recommended_for_coppeliasim_playback=true`，`recommended_for_ik_dry_run=true`。该层仍只是离线时间规划，不是真实机器人动力学优化，不做 IK，不连接 AUBO i5，不发送运动命令。

后续 AUBO command adapter 和 IK feasibility 默认样例已优先使用 `robot_target_poses_smoothed.csv`。原始 `robot_target_poses.csv` 保留为 before-retiming 对照；smoothed 输出生成 `aubo_i5_command_plan_smoothed.csv`、`aubo_i5_safety_check_smoothed.json` 和 `aubo_i5_ik_feasibility_smoothed_summary.json/report.md/points.csv`。当前仍不做真实 IK、不连接实机、不调用 SDK、不发送运动命令。
