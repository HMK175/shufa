# CoppeliaSim Minimal Workspace Path Playback

This folder contains a minimal CoppeliaSim bridge for the isolated
`experiments/llm_style_trajectory` route. It does not contain or vendor
CoppeliaSim itself.

## Scope

- Input: `robot_workspace_trajectory_resampled.csv`
- Output in CoppeliaSim: a paper plane, a pen-tip sphere, and colored path
  segments.
- Current status: pen-tip path playback only.
- Not included yet: robot arm model, inverse kinematics, gripper/tool
  calibration, collision checking, or controller tuning.

## CoppeliaSim Location

CoppeliaSim Edu should stay outside this repository. On this machine it was
detected at:

```text
D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
```

If your path differs, start CoppeliaSim from your local install directory.

## Start CoppeliaSim

1. Open `D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\coppeliaSim.exe`.
2. Keep CoppeliaSim running with an empty scene.
3. Make sure the ZeroMQ remote API add-on is available in this CoppeliaSim
   install. Recent CoppeliaSim Edu builds normally include it.

## Python Environment

Expose CoppeliaSim's ZeroMQ remote API client to the current PowerShell session:

```powershell
$env:PYTHONPATH="D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\programming\zmqRemoteApi\clients\python\src;$env:PYTHONPATH"
```

The local Python environment also needs the ZeroMQ serialization dependencies:

```powershell
python -m pip install pyzmq cbor
```

Quick import check:

```powershell
python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient; print('ok')"
```

## Dry Run

Dry-run does not connect to CoppeliaSim. It only checks the CSV and prints a
summary.

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --dry-run
```

Dry-run also writes a single playback result next to the CSV by default:

```text
coppeliasim_playback_result.json
coppeliasim_playback_result.md
```

## Real Playback

Start CoppeliaSim first, then run:

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0
```

Low-load playback options:

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0 `
  --display-stride 5

python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --no-path-objects `
  --auto-stop
```

- `--display-stride N` draws only every Nth colored path segment while the
  pen-tip sphere still follows the full CSV.
- `--no-path-objects` skips colored path drawing and only moves the pen tip,
  which reduces GUI/GPU load.
- `--auto-stop` stops the CoppeliaSim simulation after playback.

Playback completion is reported as JSON on stdout. If `--auto-stop` is not set,
the script also prints this reminder on stderr:

```text
playback finished, but CoppeliaSim simulation may still be running; use --auto-stop to stop it automatically
```

With `--auto-stop`, the result records whether `stopSimulation()` was called
successfully in `simulation_stopped`.

## Standard Writing Scene

`play_workspace_path.py` can now create a reproducible standard writing scene
before playback:

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --scene-setup standard `
  --clear-previous-scene `
  --show-axes `
  --show-boundary `
  --display-stride 5 `
  --auto-stop `
  --speed-scale 1.0
```

Standard scene objects are created with the `llm_style_trajectory_*` prefix so
the next run can remove them with `--clear-previous-scene`.

- `paper plane`: default `120mm x 120mm`, placed at `Z=0`.
- `boundary`: optional paper boundary frame enabled by `--show-boundary`.
- `X/Y/Z axes`: optional axes enabled by `--show-axes`; X is red, Y is green,
  and Z is blue.
- `pen-tip sphere`: radius controlled by `--pen-tip-radius-mm`, default `1.5`.
- `path segments`: stroke, connector, and pen-up move segments are colored
  separately unless `--no-path-objects` is set.

Scene parameters:

- `--scene-setup standard`: create the standard pen-tip scene.
- `--clear-previous-scene`: clear objects created by the previous script run.
- `--paper-size-mm 120`: set the square paper size in millimeters.
- `--pen-tip-radius-mm 1.5`: set the pen-tip sphere radius.
- `--show-axes`: draw X/Y/Z axes.
- `--show-boundary`: draw the paper boundary frame.

The result JSON/Markdown records `scene_setup`, `paper_size_mm`,
`pen_tip_radius_mm`, `axes_enabled`, `boundary_enabled`,
`clear_previous_scene`, `coordinate_mapping`, `workspace_bounds`,
`scene_warnings`, and `recommended_playback`. Dry-run uses the same scene
parameters for bounds checking without connecting to CoppeliaSim.

