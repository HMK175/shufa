# CalliRewrite Adapter Notes

## Scope

This adapter treats CalliRewrite as an external coarse-sequence baseline for
offline comparison.

It is limited to:

```text
input images
-> CalliRewrite seq_extract output .npz files
-> local recovered_strokes JSON
-> local trial_ordered_trajectory.csv
-> offline visual/manual audit
```

It does not run:

- RL fine-tuning
- calibration
- CoppeliaSim
- AUBO
- SDK motion commands
- real robot execution

## External Checkout

Keep CalliRewrite outside this MVP folder, for example:

```text
external_repos/CalliRewrite/
```

The adapter expects the external project to contain:

```text
external_repos/CalliRewrite/seq_extract/test.py
external_repos/CalliRewrite/seq_extract/environment.yml
external_repos/CalliRewrite/seq_extract/outputs/snapshot/<model_name>/
```

The default model name is:

```text
new_train_phase_2
```

## Feasibility Report

From the repository root, run:

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('offline_stroke_recovery_mvp/src'))); from callirewrite_adapter import write_callirewrite_feasibility_report; write_callirewrite_feasibility_report(Path('external_repos/CalliRewrite'), Path('offline_stroke_recovery_mvp/outputs/visual_smoke_probe_after_review/inputs'), Path('offline_stroke_recovery_mvp/outputs/callirewrite_probe'))"
```

This writes:

```text
offline_stroke_recovery_mvp/outputs/callirewrite_probe/callirewrite_feasibility.json
offline_stroke_recovery_mvp/outputs/callirewrite_probe/callirewrite_feasibility_report.md
```

If the external checkout or checkpoints are missing, the report records a
`no_go_until_external_checkout_is_ready` decision instead of pretending the
baseline ran.

## Suggested External Command

When the external checkout and checkpoints are ready, the adapter reports a
command shaped like:

```powershell
cd external_repos/CalliRewrite/seq_extract
python ./test.py --input <input_dir> --model new_train_phase_2
```

Run this only inside CalliRewrite's own environment.

## Windows CPU Runtime Notes

The successful local probe used a workspace-local uv environment:

```powershell
cd "D:\sw data\vscode\shufa"

$env:UV_CACHE_DIR = "$PWD\.uv_cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv_python"
uv python install 3.10 --install-dir ".uv_python"
uv venv ".venvs\callirewrite-seq" --python 3.10

uv --cache-dir ".uv_cache" pip install --python ".\.venvs\callirewrite-seq\Scripts\python.exe" `
  pip setuptools wheel six==1.16.0 numpy==1.23.5 scipy==1.10.1 `
  pillow==10.2.0 opencv-python==4.9.0.80 matplotlib==3.7.4 `
  protobuf==3.19.6 tensorflow==2.10.1 gizeh==0.1.11 cairocffi==1.6.1
```

TensorFlow prints CUDA DLL warnings on CPU-only Windows. They are expected for
this probe as long as inference continues after `Skipping registering GPU
devices...`.

Three small compatibility patches were needed in the external checkout:

- lazy-load `dataset_utils` `GizehRasterizor`, so inference import does not fail
  when Windows lacks the native Cairo DLL;
- skip `outputs/snapshot/pretrain_perceptual_model` when it is absent, because
  this probe only uses sampling inference and does not call perceptual loss;
- support environment-variable paths for model and sampling output roots, plus
  `CALLIREWRITE_SKIP_GIF=1` to avoid auxiliary GIF generation.

Because Codex sandbox writes are tied to the process working directory, run the
external entrypoint from the repository root and set `PYTHONPATH` to
`seq_extract`, instead of `cd`-ing into the external repo:

```powershell
cd "D:\sw data\vscode\shufa"

$env:MPLCONFIGDIR = "D:\sw data\vscode\shufa\.mplconfig"
$env:CUDA_VISIBLE_DEVICES = ""
$env:CALLIREWRITE_SKIP_GIF = "1"
$env:CALLIREWRITE_SAMPLING_BASE_DIR = "D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\callirewrite_runtime_probe"
$env:CALLIREWRITE_MODEL_BASE_DIR = "D:\sw data\vscode\shufa\external_repos\CalliRewrite\seq_extract\outputs\snapshot"
$env:PYTHONPATH = "D:\sw data\vscode\shufa\external_repos\CalliRewrite\seq_extract"

.\.venvs\callirewrite-seq\Scripts\python.exe `
  "D:\sw data\vscode\shufa\external_repos\CalliRewrite\seq_extract\test.py" `
  --input "D:\sw data\vscode\shufa\offline_stroke_recovery_mvp\outputs\visual_smoke_probe_after_review\inputs" `
  --model new_train_phase_2 `
  --sample 1
```

The same command is wrapped by:

```powershell
.\offline_stroke_recovery_mvp\scripts\run_callirewrite_probe.ps1
```

This probe produced `.npz` and PNG visualizations under:

```text
offline_stroke_recovery_mvp/outputs/callirewrite_runtime_probe/__new_train_phase_2/
```

The converted local trajectory files are under:

```text
offline_stroke_recovery_mvp/outputs/callirewrite_runtime_probe/converted/<sample>/
```

Batch conversion is wrapped by:

```powershell
.\offline_stroke_recovery_mvp\scripts\convert_callirewrite_outputs.ps1
```

## Local Hybrid Probe

Once the converted per-sample folders exist, the local hybrid probe can attach
the repository's own continuity-oriented postprocess and manual-audit outputs:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py
```

This writes a fresh timestamped batch under:

```text
offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/
```

including:

```text
batch_report.md
manual_audit_sheet.csv
visual_audit_contact_sheet.png
callirewrite_hybrid_probe_report.json
<sample>/candidate_order.png
<sample>/callirewrite_source_trajectory.png
<sample>/final_trajectory.png
<sample>/trial_ordered_trajectory.csv
```

This stage stays within the current thread boundary:

- CalliRewrite provides the external coarse visual recovery
- local code only adds continuity-oriented postprocess and audit artifacts
- no RL fine-tuning, CoppeliaSim, AUBO, SDK, or robot execution is introduced
- results still require human visual inspection

## Output Conversion

For a CalliRewrite `.npz` sequence file, run:

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('offline_stroke_recovery_mvp/src'))); from callirewrite_adapter import convert_callirewrite_npz_to_outputs; convert_callirewrite_npz_to_outputs(Path('<sample>.npz'), Path('offline_stroke_recovery_mvp/outputs/callirewrite_converted/<sample>'))"
```

This writes:

```text
callirewrite_recovered_strokes.json
trial_ordered_trajectory.csv
callirewrite_summary.json
```

The conversion is approximate and meant for offline visual comparison. It does
not claim true stroke order or robot readiness by itself.
