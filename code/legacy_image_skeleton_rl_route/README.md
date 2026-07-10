# Legacy Image Skeleton + RL Route

This directory archives the old route:

```text
image input
-> skeleton extraction
-> stroke segmentation / candidate tracing
-> stroke classification and next-stroke prediction training
-> local trajectory optimization / RL experiments
```

It is kept for historical reproduction and comparison only. The current project
line is in:

```text
experiments/llm_style_trajectory/
```

## Layout

```text
scripts/
models/
lists/
artifacts/
```

- `scripts/`: old Python scripts and modules, including `stroke.py`,
  `pipeline.py`, skeleton extraction, Make Me a Hanzi import/generation tools,
  segmentation/prediction training scripts, and RL/trajectory optimization
  utilities.
- `models/`: old model metadata JSON files.
- `lists/`: old tune/holdout character lists.
- `artifacts/`: old local generated datasets, caches, outputs, and preview
  artifacts. These are not part of the current route.

## Usage Boundary

These files do not participate in the current `experiments/llm_style_trajectory`
test suite by default.

If future work needs to reproduce or compare the old route, first check path
references, Python import paths, model/data locations, and environment
dependencies. Paths inside these scripts may still assume the old `code/` root
layout and may need local adaptation for a controlled reproduction run.

Do not connect this archive to the current LLM-style trajectory pipeline without
an explicit migration task and tests.
