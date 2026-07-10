# B-route 关键图中文化与差异辅助重绘

本轮只重绘图的表达方式，不改算法、不调参数、不接默认 pipeline。

## 中文标题与标签替换

- `original median` -> `原始中位轨迹`
- `conservative` -> `保守版`
- `balanced` -> `平衡版`
- `known positive reference` -> `已知正例参考`
- `font sections (top_mid_bottom_fallback)` -> `字体分区（上/中/下回退）`
- `median + section labels` -> `中位轨迹 + 分区标签`
- `top_band / mid_band / bottom_band` -> `上区 / 中区 / 下区`

## 差异辅助

- 三张图都增加了“原始灰色轨迹 + 调整后彩色轨迹”的叠加层。
- 在位移较明显的点上增加了淡色连线，帮助人工看到 `原始 -> 调整后` 的方向。
- `山` 增加了底部区域放大；`风` 增加了下半部和左右展开区域放大。
- `hybrid section` 图额外补了字体分区和中位轨迹分区标签，方便判断 section fallback 是否真的在起作用。

## 图级判断

| 图 | 变化表达 | 当前人工复检建议 |
|---|---|---|
| `h1_lite_u5c71_kaishu_lishu_contrast_cn.png` | balanced 后山字的 style gap 增至 bbox_aspect=0.064，lower_half_width=6.889 | 现在能看出隶书更宽底，但整体差异仍偏弱。 |
| `h1_lite_u98ce_lishu_risk_contrast_cn.png` | balanced 后 bbox_aspect=1.306，lower_half_width=225.874 | 保守版与平衡版仍接近，是三张图里最弱的一张。 |
| `hybrid_section_compare_cn.png` | section_source=top_mid_bottom_fallback，balanced aspect=1.307 | 现在最适合人工判断 section 约束是否真的生效。 |

## 诚实说明

- `山/kaishu vs 山/lishu` 的差异经过对照叠加和底部放大后更容易看，但差异仍然很弱，不能把这张图写成“风格差异非常明显”。
- `风/lishu` 的 conservative / balanced 现在更容易看出下半部和左右展开差异，但两者总体仍然接近，这张图仍需要人工反复比对。
- `hybrid_section_compare_cn` 现在最适合做人工判断，因为它把 section 分区、原始轨迹、保守版和平衡版放在同一页里，能更直观看到“分区约束是否真的带来局部变化”。

## 边界

- visual_redraw_only_not_used_by_default
- 不生成新 trajectory / execution / workspace / robot 文件
- 不改默认 pipeline，不改 style/profile，不改 trial 数据本身

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\b_route_visuals_cn_20260621_143505`
