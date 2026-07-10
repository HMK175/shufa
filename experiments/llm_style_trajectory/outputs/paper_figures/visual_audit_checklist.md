# 风格诊断人工看图校验清单

本清单用于人工视觉校验。不能只看指标得出最终视觉效果结论。
请逐项打开图片，记录是否自然、是否可区分、是否需要后续调参。

## 1. 人 / 楷书

- case_type: `high_aspect_spread`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\01_人_kaishu_high_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4eba_kaishu_20260617_200750_708344`
- reason: 人 的三风格 aspect_ratio 差异较强，spread=0.621
- 人工看图重点: 看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。
- 指标: aspect_ratio=1.414861, path_length=351.564, connection_count=0, connector_draw_length=0.0, mean_width=9.0

## 2. 人 / 隶书

- case_type: `high_aspect_spread`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\02_人_lishu_high_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4eba_lishu_20260617_200751_133475`
- reason: 人 的三风格 aspect_ratio 差异较强，spread=0.621
- 人工看图重点: 看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。
- 指标: aspect_ratio=2.036019, path_length=351.73, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 3. 人 / 行楷

- case_type: `high_aspect_spread`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\03_人_xingkai_high_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4eba_xingkai_20260617_200750_905177`
- reason: 人 的三风格 aspect_ratio 差异较强，spread=0.621
- 人工看图重点: 看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。
- 指标: aspect_ratio=1.487047, path_length=484.146, connection_count=1, connector_draw_length=131.33, mean_width=8.074409

## 4. 好 / 楷书

- case_type: `high_aspect_spread`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\04_好_kaishu_high_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u597d_kaishu_20260617_200753_941974`
- reason: 好 的三风格 aspect_ratio 差异较强，spread=0.531
- 人工看图重点: 看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。
- 指标: aspect_ratio=1.213725, path_length=792.516, connection_count=0, connector_draw_length=0.0, mean_width=9.0

## 5. 好 / 隶书

- case_type: `high_aspect_spread`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\05_好_lishu_high_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u597d_lishu_20260617_200754_538622`
- reason: 好 的三风格 aspect_ratio 差异较强，spread=0.531
- 人工看图重点: 看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。
- 指标: aspect_ratio=1.745202, path_length=802.753, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 6. 国 / 行楷

- case_type: `long_xingkai_connector`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\06_国_xingkai_long_xingkai_connector.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u56fd_xingkai_20260617_200802_724631`
- reason: 行楷 connector_draw_length 较长：810.947
- 人工看图重点: 优先看连接段是否过长、过直或穿越部件；判断是否需要限制 connector 规则。
- 指标: aspect_ratio=0.848725, path_length=1928.631, connection_count=7, connector_draw_length=810.947, mean_width=7.29022

## 7. 德 / 行楷

- case_type: `long_xingkai_connector`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\07_德_xingkai_long_xingkai_connector.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u5fb7_xingkai_20260617_200807_821353`
- reason: 行楷 connector_draw_length 较长：878.275
- 人工看图重点: 优先看连接段是否过长、过直或穿越部件；判断是否需要限制 connector 规则。
- 指标: aspect_ratio=1.092558, path_length=1971.169, connection_count=14, connector_draw_length=878.275, mean_width=7.158401

## 8. 福 / 行楷

- case_type: `long_xingkai_connector`
- priority: `1`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\08_福_xingkai_long_xingkai_connector.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u798f_xingkai_20260617_200806_334042`
- reason: 行楷 connector_draw_length 较长：886.413
- 人工看图重点: 优先看连接段是否过长、过直或穿越部件；判断是否需要限制 connector 规则。
- 指标: aspect_ratio=1.094683, path_length=1951.564, connection_count=12, connector_draw_length=886.413, mean_width=7.112963

## 9. 人 / 隶书

- case_type: `high_lishu_aspect`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\09_人_lishu_high_lishu_aspect.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4eba_lishu_20260617_200751_133475`
- reason: 隶书 aspect_ratio 较高：2.036
- 人工看图重点: 看 lishu 是否宽扁过度；是否只是全局横向拉伸而缺少隶书笔意。
- 指标: aspect_ratio=2.036019, path_length=351.73, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 10. 好 / 隶书

- case_type: `high_lishu_aspect`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\10_好_lishu_high_lishu_aspect.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u597d_lishu_20260617_200754_538622`
- reason: 隶书 aspect_ratio 较高：1.745
- 人工看图重点: 看 lishu 是否宽扁过度；是否只是全局横向拉伸而缺少隶书笔意。
- 指标: aspect_ratio=1.745202, path_length=802.753, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 11. 风 / 隶书

