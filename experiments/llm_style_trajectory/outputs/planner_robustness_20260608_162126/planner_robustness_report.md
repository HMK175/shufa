# Planner Robustness Report

## Metrics

- total: 12
- validation_ok_count: 0/12
- char_correct_count: 0/12
- style_correct_count: 0/12
- connection_constraint_correct_count: 8/12
- expected_invalid_rejected_count: 3/12
- dangerous_output_count: 0/12
- json_parse_success_count: 0/12
- average_latency: 0.0

## Typical Success

- none

## Typical Failure

- `standard_xingkai_shan`: 写一个行楷风格的山 -> api planner not configured; set LLM_STYLE_PLANNER_API_KEY; use --fallback-to-mock for the rule-based planner

## Notes

- API keys are read from environment variables and are not written to this report.
- LLM output is validated before local trajectory generation.
- Dangerous trajectory/CSV/point fields are either removed with warnings or rejected by validation.
