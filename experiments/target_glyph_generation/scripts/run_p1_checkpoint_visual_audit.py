"""Generate reproducible visual-audit artifacts for fixed P1 checkpoints."""

import argparse
from pathlib import Path
import sys


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_DIR / "src"))

from target_glyph_generation.p1_visual_audit import (  # noqa: E402
    build_generated_rows,
    load_and_validate_visual_manifest,
    stable_generated_filename,
    validate_checkpoint_directory,
    write_audit_pages,
    write_generated_manifest,
    write_run_summary,
)


DEFAULT_CHECKPOINT_STEPS = (1000, 5000, 10000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--visual-manifest", type=Path, required=True)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--fontdiffuser-root", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--expected-record-count", type=int, default=380)
    parser.add_argument("--expected-style-count", type=int, default=19)
    parser.add_argument("--limit-per-style", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument("--checkpoint-steps", nargs="+", type=int)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def select_records(records: list[dict[str, str]], limit_per_style: int) -> list[dict[str, str]]:
    """Return all rows or the first pre-sorted rows for every style."""
    if limit_per_style < 0:
        raise ValueError("limit_per_style must be zero or positive")
    if limit_per_style == 0:
        return records

    selected: list[dict[str, str]] = []
    for style_id in sorted({record["style_id"] for record in records}):
        style_records = [record for record in records if record["style_id"] == style_id]
        if len(style_records) < limit_per_style:
            raise ValueError(
                f"style {style_id!r} has {len(style_records)} records; "
                f"cannot select {limit_per_style}"
            )
        selected.extend(style_records[:limit_per_style])
    return selected


def resolve_checkpoint_steps(raw_steps: list[int] | None) -> tuple[int, ...]:
    if raw_steps is None:
        return DEFAULT_CHECKPOINT_STEPS
    if not raw_steps:
        raise ValueError("checkpoint_steps must not be empty")
    if any(checkpoint_step <= 0 for checkpoint_step in raw_steps):
        raise ValueError("checkpoint_steps must be positive")
    if len(set(raw_steps)) != len(raw_steps):
        raise ValueError("checkpoint_steps must not contain duplicates")
    return tuple(raw_steps)


def _checkpoint_directories(
    checkpoint_root: Path, checkpoint_steps: tuple[int, ...]
) -> list[tuple[int, Path]]:
    return [
        (checkpoint_step, checkpoint_root / f"global_step_{checkpoint_step}")
        for checkpoint_step in checkpoint_steps
    ]


def _validate_output_root(output_root: Path, checkpoint_root: Path) -> None:
    output_root = Path(output_root).resolve()
    checkpoint_root = Path(checkpoint_root).resolve()
    try:
        output_root.relative_to(checkpoint_root)
    except ValueError:
        return
    # No failed summary is written for this guard: it would itself write into training outputs.
    raise ValueError(
        "output_root must not equal or lie inside checkpoint_root; refusing to write audit artifacts"
    )


def _validate_empty_checkpoint_audit_outputs(
    output_root: Path, checkpoint_steps: tuple[int, ...]
) -> None:
    """Reject incomplete or completed checkpoint outputs before a rerun can overwrite them."""
    for checkpoint_step in checkpoint_steps:
        checkpoint_output = Path(output_root) / f"global_step_{checkpoint_step}"
        if checkpoint_output.exists() and (
            not checkpoint_output.is_dir() or any(checkpoint_output.iterdir())
        ):
            raise ValueError(f"checkpoint audit output already exists: {checkpoint_output}")


def build_sampling_args(
    official_root: Path, checkpoint_dir: Path, device: str, seed: int
) -> argparse.Namespace:
    """Build the fixed P1 inference config from FontDiffuser's parser at runtime."""
    official_root = Path(official_root).resolve()
    if str(official_root) not in sys.path:
        sys.path.insert(0, str(official_root))
    from configs.fontdiffuser import get_parser

    config = get_parser().parse_args([])
    config.ckpt_dir = str(Path(checkpoint_dir))
    config.device = device
    config.seed = seed
    config.demo = False
    config.character_input = False
    config.resolution = 96
    config.style_image_size = (96, 96)
    config.content_image_size = (96, 96)
    config.content_encoder_downsample_size = 3
    config.algorithm_type = "dpmsolver++"
    config.guidance_type = "classifier-free"
    config.guidance_scale = 7.5
    config.num_inference_steps = 20
    config.order = 2
    config.skip_type = "time_uniform"
    config.method = "multistep"
    config.correcting_x0_fn = None
    config.t_start = None
    config.t_end = None
    return config


def generate_one(
    config: argparse.Namespace,
    pipeline: object,
    image_process: object,
    content_path: Path,
    reference_path: Path,
) -> object:
    """Generate one image with the official preprocessing and fixed P1 parameters."""
    import torch
    from accelerate.utils import set_seed

    set_seed(config.seed)
    config.content_image_path = str(content_path)
    config.style_image_path = str(reference_path)
    content_image, style_image, _ = image_process(config)
    if content_image is None or style_image is None:
        raise ValueError(f"FontDiffuser could not process {content_path} and {reference_path}")
    with torch.no_grad():
        content_image = content_image.to(config.device)
        style_image = style_image.to(config.device)
        images = pipeline.generate(
            content_images=content_image,
            style_images=style_image,
            batch_size=1,
            order=config.order,
            num_inference_step=config.num_inference_steps,
            content_encoder_downsample_size=config.content_encoder_downsample_size,
            t_start=config.t_start,
            t_end=config.t_end,
            dm_size=config.content_image_size,
            algorithm_type=config.algorithm_type,
            skip_type=config.skip_type,
            method=config.method,
            correcting_x0_fn=config.correcting_x0_fn,
        )
    return images[0]


def run_sampling(
    args: argparse.Namespace,
    records: list[dict[str, str]],
    checkpoint_directories: list[tuple[int, Path]],
    progress: dict[str, int | str | None],
) -> list[dict[str, int]]:
    """Sample each validated checkpoint once and create complete audit artifacts."""
    if args.fontdiffuser_root is None:
        raise ValueError("--fontdiffuser-root is required unless --validate-only is used")
    official_root = Path(args.fontdiffuser_root).resolve()
    if not (official_root / "sample.py").is_file():
        raise ValueError(f"FontDiffuser root does not contain sample.py: {official_root}")

    if str(official_root) not in sys.path:
        sys.path.insert(0, str(official_root))
    import torch
    from sample import image_process, load_fontdiffuer_pipeline

    checkpoint_summaries: list[dict[str, int]] = []
    for checkpoint_step, checkpoint_dir in checkpoint_directories:
        progress["checkpoint_step"] = checkpoint_step
        progress["evaluation_id"] = None
        checkpoint_output = Path(args.output_root) / f"global_step_{checkpoint_step}"
        generated_dir = checkpoint_output / "generated"
        pipeline = None
        try:
            config = build_sampling_args(official_root, checkpoint_dir, args.device, args.seed)
            pipeline = load_fontdiffuer_pipeline(args=config)
            generated_dir.mkdir(parents=True, exist_ok=True)
            for sample_index, record in enumerate(records, start=1):
                progress["evaluation_id"] = record["evaluation_id"]
                generated_image = generate_one(
                    config,
                    pipeline,
                    image_process,
                    Path(args.dataset_root) / record["content_path"],
                    Path(args.dataset_root) / record["reference_path"],
                )
                generated_image.save(
                    generated_dir / stable_generated_filename(sample_index, record["evaluation_id"])
                )

            generated_rows = build_generated_rows(records, generated_dir, checkpoint_step)
            write_generated_manifest(checkpoint_output / "generated_manifest.csv", generated_rows)
            pages = write_audit_pages(
                generated_rows,
                args.dataset_root,
                checkpoint_output,
                checkpoint_output / "audit_pages",
                samples_per_style=args.limit_per_style or 20,
            )
            checkpoint_summaries.append(
                {
                    "checkpoint_step": checkpoint_step,
                    "image_count": len(generated_rows),
                    "audit_page_count": len(pages),
                }
            )
        finally:
            if pipeline is not None:
                del pipeline
            torch.cuda.empty_cache()
    return checkpoint_summaries


def main() -> None:
    args = parse_args()
    _validate_output_root(args.output_root, args.checkpoint_root)
    checkpoint_steps: tuple[int, ...] | None = None
    try:
        checkpoint_steps = resolve_checkpoint_steps(args.checkpoint_steps)
        records = load_and_validate_visual_manifest(
            args.visual_manifest,
            args.dataset_root,
            args.expected_record_count,
            args.expected_style_count,
        )
        checkpoint_directories = _checkpoint_directories(args.checkpoint_root, checkpoint_steps)
        for _, checkpoint_dir in checkpoint_directories:
            validate_checkpoint_directory(checkpoint_dir)
        selected_records = select_records(records, args.limit_per_style)
        _validate_empty_checkpoint_audit_outputs(args.output_root, checkpoint_steps)
    except Exception as error:
        write_run_summary(
            args.output_root / "run_summary.json",
            {
                "status": "failed",
                "checkpoint_step": None,
                "evaluation_id": None,
                "checkpoint_steps": list(checkpoint_steps) if checkpoint_steps is not None else None,
                "error": str(error),
            },
        )
        raise

    if args.validate_only:
        write_run_summary(
            args.output_root / "run_summary.json",
            {
                "status": "validated",
                "selected_record_count": len(selected_records),
                "style_count": len({record["style_id"] for record in selected_records}),
                "checkpoint_steps": list(checkpoint_steps),
                "seed": args.seed,
            },
        )
        return

    progress: dict[str, int | str | None] = {"checkpoint_step": None, "evaluation_id": None}
    try:
        checkpoint_summaries = run_sampling(
            args, selected_records, checkpoint_directories, progress
        )
    except Exception as error:
        write_run_summary(
            args.output_root / "run_summary.json",
            {
                "status": "failed",
                "selected_record_count": len(selected_records),
                "style_count": len({record["style_id"] for record in selected_records}),
                "checkpoint_steps": list(checkpoint_steps),
                "seed": args.seed,
                "checkpoint_step": progress["checkpoint_step"],
                "evaluation_id": progress["evaluation_id"],
                "error": f"{type(error).__name__}: {error}",
            },
        )
        raise

    write_run_summary(
        args.output_root / "run_summary.json",
        {
            "status": "complete",
            "selected_record_count": len(selected_records),
            "style_count": len({record["style_id"] for record in selected_records}),
            "checkpoint_steps": list(checkpoint_steps),
            "seed": args.seed,
            "checkpoints": checkpoint_summaries,
        },
    )


if __name__ == "__main__":
    main()
