# 宽度 / 压力渐变可视化诊断

## 本轮目的

本轮用颜色深浅和适度线宽显示 `execution_trajectory.csv` 中的 `width` / `pressure`。目标是让人工看图时能直观看到主体 stroke 与 connector 的粗细、压力差异。

本轮不调参数，不修改 `execution_trajectory.csv`，不改 planner，不调用 API，不连接 CoppeliaSim 或机器人接口。这些图不是最终书法效果图，只是执行层诊断图；不能只看指标，仍需要人工看图。

## 输入与输出

- cases_csv: `experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\connector_brush_diagnostic_cases.csv`
- sample_count: `16`
- generated_figure_count: `64`

## global normalization 与 per-image normalization

- `global`：所有样本共用同一组 width/pressure 范围，适合跨字、跨风格比较。
- `per-image`：每张图内部独立归一化，适合观察单个样本内部是否有细微变化。

## 全局范围

- global_width_min/max: `4.245` / `10.0`
- global_pressure_min/max: `0.338` / `1.0`

## 输出统计

- value_mode_counts: `{'width': 32, 'pressure': 32}`
- normalization_counts: `{'global': 32, 'per-image': 32}`

## 初步观察

- connector 明显更细的样本数：`6`。样本：`u56fd/xingkai, u5fb7/xingkai, u798f/xingkai, u4eba/xingkai, u4e2d/xingkai, u548c/xingkai`
- connector 明显更低压的样本数：`6`。样本：`u56fd/xingkai, u5fb7/xingkai, u798f/xingkai, u4eba/xingkai, u4e2d/xingkai, u548c/xingkai`
- stroke width nearly constant 的样本数：`16`。样本：`u56fd/xingkai, u5fb7/xingkai, u798f/xingkai, u4eba/xingkai, u4eba/kaishu, u4eba/lishu, u4e2d/kaishu, u4e2d/lishu, u4e2d/xingkai, u548c/kaishu, u548c/lishu, u548c/xingkai`

如果某个样本的主体笔画整段颜色差不多，说明当前数据中的 stroke 内部宽度/压力变化不足；这不是可视化失败，而是 execution 数据本身变化较少。
旧 selected_images 之所以肉眼看不出粗细差异，主要是因为固定墨迹渲染会把低压、细线、透明度和抗锯齿效果混在一起。

## 人工看图说明

建议先看 `global width` 图判断跨样本粗细差异，再看 `per-image width` 图判断单个样本内部变化；随后看 pressure 图判断 connector 是否低压。不要把颜色深浅当作最终书法视觉效果，它只是诊断编码。

## 边界

- 本轮不调参数。
- 本轮不修改 `execution_trajectory.csv`。
- 本轮不代表真实笔刷模型。
- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。