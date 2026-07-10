# B-route registry-gated probe

This trial-only probe compares the registry-selected B-route gate against the existing direct-pulling style references.
It is registry-gated adaptation, not direct pulling.
It does not generate formal trajectory.csv or robot outputs.

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\b_route_registry_probe_20260621_012330`
- status: `trial_only_not_used_by_default`
- registry strategy is chosen from a read-only constraint registry

## Summary

| sample | registry_strategy | fallback_used | before aspect | after aspect | before lower-half | after lower-half | max shift | path ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 山/lishu | component_first_safe | False | 0.945 | 1.049 | 187.343 | 199.554 | 9.85 | 0.989 |
| 风/lishu | fallback_first_reference_only | True | 1.188 | 1.307 | 215.040 | 223.298 | 8.82 | 0.974 |

## Interpretation

- 山/lishu is expected to use component-first safe gating when the component bbox is stable.
- 风/lishu should remain fallback-first reference-only because its section evidence is less stable.
- The registry-gated route is meant to be more controlled than direct pulling, not more aggressive.
