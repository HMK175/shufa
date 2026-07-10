"""Trajectory optimization toolkit: enhanced smoothing, velocity planning,
curvature optimization, workspace mapping.

Four independent components + top-level orchestrator. Each component can be
used standalone or chained via optimize_trajectory().

Processing order: smoothing → arc-length reparam → velocity plan →
                    curvature opt → workspace map
"""

import numpy as np
from scipy import interpolate, signal, ndimage
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# Component 1: Enhanced Smoothing
# ═══════════════════════════════════════════════════════════════

def savgol_smooth(
    points: np.ndarray,
    window_length: int = 7,
    polyorder: int = 3,
) -> np.ndarray:
    """Savitzky-Golay filter for local polynomial smoothing.

    Preserves sharp corners better than Gaussian because the polynomial
    can model linear segments exactly.

    Args:
        points: (N, 2) array [y, x]
        window_length: odd integer, filter window size
        polyorder: polynomial order
    Returns:
        (N, 2) smoothed points
    """
    n = len(points)
    if n < window_length:
        return points.copy()
    if window_length % 2 == 0:
        window_length += 1
    if polyorder >= window_length:
        polyorder = window_length - 1

    smoothed_y = signal.savgol_filter(points[:, 0], window_length, polyorder)
    smoothed_x = signal.savgol_filter(points[:, 1], window_length, polyorder)
    return np.column_stack([smoothed_y, smoothed_x])


