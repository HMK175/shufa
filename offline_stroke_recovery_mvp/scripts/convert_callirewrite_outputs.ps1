param(
    [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$SeqDataDir = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if ($SeqDataDir -eq "") {
    $SeqDataDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\callirewrite_runtime_probe\__new_train_phase_2\seq_data"
}
if ($OutputDir -eq "") {
    $OutputDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\callirewrite_runtime_probe\converted"
}

$pythonExe = Join-Path $WorkspaceRoot ".venvs\callirewrite-seq\Scripts\python.exe"
if (!(Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}
if (!(Test-Path -LiteralPath $SeqDataDir)) {
    throw "Missing seq_data directory: $SeqDataDir"
}

$script = @"
from pathlib import Path
import sys

workspace = Path(sys.argv[1])
seq_data_dir = Path(sys.argv[2])
output_dir = Path(sys.argv[3])

sys.path.insert(0, str(workspace / "offline_stroke_recovery_mvp" / "src"))
from callirewrite_adapter import convert_callirewrite_npz_to_outputs

summaries = []
for npz_path in sorted(seq_data_dir.glob("*.npz")):
    summaries.append(convert_callirewrite_npz_to_outputs(npz_path, output_dir / npz_path.stem))

print("Converted {} CalliRewrite .npz files".format(len(summaries)))
for path in summaries:
    print(path)
"@

$tempScript = Join-Path $env:TEMP "convert_callirewrite_outputs.py"
Set-Content -LiteralPath $tempScript -Value $script -Encoding UTF8
try {
    & $pythonExe $tempScript $WorkspaceRoot $SeqDataDir $OutputDir
}
finally {
    Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
}
