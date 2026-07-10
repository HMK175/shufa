# H1-lite style contrast expansion: 山 / kaishu vs lishu

This report compares the newly generated 山/kaishu H1-lite trial with the existing 山/lishu H1-lite reference.

## Boundary

- trial-only / not_used_by_default。
- 只使用 H2 `usable_for_adaptation` 的 bounded constraints。
- 不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点吸附。
- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\h1_lite_style_contrast_20260619_234043`
- contrast_png: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\h1_lite_style_contrast_20260619_234043\contrast\h1_lite_u5c71_kaishu_lishu_contrast.png`

## Sample metrics

| style | source | aspect median | aspect cons | aspect balanced | lower median | lower cons | lower balanced | max shift cons | max shift balanced | path ratio balanced |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | generated_this_run | 0.945007 | 0.965779 | 0.984478 | 187.343097 | 190.213398 | 192.664933 | 2.388712 | 4.341142 | 0.996284 |
| lishu | existing_h1_lite_reference | 0.945007 | 0.99887 | 1.048676 | 187.343097 | 193.898937 | 199.553901 | 5.461121 | 9.845336 | 0.989006 |

## Style gap

| metric | before | after conservative | after balanced | balanced - before |
|---|---:|---:|---:|---:|
| bbox_aspect_gap | 0.0 | 0.033091 | 0.064198 | 0.064198 |
| lower_half_width_gap | 0.0 | 3.685539 | 6.888968 | 6.888968 |

## Manual visual audit questions

- 山/kaishu 是否仍像楷书、没有被过度拉伸？
- 山/lishu 是否比 kaishu 更宽底、更有隶书感？
- 同字不同风格对照是否比原 style profile 更清楚？
- balanced 是否比 conservative 更自然？

## Interpretation

If the balanced gap is larger while both styles preserve stroke_count and path shape, this supports expanding H1-lite carefully. If kaishu looks stretched or lishu still lacks visible style, the next step should be more visual audit rather than adding stronger constraints.
