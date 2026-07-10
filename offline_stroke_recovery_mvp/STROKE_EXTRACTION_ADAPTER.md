# StrokeExtraction Adapter Notes

## Scope

This adapter treats StrokeExtraction as an external candidate for offline
stroke-region recovery.

It is limited to:

```text
external checkout
-> local feasibility report
-> suggested manual inference command shape
-> later offline output inspection
```

It does not run:

- training
- CoppeliaSim
- AUBO
- SDK motion commands
- real robot execution
- natural-language planning

## External Checkout

Keep StrokeExtraction outside this MVP folder:

```text
external_repos/StrokeExtraction/
```

The intended upstream repository is:

```text
https://github.com/MengLi-l1/StrokeExtraction
```

If Codex network approval is unavailable, clone it manually from the workspace
root:

```powershell
git clone --depth 1 https://github.com/MengLi-l1/StrokeExtraction.git external_repos\StrokeExtraction
```

## Feasibility Report

From the repository root, run:

```powershell
.\offline_stroke_recovery_mvp\scripts\write_stroke_extraction_report.ps1
```

This writes:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_probe/stroke_extraction_feasibility.json
offline_stroke_recovery_mvp/outputs/stroke_extraction_probe/stroke_extraction_feasibility_report.md
```

The report is conservative. If the checkout, environment file, inference
entrypoint, or checkpoints cannot be found, it records a no-go state instead of
pretending the method has run.

## Trial Interpretation

StrokeExtraction is expected to be closer to stroke-instance segmentation than
to full writing-order recovery. A successful run would likely provide stroke
masks or segmentation visualizations. Those outputs still need a separate
mask-to-centerline and ordering step before they can be compared as writable
trajectories.

The local follow-up smoke now does exactly that conversion step for offline
inspection:

```text
offline_stroke_recovery_mvp/scripts/stroke_extraction_trajectory_smoke.py
```

It uses the smoke checkpoints, an adaptive mask threshold, border-component
cleanup, and the existing `run_pipeline` stack to produce trial trajectories
and human-audit images. The result is still noisy and should be treated as a
baseline, not as proof of a robust recovery method.

## Local CUDA Smoke Test

Before downloading RHSEDB or attempting full training, run a synthetic CUDA
probe against the upstream model definitions:

```powershell
python .\offline_stroke_recovery_mvp\scripts\stroke_extraction_cuda_smoke.py --batch-sizes 1,2,4
```

The script does not need RHSEDB or pretrained checkpoints. It only creates
random 256 x 256 tensors, runs forward/backward probes for SDNet, SegNet, and
ExtractNet, and writes:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_cuda_smoke/cuda_smoke_report.json
```

If the current Python environment has CPU-only PyTorch, the report records:

```text
status: cuda_unavailable
```

That means the Python environment cannot see CUDA; it does not mean the local
GPU is unusable. Create a separate CUDA-enabled PyTorch environment before
using the report for memory decisions.

On the local RTX 4060 Ti 8GB machine, the CUDA environment
`torch 2.11.0+cu128` successfully ran the synthetic backward probe for batch
sizes 2 and 4. The recorded peak allocations were below 1 GB for the individual
model probes, so the model definitions themselves are not the immediate memory
bottleneck. Real RHSEDB training can still use more memory because it includes
data loading, saved intermediate datasets, ContentLoss, and longer training
loops.

After downloading RHSEDB, ContentNet, and VGG/CharNet weights, the local RTX
4060 Ti 8GB machine also completed a real-data SDNet training smoke test:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_realdata_smoke.py
stage: sdnet
batch_size: 2
steps: 2
peak allocation: 1272 MiB
elapsed: 67.9 s
```

This confirms that the first real-data stage is runnable on the local machine
for small smoke tests. It is still not evidence that full 40-epoch training is
practical or worthwhile.

## Guarded Training Smoke

For the first trainable upstream stage, a guarded MVP wrapper now exists:

```text
offline_stroke_recovery_mvp/scripts/stroke_extraction_training_smoke.py
```

It does not call the upstream full training recipe. Instead it:

1. runs only a tiny number of SDNet optimization steps
2. saves a temporary `sdnet_model.pth`
3. generates only a tiny number of SegNet/ExtractNet intermediate `.npy`
   samples
4. records file paths and counts in `metadata.json`

Recommended local command:

```powershell
.\.venvs\stroke-extraction-cuda\Scripts\python.exe .\offline_stroke_recovery_mvp\scripts\stroke_extraction_training_smoke.py --sdnet-steps 2 --train-intermediate-samples 2 --test-intermediate-samples 2 --batch-size 2
```

On the local RTX 4060 Ti 8GB machine this guarded command completed with:

```text
completed SDNet steps: 2
generated intermediate samples: train 2 / test 2
peak allocation: 1235 MiB
elapsed: 87.9 s
checkpoint: offline_stroke_recovery_mvp/outputs/stroke_extraction_training_smoke/model/sdnet_model.pth
```

The generated smoke dataset lives under:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_training_smoke/dataset_forSegNet_ExtractNet_RHSEDB_smoke/
```

This is enough to support the next step, which is a SegNet smoke on the
generated small dataset. It is still not evidence that the full upstream
40-epoch / 10-epoch / 20-epoch recipe is practical locally.

That SegNet smoke has now also completed locally on the RTX 4060 Ti 8GB
machine:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_segnet_smoke.py
batch_size: 2
steps: 2
peak allocation: 509 MiB
elapsed: 14.7 s
checkpoint: offline_stroke_recovery_mvp/outputs/stroke_extraction_segnet_smoke/model/model.pth
```

Because the smoke dataset currently contains only one full training batch, the
SegNet smoke script intentionally reuses that batch to complete the requested
small number of steps. This is acceptable for pipeline feasibility checking;
it is not a meaningful training protocol.

The final ExtractNet smoke has also completed locally:

```text
script: offline_stroke_recovery_mvp/scripts/stroke_extraction_extractnet_smoke.py
batch_size: 2
steps: 2
peak allocation: 519 MiB
elapsed: 27.3 s
checkpoint: offline_stroke_recovery_mvp/outputs/stroke_extraction_extractnet_smoke/model/model_extract.pth
```

Human review of the generated `train`/`test` panels shows the chain is
technically connected end-to-end, but the ExtractNet predictions are still
noisy and not yet trajectory-ready. That makes this a viable baseline, not a
finished writable-trajectory solution.

## Boundary

Use StrokeExtraction only as an offline visual/stroke-region candidate in this
thread. Short training smoke is allowed for feasibility checking, but do not
run the full upstream training recipe, CoppeliaSim, AUBO, SDK, or real robot
commands.