def adaptive_bspline_smooth(
    points: np.ndarray,
    num_points: Optional[int] = None,
    s: float = 0.0,
    curvature_knot_weight: float = 1.0,
    min_knot_spacing: int = 5,
) -> np.ndarray:
    """B-spline with curvature-based adaptive knot placement.

    More knots in high-curvature regions (corners, turns) and fewer on
    straight segments. Preserves sharp features while smoothing noise.

    Args:
        points: (N, 2)
        num_points: output count (default: same as input)
        s: global smoothing factor
        curvature_knot_weight: how much curvature influences knot density
        min_knot_spacing: minimum points between knots
    Returns:
        (num_points, 2) smoothed points
    """
    n = len(points)
    if n < 8:
        return points.copy()
    if num_points is None:
        num_points = n

    # Compute curvature
    curv = _menger_curvature(points)
    curv_max = curv.max()
    if curv_max < 1e-8:
        curv_norm = np.zeros_like(curv)
    else:
        curv_norm = curv / curv_max

    # Adaptive knot density
    base = 1.0 / n
    density = base + curvature_knot_weight * curv_norm * base * 5
    density /= density.sum()

    # Cumulative density → choose knot indices
    cum_dens = np.cumsum(density)
    n_knots = max(4, n // min_knot_spacing)
    targets = np.linspace(cum_dens[0], cum_dens[-1], n_knots)

    knot_indices = [0]
    for t in targets[1:-1]:
        idx = np.searchsorted(cum_dens, t)
        idx = np.clip(idx, 1, n - 2)
        if idx - knot_indices[-1] >= min_knot_spacing:
            knot_indices.append(int(idx))
    knot_indices.append(n - 1)
    knot_indices = sorted(set(knot_indices))

    # Build knot vector for splprep
    t_param = np.linspace(0, 1, n)
    t_knots = t_param[knot_indices]

    # Pad knot vector (degree=3 needs 4 repeated at each end)
    k = min(3, n - 1)
    t_padded = np.concatenate([
        np.full(k, t_knots[0]),
        t_knots,
        np.full(k, t_knots[-1]),
    ])

    try:
        tck, u = interpolate.splprep(
            [points[:, 0], points[:, 1]], u=t_param, t=t_padded, s=s, k=k
        )
        u_new = np.linspace(0, 1, num_points)
        smoothed = np.array(interpolate.splev(u_new, tck)).T
    except Exception:
        return points.copy()

    return smoothed


def arc_length_reparameterize(
    points: np.ndarray,
    num_points: Optional[int] = None,
) -> np.ndarray:
    """Re-parameterize by arc length for uniform point spacing.

    Computes cumulative chordal distance, then interpolates at equal
    arc-length intervals. Essential for constant-speed robot execution.

    Args:
        points: (N, 2)
        num_points: output count (default: same as input)
    Returns:
        (num_points, 2) uniformly spaced points
    """
    n = len(points)
    if n < 3:
        return points.copy()
    if num_points is None:
        num_points = n

    # Cumulative arc length
    diffs = np.diff(points, axis=0)
    seg_lens = np.linalg.norm(diffs, axis=1)
    cum_len = np.concatenate([[0.0], np.cumsum(seg_lens)])
    total = cum_len[-1]

    if total < 1e-6:
        return points.copy()

    # Equal arc-length sampling
    target_lens = np.linspace(0, total, num_points)
    interp_y = np.interp(target_lens, cum_len, points[:, 0])
    interp_x = np.interp(target_lens, cum_len, points[:, 1])
    return np.column_stack([interp_y, interp_x])


# ═══════════════════════════════════════════════════════════════
# Component 2: Velocity Planning
# ═══════════════════════════════════════════════════════════════

def trapezoidal_velocity(
    n_points: int,
    v_max: float = 1.0,
    v_start: float = 0.0,
    v_end: float = 0.0,
    t_accel_frac: float = 0.15,
    t_decel_frac: float = 0.15,
) -> np.ndarray:
    """Trapezoidal velocity profile for n_points.

    Profile: accel ramp → constant v_max → decel ramp.
    Returns (n_points,) velocity magnitudes normalized to [0, v_max].
    """
    if n_points <= 2:
        return np.full(n_points, v_max)

    n_accel = max(1, int(n_points * t_accel_frac))
    n_decel = max(1, int(n_points * t_decel_frac))

    vel = np.full(n_points, v_max)
    # Accel ramp (0 → v_max)
    vel[:n_accel] = np.linspace(v_start, v_max, n_accel)
    # Decel ramp (v_max → v_end)
    vel[-n_decel:] = np.linspace(v_max, v_end, n_decel)

    return vel


def curvature_aware_velocity(
    points: np.ndarray,
    v_max: float = 1.0,
    alpha: float = 1.0,
    speed_floor: float = 0.15,
) -> np.ndarray:
    """Assign speed per point: v = v_max / (1 + alpha * kappa).

    At straight segments (kappa ~ 0): v ≈ v_max.
    At sharp turns (high kappa): v << v_max.

    Args:
        points: (N, 2)
        v_max: maximum speed
        alpha: curvature sensitivity
        speed_floor: minimum speed as fraction of v_max
    Returns:
        (N,) speed magnitudes
    """
    curv = _menger_curvature(points)
    vel = v_max / (1.0 + alpha * curv)
    vel = np.clip(vel, speed_floor * v_max, v_max)
    return vel


def generate_timed_trajectory(
    points: np.ndarray,
    dt: float = 0.01,
    v_max: float = 1.0,
    curvature_alpha: float = 1.0,
    accel_frac: float = 0.15,
    decel_frac: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Full time-parameterized trajectory generation.

    Returns:
        timestamps: (M,) time at each output point
        timed_points: (M, 2) resampled points [y, x]
        velocities: (M, 2) velocity vectors [vy, vx]

    Algorithm:
    1. Compute curvature-aware speed at each point
    2. Apply trapezoidal envelope
    3. Integrate speed to get cumulative time
    4. Resample at uniform dt via interpolation
    5. Compute velocity vectors via finite differences
    """
    n = len(points)
    if n < 3:
        t = np.linspace(0, dt * n, n)
        v = np.zeros((n, 2))
        if n > 1:
            v[:-1] = np.diff(points, axis=0) / dt
        return t, points.copy(), v

    # 1. Curvature-aware speed
    speed = curvature_aware_velocity(points, v_max, curvature_alpha)

    # 2. Trapezoidal envelope
    envelope = trapezoidal_velocity(len(points), 1.0, 0.0, 0.0,
                                    accel_frac, decel_frac)
    speed = speed * envelope

    # Ensure minimum speed
    speed = np.maximum(speed, 0.01 * v_max)

    # 3. Integrate speed to get cumulative time
    seg_lens = np.linalg.norm(np.diff(points, axis=0), axis=1)
    seg_times = seg_lens / (speed[:-1] + speed[1:] + 1e-8) * 2
    cum_time = np.concatenate([[0.0], np.cumsum(seg_times)])

    # 4. Resample at uniform dt
    total_time = cum_time[-1]
    n_out = max(n, int(total_time / dt) + 1)
    t_out = np.linspace(0, total_time, n_out)

    timed_y = np.interp(t_out, cum_time, points[:, 0])
    timed_x = np.interp(t_out, cum_time, points[:, 1])
    timed_points = np.column_stack([timed_y, timed_x])

    # 5. Velocity vectors
    vel = np.zeros((n_out, 2))
    vel[:-1] = np.diff(timed_points, axis=0) / dt
    vel[-1] = vel[-2] if n_out > 1 else np.zeros(2)

    return t_out, timed_points, vel


# ═══════════════════════════════════════════════════════════════
# Component 3: Curvature Optimization
# ═══════════════════════════════════════════════════════════════

def _menger_curvature(points: np.ndarray) -> np.ndarray:
    """Menger curvature at each interior point.

    k = 4 * area(a,b,c) / (|ab| * |bc| * |ac|)
    Returns (N,) array; boundary points set to 0.
    """
    n = len(points)
    curv = np.zeros(n)
    if n < 3:
        return curv

    a = points[:-2]
    b = points[1:-1]
    c = points[2:]

    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ac = np.linalg.norm(c - a, axis=1)

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = ab * bc * ac
        # Area via cross product (2D)
        cross = np.abs(
            (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) -
            (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        )
        k = 4.0 * cross / denom
        k[~np.isfinite(k)] = 0.0

    curv[1:-1] = k
    return curv


def compute_curvature(points: np.ndarray) -> np.ndarray:
    """Menger 3-point discrete curvature (public alias)."""
    return _menger_curvature(points)


def detect_curvature_peaks(
    curvature: np.ndarray,
    threshold_percentile: float = 85.0,
    min_distance: int = 10,
) -> np.ndarray:
    """Find indices of local curvature maxima above threshold.

    Args:
        curvature: (N,) curvature values
        threshold_percentile: percentile threshold for peak detection
        min_distance: minimum samples between peaks
    Returns:
        array of peak indices sorted by descending curvature
    """
    if len(curvature) < 3:
        return np.array([], dtype=int)

    threshold = np.percentile(curvature, threshold_percentile)
    peaks, properties = signal.find_peaks(
        curvature,
        height=threshold,
        distance=min_distance,
    )
    # Sort by peak prominence (or height) descending
    order = np.argsort(properties['peak_heights'])[::-1]
    return peaks[order]


def local_constrained_bspline(
    points: np.ndarray,
    peak_idx: int,
    binary: np.ndarray,
    window_radius: int = 15,
    s: float = 2.0,
    dist_transform: Optional[np.ndarray] = None,
    max_displacement: float = 5.0,
) -> np.ndarray:
    """Apply local B-spline smoothing around a curvature peak.

    Boundary points outside the window are fixed as constraints.
    After smoothing, points that fall outside the stroke boundary are
    projected back to the nearest foreground pixel.

    Args:
        points: (N, 2)
        peak_idx: index of curvature peak
        binary: (H, W) binary image (0/255, fg=255)
        window_radius: half-width of smoothing window
        s: B-spline smoothing factor
        dist_transform: precomputed fg→bg distance (computed if None)
        max_displacement: max allowed distance from foreground
    Returns:
        (N, 2) modified points
    """
    n = len(points)
    if n < 2 * window_radius:
        return points.copy()

    H, W = binary.shape

    # Window bounds
    lo = max(0, peak_idx - window_radius)
    hi = min(n, peak_idx + window_radius + 1)
    if hi - lo < 5:
        return points.copy()

    # Distance transform for boundary checking
    if dist_transform is None:
        fg_mask = (binary > 0).astype(np.float32)
        dist_transform = ndimage.distance_transform_edt(1 - fg_mask)

    # Smooth the window region
    window_pts = points[lo:hi].copy()
    if len(window_pts) < 4:
        return points.copy()

    try:
        tck, _ = interpolate.splprep(
            [window_pts[:, 0], window_pts[:, 1]], s=s, k=min(3, len(window_pts) - 1)
        )
        t_new = np.linspace(0, 1, len(window_pts))
        smoothed_window = np.array(interpolate.splev(t_new, tck)).T
    except Exception:
        return points.copy()

    # Constraint: ensure smoothed points stay within stroke boundary
    result = points.copy()
    for i, idx in enumerate(range(lo, hi)):
        sy, sx = smoothed_window[i]
        siy, six = int(round(sy)), int(round(sx))
        if 0 <= siy < H and 0 <= six < W:
            d = dist_transform[siy, six]
            if d <= max_displacement:
                result[idx] = [sy, sx]
            else:
                # Project back toward original
                orig = points[idx]
                result[idx] = orig + 0.3 * (np.array([sy, sx]) - orig)
        # else: keep original point

    return result


def optimize_curvature(
    points: np.ndarray,
    binary: np.ndarray,
    curvature_threshold_percentile: float = 85.0,
    window_radius: int = 15,
    s: float = 2.0,
) -> np.ndarray:
    """Detect curvature peaks and apply local constrained smoothing.

    Processes peaks in descending order of curvature magnitude.
    Skips peaks whose windows overlap already-processed regions.

    Args:
        points: (N, 2)
        binary: (H, W) binary image for boundary constraints
        curvature_threshold_percentile: peak detection threshold
        window_radius: smoothing window half-width
        s: B-spline smoothing factor
    Returns:
        (N, 2) optimized points
    """
    n = len(points)
    if n < 2 * window_radius:
        return points.copy()

    curv = _menger_curvature(points)
    peaks = detect_curvature_peaks(curv, curvature_threshold_percentile,
                                   min_distance=window_radius)

    # Precompute distance transform
    fg_mask = (binary > 0).astype(np.float32)
    dist_transform = ndimage.distance_transform_edt(1 - fg_mask)

    result = points.copy()
    smoothed_regions = set()
    for peak_idx in peaks:
        lo = max(0, peak_idx - window_radius)
        hi = min(n, peak_idx + window_radius + 1)
        # Check overlap with already-processed regions
        region = set(range(lo, hi))
        if region & smoothed_regions:
            continue
        result = local_constrained_bspline(
            result, peak_idx, binary, window_radius, s, dist_transform
        )
        smoothed_regions |= region

    return result


# ═══════════════════════════════════════════════════════════════
# Component 4: Workspace Mapping
# ═══════════════════════════════════════════════════════════════

def image_to_workspace(
    points: np.ndarray,
    image_shape: Tuple[int, int],
    workspace_origin: Tuple[float, float, float] = (0.0, 0.0, 0.05),
    workspace_scale: Tuple[float, float] = (0.15, 0.15),
    z_plane: float = 0.05,
    flip_y: bool = True,
) -> np.ndarray:
    """Convert image pixels (y, x) to robot workspace (X, Y, Z) in meters.

    Image: origin top-left, Y increases downward.
    Robot: Z-up, Y-forward, X-right typical.

    Transform:
        X = origin_x + (x / W) * scale_x
        Y = origin_y + (y / H) * scale_y * (1 or -1)
        Z = z_plane (constant writing surface height)

    Args:
        points: (N, 2) [y, x] in image pixels
        image_shape: (H, W) of source image
        workspace_origin: (X, Y, Z) origin in meters
        workspace_scale: (scale_x, scale_y) in meters
        z_plane: constant Z height
        flip_y: if True, Y inverted (image top → robot forward)
    Returns:
        (N, 3) [X, Y, Z] in meters
    """
    H, W = image_shape
    origin_x, origin_y, origin_z = workspace_origin
    scale_x, scale_y = workspace_scale
    y_sign = -1.0 if flip_y else 1.0

    if len(points) == 0:
        return np.empty((0, 3))

    X = origin_x + (points[:, 1] / W) * scale_x
    Y = origin_y + (points[:, 0] / H) * scale_y * y_sign
    Z = np.full(len(points), z_plane)

    return np.column_stack([X, Y, Z])


def workspace_to_csv(
    workspace_points: np.ndarray,
    path: str,
    with_timestamps: bool = False,
    timestamps: Optional[np.ndarray] = None,
):
    """Save workspace coordinates to CSV.

    Columns: X, Y, Z[, t]
    """
    header = "X,Y,Z"
    if with_timestamps and timestamps is not None:
        header += ",t"
        data = np.column_stack([workspace_points, timestamps])
        np.savetxt(path, data, delimiter=",", fmt="%.6f", header=header, comments="")
    else:
        np.savetxt(path, workspace_points, delimiter=",", fmt="%.6f",
                   header=header, comments="")


def save_timed_csv(
    timed_points: np.ndarray,
    velocities: np.ndarray,
    timestamps: np.ndarray,
    path: str,
):
    """Save time-parameterized trajectory: t, y, x, vy, vx."""
    data = np.column_stack([timestamps, timed_points, velocities])
    np.savetxt(path, data, delimiter=",", fmt="%.6f",
               header="t,y,x,vy,vx", comments="")


# ═══════════════════════════════════════════════════════════════
# Top-level orchestrator
# ═══════════════════════════════════════════════════════════════

def optimize_trajectory(
    strokes: List[np.ndarray],
    binary: np.ndarray,
    smooth_method: str = "savgol",
    apply_arc_length: bool = True,
    apply_velocity_plan: bool = False,
    apply_curvature_opt: bool = False,
    apply_workspace_map: bool = False,
    svg_window: int = 7,
    svg_order: int = 3,
    bspline_s: float = 0.0,
    bspline_curv_weight: float = 1.0,
    curv_window_radius: int = 15,
    curv_s: float = 2.0,
    curv_threshold_pct: float = 85.0,
    v_max: float = 1.0,
    curv_alpha: float = 1.0,
    accel_frac: float = 0.15,
    decel_frac: float = 0.15,
    dt: float = 0.01,
    workspace_origin: Tuple[float, float, float] = (0.0, 0.0, 0.05),
    workspace_scale: Tuple[float, float] = (0.15, 0.15),
    z_plane: float = 0.05,
) -> Dict:
    """Full trajectory optimization applied to each stroke.

    Processing order:
    1. Enhanced smoothing (savgol or adaptive_bspline)
    2. Arc-length reparameterization (if enabled)
    3. Velocity planning (if enabled)
    4. Curvature optimization (if enabled)
    5. Workspace mapping (if enabled)

    Returns dict:
        'strokes': List[np.ndarray]       — optimized stroke points
        'timestamps': List[np.ndarray]    — per-stroke time arrays (or None)
        'velocities': List[np.ndarray]    — per-stroke velocity arrays (or None)
        'workspace': List[np.ndarray]     — per-stroke workspace points (or None)
        'chamfer': float                  — average Chamfer distance to foreground
    """
    H, W = binary.shape
    # Precompute distance transform for Chamfer
    fg = (binary > 0).astype(np.float32)
    fg_dist = ndimage.distance_transform_edt(1 - fg)

    optimized_strokes = []
    all_timestamps = []
    all_velocities = []
    all_workspace = []
    chamfer_vals = []

    for stroke in strokes:
        if len(stroke) < 4:
            optimized_strokes.append(stroke.copy())
            all_timestamps.append(None)
            all_velocities.append(None)
            all_workspace.append(None)
            continue

        pts = stroke.astype(np.float64)

        # 1. Enhanced smoothing
        if smooth_method == "savgol":
            pts = savgol_smooth(pts, window_length=svg_window,
                               polyorder=svg_order)
        elif smooth_method == "adaptive_bspline":
            pts = adaptive_bspline_smooth(pts, s=bspline_s,
                                         curvature_knot_weight=bspline_curv_weight)
        elif smooth_method == "both":
            pts = savgol_smooth(pts, window_length=svg_window,
                               polyorder=svg_order)
            pts = adaptive_bspline_smooth(pts, s=bspline_s,
                                         curvature_knot_weight=bspline_curv_weight)

        # 2. Arc-length reparameterization
        if apply_arc_length:
            pts = arc_length_reparameterize(pts)

        # 3. Curvature optimization (before velocity to fix geometry first)
        if apply_curvature_opt:
            pts = optimize_curvature(
                pts, binary,
                curvature_threshold_percentile=curv_threshold_pct,
                window_radius=curv_window_radius,
                s=curv_s,
            )

        optimized_strokes.append(pts)

        # Chamfer distance
        chamfer = 0.0
        for y, x in pts:
            iy, ix = int(round(y)), int(round(x))
            if 0 <= iy < H and 0 <= ix < W:
                chamfer += fg_dist[iy, ix]
            else:
                chamfer += 20.0
        chamfer_vals.append(chamfer / len(pts))

        # 4. Velocity planning
        if apply_velocity_plan:
            t, tp, vel = generate_timed_trajectory(
                pts, dt=dt, v_max=v_max, curvature_alpha=curv_alpha,
                accel_frac=accel_frac, decel_frac=decel_frac,
            )
            all_timestamps.append(t)
            # Replace stroke with timed points
            optimized_strokes[-1] = tp
            all_velocities.append(vel)
        else:
            all_timestamps.append(None)
            all_velocities.append(None)

        # 5. Workspace mapping
        if apply_workspace_map:
            ws = image_to_workspace(
                optimized_strokes[-1], (H, W),
                workspace_origin=workspace_origin,
                workspace_scale=workspace_scale,
                z_plane=z_plane,
            )
            all_workspace.append(ws)
        else:
            all_workspace.append(None)

    avg_chamfer = np.mean(chamfer_vals) if chamfer_vals else 0.0

    return {
        'strokes': optimized_strokes,
        'timestamps': all_timestamps if apply_velocity_plan else None,
        'velocities': all_velocities if apply_velocity_plan else None,
        'workspace': all_workspace if apply_workspace_map else None,
        'chamfer': avg_chamfer,
        'chamfer_per_stroke': chamfer_vals,
    }
