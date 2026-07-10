# Median-to-font skeleton alignment prototype index

本索引固定 B 路线 very small-sample median-to-font skeleton alignment / adaptation prototype 的结果。

## Source

- Output directory: `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307`
- Summary: `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\median_font_alignment_summary.csv`
- Report: `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\median_font_alignment_report.md`

## Samples

| char | style | stroke_count | alpha=0.25 distance | alpha=0.5 distance | compare |
|---|---|---:|---:|---:|---|
| 人 | kaishu | 2 | 4.91814 | 3.27876 | `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\u4eba_kaishu\median_font_alignment_compare.png` |
| 山 | lishu | 3 | 29.389616 | 23.972679 | `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\u5c71_lishu\median_font_alignment_compare.png` |

## Boundary

该结果是 median + font skeleton 融合诊断，不是纯 skeleton 轨迹，不是真实笔顺恢复，不生成正式 trajectory.csv，也不接机器人。