- case_type: `high_lishu_aspect`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\11_风_lishu_high_lishu_aspect.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u98ce_lishu_20260617_200805_153657`
- reason: 隶书 aspect_ratio 较高：1.714
- 人工看图重点: 看 lishu 是否宽扁过度；是否只是全局横向拉伸而缺少隶书笔意。
- 指标: aspect_ratio=1.714482, path_length=743.602, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 12. 中 / 楷书

- case_type: `low_aspect_spread`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\12_中_kaishu_low_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4e2d_kaishu_20260617_200746_949523`
- reason: 中 的三风格 aspect_ratio 差异较弱，spread=0.304
- 人工看图重点: 看三风格是否肉眼难分；若难分，后续可能需要重新估计部件比例和笔画风格参数。
- 指标: aspect_ratio=0.693486, path_length=603.423, connection_count=0, connector_draw_length=0.0, mean_width=9.0

## 13. 中 / 隶书

- case_type: `low_aspect_spread`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\13_中_lishu_low_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4e2d_lishu_20260617_200747_434585`
- reason: 中 的三风格 aspect_ratio 差异较弱，spread=0.304
- 人工看图重点: 看三风格是否肉眼难分；若难分，后续可能需要重新估计部件比例和笔画风格参数。
- 指标: aspect_ratio=0.997268, path_length=595.574, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 14. 中 / 行楷

- case_type: `low_aspect_spread`
- priority: `2`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\14_中_xingkai_low_aspect_spread.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u4e2d_xingkai_20260617_200747_188596`
- reason: 中 的三风格 aspect_ratio 差异较弱，spread=0.304
- 人工看图重点: 看三风格是否肉眼难分；若难分，后续可能需要重新估计部件比例和笔画风格参数。
- 指标: aspect_ratio=0.730097, path_length=915.162, connection_count=3, connector_draw_length=310.786, mean_width=7.715285

## 15. 和 / 楷书

- case_type: `representative`
- priority: `5`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\15_和_kaishu_representative.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u548c_kaishu_20260617_200754_846285`
- reason: 楷书 接近当前风格均值，可作异常样本对照。
- 人工看图重点: 作为对照样本看该风格的平均视觉效果是否可接受。
- 指标: aspect_ratio=0.992528, path_length=840.752, connection_count=0, connector_draw_length=0.0, mean_width=9.0

## 16. 和 / 隶书

- case_type: `representative`
- priority: `5`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\16_和_lishu_representative.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u548c_lishu_20260617_200755_453193`
- reason: 隶书 接近当前风格均值，可作异常样本对照。
- 人工看图重点: 作为对照样本看该风格的平均视觉效果是否可接受。
- 指标: aspect_ratio=1.428057, path_length=842.811, connection_count=0, connector_draw_length=0.0, mean_width=10.0

## 17. 和 / 行楷

- case_type: `representative`
- priority: `5`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\17_和_xingkai_representative.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u548c_xingkai_20260617_200755_134353`
- reason: 行楷 接近当前风格均值，可作异常样本对照。
- 人工看图重点: 作为对照样本看该风格的平均视觉效果是否可接受。
- 指标: aspect_ratio=1.044831, path_length=1375.19, connection_count=7, connector_draw_length=531.326, mean_width=7.469496

## 18. 思 / 楷书

- case_type: `representative`
- priority: `5`
- image: `experiments\llm_style_trajectory\outputs\style_visual_audit_20260617_224321\selected_images\18_思_kaishu_representative.png`
- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_diagnostics_20260617_200746\u601d_kaishu_20260617_200757_561274`
- reason: 楷书 接近当前风格均值，可作异常样本对照。
- 人工看图重点: 作为对照样本看该风格的平均视觉效果是否可接受。
- 指标: aspect_ratio=1.091889, path_length=880.877, connection_count=0, connector_draw_length=0.0, mean_width=9.0
