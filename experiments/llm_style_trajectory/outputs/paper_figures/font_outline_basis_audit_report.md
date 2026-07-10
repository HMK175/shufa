# Font outline basis manual audit pack

本轮目的：从 font-outline feasibility 结果中筛出最值得人工看图的样本，并把 skeleton 问题分成 endpoint 多、branch 多、断裂/多连通分量、aspect gap 大、skeleton 复杂等类别。

- input_feasibility_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008`
- total_candidates: 30
- selected_images: 10
- 说明：以下阈值是 diagnostic threshold，不是最终判据；当前 skeleton 不能直接作为轨迹，需人工判断和后处理。

## Diagnostic thresholds

| metric | threshold |
|---|---:|
| endpoint_count | 11.750 |
| branch_point_count | 30.750 |
| skeleton_pixel_count | 732.500 |
| abs(aspect_gap) | 0.430 |

## Issue tag counts

| issue_tag | count |
|---|---:|
| disconnected_skeleton | 15 |
| promising_candidate | 10 |
| complex_skeleton | 8 |
| high_aspect_gap | 8 |
| high_branch_count | 8 |
| high_endpoint_count | 8 |

## Issue counts by style

| style | high_endpoint | high_branch | disconnected | high_aspect | complex | promising |
|---|---:|---:|---:|---:|---:|---:|
| kaishu | 5 | 3 | 7 | 0 | 3 | 3 |
| xingkai | 2 | 4 | 2 | 0 | 2 | 6 |
| lishu | 1 | 1 | 6 | 8 | 3 | 1 |

## Endpoint/branch top samples

| char | style | endpoints | branches | issue_tags | image |
|---|---|---:|---:|---|---|
| 德 | xingkai | 20 | 79 | high_endpoint_count;high_branch_count;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u5fb7.png` |
| 福 | kaishu | 19 | 44 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u798f.png` |
| 德 | kaishu | 23 | 39 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u5fb7.png` |
| 德 | lishu | 18 | 40 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u5fb7.png` |
| 明 | xingkai | 8 | 47 | high_branch_count;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u660e.png` |
| 和 | xingkai | 11 | 42 | high_branch_count;disconnected_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u548c.png` |
| 福 | xingkai | 12 | 35 | high_endpoint_count;high_branch_count;disconnected_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u798f.png` |
| 和 | kaishu | 12 | 30 | high_endpoint_count;disconnected_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u548c.png` |
| 明 | kaishu | 11 | 31 | high_branch_count;disconnected_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u660e.png` |
| 国 | kaishu | 12 | 26 | high_endpoint_count;disconnected_skeleton;complex_skeleton | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u56fd.png` |

## Aspect gap top samples

| char | style | aspect | median_aspect | aspect_gap | issue_tags |
|---|---|---:|---:|---:|---|
| 国 | lishu | 1.375 | 0.807388 | 0.567612 | disconnected_skeleton;high_aspect_gap;complex_skeleton |
| 永 | lishu | 1.560976 | 1.055 | 0.505976 | disconnected_skeleton;high_aspect_gap |
| 和 | lishu | 1.495798 | 0.990111 | 0.505687 | disconnected_skeleton;high_aspect_gap |
| 中 | lishu | 1.195312 | 0.69988 | 0.495432 | high_aspect_gap |
| 风 | lishu | 1.631579 | 1.188427 | 0.443152 | high_aspect_gap |
| 福 | lishu | 1.487603 | 1.044888 | 0.442715 | disconnected_skeleton;high_aspect_gap;complex_skeleton |
| 明 | lishu | 1.291667 | 0.85422 | 0.437447 | disconnected_skeleton;high_aspect_gap |
| 山 | lishu | 1.375 | 0.945007 | 0.429993 | high_aspect_gap |
| 德 | lishu | 1.46875 | 1.039521 | 0.429229 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton |
| 人 | xingkai | 1.653846 | 1.414861 | 0.238985 | promising_candidate |

## Recommended first-look samples

| char | style | priority | issue_tags | focus |
|---|---|---:|---|---|
| 德 | kaishu | 8 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 德 | lishu | 8 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 福 | kaishu | 8 | high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 国 | kaishu | 7 | high_endpoint_count;disconnected_skeleton;complex_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 国 | lishu | 7 | disconnected_skeleton;high_aspect_gap;complex_skeleton | 看 aspect 差异是否是真实风格信号还是形变过度 |
| 德 | xingkai | 7 | high_endpoint_count;high_branch_count;complex_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 福 | lishu | 7 | disconnected_skeleton;high_aspect_gap;complex_skeleton | 看 aspect 差异是否是真实风格信号还是形变过度 |
| 福 | xingkai | 7 | high_endpoint_count;high_branch_count;disconnected_skeleton | 看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂 |
| 中 | lishu | 5 | high_aspect_gap | 看 aspect 差异是否是真实风格信号还是形变过度 |
| 山 | lishu | 5 | high_aspect_gap | 看 aspect 差异是否是真实风格信号还是形变过度 |

## Manual audit boundary

- 本轮没有替用户完成视觉判断。
- 数值分类只用于挑图和标注风险，不能替代人工看图。
- 当前 skeleton 不能直接作为轨迹；若人工认为有价值，下一步还需要去噪、连通性修复、主路径提取和笔画顺序恢复。
- 本轮不改默认 pipeline、不改 style profiles、不改 run_demo 默认行为、不调用 API、不连接 CoppeliaSim/AUBO/SDK、不做机器人控制。
