"""Play a resampled workspace trajectory in CoppeliaSim with a pen-tip sphere.

The dry-run path is intentionally dependency-free and is covered by tests.
The live path uses CoppeliaSim's ZeroMQ remote API when available.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CSV = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "batch_20260613_092733"
    / "u5c71_xingkai_20260613_092733_979792"
    / "robot_workspace_trajectory_resampled.csv"
)
PAPER_WIDTH_M = 0.12
PAPER_HEIGHT_M = 0.12
PAPER_WIDTH_MM = PAPER_WIDTH_M * 1000.0
PAPER_HEIGHT_MM = PAPER_HEIGHT_M * 1000.0
DEFAULT_PAPER_SIZE_MM = 120.0
DEFAULT_PEN_TIP_RADIUS_MM = 1.5
DEFAULT_Z_MAX_MM = 8.0
OBJECT_PREFIX = "llm_style_trajectory"
HANDLE_SIGNAL = f"{OBJECT_PREFIX}_handles_json"
RESULT_JSON_NAME = "coppeliasim_playback_result.json"
RESULT_MD_NAME = "coppeliasim_playback_result.md"
SCOPE_NOTE = "standard pen-tip scene only, no robot arm IK (pen-tip/sphere playback only)"


def mm_to_m(value_mm: float | int | str) -> float:
    return float(value_mm) / 1000.0


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def load_workspace_path(csv_path: Path | str) -> list[dict[str, Any]]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    points: list[dict[str, Any]] = []
    for row in rows:
        x_mm = _float(row.get("X_mm"))
        y_mm = _float(row.get("Y_mm"))
        z_mm = _float(row.get("Z_mm"))
        speed_mm_s = _float(row.get("speed_mm_s"))
        points.append(
            {
                "segment_id": _int(row.get("segment_id")),
                "stroke_id": _int(row.get("stroke_id")),
                "point_id": _int(row.get("point_id")),
                "x_mm": x_mm,
                "y_mm": y_mm,
                "z_mm": z_mm,
                "position_m": (mm_to_m(x_mm), mm_to_m(y_mm), mm_to_m(z_mm)),
                "speed_mm_s": speed_mm_s,
                "pressure": _float(row.get("pressure")),
                "width": _float(row.get("width")),
                "pen_down": _int(row.get("pen_down")),
                "is_connector": _int(row.get("is_connector")),
                "segment_type": str(row.get("segment_type", "")),
            }
        )
    return points


def _distance_mm(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = b["x_mm"] - a["x_mm"]
    dy = b["y_mm"] - a["y_mm"]
    dz = b["z_mm"] - a["z_mm"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _step_components_mm(a: dict[str, Any], b: dict[str, Any]) -> dict[str, float]:
    dx = b["x_mm"] - a["x_mm"]
    dy = b["y_mm"] - a["y_mm"]
    dz = b["z_mm"] - a["z_mm"]
    return {
        "step_3d": math.sqrt(dx * dx + dy * dy + dz * dz),
        "step_xy": math.sqrt(dx * dx + dy * dy),
        "step_z": abs(dz),
    }


def dry_run_summary(
    csv_path: Path | str,
    paper_width_mm: float = PAPER_WIDTH_MM,
    paper_height_mm: float = PAPER_HEIGHT_MM,
) -> dict[str, Any]:
    points = load_workspace_path(csv_path)
    if not points:
        return {
            "csv": str(csv_path),
            "point_count": 0,
            "segment_type_counts": {},
            "x_mm_range": [0.0, 0.0],
            "y_mm_range": [0.0, 0.0],
            "z_mm_range": [0.0, 0.0],
            "duration_estimate_s": 0.0,
            "path_length_mm": 0.0,
            "max_step_mm": 0.0,
            "max_step_3d_mm": 0.0,
            "max_xy_step_mm": 0.0,
            "max_z_step_mm": 0.0,
            "stroke_count": 0,
            "connector_count": 0,
            "pen_up_move_count": 0,
            "out_of_workspace_bounds": False,
        }

    counts = Counter(point["segment_type"] for point in points)
    duration = 0.0
    path_length = 0.0
    max_step_3d = 0.0
    max_xy_step = 0.0
    max_z_step = 0.0
    for prev, cur in zip(points, points[1:]):
        components = _step_components_mm(prev, cur)
        step = components["step_3d"]
        path_length += step
        max_step_3d = max(max_step_3d, components["step_3d"])
        max_xy_step = max(max_xy_step, components["step_xy"])
        max_z_step = max(max_z_step, components["step_z"])
        speed = max(cur.get("speed_mm_s") or prev.get("speed_mm_s") or 1.0, 1e-9)
        duration += step / speed

    xs = [point["x_mm"] for point in points]
    ys = [point["y_mm"] for point in points]
    zs = [point["z_mm"] for point in points]
    half_width = paper_width_mm / 2.0
    half_height = paper_height_mm / 2.0
    out_of_bounds = min(xs) < -half_width or max(xs) > half_width or min(ys) < -half_height or max(ys) > half_height
    return {
        "csv": str(csv_path),
        "point_count": len(points),
        "segment_type_counts": dict(sorted(counts.items())),
        "x_mm_range": [round(min(xs), 6), round(max(xs), 6)],
        "y_mm_range": [round(min(ys), 6), round(max(ys), 6)],
        "z_mm_range": [round(min(zs), 6), round(max(zs), 6)],
        "duration_estimate_s": round(duration, 6),
        "path_length_mm": round(path_length, 6),
        "max_step_mm": round(max_step_3d, 6),
        "max_step_3d_mm": round(max_step_3d, 6),
        "max_xy_step_mm": round(max_xy_step, 6),
        "max_z_step_mm": round(max_z_step, 6),
        "stroke_count": counts.get("stroke", 0),
        "connector_count": counts.get("connector", 0),
        "pen_up_move_count": counts.get("pen_up_move", 0),
        "out_of_workspace_bounds": out_of_bounds,
    }


def build_playback_result(
    csv_path: Path | str,
    summary: dict[str, Any],
    *,
    status: str,
    dry_run: bool,
    speed_scale: float,
    display_stride: int,
    no_path_objects: bool,
    auto_stop: bool,
    simulation_stopped: bool,
    scene_setup: str = "standard",
    paper_size_mm: float = DEFAULT_PAPER_SIZE_MM,
    pen_tip_radius_mm: float = DEFAULT_PEN_TIP_RADIUS_MM,
    axes_enabled: bool = False,
    boundary_enabled: bool = False,
    clear_previous_scene: bool = False,
) -> dict[str, Any]:
    scene_report = build_scene_report(
        summary,
        scene_setup=scene_setup,
        paper_size_mm=paper_size_mm,
        pen_tip_radius_mm=pen_tip_radius_mm,
        axes_enabled=axes_enabled,
        boundary_enabled=boundary_enabled,
        clear_previous_scene=clear_previous_scene,
    )
    result = dict(summary)
    result.update(
        {
            "status": status,
            "csv": str(csv_path),
            "speed_scale": float(speed_scale),
            "display_stride": max(1, int(display_stride)),
            "no_path_objects": bool(no_path_objects),
            "path_objects_enabled": not bool(no_path_objects),
            "auto_stop": bool(auto_stop),
            "simulation_stopped": bool(simulation_stopped),
            "dry_run": bool(dry_run),
            "scope": SCOPE_NOTE,
            **scene_report,
        }
    )
    bounds = result["workspace_bounds"]
    result["out_of_workspace_bounds"] = not bool(bounds["xy_within_bounds"])
    result["recommended_playback"] = bool(bounds["recommended_playback"])
    return result


def build_scene_report(
    summary: dict[str, Any],
    *,
    scene_setup: str = "standard",
    paper_size_mm: float = DEFAULT_PAPER_SIZE_MM,
    pen_tip_radius_mm: float = DEFAULT_PEN_TIP_RADIUS_MM,
    axes_enabled: bool = False,
    boundary_enabled: bool = False,
    clear_previous_scene: bool = False,
) -> dict[str, Any]:
    x_range = summary.get("x_mm_range", [0.0, 0.0])
    y_range = summary.get("y_mm_range", [0.0, 0.0])
    z_range = summary.get("z_mm_range", [0.0, 0.0])
    half = float(paper_size_mm) / 2.0
    x_ok = float(x_range[0]) >= -half and float(x_range[1]) <= half
    y_ok = float(y_range[0]) >= -half and float(y_range[1]) <= half
    z_ok = float(z_range[0]) >= 0.0 and float(z_range[1]) <= DEFAULT_Z_MAX_MM
    warnings: list[str] = []
    if not x_ok or not y_ok:
        warnings.append(f"XY path exceeds paper bounds +/-{half:g}mm")
    if not z_ok:
        warnings.append(f"Z path exceeds expected range 0..{DEFAULT_Z_MAX_MM:g}mm")
    recommended = x_ok and y_ok and z_ok
    return {
        "scene_setup": scene_setup,
        "paper_size_mm": float(paper_size_mm),
        "pen_tip_radius_mm": float(pen_tip_radius_mm),
        "axes_enabled": bool(axes_enabled),
        "boundary_enabled": bool(boundary_enabled),
        "clear_previous_scene": bool(clear_previous_scene),
        "coordinate_mapping": {
            "X_m": "X_mm / 1000",
            "Y_m": "Y_mm / 1000",
            "Z_m": "Z_mm / 1000",
        },
        "workspace_bounds": {
            "paper_half_size_mm": half,
            "x_range_mm": x_range,
            "y_range_mm": y_range,
            "z_range_mm": z_range,
            "x_within_bounds": x_ok,
            "y_within_bounds": y_ok,
            "xy_within_bounds": x_ok and y_ok,
            "z_allowed_range_mm": [0.0, DEFAULT_Z_MAX_MM],
            "z_within_bounds": z_ok,
            "recommended_playback": recommended,
            "warnings": warnings,
        },
        "scene_warnings": warnings,
    }


def _playback_result_markdown(result: dict[str, Any]) -> str:
    fields = [
        "status",
        "csv",
        "point_count",
        "segment_type_counts",
        "duration_estimate_s",
        "speed_scale",
        "display_stride",
        "path_objects_enabled",
        "no_path_objects",
        "auto_stop",
        "simulation_stopped",
        "dry_run",
        "x_mm_range",
        "y_mm_range",
        "z_mm_range",
        "max_step_3d_mm",
        "max_xy_step_mm",
        "max_z_step_mm",
        "scene_setup",
        "paper_size_mm",
        "pen_tip_radius_mm",
        "axes_enabled",
        "boundary_enabled",
        "clear_previous_scene",
        "coordinate_mapping",
        "workspace_bounds",
        "recommended_playback",
        "scene_warnings",
        "scope",
    ]
    lines = [
        "# CoppeliaSim Playback Result",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for field in fields:
        value = result.get(field, "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{field}` | `{value}` |")
    lines.extend(
        [
            "",
            f"Scope note: {SCOPE_NOTE}.",
            "",
        ]
    )
    return "\n".join(lines)


def write_playback_result(result: dict[str, Any], out_dir: Path | str) -> dict[str, str]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / RESULT_JSON_NAME
    md_path = target / RESULT_MD_NAME
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_playback_result_markdown(result), encoding="utf-8")
    return {"result_json": str(json_path), "result_md": str(md_path)}


def _remote_api_client():
    try:
        from coppeliasim_zmqremoteapi_client import RemoteAPIClient
    except ImportError as exc:
        raise RuntimeError(
            "CoppeliaSim ZeroMQ remote API Python client is not available. "
            "Install/expose coppeliasim_zmqremoteapi_client, or run with --dry-run."
        ) from exc
    try:
        client = RemoteAPIClient()
        sim = client.require("sim") if hasattr(client, "require") else client.getObject("sim")
        return client, sim
    except Exception as exc:  # pragma: no cover - requires live CoppeliaSim
        raise RuntimeError(
            "Could not connect to CoppeliaSim. Start CoppeliaSim first, "
            "then rerun this script, or use --dry-run."
        ) from exc


def _call_first(sim: Any, candidates: list[tuple[str, tuple[Any, ...]]]) -> Any:
    last_error: Exception | None = None
    for name, args in candidates:
        func = getattr(sim, name, None)
        if func is None:
            continue
        try:
            return func(*args)
        except Exception as exc:  # pragma: no cover - live CoppeliaSim fallback
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"CoppeliaSim API function not available: {[name for name, _ in candidates]}")


def _safe_call(func: Any, *args: Any) -> Any:
    try:
        return func(*args)
    except Exception:
        return None


def _set_alias(sim: Any, handle: Any, alias: str) -> None:
    setter = getattr(sim, "setObjectAlias", None)
    if setter is not None:
        _safe_call(setter, handle, alias)


def _get_signal_handles(sim: Any) -> list[int]:
    getter = getattr(sim, "getStringSignal", None)
    if getter is None:
        return []
    data = _safe_call(getter, HANDLE_SIGNAL)
    if not data:
        return []
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")
    try:
        parsed = json.loads(str(data))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [int(item) for item in parsed if isinstance(item, int) or str(item).lstrip("-").isdigit()]


def _store_signal_handles(sim: Any, handles: list[Any]) -> None:
    setter = getattr(sim, "setStringSignal", None)
    if setter is None:
        return
    numeric = [int(handle) for handle in handles if isinstance(handle, int) or str(handle).lstrip("-").isdigit()]
    _safe_call(setter, HANDLE_SIGNAL, json.dumps(numeric))


def _clear_previous_scene(sim: Any) -> None:
    for handle in _get_signal_handles(sim):
        remover_drawing = getattr(sim, "removeDrawingObject", None)
        if remover_drawing is not None:
            _safe_call(remover_drawing, handle)
        remover_object = getattr(sim, "removeObject", None)
        if remover_object is not None:
            _safe_call(remover_object, handle)
    clearer = getattr(sim, "clearStringSignal", None)
    if clearer is not None:
        _safe_call(clearer, HANDLE_SIGNAL)


def _create_scene_objects(
    sim: Any,
    *,
    paper_size_mm: float = DEFAULT_PAPER_SIZE_MM,
    pen_tip_radius_mm: float = DEFAULT_PEN_TIP_RADIUS_MM,
) -> dict[str, Any]:
    # A thin cuboid paper plane and a small pen-tip sphere. API variants differ
    # slightly across CoppeliaSim builds, so calls are kept in small fallbacks.
    paper_size_m = float(paper_size_mm) / 1000.0
    radius_m = float(pen_tip_radius_mm) / 1000.0
    diameter_m = max(radius_m * 2.0, 0.0005)
    paper = _call_first(
        sim,
        [
            ("createPrimitiveShape", (getattr(sim, "primitiveshape_cuboid", 0), [paper_size_m, paper_size_m, 0.001], 0)),
            ("createPureShape", (0, 8, [paper_size_m, paper_size_m, 0.001], 0.0, None)),
        ],
    )
    _set_alias(sim, paper, f"{OBJECT_PREFIX}_paper")
    sim.setObjectPosition(paper, -1, [0.0, 0.0, -0.0005])

    pen = _call_first(
        sim,
        [
            ("createPrimitiveShape", (getattr(sim, "primitiveshape_spheroid", 1), [diameter_m, diameter_m, diameter_m], 0)),
            ("createPureShape", (1, 8, [diameter_m, diameter_m, diameter_m], 0.0, None)),
        ],
    )
    _set_alias(sim, pen, f"{OBJECT_PREFIX}_pen_tip")
    sim.setObjectPosition(pen, -1, [0.0, 0.0, max(radius_m, 0.001)])

    return {"paper": paper, "pen": pen, "handles": [paper, pen]}


def _draw_line_group(sim: Any, lines: list[tuple[float, float, float, float, float, float]], color: list[float]) -> Any:
    drawing_lines = getattr(sim, "drawing_lines", 1)
    handle = sim.addDrawingObject(drawing_lines, 2.0, 0.0, -1, max(1, len(lines)), color)
    for line in lines:
        sim.addDrawingObjectItem(handle, list(line))
    return handle


def _draw_boundary(sim: Any, paper_size_mm: float) -> Any:
    half = float(paper_size_mm) / 2000.0
    z = 0.0008
    lines = [
        (-half, -half, z, half, -half, z),
        (half, -half, z, half, half, z),
        (half, half, z, -half, half, z),
        (-half, half, z, -half, -half, z),
    ]
    return _draw_line_group(sim, lines, [0.1, 0.1, 0.1])


def _draw_axes(sim: Any, paper_size_mm: float) -> list[Any]:
    half = float(paper_size_mm) / 2000.0
    z_len = min(0.03, max(0.01, half * 0.5))
    return [
        _draw_line_group(sim, [(0.0, 0.0, 0.0015, half, 0.0, 0.0015)], [1.0, 0.0, 0.0]),
        _draw_line_group(sim, [(0.0, 0.0, 0.0015, 0.0, half, 0.0015)], [0.0, 0.8, 0.0]),
        _draw_line_group(sim, [(0.0, 0.0, 0.0015, 0.0, 0.0, z_len)], [0.0, 0.2, 1.0]),
    ]


def _create_standard_scene(
    sim: Any,
    *,
    paper_size_mm: float,
    pen_tip_radius_mm: float,
    show_axes: bool,
    show_boundary: bool,
    clear_previous_scene: bool,
) -> dict[str, Any]:
    if clear_previous_scene:
        _clear_previous_scene(sim)
    objects = _create_scene_objects(sim, paper_size_mm=paper_size_mm, pen_tip_radius_mm=pen_tip_radius_mm)
    handles = list(objects.get("handles", []))
    if show_boundary:
        handles.append(_draw_boundary(sim, paper_size_mm))
    if show_axes:
        handles.extend(_draw_axes(sim, paper_size_mm))
    objects["handles"] = handles
    return objects


def _drawing_color(segment_type: str) -> list[float]:
    if segment_type == "connector":
        return [1.0, 0.1, 0.05]
    if segment_type == "pen_up_move":
        return [0.55, 0.55, 0.55]
    return [0.05, 0.35, 1.0]


def _draw_path(sim: Any, points: list[dict[str, Any]], display_stride: int = 1) -> list[Any]:
    handles: list[Any] = []
    drawing_lines = getattr(sim, "drawing_lines", 1)
    max_items = max(1, len(points) * 2)
    by_type = {"stroke": [], "connector": [], "pen_up_move": []}
    stride = max(1, int(display_stride))
    for idx, (prev, cur) in enumerate(zip(points, points[1:])):
        if idx % stride != 0:
            continue
        segment_type = cur["segment_type"] or prev["segment_type"]
        by_type.setdefault(segment_type, []).append((*prev["position_m"], *cur["position_m"]))
    for segment_type, line_items in by_type.items():
        if not line_items:
            continue
        color = _drawing_color(segment_type)
        handle = sim.addDrawingObject(drawing_lines, 2.0, 0.0, -1, max_items, color)
        handles.append(handle)
        for item in line_items:
            sim.addDrawingObjectItem(handle, list(item))
    return handles


def play_path(
    csv_path: Path | str,
    speed_scale: float = 1.0,
    display_stride: int = 1,
    no_path_objects: bool = False,
    auto_stop: bool = False,
    scene_setup: str = "standard",
    paper_size_mm: float = DEFAULT_PAPER_SIZE_MM,
    pen_tip_radius_mm: float = DEFAULT_PEN_TIP_RADIUS_MM,
    show_axes: bool = False,
    show_boundary: bool = False,
    clear_previous_scene: bool = False,
) -> dict[str, Any]:
    points = load_workspace_path(csv_path)
    if not points:
        raise ValueError(f"No points in CSV: {csv_path}")

    _, sim = _remote_api_client()
    if scene_setup != "standard":
        raise ValueError(f"Unsupported scene setup: {scene_setup}")
    objects = _create_standard_scene(
        sim,
        paper_size_mm=paper_size_mm,
        pen_tip_radius_mm=pen_tip_radius_mm,
        show_axes=show_axes,
        show_boundary=show_boundary,
        clear_previous_scene=clear_previous_scene,
    )
    handles = list(objects.get("handles", []))
    if not no_path_objects:
        handles.extend(_draw_path(sim, points, display_stride=display_stride))
    _store_signal_handles(sim, handles)

    try:
        sim.startSimulation()
    except Exception:
        pass

    prev = points[0]
    for cur in points:
        sim.setObjectPosition(objects["pen"], -1, list(cur["position_m"]))
        step_mm = _distance_mm(prev, cur)
        speed = max(cur.get("speed_mm_s") or 1.0, 1e-9) * max(speed_scale, 1e-9)
        time.sleep(min(0.1, step_mm / speed))
        prev = cur

    simulation_stopped = False
    if auto_stop:
        try:
            sim.stopSimulation()
            simulation_stopped = True
        except Exception:
            pass

    summary = dry_run_summary(csv_path)
    summary["simulation_stopped"] = simulation_stopped
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play a resampled workspace path in CoppeliaSim")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="robot_workspace_trajectory_resampled.csv path")
    parser.add_argument("--speed-scale", type=float, default=1.0)
    parser.add_argument("--scene-setup", choices=["standard"], default="standard")
    parser.add_argument("--clear-previous-scene", action="store_true")
    parser.add_argument("--paper-size-mm", type=float, default=DEFAULT_PAPER_SIZE_MM)
    parser.add_argument("--pen-tip-radius-mm", type=float, default=DEFAULT_PEN_TIP_RADIUS_MM)
    parser.add_argument("--show-axes", action="store_true")
    parser.add_argument("--show-boundary", action="store_true")
    parser.add_argument(
        "--display-stride",
        type=int,
        default=1,
        help="Draw every Nth visual path segment while keeping full pen-tip playback",
    )
    parser.add_argument("--no-path-objects", action="store_true", help="Only move the pen-tip sphere; skip colored path objects")
    parser.add_argument("--auto-stop", action="store_true", help="Stop the CoppeliaSim simulation after playback")
    parser.add_argument("--result-out-dir", default=None, help="Directory for single playback result JSON/Markdown")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    result_out_dir = Path(args.result_out_dir) if args.result_out_dir else csv_path.parent
    if args.dry_run:
        result = build_playback_result(
            csv_path,
            dry_run_summary(csv_path, paper_width_mm=args.paper_size_mm, paper_height_mm=args.paper_size_mm),
            status="dry_run",
            dry_run=True,
            speed_scale=args.speed_scale,
            display_stride=args.display_stride,
            no_path_objects=args.no_path_objects,
            auto_stop=args.auto_stop,
            simulation_stopped=False,
            scene_setup=args.scene_setup,
            paper_size_mm=args.paper_size_mm,
            pen_tip_radius_mm=args.pen_tip_radius_mm,
            axes_enabled=args.show_axes,
            boundary_enabled=args.show_boundary,
            clear_previous_scene=args.clear_previous_scene,
        )
        result.update(write_playback_result(result, result_out_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        play_summary = play_path(
            csv_path,
            speed_scale=args.speed_scale,
            display_stride=args.display_stride,
            no_path_objects=args.no_path_objects,
            auto_stop=args.auto_stop,
            scene_setup=args.scene_setup,
            paper_size_mm=args.paper_size_mm,
            pen_tip_radius_mm=args.pen_tip_radius_mm,
            show_axes=args.show_axes,
            show_boundary=args.show_boundary,
            clear_previous_scene=args.clear_previous_scene,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    simulation_stopped = bool(play_summary.pop("simulation_stopped", False))
    result = build_playback_result(
        csv_path,
        play_summary,
        status="finished",
        dry_run=False,
        speed_scale=args.speed_scale,
        display_stride=args.display_stride,
        no_path_objects=args.no_path_objects,
        auto_stop=args.auto_stop,
        simulation_stopped=simulation_stopped,
        scene_setup=args.scene_setup,
        paper_size_mm=args.paper_size_mm,
        pen_tip_radius_mm=args.pen_tip_radius_mm,
        axes_enabled=args.show_axes,
        boundary_enabled=args.show_boundary,
        clear_previous_scene=args.clear_previous_scene,
    )
    result.update(write_playback_result(result, result_out_dir))
    if not args.auto_stop:
        print(
            "playback finished, but CoppeliaSim simulation may still be running; "
            "use --auto-stop to stop it automatically",
            file=sys.stderr,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