Verified standard-scene playback on 2026-06-13:

```text
CSV: experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv
status: finished
point_count: 275
simulation_stopped: true
paper_size_mm: 120.0
pen_tip_radius_mm: 1.5
axes_enabled: true
boundary_enabled: true
clear_previous_scene: true
recommended_playback: true
max_step_3d_mm: 2.487672
max_xy_step_mm: 2.487672
max_z_step_mm: 0.0
workspace_bounds: XY within +/-60mm, Z within 0..8mm
```

Result files:

```text
experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\coppeliasim_playback_result.json
experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\coppeliasim_playback_result.md
```

This remains a standard pen-tip/sphere scene only. It does not include a robot
arm model, IK, dynamics, collision checking, or a real controller.

## Single Playback Result

Every dry-run or real playback writes a per-run result record:

```text
coppeliasim_playback_result.json
coppeliasim_playback_result.md
```

By default these files are written to the CSV directory. To write them elsewhere:

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv `
  --display-stride 5 `
  --auto-stop `
  --result-out-dir experiments\llm_style_trajectory\outputs\playback_results `
  --dry-run
```

The result contains `status`, `point_count`, `segment_type_counts`,
`duration_estimate_s`, `speed_scale`, `display_stride`,
`path_objects_enabled`, `auto_stop`, `simulation_stopped`, `dry_run`,
`max_step_3d_mm`, `max_xy_step_mm`, `max_z_step_mm`, and XYZ ranges.

Current scope remains `pen-tip/sphere playback only, no robot IK`.

If the Python ZeroMQ client is missing, install or expose the CoppeliaSim remote
API client in your local Python environment. The script reports a friendly
configuration error instead of failing with a long traceback.

## Batch Dry Run

Batch dry-run summarizes every `robot_workspace_trajectory_resampled.csv` in a
batch directory without connecting to CoppeliaSim:

```powershell
python experiments\llm_style_trajectory\coppeliasim\evaluate_playback_batch.py `
  --batch-dir experiments\llm_style_trajectory\outputs\batch_20260613_092733
```

Outputs:

```text
experiments\llm_style_trajectory\outputs\batch_20260613_092733\coppeliasim_playback_summary.csv
experiments\llm_style_trajectory\outputs\batch_20260613_092733\coppeliasim_playback_report.md
```

The report separates point-to-point jumps into `max_step_3d_mm`,
`max_xy_step_mm`, and `max_z_step_mm`, so pen-up height changes are not confused
with XY plane jumps.

## Verified Manual Playback

Verified on 2026-06-13 with:

```text
CoppeliaSim: D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
CSV: experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv
```

Dry-run summary:

```json
{
  "point_count": 258,
  "segment_type_counts": {
    "pen_up_move": 21,
    "stroke": 237
  },
  "x_mm_range": [-49.057031, 48.721406],
  "y_mm_range": [-49.392188, 49.392188],
  "z_mm_range": [0.0, 8.0],
  "duration_estimate_s": 12.972534,
  "path_length_mm": 391.530547,
  "max_step_mm": 8.0,
  "max_step_3d_mm": 8.0,
  "max_xy_step_mm": 4.749192,
  "max_z_step_mm": 8.0,
  "status": "dry_run",
  "dry_run": true
}
```

The real playback command succeeded after setting `PYTHONPATH` and installing
`pyzmq` / `cbor`. Current scope is still pen-tip or sphere path playback only:
there is no robot arm model, inverse kinematics, end-effector calibration,
collision checking, or controller tuning yet.

Note: `max_step_mm` is retained as a compatibility alias for
`max_step_3d_mm`. New reports should prefer `max_step_3d_mm`,
`max_xy_step_mm`, and `max_z_step_mm`.

## Coordinates

The CSV is in millimeters. CoppeliaSim uses meters:

```text
X_m = X_mm / 1000
Y_m = Y_mm / 1000
Z_m = Z_mm / 1000
```

The default paper is `120mm x 120mm`, represented as `0.12m x 0.12m`.
