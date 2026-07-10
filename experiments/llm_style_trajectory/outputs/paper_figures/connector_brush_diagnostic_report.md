# Connector / Brush Visual Diagnostics

## Purpose

本轮从上一轮 visual audit 进入更细的 connector / brush 可视化诊断。目标是把 stroke、connector、pen_up_move、width、pressure 拆开看清楚，为人工看图提供依据。

边界：本轮不调参数、不改 planner、不扩大样本、不调用 API、不连接 CoppeliaSim 或 AUBO i5。不能只看指标，本报告只准备图包和诊断线索，最终视觉判断仍需人工校验。

## Inputs

- visual_audit_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321`
- diagnostic_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510`

## What The Figures Show

- `segment_legend.png`: 说明 stroke / connector / pen_up_move 的颜色和线型。
- `connector_overlay_*`: 用红/橙色突出 xingkai connector，灰色虚线只表示 pen-up move。
- `style_side_by_side_*`: 对同一字展示 centerline、execution width、connector 高亮视图。
- `lishu_deformation_*`: 对比 kaishu 与 lishu 的 bbox / aspect，检查是否主要是整体拉宽压扁。
- `brush_width_diagnostic_*`: 对比 stroke 与 connector 的 width / pressure，检查普通渲染是否隐藏差异。

## Answers To Current Visual Questions

1. 灰线是什么？在旧的 selected_images 中，灰线/浅线可能来自渲染透明度、connector 过渡或 pen-up/transition 可视化混在一起；新图中灰色虚线只表示 `pen_up_move`，红/橙色才表示 connector。
2. 为什么宽度看起来都一样？之前的固定渲染更偏最终墨迹预览，connector 的低 pressure / 小 width 可能被抗锯齿、透明度和整体缩放吞掉；本图包单独画 width/pressure 才能看到执行层差异。
3. 为什么 lishu 像横向拉伸？当前 lishu 的可见差异主要来自 horizontal/vertical scale 和笔宽，stroke-level 的蚕头燕尾、波磔等隶书特征还不足，所以需要人工确认是否只是全局变形。
4. xingkai connector 是否太多？指标显示部分复杂字 connector_draw_length 较长，本轮重点给出 `国/德/福` overlay；是否过多、是否自然必须看图判断。
5. 为什么需要新可视化？因为中心线和固定墨迹图无法明确区分 connector、pen-up move、width 和 pressure。调参前先把执行层证据分离，避免只凭数值误判。

## Case Counts

| case_type | count |
|---|---:|
| `brush_width_diagnostic` | 1 |
| `lishu_deformation` | 6 |
| `long_xingkai_connector` | 3 |
| `style_side_by_side` | 9 |

## Generated Cases

| char | style | case_type | figure | focus |
|---|---|---|---|---|
| 国 | xingkai | `long_xingkai_connector` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\connector_overlay_u56fd_xingkai.png` | Check whether xingkai connector is too long, too straight, or crossing components. |
| 德 | xingkai | `long_xingkai_connector` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\connector_overlay_u5fb7_xingkai.png` | Check whether xingkai connector is too long, too straight, or crossing components. |
| 福 | xingkai | `long_xingkai_connector` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\connector_overlay_u798f_xingkai.png` | Check whether xingkai connector is too long, too straight, or crossing components. |
| 人 | xingkai | `brush_width_diagnostic` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\brush_width_diagnostic_u4eba_xingkai.png` | Compare stroke and connector width/pressure; check whether fixed render hides differences. |
| 人 | kaishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4eba.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 人 | lishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4eba.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 人 | xingkai | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4eba.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 中 | kaishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4e2d.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 中 | lishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4e2d.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 中 | xingkai | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u4e2d.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 和 | kaishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u548c.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 和 | lishu | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u548c.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 和 | xingkai | `style_side_by_side` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\style_side_by_side_u548c.png` | Compare centerline, execution width, and connector-highlighted visual difference across styles. |
| 人 | kaishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u4eba.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |
| 人 | lishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u4eba.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |
| 好 | kaishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u597d.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |
| 好 | lishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u597d.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |
| 风 | kaishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u98ce.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |
| 风 | lishu | `lishu_deformation` | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\connector_brush_visual_diagnostics_20260618_093510\figures\lishu_deformation_u98ce.png` | Check whether lishu is mainly global horizontal widening / vertical compression. |

## Manual Review Guidance

请优先人工看图：
- `国/德/福` 的 xingkai connector 是否过长、过直或穿越部件。
- `人/好/风` 的 lishu 是否只是横向拉宽、纵向压缩，而缺少真实隶书笔画特征。
- `人/中/和` 的三风格是否肉眼能区分，还是只在指标上有差异。
- brush width diagnostic 中 connector 是否确实比 stroke 更细、更低压。

本轮不调参数。等用户人工看图反馈后，再决定是否调整 style profile、modifier 或 brush mapping。