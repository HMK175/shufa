# Style Profile Build Report

## Outputs

- style_metrics.csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_build_20260605_235140\style_metrics.csv`
- style_profile_estimated.json: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_build_20260605_235140\style_profile_estimated.json`
- comparison.csv: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_build_20260605_235140\style_profile_comparison.csv`
- compare_styles.png: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\style_profile_build_20260605_235140\compare_styles.png`

## Render Success Counts

- kaishu: 10
- lishu: 10
- xingkai: 10

## Parameter Sources

- estimated: corner_rounding, horizontal_scale, smoothness, speed_scale, vertical_scale
- default_prior: allow_interstroke_connections, connection_strength, pen_up_height

Static font images cannot reliably estimate inter-stroke connection or pen-up behavior.
Connection strength, allow_interstroke_connections, and pen-up height remain priors in this version.
Kaishu and lishu are forced to no inter-stroke connection; xingkai may keep a hand-set connection prior.
