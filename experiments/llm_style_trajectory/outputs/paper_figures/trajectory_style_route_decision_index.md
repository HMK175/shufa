# Trajectory Style Route Decision Index

Date: 2026-06-19

This index records the route-level decision after comparing three directions:

- Route A: MakeMeAHanzi median + style profile
- Route B: median + font skeleton / font mask adaptation
- Route C: font skeleton derived path

## Fixed Files

| file | content |
|---|---|
| `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md` | Human-readable route decision report |
| `experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json` | Machine-readable route status and recommendation |

## Route Status

| route | recommended status | short decision |
|---|---|---|
| A | stable baseline / robot backbone | Keep as default system route and dry-run robotics chain |
| B | safe style adaptation research direction | Continue only with bounded hybrid/adaptation design |
| C | style basis research only | Keep small-sample and manually screened; do not connect to default pipeline |

## Main Recommendation

Do not keep blindly tuning connector/taper, and do not directly replace MakeMeAHanzi median with font skeleton paths.

The next recommended step is a hybrid route design spec:

```text
A supplies stroke order, writability, execution semantics, and robot precheck chain.
B supplies bounded morphology adaptation rules.
C supplies manually screened font-outline style references.
```

## Boundary

This is a decision report only. It adds no generation algorithm, changes no default pipeline, calls no API, and performs no CoppeliaSim/AUBO/SDK/robot action.
