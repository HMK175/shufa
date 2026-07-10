"""Real-data smoke test for StrokeExtraction training prerequisites.

This script runs a tiny RHSEDB-backed SDNet training probe. It is intentionally
not a full training script: it reads a few batches, runs forward/loss/backward,
records time and GPU memory, then exits.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("external_repos") / "StrokeExtraction",
        help="Path to the external StrokeExtraction checkout.",
    )
    parser.add_argument(
        "--stage",
        choices=["sdnet"],
        default="sdnet",
        help="Real-data smoke stage to run. SegNet/ExtractNet depend on SDNet-generated intermediate data.",
    )
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=2)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_realdata_smoke"
        / "realdata_smoke_report.json",
    )
    return parser


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = run_sdnet_smoke(args.repo, batch_size=args.batch_size, max_steps=args.max_steps)
    write_report(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


def run_sdnet_smoke(repo_dir: Path, *, batch_size: int, max_steps: int) -> dict[str, Any]:
    import sys

    import torch
    import torch.nn.functional as F
    import torch.optim as optim
    import torch.utils.data as data

    repo_dir = Path(repo_dir)
    dataset_dir = repo_dir / "dataset" / "RHSEDB"
    content_model_path = repo_dir / "content_net_model" / "out" / "model_content.pth"
    char_model_pth = repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.pth"
    char_model_th = repo_dir / "char_recognise" / "out_vgg_bn" / "model" / "model.th"
    required_paths = [repo_dir, dataset_dir / "train", dataset_dir / "test", content_model_path, char_model_pth, char_model_th]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return {"status": "missing_required_paths", "stage": "sdnet", "missing": missing}
    if batch_size <= 0 or max_steps <= 0:
        return {"status": "invalid_args", "stage": "sdnet", "batch_size": batch_size, "max_steps": max_steps}

    sys.path.insert(0, str(repo_dir))
    if not torch.cuda.is_available():
        return {
            "status": "cuda_unavailable",
            "stage": "sdnet",
            "environment": _environment(torch),
        }

    from load_data_for_SDNet import SDNetLoader
    from model.model_of_SDNet import SDNet
    from utils_loss_val import ContentLoss, gradient_loss

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True
    train_dataset = SDNetLoader(is_training=True, dataset_path=str(dataset_dir))
    train_loader = data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)

    content_loss = ContentLoss().to(device).eval().requires_grad_(False)
    sd_net = SDNet().to(device).train()
    optimizer = optim.Adam(sd_net.parameters(), lr=0.0001, betas=(0.5, 0.999))

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    steps: list[dict[str, Any]] = []
    for step_index, batch_sample in enumerate(train_loader, start=1):
        if step_index > max_steps:
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
        reference_image = torch.clip(torch.sum(reference_single_stroke, dim=1, keepdim=True), 0, 1)

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
        torch.cuda.synchronize()

        steps.append(
            {
                "step": step_index,
                "seconds": round(time.perf_counter() - step_start, 4),
                "loss_sum": float(loss_sum.detach().cpu()),
                "content_loss_global": float(content_loss_global.detach().cpu()),
                "content_loss_single_linear": float(content_loss_single_linear.detach().cpu()),
                "smooth_loss_global": float(smooth_loss_global.detach().cpu()),
                "max_memory_allocated_mib": _max_memory_mib(torch),
            }
        )

    return {
        "status": "ok" if steps else "no_steps_completed",
        "stage": "sdnet",
        "environment": _environment(torch),
        "dataset": {
            "path": str(dataset_dir),
            "train_sample_count": len(train_dataset),
        },
        "batch_size": batch_size,
        "max_steps": max_steps,
        "completed_steps": len(steps),
        "total_seconds": round(time.perf_counter() - start, 4),
        "max_memory_allocated_mib": _max_memory_mib(torch),
        "steps": steps,
    }


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


def _environment(torch_module: Any) -> dict[str, Any]:
    return {
        "torch_version": torch_module.__version__,
        "cuda_available": torch_module.cuda.is_available(),
        "device_name": torch_module.cuda.get_device_name(0) if torch_module.cuda.is_available() else "",
        "cuda_runtime": getattr(torch_module.version, "cuda", None),
    }


def _max_memory_mib(torch_module: Any) -> int:
    return int(round(torch_module.cuda.max_memory_allocated() / 1024 / 1024))


if __name__ == "__main__":
    raise SystemExit(main())
