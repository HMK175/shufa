# AUBO i5 IK 可行性 Dry-Run 说明

日期：2026-06-16

## 范围

该层检查 `robot_target_poses.csv` 是否足够干净，是否具备进入未来真实 IK dry-run 的基本条件。它仍然只是离线 feasibility 前检查。

它不会：

- 求真实 AUBO i5 IK；
- import 或执行 `libpyauboi5`；
- 连接真实 AUBO i5；
- 把历史 IP 作为默认配置；
- 发送任何机器人命令；
- 检查关节限位、碰撞、奇异位形、动力学或标定后的真实可达性。

输出结果只是未来 SDK/IK adapter 前的保守 gate。

## 输入

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

## 输出

在同一任务目录生成：

```text
aubo_i5_ik_feasibility_summary.json
aubo_i5_ik_feasibility_report.md
aubo_i5_ik_feasibility_points.csv
```

## 检查项

dry-run 检查：

- target pose 必需字段；
- XY 纸面范围；
- Z 范围；
- 相邻点距离；
- target pose 速度；
- 时间单调性；
- quaternion 归一化；
- NaN / inf；
- 相对可配置 origin 的保守半径 envelope。

默认阈值：

```text
paper half size = 0.060 m
Z range = 0..0.008 m
max_step_m <= 0.015
max_speed_m_s <= 0.10
quaternion norm tolerance = 1e-6
radius envelope = 0.0..0.90 m
```

半径 envelope 只是粗略提示。它不是关节级 IK，不是碰撞检测，不是奇异位形检测，也不能保证 AUBO i5 一定能到达所有位姿。

## 当前样例结果

weak 行楷“山”样例：

```text
point_count = 275
xy_range_m = x[-0.049057, 0.048721], y[-0.049392, 0.049392]
z_range_m = [0.0, 0.0]
radius_range_m = [0.000756, 0.064444]
max_step_m = 0.002488
max_speed_m_s = 0.04
time_monotonic = true
quaternion_normalized = true
has_nan_or_inf = false
required_fields_present = true
within_conservative_envelope = true
recommended_for_real_ik_check = true
warnings = []
```

## 下一步

进入真实 IK 或任何 AUBO i5 实机测试之前，需要确认：

- 机器人 IP 和控制器状态；
- 急停和人员安全边界；
- 工具 TCP 和笔夹具；
- 纸面在机器人 base 坐标系中的位姿；
- 速度与加速度限制；
- 可达性和碰撞余量；
- 现场监督。

历史 AUBO SDK 资料只作为参考：

```text
AUBO_I5_PLATFORM_NOTES.md
```
