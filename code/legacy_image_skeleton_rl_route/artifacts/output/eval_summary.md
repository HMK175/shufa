# 2026-05-18 Evaluation Summary

Source CSV:
- `code/output/tune_eval.csv`
- `code/output/holdout_eval.csv`

## Overall

| subset | total | count correct | highest max winding |
|---|---:|---:|---|
| tune | 12 | 6 | fu = 4.59 |
| holdout | 13 | 12 | xiu = 3.99 |

Note: `count_correct=no` requires care when `expected` is empty. In the current
tune CSV, `yi/san/shi/kou/tian/mu` are marked not correct because expected
counts are not recorded in `stroke_knowledge.py`, not necessarily because the
final stroke count is wrong.

## Tune Set

Current `count_correct=no` rows:

| char | expected | final CSV strokes | method | fallback | max winding | note |
|---|---:|---:|---|---|---:|---|
| yi | - | 1 | legacy+prior | legacy_preferred_conservative_gate;simple_prior_longest_main_stroke | 1.35 | expected missing |
| san | - | 3 | global+prior | none | 1.65 | expected missing |
| shi | - | 4 | legacy | legacy_preferred_conservative_gate | 1.14 | expected missing |
| kou | - | 3 | global | none | 1.65 | expected missing |
| tian | - | 5 | legacy+prior | global_high_winding;closed_prior_split_frame_detour | 2.47 | expected missing |
| mu | - | 7 | legacy | legacy_preferred_conservative_gate | 1.77 | expected missing |

Known-expected tune samples are all count-correct:
`zhong, chuan, zhi, yong, fu, ming`.

## Holdout Set

Count mismatch:

| char | expected | final CSV strokes | method | fallback | max winding |
|---|---:|---:|---|---|---:|
| ri | 4 | 3 | legacy | global_count_farther_from_expected | 1.55 |

## Problem Classes

### A. Stroke Count Issues

- `ri`: expected 4, final 3. This is the only confirmed count mismatch in
  holdout.
- `yi/san/shi/kou/tian/mu`: tune rows marked incorrect because expected count is
  empty. First decide whether to add engineering expected counts before treating
  them as algorithm errors.

### B. Count Correct But High Winding

- `fu`: final 13 matches expected 13, max winding 4.59.
- `xiu`: final 6 matches expected 6, max winding 3.99.

Secondary watchlist below the main threshold:
`guo=3.44`, `hui=3.38`, `xiao=3.28`, `hao=3.26`, `shan=3.23`, `shui=3.12`.

### C. Stable Demonstration Candidates

Good candidates for paper figures and qualitative examples:
`yi, san, chuan, kou, tian, zhong, shui, pin`.

## Next Priorities

1. Explain why tune set is only 6/12 count-correct: likely first a validation
   data issue because six tune rows have empty expected counts.
2. Fix `ri` missing one stroke after the validation target is clarified.
3. Investigate high-winding cases `xiu` and `fu` without disturbing the stable
   demonstration samples.

