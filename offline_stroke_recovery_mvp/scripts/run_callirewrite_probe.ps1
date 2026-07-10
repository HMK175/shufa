param(
    [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$InputDir = "",
    [string]$OutputDir = "",
    [string]$ModelName = "new_train_phase_2",
    [int]$Sample = 1
)

$ErrorActionPreference = "Stop"

if ($InputDir -eq "") {
    $InputDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\visual_smoke_probe_after_review\inputs"
}
if ($OutputDir -eq "") {
    $OutputDir = Join-Path $WorkspaceRoot "offline_stroke_recovery_mvp\outputs\callirewrite_runtime_probe"
}

$pythonExe = Join-Path $WorkspaceRoot ".venvs\callirewrite-seq\Scripts\python.exe"
$seqExtractDir = Join-Path $WorkspaceRoot "external_repos\CalliRewrite\seq_extract"
$testPy = Join-Path $seqExtractDir "test.py"
$modelBaseDir = Join-Path $seqExtractDir "outputs\snapshot"

if (!(Test-Path -LiteralPath $pythonExe)) {
    throw "Missing Python environment: $pythonExe"
}
if (!(Test-Path -LiteralPath $testPy)) {
    throw "Missing CalliRewrite test.py: $testPy"
}
if (!(Test-Path -LiteralPath (Join-Path $modelBaseDir $ModelName))) {
    throw "Missing CalliRewrite model directory: $(Join-Path $modelBaseDir $ModelName)"
}
if (!(Test-Path -LiteralPath $InputDir)) {
    throw "Missing input directory: $InputDir"
}

$env:MPLCONFIGDIR = Join-Path $WorkspaceRoot ".mplconfig"
$env:CUDA_VISIBLE_DEVICES = ""
$env:CALLIREWRITE_SKIP_GIF = "1"
$env:CALLIREWRITE_SAMPLING_BASE_DIR = $OutputDir
$env:CALLIREWRITE_MODEL_BASE_DIR = $modelBaseDir
$env:PYTHONPATH = $seqExtractDir

New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Push-Location $WorkspaceRoot
try {
    & $pythonExe $testPy --input $InputDir --model $ModelName --sample $Sample
}
finally {
    Pop-Location
}
