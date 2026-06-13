# Planner Robustness Report

## Metrics

- total: 12
- validation_ok_count: 9/12
- char_correct_count: 12/12
- style_correct_count: 12/12
- connection_constraint_correct_count: 12/12
- expected_invalid_rejected_count: 3/12
- dangerous_output_count: 0/12
- json_parse_success_count: 12/12
- average_latency: 0.0459

## Typical Success

- `standard_xingkai_shan`: 写一个行楷风格的山 -> char=山, style=xingkai

## Typical Failure

- `unsupported_caoshu_shan`: 写一个草书风格的山 -> unsupported style requested: 草书; style is not available in style profiles: caoshu

## Notes

- API keys are read from environment variables and are not written to this report.
- LLM output is validated before local trajectory generation.
- Dangerous trajectory/CSV/point fields are either removed with warnings or rejected by validation.
