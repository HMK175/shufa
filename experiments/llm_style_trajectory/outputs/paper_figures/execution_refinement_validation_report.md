# candidate_default_v1 多样本验证

## 本轮目的

本轮只验证 `candidate_default_v1`，不继续调参，不新增 balanced 档，不替换全局默认。
目标是把已有人看图认可的 conservative connector + simple_taper 应用到更多样本，检查它是否适合作为后续默认 execution layer 候选。

## 输入与输出

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238`
- candidate_default: `candidate_default_v1`
- connector_rule: `conservative`
- stroke_width_profile: `simple_taper`
- status: `accepted_for_next_round_candidate`

## 样本统计

- selected_count: `18`
- success_count: `18`
- failure_count: `0`
- xingkai_success_count: `8`
- non_xingkai_success_count: `10`

## 核心判断

- xingkai connector 平均 reduction_ratio: `0.927083`
- xingkai after 仍保留 connector 的样本数: `4` / `8`
- kaishu/lishu connector violation: `0`
- stroke taper 是否生效：看 `after_stroke_width_range` 与 `after_stroke_pressure_range` 是否大于 before。

## before/after 指标表

| char | style | conn before | conn after | connector length before | connector length after | stroke width range before | stroke width range after | violation |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 国 | xingkai | 7 | 1 | 810.946 | 106.146 | 0.0 | 3.23 | False |
| 德 | xingkai | 14 | 1 | 878.276 | 45.035 | 0.0 | 3.23 | False |
| 福 | xingkai | 12 | 1 | 886.416 | 96.856 | 0.0 | 3.229996 | False |
| 和 | xingkai | 7 | 2 | 531.324 | 101.215 | 0.0 | 3.229996 | False |
| 中 | xingkai | 3 | 0 | 310.785 | 0.0 | 0.0 | 3.229764 | False |
| 人 | xingkai | 1 | 0 | 131.331 | 0.0 | 0.0 | 3.226268 | False |
| 明 | xingkai | 7 | 0 | 785.3 | 0.0 | 0.0 | 3.229995 | False |
| 林 | xingkai | 7 | 0 | 603.738 | 0.0 | 0.0 | 3.229995 | False |
| 人 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.054751 | False |
| 人 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.3998 | False |
| 中 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.059968 | False |
| 中 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.399991 | False |
| 好 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.399957 | False |
| 风 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.399992 | False |
| 好 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.059986 | False |
| 和 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.059997 | False |
| 和 | lishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.4 | False |
| 思 | kaishu | 0 | 0 | 0.0 | 0.0 | 0.0 | 3.059999 | False |

## 需要人工看图的样本

- 国 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u56fd_xingkai.png`；人工看图：确认 connector 是否从过多变为自然少量连接。
- 德 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u5fb7_xingkai.png`；人工看图：确认 connector 是否从过多变为自然少量连接。
- 福 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u798f_xingkai.png`；人工看图：确认 connector 是否从过多变为自然少量连接。
- 和 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u548c_xingkai.png`；人工看图：确认 connector 是否从过多变为自然少量连接。
- 中 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4e2d_xingkai.png`；人工看图：确认 candidate_default_v1 是否过于保守，connector 是否太少。
- 人 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4eba_xingkai.png`；人工看图：确认 candidate_default_v1 是否过于保守，connector 是否太少。
- 明 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u660e_xingkai.png`；人工看图：确认 candidate_default_v1 是否过于保守，connector 是否太少。
- 林 / xingkai: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u6797_xingkai.png`；人工看图：确认 candidate_default_v1 是否过于保守，connector 是否太少。
- 人 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4eba_kaishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 人 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4eba_lishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 中 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4e2d_kaishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 中 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u4e2d_lishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 好 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u597d_lishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 风 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u98ce_lishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 好 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u597d_kaishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 和 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u548c_kaishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 和 / lishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u548c_lishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。
- 思 / kaishu: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\execution_refinement_validation_20260618_120238\figures\before_after_u601d_kaishu.png`；人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。

## 边界

- candidate_default_v1 不是全局默认。
- 本轮不继续调参，不新增 balanced 档。
- 本轮不解决 lishu 真实风格来源问题。
- 本轮不代表真实笔刷模型。
- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。

## 下一步建议

- 如果用户觉得 connector 太少，再设计 balanced 档。
- 如果用户接受本轮多样本图，可以下一轮考虑把 candidate_default_v1 接入默认 execution 层或论文 refined baseline。
