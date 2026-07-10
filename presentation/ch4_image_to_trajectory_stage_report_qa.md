# 阶段汇报 PPT QA

- 生成状态：成功
- 幻灯片数：6
- 预览图数：6
- 自检方式：原生 PPTX 包结构检查 + 本地预览图人工目检

## 已检查

- 标题、图片和文字框均保持在 16:9 画布内
- 内容页总数为 5 页，符合不超过 5 页的要求
- 主图均来自本地已有结果图，无新增复杂重绘
- 整体语气保持为阶段性介绍，不宣称问题已完全解决

## 使用图片

- `D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_hybrid_probe\callirewrite_hybrid_batch_20260701_154310_079390\visual_audit_contact_sheet.png`
- `D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_hybrid_probe\callirewrite_hybrid_batch_20260701_154310_079390\kou\rendered_execution.png`
- `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\paper_figures\mini_paper_figures\fig4_execution_width_pressure.png`
- `D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_hybrid_probe\callirewrite_hybrid_batch_20260701_154310_079390\xin\rendered_execution.png`
- `D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_hybrid_probe\callirewrite_hybrid_batch_20260701_154310_079390\yong\rendered_execution.png`
- `D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_hybrid_probe\callirewrite_hybrid_batch_20260701_154310_079390\zhong\rendered_execution.png`

## 已知限制

- 当前环境无法直接调用 PowerPoint 或 python-pptx 渲染整套文件，因此最终版式依赖生成脚本的预览自检。
- 汇报仍建议在正式使用前人工打开 PPT 再快速过一遍字号和图片位置。
