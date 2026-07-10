# Font-driven style gap analysis / 字体轮廓驱动的风格差距诊断

## 本轮目的

本轮停止细枝末节调参，先分析真实字体轮廓与当前参数化轨迹之间的差距。
本轮不调参数，不替换全局默认，不生成最终新轨迹。

## 输入与输出

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_style_gap_analysis_20260618_144838`
- font_sources: `experiments\llm_style_trajectory\configs\style_sources.json`
- trajectory_diagnostics_dir: `experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746`
- chars: `18`
- styles: `kaishu, xingkai, lishu`

## 样本统计

- total: `54`
- rendered_success: `54`
- failures: `0`

## 三风格字体侧均值

| style | samples | mean_font_aspect_ratio | mean_trajectory_aspect_ratio | mean_abs_aspect_ratio_gap | mean_font_components | mean_trajectory_connections | mean_font_stroke_width | mean_trajectory_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.029878 | 1.018672 | 0.058451 | 2.888889 | 0.0 | 6.320909 | 9.0 |
| xingkai | 18 | 0.989059 | 1.070791 | 0.126632 | 1.555556 | 6.055556 | 9.575023 | 7.488813 |
| lishu | 18 | 1.480275 | 1.465173 | 0.110869 | 2.5 | 0.0 | 8.956169 | 10.0 |

## 字体 vs 当前轨迹的主要 gap

- lishu：重点看 `font_aspect_ratio` 与当前 `trajectory_aspect_ratio` 的差距，判断当前是否只是全局压扁/拉宽。
- xingkai：字体图像的 connected component 只能弱对应连通性，不能直接等价于真实连笔；它用于提示当前 connector prior 是否过于人工。
- kaishu / xingkai / lishu：比较字体三风格的 aspect spread 与轨迹三风格的 aspect spread，定位哪些字的字体差异大但轨迹差异小。

### 主要发现

- lishu 平均字体 aspect ratio `1.480275`，当前轨迹 `1.465173`；均值接近，但这不能证明已经学到隶书结构，只说明全局宽扁比例接近。
- xingkai 平均字体 connected component `1.555556`，当前轨迹 connection_count `6.055556`；当前 connector 规则比字体静态连通性更激进，且二者只是弱对应。
- kaishu 平均字体 aspect ratio `1.029878`，当前轨迹 `1.018672`；楷书整体比例 gap 最小。
- style gap 的重点不是继续微调 connector，而是把横纵比例、笔画宽度分布、投影分布和连接先验从字体/图像统计中系统估计出来。

## 参数升级建议

- 可从字体统计估计：`horizontal_scale / vertical_scale`、stroke width distribution、component-level proportions、connectedness / connector prior、projection distribution。
- 仍不能从静态字体直接估计：真实速度、真实抬笔高度、真实机器人动态控制。

## 失败样本

- 无。

## 边界

- 字体轮廓不等于真实书写轨迹。
- 字体静态图无法直接给出真实书写时序。
- 本轮不调参数，不进入 CoppeliaSim / AUBO i5 / IK / SDK / 机器人控制。
- 仍需要人工看图校验，尤其是字体网格图和 gap 图。
