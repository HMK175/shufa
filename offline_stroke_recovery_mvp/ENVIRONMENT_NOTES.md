# Environment Notes

This route should be runnable without robot tools, CoppeliaSim, AUBO SDK, or
network access during normal iteration. The main reliability rule is:

```text
keep runtime, caches, model paths, inputs, and outputs inside the workspace
```

## Known Failure Classes

### Approval service 503

Codex sometimes cannot request elevated or network permissions because the
approval review service returns `503 Service Unavailable`. This is outside the
project and cannot be fixed from repository code.

Practical mitigation:

- avoid commands that require elevation during normal iteration;
- ask the user to run one-time network commands manually;
- keep reusable scripts in `offline_stroke_recovery_mvp/scripts/`;
- avoid recursive delete/move cleanup unless truly necessary.

### Network and package installation

Do network setup manually from PowerShell, then reuse the installed workspace
environment:

```powershell
cd "D:\sw data\vscode\shufa"

$env:UV_CACHE_DIR = "$PWD\.uv_cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv_python"
uv python install 3.10 --install-dir ".uv_python"
uv venv ".venvs\callirewrite-seq" --python 3.10
```

For CalliRewrite, install the pinned Windows CPU dependency set once:

```powershell
uv --cache-dir ".uv_cache" pip install --python ".\.venvs\callirewrite-seq\Scripts\python.exe" `
  pip setuptools wheel six==1.16.0 numpy==1.23.5 scipy==1.10.1 `
  pillow==10.2.0 opencv-python==4.9.0.80 matplotlib==3.7.4 `
  protobuf==3.19.6 tensorflow==2.10.1 gizeh==0.1.11 cairocffi==1.6.1
```

After this, normal runs should not need package downloads.

### User AppData permissions

Avoid virtual environments that point to `C:\Users\TRN\AppData\...`, because the
Codex sandbox user may not be able to execute that interpreter. Use
`.uv_python` and `.venvs` under the workspace instead.

### Matplotlib cache permissions

Set `MPLCONFIGDIR` under the workspace before importing `matplotlib`:

```powershell
$env:MPLCONFIGDIR = "D:\sw data\vscode\shufa\.mplconfig"
```

### External repo working directory writes

When launching external Python code from Codex, prefer working directory
`D:\sw data\vscode\shufa` and set `PYTHONPATH` to the external package. In this
project, launching CalliRewrite from `external_repos/CalliRewrite/seq_extract`
caused write permission failures for workspace output directories.

Use:

```powershell
.\offline_stroke_recovery_mvp\scripts\run_callirewrite_probe.ps1
.\offline_stroke_recovery_mvp\scripts\convert_callirewrite_outputs.ps1
```

instead of running ad hoc commands from inside the external checkout.

## Offline Verification

Run the local MVP tests:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests -q
```

For visual outputs, do manual inspection. Metrics and successful file creation
do not prove stroke order quality.
