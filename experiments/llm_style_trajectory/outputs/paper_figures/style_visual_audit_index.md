# Style Visual Audit Index

源输出目录：`experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321`

| 文件 | 内容 |
|---|---|
| `visual_audit_report.md` | 异常/代表样本人工看图校验报告 |
| `visual_audit_checklist.md` | 可逐项人工标注的看图清单 |
| `visual_audit_candidates.csv` | 候选样本、指标与选择理由 |

- candidate_count: `18`
- case_type_counts: `{'high_aspect_spread': 5, 'high_lishu_aspect': 3, 'long_xingkai_connector': 3, 'low_aspect_spread': 3, 'representative': 4}`

边界：该索引只整理人工视觉校验包。本轮不调参、不调用 API、不连接仿真器或机器人。