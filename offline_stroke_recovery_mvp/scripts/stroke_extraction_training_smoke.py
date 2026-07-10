"""Short SDNet training and limited intermediate-data generation.

This is a guarded StrokeExtraction trial entrypoint. It intentionally runs only
a tiny number of SDNet optimization steps and generates a tiny SegNet/ExtractNet
intermediate dataset for feasibility testing.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = (
    Path("offline_stroke_recovery_mvp")
    / "outputs"
    / "stroke_extraction_training_smoke"
)
DEFAULT_ALLOWED_OUTPUT_ROOT = Path("offline_stroke_recovery_mvp") / "outputs"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("external_repos") / "StrokeExtraction",
        help="Path to the external StrokeExtraction checkout.",
    )
    parser.add_argument("--dataset", default="RHSEDB")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--sdnet-steps", type=int, default=2)
    parser.add_argument("--train-intermediate-samples", type=int, default=2)
    parser.add_argument("--test-intermediate-samples", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path. Defaults to <output-dir>/training_smoke_report.json.",
    )
    return parser


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = run_training_smoke(
        args.repo,
        output_dir=args.output_dir,
        dataset=args.dataset,
        batch_size=args.batch_size,
        sdnet_steps=args.sdnet_steps,
        train_intermediate_samples=args.train_intermediate_samples,
        test_intermediate_samples=args.test_intermediate_samples,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    report_path = args.report or (args.output_dir / "training_smoke_report.json")
    write_report(report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


def run_training_smoke(
    repo_dir: Path,
    *,
    output_dir: Path,
    dataset: str,
    batch_size: int,
    sdnet_steps: int,
    train_intermediate_samples: int,
    test_intermediate_samples: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    stage = "sdnet_training_and_intermediate_generation"
    repo_dir = Path(repo_dir)
    output_dir = Path(output_dir)
    dataset_dir = repo_dir / "dataset" / dataset
    content_model_path = repo_dir / "content_net_model" / "out" / "model_content.pth"
    char_model_pth = repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.pth"
    char_model_th = repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.th"
    required_paths = [
        repo_dir,
        dataset_dir / "train",
        dataset_dir / "test",
        content_model_path,
        char_model_pth,
        char_model_th,
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return {"status": "missing_required_paths", "stage": stage, "missing": missing}

    if not _is_within_output_root(output_dir, DEFAULT_ALLOWED_OUTPUT_ROOT):
        return {
            "status": "invalid_output_dir",
            "stage": stage,
            "output_dir": str(output_dir),
            "allowed_root": str(DEFAULT_ALLOWED_OUTPUT_ROOT),
        }

    invalid_args = {
        "batch_size": batch_size,
        "sdnet_steps": sdnet_steps,
        "train_intermediate_samples": train_intermediate_samples,
        "test_intermediate_samples": test_intermediate_samples,
        "learning_rate": learning_rate,
    }
    if (
        batch_size <= 0
        or sdnet_steps <= 0
        or train_intermediate_samples < 0
        or test_intermediate_samples < 0
        or learning_rate <= 0
    ):
        return {"status": "invalid_args", "stage": stage, "args": invalid_args}

    import sys

    import numpy as np
    import torch
    import torch.optim as optim
    import torch.utils.data as data

    # The upstream code uses deprecated NumPy aliases in inverse-grid and
    # SegNet/ExtractNet loaders. Keep the compatibility shim local to this
    # guarded script instead of patching the external checkout.
    if not hasattr(np, "float"):
        np.float = float  # type: ignore[attr-defined]
    if not hasattr(np, "int"):
        np.int = int  # type: ignore[attr-defined]

    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))
    if not torch.cuda.is_available():
        return {"status": "cuda_unavailable", "stage": stage, "environment": _environment(torch)}

    from load_data_for_SDNet import SDNetLoader
    from model.model_of_SDNet import SDNet
    from utils import apply_stroke, seg_colors
    from utils_loss_val import ContentLoss, gradient_loss

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True
    train_dataset = SDNetLoader(is_training=True, dataset_path=str(dataset_dir))
    train_loader = data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)

    content_loss = ContentLoss().to(device).eval().requires_grad_(False)
    sd_net = SDNet().to(device).train()
    optimizer = optim.Adam(sd_net.parameters(), lr=learning_rate, betas=(0.5, 0.999))

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "model"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir = output_dir / f"dataset_forSegNet_ExtractNet_{dataset}_smoke"

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    training_steps = _run_sdnet_steps(
        sd_net,
        content_loss,
        optimizer,
        train_loader,
        batch_size=batch_size,
        max_steps=sdnet_steps,
        device=device,
        torch_module=torch,
        gradient_loss=gradient_loss,
    )
    checkpoint_path = checkpoint_dir / "sdnet_model.pth"
    torch.save(
        {
            "net": sd_net.state_dict(),
            "start_step": len(training_steps),
            "source": "offline_stroke_recovery_mvp.stroke_extraction_training_smoke",
            "dataset": dataset,
        },
        checkpoint_path,
    )

    sd_net.eval()
    intermediate = {
        "train": _generate_intermediate_split(
            sd_net,
            SDNetLoader(is_training=True, dataset_path=str(dataset_dir), is_inference=True),
            split_dir=intermediate_dir / "train",
            max_samples=train_intermediate_samples,
            device=device,
            torch_module=torch,
            apply_stroke=apply_stroke,
            seg_colors=seg_colors,
        ),
        "test": _generate_intermediate_split(
            sd_net,
            SDNetLoader(is_training=False, dataset_path=str(dataset_dir), is_inference=True),
            split_dir=intermediate_dir / "test",
            max_samples=test_intermediate_samples,
            device=device,
            torch_module=torch,
            apply_stroke=apply_stroke,
            seg_colors=seg_colors,
        ),
    }
    intermediate_metadata_path = intermediate_dir / "metadata.json"
    write_report(
        intermediate_metadata_path,
        {
            "source": "stroke_extraction_training_smoke",
            "dataset": dataset,
            "train_samples": len(intermediate["train"]),
            "test_samples": len(intermediate["test"]),
            "files_per_sample": [
                "_kaiti_color.npy",
                "_style.npy",
                "_seg.npy",
                "_single.npy",
                "_style_single.npy",
            ],
            "samples": intermediate,
        },
    )

    status = "ok" if len(training_steps) == sdnet_steps else "no_steps_completed"
    return {
        "status": status,
        "stage": stage,
        "environment": _environment(torch),
        "dataset": {
            "name": dataset,
            "path": str(dataset_dir),
            "train_sample_count": len(train_dataset),
        },
        "args": invalid_args | {"seed": seed},
        "completed_steps": len(training_steps),
        "total_seconds": round(time.perf_counter() - start, 4),
        "max_memory_allocated_mib": _max_memory_mib(torch),
        "checkpoint_path": str(checkpoint_path),
        "intermediate_dir": str(intermediate_dir),
        "intermediate_metadata_path": str(intermediate_metadata_path),
        "intermediate_counts": {
            "train": len(intermediate["train"]),
            "test": len(intermediate["test"]),
        },
        "steps": training_steps,
    }


def _run_sdnet_steps(
    sd_net: Any,
    content_loss: Any,
    optimizer: Any,
    train_loader: Any,
    *,
    batch_size: int,
    max_steps: int,
    device: Any,
    torch_module: Any,
    gradient_loss: Any,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for loader_index, batch_sample in enumerate(train_loader, start=1):
        if len(steps) >= max_steps:
            break
        if batch_sample["target_data"].size(0) != batch_size:
            continue
        step_start = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        target_single_stroke = batch_sample["target_single_stroke"].to(device).float()
        reference_single_stroke = batch_sample["reference_single_stroke"].to(device).float()
        target_data = batch_sample["target_data"].to(device).float()
        reference_color = batch_sample["reference_color"].to(device).float()
        stroke_num = batch_sample["stroke_num"].to(device).float()
        reference_single_stroke_centroid = batch_sample["reference_single_stroke_centroid"].to(device).float()
        reference_image = torch_module.clip(torch_module.sum(reference_single_stroke, dim=1, keepdim=True), 0, 1)

        transformed_target_data, flow_global, grid_for_linear = sd_net.get_two_registration_field(reference_color, target_data)
        smooth_loss_global = gradient_loss(flow_global)
        content_loss_global = content_loss(transformed_target_data, reference_image)
        content_loss_single_linear = _linear_content_loss(
            sd_net,
            content_loss,
            reference_single_stroke,
            target_single_stroke,
            grid_for_linear,
            stroke_num,
            reference_single_stroke_centroid,
            batch_size=batch_size,
        )
        loss_sum = 0.5 * content_loss_single_linear + content_loss_global + 5 * smooth_loss_global
        loss_sum.backward()
        optimizer.step()
        torch_module.cuda.synchronize()
        steps.append(
            {
                "step": len(steps) + 1,
                "loader_index": loader_index,
                "seconds": round(time.perf_counter() - step_start, 4),
                "loss_sum": float(loss_sum.detach().cpu()),
                "content_loss_global": float(content_loss_global.detach().cpu()),
                "content_loss_single_linear": float(content_loss_single_linear.detach().cpu()),
                "smooth_loss_global": float(smooth_loss_global.detach().cpu()),
                "max_memory_allocated_mib": _max_memory_mib(torch_module),
            }
        )
    return steps


def _linear_content_loss(
    sd_net: Any,
    content_loss: Any,
    reference_single_stroke: Any,
    target_single_stroke: Any,
    grid_for_linear: Any,
    stroke_num: Any,
    reference_single_stroke_centroid: Any,
    *,
    batch_size: int,
) -> Any:
    import torch
    import torch.nn.functional as F

    loss = torch.zeros((), device=reference_single_stroke.device)
    for sample_index in range(batch_size):
        active_strokes = int(stroke_num[sample_index])
        target_stroke = target_single_stroke[sample_index, :active_strokes].unsqueeze(1)
        reference_stroke = reference_single_stroke[sample_index, :active_strokes].unsqueeze(1)
        grid = grid_for_linear[sample_index].unsqueeze(0).repeat(target_stroke.size(0), 1, 1, 1)
        affine_grid = sd_net.get_linear_estimation(
            reference_stroke,
            grid,
            reference_single_stroke_centroid[sample_index, :active_strokes],
        )
        affine_tran = F.grid_sample(target_stroke, affine_grid)
        loss = loss + content_loss(affine_tran, reference_stroke)
    return loss / batch_size


def _generate_intermediate_split(
    sd_net: Any,
    inference_dataset: Any,
    *,
    split_dir: Path,
    max_samples: int,
    device: Any,
    torch_module: Any,
    apply_stroke: Any,
    seg_colors: Any,
) -> list[dict[str, Any]]:
    import torch.utils.data as data

    split_dir.mkdir(parents=True, exist_ok=True)
    if max_samples == 0:
        return []
    loader = data.DataLoader(inference_dataset, batch_size=1, shuffle=False, num_workers=0)
    records: list[dict[str, Any]] = []
    with torch_module.no_grad():
        for batch_sample in loader:
            if len(records) >= max_samples:
                break
            target_single_stroke = batch_sample["target_single_stroke"].to(device).float()
            reference_single_stroke = batch_sample["reference_single_stroke"].to(device).float()
            target_data = batch_sample["target_data"].to(device).float()
            reference_color = batch_sample["reference_color"].to(device).float()
            stroke_num = batch_sample["stroke_num"].to(device).float()
            reference_single_stroke_centroid = batch_sample["reference_single_stroke_centroid"].to(device).float()
            stroke_label = batch_sample["stroke_label"].to(device).long()

            _, _, grid_for_linear = sd_net.get_two_registration_field(reference_color, target_data)
            transformed_reference_color, transformed_single_reference_stroke = _linear_transform_reference(
                sd_net,
                reference_single_stroke,
                target_single_stroke,
                grid_for_linear,
                stroke_num,
                reference_single_stroke_centroid,
                stroke_label,
                apply_stroke=apply_stroke,
                seg_colors=seg_colors,
            )
            active_strokes = int(stroke_num[0])
            save_num = len(records)
            paths = _save_intermediate_sample(
                split_dir,
                save_num,
                transformed_reference_color,
                target_data,
                transformed_single_reference_stroke,
                target_single_stroke[0, :active_strokes],
                stroke_label[0, :active_strokes],
                torch_module=torch_module,
            )
            records.append(
                {
                    "sample_index": save_num,
                    "stroke_num": active_strokes,
                    "files": {key: str(path) for key, path in paths.items()},
                }
            )
    return records


def _linear_transform_reference(
    sd_net: Any,
    reference_single_stroke: Any,
    target_single_stroke: Any,
    grid_for_linear: Any,
    stroke_num: Any,
    reference_single_stroke_centroid: Any,
    stroke_label: Any,
    *,
    apply_stroke: Any,
    seg_colors: Any,
) -> tuple[Any, Any]:
    import torch
    import torch.nn.functional as F

    linear_tran_whole = []
    active_strokes = int(stroke_num[0])
    for stroke_index in range(active_strokes):
        reference_single = reference_single_stroke[0][stroke_index].unsqueeze(0).unsqueeze(0)
        grid = grid_for_linear[0].unsqueeze(0)
        linear_grid = sd_net.get_linear_estimation(
            reference_single,
            grid,
            reference_single_stroke_centroid[0][stroke_index],
            inverse=True,
        )
        linear_tran_whole.append(F.grid_sample(reference_single, linear_grid))

    transformed_single_reference_stroke = torch.cat(linear_tran_whole, dim=1).squeeze(0)
    transformed_reference_color = _get_color_tensor(
        transformed_single_reference_stroke.detach().cpu().numpy(),
        stroke_label[0, :active_strokes].detach().cpu().numpy(),
        apply_stroke=apply_stroke,
        seg_colors=seg_colors,
        device=reference_single_stroke.device,
    )
    return transformed_reference_color, transformed_single_reference_stroke


def _get_color_tensor(
    single_image: Any,
    stroke_label: Any,
    *,
    apply_stroke: Any,
    seg_colors: Any,
    device: Any,
) -> Any:
    import numpy as np
    import torch

    color_kaiti = np.zeros(shape=(256, 256, 3))
    for index in range(single_image.shape[0]):
        color_kaiti = apply_stroke(color_kaiti, single_image[index], seg_colors[int(stroke_label[index])])
    color_kaiti = np.transpose(color_kaiti, [2, 0, 1])
    return torch.from_numpy(color_kaiti).float().to(device).unsqueeze(0)


def _save_intermediate_sample(
    split_dir: Path,
    save_num: int,
    transformed_reference_color: Any,
    target_data: Any,
    transformed_single_reference_stroke: Any,
    target_single_stroke: Any,
    stroke_label: Any,
    *,
    torch_module: Any,
) -> dict[str, Path]:
    import numpy as np

    paths = {
        "kaiti_color": split_dir / f"{save_num}_kaiti_color.npy",
        "style": split_dir / f"{save_num}_style.npy",
        "seg": split_dir / f"{save_num}_seg.npy",
        "single": split_dir / f"{save_num}_single.npy",
        "style_single": split_dir / f"{save_num}_style_single.npy",
    }
    style_image_save = torch_module.zeros(size=(7, 256, 256), device=target_data.device).float()
    style_original_image_save = target_data[0]
    save_data = torch_module.cat([style_original_image_save, style_image_save], dim=0).detach().cpu().numpy()
    np.save(paths["kaiti_color"], transformed_reference_color[0].detach().cpu().numpy())
    np.save(paths["style"], save_data > 0.5)
    np.save(paths["seg"], stroke_label.detach().cpu().numpy())
    np.save(paths["single"], transformed_single_reference_stroke.detach().cpu().numpy() > 0.5)
    np.save(paths["style_single"], target_single_stroke.detach().cpu().numpy() > 0.5)
    return paths


def _environment(torch_module: Any) -> dict[str, Any]:
    return {
        "torch_version": torch_module.__version__,
        "cuda_available": torch_module.cuda.is_available(),
        "device_name": torch_module.cuda.get_device_name(0) if torch_module.cuda.is_available() else "",
        "cuda_runtime": getattr(torch_module.version, "cuda", None),
    }


def _max_memory_mib(torch_module: Any) -> int:
    return int(round(torch_module.cuda.max_memory_allocated() / 1024 / 1024))


def _is_within_output_root(path: Path, root: Path) -> bool:
    path_parts = Path(path).parts
    root_parts = Path(root).parts
    return len(path_parts) >= len(root_parts) and path_parts[: len(root_parts)] == root_parts


if __name__ == "__main__":
    raise SystemExit(main())
