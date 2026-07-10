# StrokeExtraction Trial Plan

## Goal

Try StrokeExtraction as a second public-code candidate for the independent
offline image-to-stroke route.

The immediate goal is not to make it the main method. The trial should answer:

1. Is the public repository locally reproducible enough to run on our smoke
   character images?
2. Does it output stroke-instance masks, direct centerlines, or only visual
   segmentation figures?
3. Can its output be converted into our local offline trajectory format without
   claiming true stroke order?

## Boundaries

This trial stays offline:

- no CoppeliaSim
- no AUBO
- no SDK motion commands
- no robot connection
- no natural-language planner
- no full upstream training unless a later experiment explicitly chooses it

The external repository stays outside this MVP folder:

```text
external_repos/StrokeExtraction/
```

The MVP folder may contain only adapters, scripts, reports, and converted
outputs.

## Planned Steps

1. Add a thin audit/report adapter for the external checkout.
2. Generate a no-go report when the checkout, entrypoint, requirements, or
   checkpoints are missing.
3. Provide a repeatable PowerShell report script that can be rerun after the
   user manually clones or downloads files.
4. Run a guarded SDNet smoke on the local CUDA machine, save a temporary
   checkpoint, and generate only a tiny SegNet/ExtractNet intermediate dataset.
5. Run SegNet on the generated small dataset and measure whether the next stage
   is locally reproducible.
6. If the output contains usable stroke masks, convert each mask to local
   skeleton paths and export `trial_ordered_trajectory.csv` for visual
   inspection.

## Initial Assumption

StrokeExtraction is expected to be closer to stroke-instance segmentation than
to full writing-order recovery. It is therefore treated as a candidate visual
stroke-region source, not as evidence of true historical stroke order.

## Current Status

The guarded SDNet smoke has already completed locally on the RTX 4060 Ti 8GB
machine:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_training_smoke.py
SDNet steps: 2
generated intermediate samples: train 2 / test 2
peak allocation: 1235 MiB
elapsed: 87.9 s
```

That SegNet question is now answered at smoke-test level as well:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_segnet_smoke.py
batch_size: 2
steps: 2
peak allocation: 509 MiB
elapsed: 14.7 s
```

So the next technical step is no longer "can SegNet consume the smoke
dataset?" but "can we push one stage further into ExtractNet, or should we
pause here and first inspect whether the upstream segmentation outputs are
visually useful for our writable-trajectory route?"

That answer is now in hand as well:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_extractnet_smoke.py
batch_size: 2
steps: 2
peak allocation: 519 MiB
elapsed: 27.3 s
```

Manual review of the generated panels suggests the full chain is connected,
but ExtractNet is still noisy. The route therefore needs one more layer of
trajectory-aware post-processing before it can be treated as a writable
trajectory source.

That post-processing layer now exists as a guarded offline smoke:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_trajectory_smoke.py
batch_size: 2
mask_quantile: 0.7
completed samples: 2 (train 1 / test 1)
```

It converts the smoke checkpoints into local trajectory debug artifacts via
adaptive mask cleanup and the existing skeleton/ordering/export stack. The
train sample is promising and the test sample is still noisy, so this remains a
baseline for manual inspection rather than a finished writable-trajectory
solution.
