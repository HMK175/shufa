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
- average_latency: 0.0136

## Typical Success

- none

## Typical Failure

- `standard_xingkai_shan`: 写一个行楷风格的山 -> api planner request failed: [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。

## Notes

- API keys are read from environment variables and are not written to this report.
- LLM output is validated before local trajectory generation.
- Dangerous trajectory/CSV/point fields are either removed with warnings or rejected by validation.
