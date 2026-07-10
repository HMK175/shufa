# B-route Visual Conclusion Freeze Note

## 1. Purpose

本页用于固定当前 B-route 关键中文图在人工复检后的视觉结论与论文定位。

它的作用是：

- 固定三张关键图的推荐用途，避免后续线程反复改变角色；
- 明确哪些图适合放正文，哪些更适合作补充材料或局限性图；
- 给出可直接复用的简短图注建议；
- 强调这不是新实验结果，只是对已有图的人工使用建议。

本页不新增算法，不调参数，不重画图，不接默认 pipeline。

## 2. Figure-by-Figure Decision

### 2.1 山 / 楷书 vs 隶书

- file:
  `experiments/llm_style_trajectory/outputs/b_route_visuals_cn_20260621_143505/h1_lite_u5c71_kaishu_lishu_contrast_cn.png`
- recommended_role: `supplementary_candidate`
- confidence: `medium`
- why:
  图中确实能看出 `山/lishu` 比 `山/kaishu` 更朝宽底方向移动，中文重绘后这种差异比原图更容易观察；但整体差异仍偏弱，不足以作为“强风格分离”主图。
- paper_usage_note:
  `该对照图表明，在保持中位笔顺结构不变的前提下，H1-lite 可将山字的隶书 trial 轻度推向更宽底的形态，但当前差异仍属于弱而可见的层级。`
- caution:
  不要写成“楷书与隶书已经明显分离”或“已实现稳定隶书风格迁移”。

### 2.2 风 / 隶书风险试验

- file:
  `experiments/llm_style_trajectory/outputs/b_route_visuals_cn_20260621_143505/h1_lite_u98ce_lishu_risk_contrast_cn.png`
- recommended_role: `limitation_or_risk_case`
- confidence: `high`
- why:
  这张图清楚展示了复杂隶书字上的风险边界。即使加了局部放大，`conservative` 与 `balanced` 仍然较接近，说明 H1-lite 在更复杂的 lishu 字上开始接近表达上限。
- paper_usage_note:
  `风字风险试验说明，H1-lite 在复杂隶书字上仍只能提供有限形态偏移，当前结果更适合作为风险边界与方法局限性示例。`
- caution:
  不要写成“复杂隶书字也取得良好效果”，更不能把它当作成功主图。

### 2.3 风 / 隶书 hybrid section refinement

- file:
  `experiments/llm_style_trajectory/outputs/b_route_visuals_cn_20260621_143505/hybrid_section_compare_cn.png`
- recommended_role: `main_candidate`
- confidence: `medium`
- why:
  这张图把字体分区、原始中位轨迹、分区标签、保守版和平衡版放在同一页，最利于解释 B-route 当前真正有价值的点：section-level constraints 比直接点级拉扯更可解释，也更稳。
- paper_usage_note:
  `该图展示了分区级约束如何在不改变中位笔顺结构的前提下，对风字隶书 trial 提供更可解释的局部形态调节线索。`
- caution:
  仍要明确这是 `trial-only` 的风格增强探索，不构成成熟的风格生成方法，也不代表复杂隶书字已被稳定解决。

## 3. Recommended Use in Paper

- 正文候选优先使用：
  `hybrid_section_compare_cn.png`
- 补充材料候选：
  `h1_lite_u5c71_kaishu_lishu_contrast_cn.png`
- 风险 / 局限性图：
  `h1_lite_u98ce_lishu_risk_contrast_cn.png`

## 4. Writing Guidance

- 不要把 `山/kaishu vs 山/lishu` 写成“明显风格分离”。
- 不要把 `风/lishu` 风险图写成“复杂隶书也取得良好效果”。
- `hybrid_section_compare_cn.png` 可以更稳妥地写成：

  `section-level constraints 提供了比直接点级拉扯更稳定的形态调节线索，但当前仍属于 trial-only 风格增强探索，不构成成熟风格生成方法。`

- 如果论文需要诚实陈述 B-route 现状，可以使用：

  `当前 B-route 更适合作为带有人审 gate 的可解释风格增强研究方向，而不是默认生成主链路。`

## 5. Current Freeze Decision

- 这三张图的论文使用定位先冻结。
- 后续除非出现新的、明显更强且经人工复检认可的 B-route 图，否则不要随意替换这三张图当前的角色。
- 若新增图表，必须先经过人工复检，再决定是否升级为正文候选或替换既有角色。

## 6. Boundary Statement

- 本页不是新算法；
- 不生成轨迹；
- 不接默认 pipeline；
- 不调用 API；
- 不连接 CoppeliaSim / AUBO / SDK；
- 不修改 `code/data` 或 `code/legacy_image_skeleton_rl_route`。
