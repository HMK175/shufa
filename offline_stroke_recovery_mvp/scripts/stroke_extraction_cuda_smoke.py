"""Synthetic CUDA memory smoke test for StrokeExtraction models.

This script does not train StrokeExtraction and does not need RHSEDB or model
checkpoints. It only instantiates the upstream model definitions and runs tiny
synthetic forward/backward probes to estimate whether the local CUDA PyTorch
environment can execute the models.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Callable


def parse_batch_sizes(value: str) -> list[int]:
    sizes = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not sizes or any(size <= 0 for size in sizes):
        raise ValueError("batch sizes must be positive integers")
    return sizes


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_missing_modules(module_names: list[str]) -> list[str]:
    return [name for name in module_names if importlib.util.find_spec(name) is None]


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        batch_sizes = parse_batch_sizes(args.batch_sizes)
    except ValueError as error:
        parser.error(str(error))

    payload = run_smoke(
        args.repo,
        batch_sizes=batch_sizes,
        skip_sdnet=args.skip_sdnet,
        backward=args.backward,
    )
    write_report(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] in {"ok", "cuda_unavailable"} else 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("external_repos") / "StrokeExtraction",
        help="Path to the external StrokeExtraction checkout.",
    )
    parser.add_argument(
        "--batch-sizes",
        default="1,2,4",
        help="Comma-separated batch sizes to probe.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "stroke_extraction_cuda_smoke"
        / "cuda_smoke_report.json",
        help="JSON report path.",
    )
    parser.add_argument(
        "--skip-sdnet",
        action="store_true",
        help="Skip SDNet probe. Useful because SDNet includes CharNet and is the largest model.",
    )
    parser.add_argument(
        "--backward",
        action="store_true",
        help=(
            "Run training-style backward probes. By default the script runs eval "
            "forward probes so batch_size=1 can pass BatchNorm layers."
        ),
    )
    return parser


def run_smoke(
    repo_dir: Path,
    *,
    batch_sizes: list[int],
    skip_sdnet: bool,
    backward: bool,
) -> dict[str, Any]:
    import sys

    import torch

    repo_dir = Path(repo_dir)
    if not repo_dir.exists():
        return {
            "status": "missing_repo",
            "repo_dir": str(repo_dir),
            "batch_results": [],
        }

    sys.path.insert(0, str(repo_dir))
    environment = {
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "cuda_runtime": getattr(torch.version, "cuda", None),
    }
    if not torch.cuda.is_available():
        return {
            "status": "cuda_unavailable",
            "repo_dir": str(repo_dir),
            "environment": environment,
            "recommendation": "Install a CUDA-enabled PyTorch environment before running GPU memory probes.",
            "batch_results": [],
        }

    missing_modules = find_missing_modules(["matplotlib", "cv2"])
    if missing_modules:
        return {
            "status": "missing_python_dependencies",
            "repo_dir": str(repo_dir),
            "environment": environment,
            "missing_modules": missing_modules,
            "recommendation": (
                "Install missing modules in this same virtual environment, for example: "
                "python -m pip install matplotlib opencv-python"
            ),
            "batch_results": [],
        }

    from model.model_of_ExtractNet import ExtractNet
    from model.model_of_SDNet import SDNet
    from model.model_of_SegNet import SegNet

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True

    probes: list[tuple[str, Callable[[int, torch.device], torch.Tensor]]] = [
        ("SegNet", lambda batch, device: _probe_segnet(SegNet(out_feature=True), batch, device, backward=backward)),
        ("ExtractNet", lambda batch, device: _probe_extractnet(ExtractNet(), batch, device, backward=backward)),
    ]
    if not skip_sdnet:
        probes.insert(0, ("SDNet", lambda batch, device: _probe_sdnet(SDNet(), batch, device, backward=backward)))

    results: list[dict[str, Any]] = []
    for batch_size in batch_sizes:
        for model_name, probe in probes:
            results.append(_run_one_probe(model_name, batch_size, device, probe))
            if results[-1]["status"] == "oom":
                break

    return {
        "status": "ok",
        "repo_dir": str(repo_dir),
        "environment": environment,
        "batch_sizes": batch_sizes,
        "probe_mode": "backward" if backward else "eval_forward",
        "batch_results": results,
    }


def _run_one_probe(
    model_name: str,
    batch_size: int,
    device: Any,
    probe: Callable[[int, Any], Any],
) -> dict[str, Any]:
    import torch

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    try:
        loss = probe(batch_size, device)
        if loss.requires_grad:
            loss.backward()
        torch.cuda.synchronize()
    except torch.cuda.OutOfMemoryError as error:
        torch.cuda.empty_cache()
        return {
            "model": model_name,
            "batch_size": batch_size,
            "status": "oom",
            "error": str(error),
            "max_memory_allocated_mib": _max_memory_mib(torch),
        }
    except (RuntimeError, ValueError) as error:
        torch.cuda.empty_cache()
        return {
            "model": model_name,
            "batch_size": batch_size,
            "status": "runtime_error",
            "error": str(error),
            "max_memory_allocated_mib": _max_memory_mib(torch),
        }
    elapsed = time.perf_counter() - start
    max_allocated = _max_memory_mib(torch)
    torch.cuda.empty_cache()
    return {
        "model": model_name,
        "batch_size": batch_size,
        "status": "ok",
        "seconds": round(elapsed, 4),
        "max_memory_allocated_mib": max_allocated,
    }


def _probe_sdnet(model: Any, batch_size: int, device: Any, *, backward: bool) -> Any:
    import torch

    model = model.to(device).train(backward)
    color_reference = torch.rand(batch_size, 3, 256, 256, device=device)
    target_data = torch.rand(batch_size, 1, 256, 256, device=device)
    with torch.set_grad_enabled(backward):
        transformed_target, flow_global, grid_for_linear = model.get_two_registration_field(
            color_reference,
            target_data,
        )
    return transformed_target.mean() + flow_global.square().mean() + grid_for_linear.square().mean()


def _probe_segnet(model: Any, batch_size: int, device: Any, *, backward: bool) -> Any:
    import torch

    model = model.to(device).train(backward)
    target_data = torch.rand(batch_size, 3, 256, 256, device=device)
    reference_data = torch.rand(batch_size, 3, 256, 256, device=device)
    with torch.set_grad_enabled(backward):
        seg_out, feature = model(target_data, reference_data)
    return seg_out.square().mean() + feature["out_64_32"].square().mean()


def _probe_extractnet(model: Any, batch_size: int, device: Any, *, backward: bool) -> Any:
    import torch

    model = model.to(device).train(backward)
    trans_single = torch.rand(batch_size, 3, 256, 256, device=device)
    kaiti_seg_tran = torch.rand(batch_size, 1, 256, 256, device=device)
    seg_out = torch.rand(batch_size, 1, 256, 256, device=device)
    style_original = torch.rand(batch_size, 3, 256, 256, device=device)
    feature_64 = torch.rand(batch_size, 32, 64, 64, device=device)
    with torch.set_grad_enabled(backward):
        out = model(trans_single, kaiti_seg_tran, seg_out, style_original, feature_64)
    return out.square().mean()


def _max_memory_mib(torch_module: Any) -> int:
    return int(round(torch_module.cuda.max_memory_allocated() / 1024 / 1024))


if __name__ == "__main__":
    raise SystemExit(main())
