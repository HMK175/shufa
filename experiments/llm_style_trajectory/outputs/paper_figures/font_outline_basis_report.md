# Font-outline-derived trajectory basis feasibility

本轮目的：只读比较 MakeMeAHanzi median 基底与字体轮廓提取的风格化骨架/中心线候选，判断是否值得继续探索 font-outline-derived trajectory basis。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008`
- skeleton_method request: `auto`
- 边界：不替换默认 pipeline，不改 `style_profiles.json`，不改 `run_demo.py` 默认行为，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制。

## Skeleton success rate by style

| style | success | total | success_rate |
|---|---:|---:|---:|
| kaishu | 10 | 10 | 1.000 |
| xingkai | 10 | 10 | 1.000 |
| lishu | 10 | 10 | 1.000 |

## Manual visual audit questions

- xingkai 字体骨架是否比 MakeMeAHanzi median 更有行楷结构，而不是“楷书中心线 + 少量连接”？
- lishu 字体骨架是否不仅是横向拉宽/纵向压扁，而是有笔形或结构差异？
- skeleton 是否太噪声、断裂，或者端点/分叉过多，导致不可直接用于轨迹？
- 是否值得把字体轮廓骨架作为下一阶段轨迹基底，还是只把它当作参数估计来源？

## Aspect-difference candidates

| char | style | font_aspect | median_aspect | delta | image |
|---|---|---:|---:|---:|---|
| 国 | lishu | 1.375 | 0.807 | 0.568 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u56fd.png` |
| 永 | lishu | 1.561 | 1.055 | 0.506 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u6c38.png` |
| 和 | lishu | 1.496 | 0.990 | 0.506 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u548c.png` |
| 中 | lishu | 1.195 | 0.700 | 0.495 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u4e2d.png` |
| 风 | lishu | 1.632 | 1.188 | 0.443 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u98ce.png` |
| 福 | lishu | 1.488 | 1.045 | 0.443 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u798f.png` |
| 明 | lishu | 1.292 | 0.854 | 0.437 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u660e.png` |
| 山 | lishu | 1.375 | 0.945 | 0.430 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_feasibility_20260619_115008\figures\basis_compare_u5c71.png` |

## Potentially noisy or fragmented skeleton candidates

| char | style | components | skeleton_pixels | endpoints | branches | warnings |
|---|---|---:|---:|---:|---:|---|
| 德 | xingkai | 1 | 971 | 20 | 79 |  |
| 福 | kaishu | 5 | 834 | 19 | 44 |  |
| 德 | kaishu | 8 | 846 | 23 | 39 |  |
| 德 | lishu | 6 | 748 | 18 | 40 |  |
| 明 | xingkai | 1 | 805 | 8 | 47 |  |
| 和 | xingkai | 2 | 548 | 11 | 42 |  |
| 福 | xingkai | 3 | 725 | 12 | 35 |  |
| 明 | kaishu | 2 | 714 | 11 | 31 |  |

## Failure summary

- missing_font_rows: 0
- failed_skeleton_rows: 0

## Interpretation boundary

这些指标不能代替人工看图。本轮只说明字体轮廓骨架候选是否值得继续探索；不承诺它能直接变成稳定书写轨迹，也不代表真实书法风格学习已经完成。
