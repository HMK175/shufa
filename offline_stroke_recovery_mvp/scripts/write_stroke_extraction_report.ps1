param(
    [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$CheckoutDir = "",
    [string]$InputDir = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if ($CheckoutDir -eq "") {
    $CheckoutDir = Join-Path $WorkspaceRoot "external_repos\StrokeExtraction"
}
if ($InputDir -eq "") {
    $InputDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\visual_smoke_probe_after_review\inputs"
}
if ($OutputDir -eq "") {
    $OutputDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\stroke_extraction_probe"
}

$pythonExe = Join-Path $WorkspaceRoot ".venvs\callirewrite-seq\Scripts\python.exe"
if (!(Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}

$script = @"
from pathlib import Path
import sys

workspace = Path(sys.argv[1])
checkout_dir = Path(sys.argv[2])
input_dir = Path(sys.argv[3])
output_dir = Path(sys.argv[4])

sys.path.insert(0, str(workspace / "offline_stroke_recovery_mvp" / "src"))
from stroke_extraction_adapter import write_stroke_extraction_feasibility_report

report_path = write_stroke_extraction_feasibility_report(
    checkout_dir,
    input_dir,
    output_dir,
)
print(report_path)
"@

$tempScript = Join-Path $env:TEMP "write_stroke_extraction_report.py"
Set-Content -LiteralPath $tempScript -Value $script -Encoding UTF8
try {
    & $pythonExe $tempScript $WorkspaceRoot $CheckoutDir $InputDir $OutputDir
}
finally {
    Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
}
