"""Shared helpers for raw vs smoothed target-pose CSV handling."""

from __future__ import annotations

from pathlib import Path


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_POSE_DIR = (
    EXP_DIR / "outputs" / "batch_20260613_154131" / "u5c71_xingkai_20260613_154132_009898"
)
RAW_TARGET_POSES_NAME = "robot_target_poses.csv"
SMOOTHED_TARGET_POSES_NAME = "robot_target_poses_smoothed.csv"


def select_default_target_pose_csv(task_dir: Path | str | None = None) -> Path:
    """Return the recommended default target-pose CSV for a task directory.

    Smoothed poses are preferred when present. Raw poses remain available as
    before-retiming comparison data and are used as the fallback.
    """

    directory = Path(task_dir) if task_dir is not None else DEFAULT_TARGET_POSE_DIR
    smoothed = directory / SMOOTHED_TARGET_POSES_NAME
    if smoothed.exists():
        return smoothed
    return directory / RAW_TARGET_POSES_NAME


def target_pose_kind(csv_path: Path | str) -> str:
    path = Path(csv_path)
    return "smoothed" if path.name == SMOOTHED_TARGET_POSES_NAME else "raw"


def target_pose_output_suffix(csv_path: Path | str) -> str:
    return "_smoothed" if target_pose_kind(csv_path) == "smoothed" else ""


def retiming_summary_path(csv_path: Path | str) -> Path | None:
    path = Path(csv_path)
    candidate = path.parent / "target_pose_retiming_summary.json"
    return candidate if candidate.exists() else None


def motion_continuity_after_retiming_path(csv_path: Path | str) -> Path | None:
    path = Path(csv_path)
    candidate = path.parent / "motion_continuity_after_retiming_summary.json"
    return candidate if candidate.exists() else None


def retiming_metadata(csv_path: Path | str) -> dict[str, str | None]:
    retiming = retiming_summary_path(csv_path)
    motion = motion_continuity_after_retiming_path(csv_path)
    return {
        "source_retiming_summary": str(retiming) if retiming else None,
        "source_retimming_summary": str(retiming) if retiming else None,
        "source_motion_continuity_after_retiming": str(motion) if motion else None,
    }
