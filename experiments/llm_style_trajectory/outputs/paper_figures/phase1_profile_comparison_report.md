# Phase 1 readonly estimates 非默认对比图验证

## 本轮目的

本轮只验证 `style_profile_phase1_estimates.json` 的全局 scale hints 对可视效果和指标的影响。输出是 comparison-only，不接默认流程，不替换 `style_profiles.json`，不改变 `run_demo.py` 默认行为。

## 输入与候选 profile

- estimates: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_phase1_estimates_20260618_152952\style_profile_phase1_estimates.json`
- current profile: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\configs\style_profiles.json`
- phase1 candidate profile: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\style_profile_phase1_candidate.json`
- candidate `_status`: `comparison_only_not_default`

## 样本统计

- sample_pairs_success: `12`
- row_count_current_plus_phase1: `24`
- failure_count: `0`

## current vs phase1 平均变化

| style | samples | mean_abs_aspect_ratio_delta | mean_abs_path_length_delta | mean_abs_mean_width_delta |
|---|---:|---:|---:|---:|
| kaishu | 3 | 0.0 | 0.0 | 0.0 |
| xingkai | 5 | 0.090515 | 7.508 | 0.006537 |
| lishu | 4 | 0.00168 | 10.367 | 0.0 |

## 初步结论

- kaishu：Phase 1 scale 与当前 profile 基本一致，预期视觉变化很小。
- lishu：全局宽扁 scale 只会带来小幅变化；如果图像仍像“压扁版楷书”，问题不在全局 scale，而在结构/笔画级特征。
- xingkai：Phase 1 只改变全局 scale，保留当前 connector 规则，因此不能据此宣称行楷味已经改善。
- Phase 1 的作用是确认全局比例是否值得接入；如果变化有限，Phase 2 应转向 component/stroke-level style modeling。

## 人工看图优先级

不要只看指标。优先查看以下图和单样本目录：

| priority | char | style | figure | focus |
|---|---|---|---|---|
| medium | 人 | kaishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4eba_all_styles.png` | 人工看图：楷书是否基本不变，作为 Phase 1 对照。 |
| high | 人 | xingkai | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4eba_all_styles.png` | 人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。 |
| high | 人 | lishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4eba_all_styles.png` | 人工看图：隶书是否仍像压扁楷书，是否缺少笔画级隶书特征。 |
| medium | 中 | kaishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4e2d_all_styles.png` | 人工看图：楷书是否基本不变，作为 Phase 1 对照。 |
| high | 中 | xingkai | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4e2d_all_styles.png` | 人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。 |
| high | 中 | lishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u4e2d_all_styles.png` | 人工看图：隶书是否仍像压扁楷书，是否缺少笔画级隶书特征。 |
| high | 好 | lishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u597d_lishu.png` | 人工看图：隶书是否仍像压扁楷书，是否缺少笔画级隶书特征。 |
| high | 风 | lishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u98ce_lishu.png` | 人工看图：隶书是否仍像压扁楷书，是否缺少笔画级隶书特征。 |
| high | 国 | xingkai | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u56fd_xingkai.png` | 人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。 |
| high | 德 | xingkai | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u5fb7_xingkai.png` | 人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。 |
| high | 福 | xingkai | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u798f_xingkai.png` | 人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。 |
| medium | 永 | kaishu | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\phase1_profile_comparison_20260618_155353\figures\compare_current_phase1_u6c38_kaishu.png` | 人工看图：楷书是否基本不变，作为 Phase 1 对照。 |

## 失败样本

- 无。

## 边界

- 字体轮廓不等于真实书写轨迹。
- 本轮不生成真实风格学习结果。
- 本轮不接默认、不调用 API、不连接 CoppeliaSim/AUBO i5、不做 IK、不发送机器人命令。
- Phase 1 未覆盖 connector_trigger、connector_shape、pressure_curve、speed_scale、pen_up_height 等过程参数。
