# Hybrid Style Trajectory Design Index

Date: 2026-06-19

This index records the design-only hybrid route specification after the A/B/C route decision.

## Fixed Files

| file | content |
|---|---|
| `experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md` | Human-readable hybrid route architecture and interface contract |
| `experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json` | Machine-readable module contract and prototype options |
| `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md` | Previous route decision report |
| `experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json` | Previous route decision JSON summary |

## Hybrid Core

```text
A route: stable median trajectory, stroke order, execution and robot precheck backbone
B route: bounded adaptation module, trial-only, preserves stroke order and stroke count
C route: font-reference module, manually screened, does not directly replace A
Human audit gate: required before visual style claims or any prototype promotion
```

## Recommended Next Prototype

| id | name | recommendation |
|---|---|---|
| H1 | A median + B bounded adaptation | useful later, but current B evidence still hits caps on lishu |
| H2 | A median + C font reference constraints only | recommended next step |
| H3 | A baseline + C-derived style exemplar visualization | useful for paper evidence |

Recommended: H2, because it defines which font-derived references are trustworthy before attempting more point movement.

## Boundary

This is a design specification only. It does not add algorithms, does not tune parameters, does not change the default pipeline, does not generate trajectories, and does not connect API, CoppeliaSim, AUBO i5, SDK, or robot control.
