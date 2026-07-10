# code/ Directory

This directory is no longer the active experiment entry point.

The current project line lives in:

```text
experiments/llm_style_trajectory/
```

## Current Shared Data

The current route may still use Make Me a Hanzi data from:

```text
code/data/makemeahanzi/
```

Important files include:

```text
code/data/makemeahanzi/graphics.txt
code/data/makemeahanzi/dictionary.txt
code/data/makemeahanzi/COPYING
code/data/makemeahanzi/LGPL
```

Do not move this directory unless the new route is updated and tested.

## Legacy Archive

Old image-skeleton, stroke-segmentation, prediction-training, and RL
optimization code has been archived under:

```text
code/legacy_image_skeleton_rl_route/
```

By default, do not add new current-route experiment scripts under `code/`.
New work should go under `experiments/llm_style_trajectory/`.

By default, do not edit the legacy archive unless the goal is to reproduce,
audit, or compare the old image-skeleton/RL route.
