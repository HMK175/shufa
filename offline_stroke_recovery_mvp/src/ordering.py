"""Conservative candidate writable ordering for extracted graph segments."""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import permutations, product
from typing import Any, Iterable, Sequence


Point = tuple[float, float]
ENDPOINT_DIRECTION_SAMPLE_STEPS = 4
CLOSED_POINT_EPSILON = 1e-6
MAX_EXACT_GROUP_SEGMENTS = 7
MAX_EXACT_COMPONENT_GROUPS = 6
MAX_BEAM_GROUP_SEGMENTS = 10
MAX_BEAM_COMPONENT_GROUPS = 10
BEAM_WIDTH = 32


def order_segments(
    segments: Sequence[dict[str, Any]],
    *,
    endpoint_merge_distance: float = 0.0,
    direction_cos_threshold: float = 0.65,
) -> list[dict[str, Any]]:
    """Return deterministic stroke-like segment candidates.

    This is intentionally conservative: components stay grouped, longer
    segments lead within each group, and endpoint merging only applies to
    nearby non-loop segments whose local directions are compatible.
    """

    normalized = [_normalize_segment(segment) for segment in segments]
    by_component: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for segment in normalized:
        by_component[segment.get("component_id")].append(segment)

    ordered: list[dict[str, Any]] = []
    for component_id in sorted(by_component, key=_component_sort_key):
        group = _sort_group(by_component[component_id])
        if endpoint_merge_distance > 0:
            group = _merge_group(
                group,
                endpoint_merge_distance=endpoint_merge_distance,
                direction_cos_threshold=direction_cos_threshold,
            )
            group = _sort_group(group)
        group = _bridge_closed_anchor_crossing(group)
        group = _sequence_group(group)
        ordered.append(group)

    flattened = [
        segment
        for group in _sequence_component_groups(ordered)
        for segment in group
    ]
    return [_with_order(segment, index) for index, segment in enumerate(flattened, start=1)]


def _normalize_segment(segment: dict[str, Any]) -> dict[str, Any]:
    points = [_as_point(point) for point in segment.get("points", ())]
    source_ids = segment.get("source_segment_ids")
    if source_ids is None:
        source_ids = (segment.get("segment_id"),)
    source_ids = tuple(source_id for source_id in source_ids if source_id is not None)

    normalized: dict[str, Any] = {
        **segment,
        "source_segment_ids": source_ids,
        "points": points,
        "length_px": float(segment.get("length_px", _polyline_length(points))),
    }
    if "is_loop" in segment:
        normalized["is_loop"] = bool(segment["is_loop"])
    return normalized


def _with_order(segment: dict[str, Any], index: int) -> dict[str, Any]:
    output = dict(segment)
    output["stroke_like_id"] = index
    output["order_index"] = index
    output["source_segment_ids"] = tuple(output["source_segment_ids"])
    output["points"] = list(output["points"])
    _refresh_geometry_metadata(output)
    return output


def _sort_group(segments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        segments,
        key=lambda segment: (
            -float(segment.get("length_px", 0.0)),
            *_top_left_start(segment.get("points", ())),
            segment["source_segment_ids"],
        ),
    )


def _sequence_group(segments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(segments) <= 1:
        return [_copy_segment(segment) for segment in segments]

    exact = _sequence_group_exact(segments)
    if exact is not None:
        return exact

    beam = _sequence_group_beam(segments)
    if beam is not None:
        return beam

    pending = [_copy_segment(segment) for segment in segments]
    ordered = [pending.pop(0)]

    while pending:
        previous_end = ordered[-1]["points"][-1] if ordered[-1].get("points") else None
        best: tuple[float, float, float, float, tuple[Any, ...], int, dict[str, Any]] | None = None
        for index, candidate in enumerate(pending):
            oriented = _orient_segment_for_continuation(candidate, previous_end)
            points = oriented.get("points", ())
            distance = 0.0
            if previous_end is not None and points:
                distance = _distance(previous_end, points[0])
            item = (
                distance,
                -float(oriented.get("length_px", 0.0)),
                *_top_left_start(points),
                oriented["source_segment_ids"],
                index,
                oriented,
            )
            if best is None or item < best:
                best = item
        assert best is not None
        ordered.append(best[-1])
        pending.pop(best[-2])

    return ordered


def _sequence_group_exact(
    segments: Sequence[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    if len(segments) > MAX_EXACT_GROUP_SEGMENTS:
        return None

    normalized_segments = [_copy_segment(segment) for segment in segments]
    best_key: tuple[Any, ...] | None = None
    best_sequence: list[dict[str, Any]] | None = None

    for segment_order in permutations(range(len(normalized_segments))):
        for flip_flags in product((0, 1), repeat=len(normalized_segments)):
            candidate_segments: list[dict[str, Any]] = []
            jumps: list[float] = []
            previous_end = None

            for position, segment_index in enumerate(segment_order):
                base_segment = normalized_segments[segment_index]
                segment = (
                    _copy_segment(base_segment)
                    if flip_flags[position] == 0
                    else _reversed_segment(base_segment)
                )
                points = segment.get("points", ())
                if previous_end is not None and points:
                    jumps.append(_distance(previous_end, points[0]))
                if points:
                    previous_end = points[-1]
                candidate_segments.append(segment)

            first_segment_rank = segment_order[0] if segment_order else 0
            first_orientation_penalty = 0
            if candidate_segments:
                preferred_first = _orient_seed_segment(normalized_segments[segment_order[0]])
                first_orientation_penalty = int(
                    tuple(candidate_segments[0].get("points", ())) != tuple(preferred_first.get("points", ()))
                )
            source_ids = tuple(segment.get("source_segment_ids", ()) for segment in candidate_segments)
            starts = tuple(
                segment.get("points", [(float("inf"), float("inf"))])[0]
                if segment.get("points")
                else (float("inf"), float("inf"))
                for segment in candidate_segments
            )
            key = (
                max(jumps) if jumps else 0.0,
                sum(jumps),
                first_segment_rank,
                first_orientation_penalty,
                source_ids,
                starts,
                flip_flags,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_sequence = candidate_segments

    return best_sequence


def _sequence_group_beam(
    segments: Sequence[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    if len(segments) <= MAX_EXACT_GROUP_SEGMENTS or len(segments) > MAX_BEAM_GROUP_SEGMENTS:
        return None

    normalized_segments = [_copy_segment(segment) for segment in segments]
    seed_segment = _copy_segment(normalized_segments[0])
    remaining_segments = normalized_segments[1:]
    seed_points = seed_segment.get("points", ())
    previous_end = seed_points[-1] if seed_points else None

    beam: list[tuple[tuple[Any, ...], list[dict[str, Any]], list[float], tuple[int, ...], Point | None]] = [
        (
            _sequence_beam_key([seed_segment], []),
            [seed_segment],
            [],
            tuple(range(len(remaining_segments))),
            previous_end,
        )
    ]

    while beam and len(beam[0][1]) < len(normalized_segments):
        next_beam: list[tuple[tuple[Any, ...], list[dict[str, Any]], list[float], tuple[int, ...], Point | None]] = []
        for _, sequence, jumps, remaining_indices, previous_end in beam:
            for segment_index in remaining_indices:
                base_segment = remaining_segments[segment_index]
                forward = _copy_segment(base_segment)
                reverse = _reversed_segment(base_segment)
                candidates = [forward]
                if reverse.get("points") != forward.get("points"):
                    candidates.append(reverse)
                for candidate in candidates:
                    points = candidate.get("points", ())
                    next_jumps = list(jumps)
                    if previous_end is not None and points:
                        next_jumps.append(_distance(previous_end, points[0]))
                    next_previous_end = points[-1] if points else previous_end
                    next_sequence = [*sequence, candidate]
                    next_remaining = tuple(index for index in remaining_indices if index != segment_index)
                    next_beam.append(
                        (
                            _sequence_beam_key(next_sequence, next_jumps),
                            next_sequence,
                            next_jumps,
                            next_remaining,
                            next_previous_end,
                        )
                    )
        if not next_beam:
            return None
        next_beam.sort(key=lambda item: item[0])
        beam = next_beam[:BEAM_WIDTH]

    if not beam:
        return None
    return beam[0][1]


def _bridge_closed_anchor_crossing(
    segments: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    copied = [_copy_segment(segment) for segment in segments]
    for loop_index, loop_segment in enumerate(copied):
        if not _is_closed_segment(loop_segment):
            continue
        loop_points = list(loop_segment.get("points", ()))
        if len(loop_points) < 4:
            continue
        anchor = loop_points[0]
        for candidate_index, candidate in enumerate(copied):
            if candidate_index == loop_index:
                continue
            split = _split_segment_around_anchor(candidate, anchor)
            if split is None:
                continue
            head, tail = split
            bridged = [head, loop_segment, tail]
            bridged.extend(
                _copy_segment(segment)
                for index, segment in enumerate(copied)
                if index not in {loop_index, candidate_index}
            )
            return bridged
    return copied


def _sequence_component_groups(groups: Sequence[Sequence[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    if len(groups) <= 1:
        return [[_copy_segment(segment) for segment in group] for group in groups]

    exact = _sequence_component_groups_exact(groups)
    if exact is not None:
        return exact

    beam = _sequence_component_groups_beam(groups)
    if beam is not None:
        return beam

    pending = [[_copy_segment(segment) for segment in group] for group in groups]
    ordered = [pending.pop(0)]

    while pending:
        previous_end = _group_end(ordered[-1])
        best: tuple[float, float, float, float, tuple[Any, ...], int, list[dict[str, Any]]] | None = None
        for index, group in enumerate(pending):
            oriented = _orient_group_for_continuation(group, previous_end)
            points = oriented[0].get("points", ()) if oriented else ()
            distance = 0.0
            if previous_end is not None and points:
                distance = _distance(previous_end, points[0])
            first_segment = oriented[0] if oriented else {"length_px": 0.0, "source_segment_ids": ()}
            item = (
                distance,
                -float(first_segment.get("length_px", 0.0)),
                *_top_left_start(points),
                tuple(first_segment.get("source_segment_ids", ())),
                index,
                oriented,
            )
            if best is None or item < best:
                best = item
        assert best is not None
        ordered.append(best[-1])
        pending.pop(best[-2])

    return ordered


def _sequence_component_groups_exact(
    groups: Sequence[Sequence[dict[str, Any]]],
) -> list[list[dict[str, Any]]] | None:
    if len(groups) > MAX_EXACT_COMPONENT_GROUPS:
        return None

    normalized_groups = [[_copy_segment(segment) for segment in group] for group in groups]
    seed_group = [_copy_segment(segment) for segment in normalized_groups[0]]
    remaining_groups = normalized_groups[1:]
    best_key: tuple[Any, ...] | None = None
    best_groups: list[list[dict[str, Any]]] | None = None

    for group_order in permutations(range(len(remaining_groups))):
        for flip_flags in product((0, 1), repeat=len(remaining_groups)):
            candidate_groups: list[list[dict[str, Any]]] = [[_copy_segment(segment) for segment in seed_group]]
            jumps: list[float] = []
            previous_end = _group_end(seed_group)

            for position, group_index in enumerate(group_order):
                base_group = remaining_groups[group_index]
                group = (
                    [_copy_segment(segment) for segment in base_group]
                    if flip_flags[position] == 0
                    else _reversed_group(base_group)
                )
                start = _group_start(group)
                end = _group_end(group)
                if previous_end is not None and start is not None:
                    jumps.append(_distance(previous_end, start))
                previous_end = end
                candidate_groups.append(group)

            sequence_ids = tuple(
                tuple(segment.get("source_segment_ids", ()) for segment in group)
                for group in candidate_groups
            )
            group_starts = tuple(_group_start(group) or (float("inf"), float("inf")) for group in candidate_groups)
            key = (
                max(jumps) if jumps else 0.0,
                sum(jumps),
                sequence_ids,
                group_starts,
                flip_flags,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_groups = candidate_groups

    return best_groups


def _sequence_component_groups_beam(
    groups: Sequence[Sequence[dict[str, Any]]],
) -> list[list[dict[str, Any]]] | None:
    if len(groups) <= MAX_EXACT_COMPONENT_GROUPS or len(groups) > MAX_BEAM_COMPONENT_GROUPS:
        return None

    normalized_groups = [[_copy_segment(segment) for segment in group] for group in groups]
    seed_group = [_copy_segment(segment) for segment in normalized_groups[0]]
    remaining_groups = normalized_groups[1:]

    beam: list[tuple[tuple[Any, ...], list[list[dict[str, Any]]], list[float], tuple[int, ...], Point | None]] = [
        (
            _group_sequence_beam_key([seed_group], []),
            [seed_group],
            [],
            tuple(range(len(remaining_groups))),
            _group_end(seed_group),
        )
    ]

    while beam and len(beam[0][1]) < len(normalized_groups):
        next_beam: list[tuple[tuple[Any, ...], list[list[dict[str, Any]]], list[float], tuple[int, ...], Point | None]] = []
        for _, sequence, jumps, remaining_indices, previous_end in beam:
            for group_index in remaining_indices:
                base_group = remaining_groups[group_index]
                forward = [_copy_segment(segment) for segment in base_group]
                reverse = _reversed_group(base_group)
                candidates = [forward]
                if _group_signature(reverse) != _group_signature(forward):
                    candidates.append(reverse)
                for group in candidates:
                    start = _group_start(group)
                    next_jumps = list(jumps)
                    if previous_end is not None and start is not None:
                        next_jumps.append(_distance(previous_end, start))
                    next_previous_end = _group_end(group)
                    next_sequence = [*sequence, group]
                    next_remaining = tuple(index for index in remaining_indices if index != group_index)
                    next_beam.append(
                        (
                            _group_sequence_beam_key(next_sequence, next_jumps),
                            next_sequence,
                            next_jumps,
                            next_remaining,
                            next_previous_end,
                        )
                    )
        if not next_beam:
            return None
        next_beam.sort(key=lambda item: item[0])
        beam = next_beam[:BEAM_WIDTH]

    if not beam:
        return None
    return beam[0][1]


def _component_sort_key(component_id: Any) -> tuple[int, Any]:
    if component_id is None:
        return (0, "")
    return (1, component_id)


def _is_closed_segment(segment: dict[str, Any]) -> bool:
    if bool(segment.get("is_loop", False)):
        return True
    points = list(segment.get("points", ()))
    if len(points) < 2:
        return False
    return _distance(points[0], points[-1]) <= CLOSED_POINT_EPSILON


def _top_left_start(points: Sequence[Point]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    y, x = min(points, key=lambda point: (float(point[0]), float(point[1])))
    return (float(y), float(x))


def _merge_group(
    segments: Sequence[dict[str, Any]],
    *,
    endpoint_merge_distance: float,
    direction_cos_threshold: float,
) -> list[dict[str, Any]]:
    pending = list(segments)
    changed = True
    while changed:
        changed = False
        used: set[int] = set()
        next_pending: list[dict[str, Any]] = []
        for i, current in enumerate(pending):
            if i in used:
                continue
            match = _best_merge_match(
                current,
                pending,
                i,
                used,
                endpoint_merge_distance=endpoint_merge_distance,
                direction_cos_threshold=direction_cos_threshold,
            )
            if match is None:
                next_pending.append(current)
                used.add(i)
                continue
            j, current_points, candidate_points = match
            next_pending.append(_merged_segment(current, pending[j], current_points, candidate_points))
            used.add(i)
            used.add(j)
            changed = True
        pending = next_pending
    return pending


def _best_merge_match(
    current: dict[str, Any],
    pending: Sequence[dict[str, Any]],
    current_index: int,
    used: set[int],
    *,
    endpoint_merge_distance: float,
    direction_cos_threshold: float,
) -> tuple[int, list[Point], list[Point]] | None:
    if current.get("is_loop"):
        return None

    best: tuple[float, tuple[Any, ...], int, list[Point], list[Point]] | None = None
    for candidate_index, candidate in enumerate(pending):
        if candidate_index == current_index or candidate_index in used or candidate.get("is_loop"):
            continue
        oriented = _orient_for_merge(current["points"], candidate["points"])
        if oriented is None:
            continue
        current_points, candidate_points, distance = oriented
        if distance > endpoint_merge_distance:
            continue
        tail = _endpoint_direction(current_points, at_end=True)
        head = _endpoint_direction(candidate_points, at_end=False)
        if _dot(tail, head) < direction_cos_threshold:
            continue
        tie_key = tuple(candidate["source_segment_ids"])
        item = (distance, tie_key, candidate_index, current_points, candidate_points)
        if best is None or item < best:
            best = item

    if best is None:
        return None
    _, _, candidate_index, current_points, candidate_points = best
    return candidate_index, current_points, candidate_points


def _merged_segment(
    first: dict[str, Any],
    second: dict[str, Any],
    first_points: list[Point],
    second_points: list[Point],
) -> dict[str, Any]:
    merged = dict(first)
    merged["points"] = _connect_points(first_points, second_points)
    merged["source_segment_ids"] = tuple(first["source_segment_ids"]) + tuple(second["source_segment_ids"])
    merged["length_px"] = _polyline_length(merged["points"])
    if first.get("component_id") is not None:
        merged["component_id"] = first["component_id"]
    elif second.get("component_id") is not None:
        merged["component_id"] = second["component_id"]
    if "is_loop" in first or "is_loop" in second:
        merged["is_loop"] = bool(first.get("is_loop", False) or second.get("is_loop", False))
    return merged


def _connect_points(first_points: Sequence[Point], second_points: Sequence[Point]) -> list[Point]:
    points = list(first_points)
    if points and second_points and points[-1] == second_points[0]:
        points.extend(second_points[1:])
    else:
        points.extend(second_points)
    return points


def _refresh_geometry_metadata(segment: dict[str, Any]) -> None:
    points = list(segment.get("points", ()))
    segment["points"] = points
    segment["length_px"] = _polyline_length(points)
    segment["pixel_count"] = len(points)
    if points:
        segment["start"] = points[0]
        segment["end"] = points[-1]


def _copy_segment(segment: dict[str, Any]) -> dict[str, Any]:
    copied = dict(segment)
    copied["source_segment_ids"] = tuple(copied.get("source_segment_ids", ()))
    copied["points"] = list(copied.get("points", ()))
    _refresh_geometry_metadata(copied)
    return copied


def _orient_seed_segment(segment: dict[str, Any]) -> dict[str, Any]:
    points = list(segment.get("points", ()))
    if len(points) < 2:
        return _copy_segment(segment)
    if _point_sort_key(points[-1]) < _point_sort_key(points[0]):
        return _reversed_segment(segment)
    return _copy_segment(segment)


def _orient_segment_for_continuation(
    segment: dict[str, Any],
    previous_end: Point | None,
) -> dict[str, Any]:
    if previous_end is None:
        return _orient_seed_segment(segment)

    forward = _copy_segment(segment)
    reverse = _reversed_segment(segment)
    forward_points = forward.get("points", ())
    reverse_points = reverse.get("points", ())
    forward_distance = _distance(previous_end, forward_points[0]) if forward_points else float("inf")
    reverse_distance = _distance(previous_end, reverse_points[0]) if reverse_points else float("inf")
    if reverse_distance < forward_distance:
        return reverse
    if forward_distance < reverse_distance:
        return forward
    if _point_sort_key(reverse_points[0]) < _point_sort_key(forward_points[0]):
        return reverse
    return forward


def _orient_group_for_continuation(
    group: Sequence[dict[str, Any]],
    previous_end: Point | None,
) -> list[dict[str, Any]]:
    forward = [_copy_segment(segment) for segment in group]
    reverse = _reversed_group(group)
    if previous_end is None:
        return forward
    forward_start = _group_start(forward)
    reverse_start = _group_start(reverse)
    forward_distance = _distance(previous_end, forward_start) if forward_start is not None else float("inf")
    reverse_distance = _distance(previous_end, reverse_start) if reverse_start is not None else float("inf")
    if reverse_distance < forward_distance:
        return reverse
    if forward_distance < reverse_distance:
        return forward
    if reverse_start is not None and forward_start is not None and _point_sort_key(reverse_start) < _point_sort_key(forward_start):
        return reverse
    return forward


def _reversed_segment(segment: dict[str, Any]) -> dict[str, Any]:
    reversed_segment = dict(segment)
    reversed_segment["source_segment_ids"] = tuple(reversed_segment.get("source_segment_ids", ()))
    reversed_segment["points"] = list(reversed(segment.get("points", ())))
    _refresh_geometry_metadata(reversed_segment)
    return reversed_segment


def _reversed_group(group: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_reversed_segment(segment) for segment in reversed(group)]


def _split_segment_around_anchor(
    segment: dict[str, Any],
    anchor: Point,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    oriented = _orient_seed_segment(segment)
    points = list(oriented.get("points", ()))
    if len(points) < 3:
        return None

    split_index = None
    for index in range(1, len(points) - 1):
        if _distance(points[index], anchor) <= CLOSED_POINT_EPSILON:
            split_index = index
            break
    if split_index is None:
        return None

    head_points = points[: split_index + 1]
    tail_points = points[split_index:]
    if len(head_points) < 2 or len(tail_points) < 2:
        return None

    head = dict(oriented)
    head["points"] = head_points
    _refresh_geometry_metadata(head)

    tail = dict(oriented)
    tail["points"] = tail_points
    _refresh_geometry_metadata(tail)
    return head, tail


def _group_start(group: Sequence[dict[str, Any]]) -> Point | None:
    for segment in group:
        points = segment.get("points", ())
        if points:
            return points[0]
    return None


def _group_end(group: Sequence[dict[str, Any]]) -> Point | None:
    for segment in reversed(group):
        points = segment.get("points", ())
        if points:
            return points[-1]
    return None


def _orient_for_merge(
    first: Sequence[Point],
    second: Sequence[Point],
) -> tuple[list[Point], list[Point], float] | None:
    if len(first) < 2 or len(second) < 2:
        return None

    first_forward = list(first)
    first_reversed = list(reversed(first_forward))
    second_forward = list(second)
    second_reversed = list(reversed(second_forward))
    candidates = [
        (first_forward, second_forward),
        (first_forward, second_reversed),
        (first_reversed, second_forward),
        (first_reversed, second_reversed),
    ]
    return min(
        (
            (a, b, _distance(a[-1], b[0]))
            for a, b in candidates
        ),
        key=lambda item: item[2],
    )


def _endpoint_direction(points: Sequence[Point], *, at_end: bool) -> Point:
    if len(points) < 2:
        return (0.0, 0.0)
    if at_end:
        end = points[-1]
        start = points[max(0, len(points) - 1 - ENDPOINT_DIRECTION_SAMPLE_STEPS)]
    else:
        start = points[0]
        end = points[min(len(points) - 1, ENDPOINT_DIRECTION_SAMPLE_STEPS)]
    dy = float(end[0] - start[0])
    dx = float(end[1] - start[1])
    norm = math.hypot(dy, dx)
    if norm <= 1e-12:
        return (0.0, 0.0)
    return (dy / norm, dx / norm)


def _as_point(point: Iterable[Any]) -> Point:
    y, x = point
    return (float(y), float(x))


def _polyline_length(points: Sequence[Point]) -> float:
    return sum(_distance(start, end) for start, end in zip(points[:-1], points[1:]))


def _distance(first: Point, second: Point) -> float:
    return math.hypot(float(first[0] - second[0]), float(first[1] - second[1]))


def _dot(first: Point, second: Point) -> float:
    return float(first[0] * second[0] + first[1] * second[1])


def _point_sort_key(point: Point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _sequence_beam_key(
    sequence: Sequence[dict[str, Any]],
    jumps: Sequence[float],
) -> tuple[Any, ...]:
    source_ids = tuple(segment.get("source_segment_ids", ()) for segment in sequence)
    starts = tuple(
        segment.get("points", [(float("inf"), float("inf"))])[0]
        if segment.get("points")
        else (float("inf"), float("inf"))
        for segment in sequence
    )
    return (
        max(jumps) if jumps else 0.0,
        sum(jumps),
        source_ids,
        starts,
    )


def _group_sequence_beam_key(
    groups: Sequence[Sequence[dict[str, Any]]],
    jumps: Sequence[float],
) -> tuple[Any, ...]:
    sequence_ids = tuple(
        tuple(segment.get("source_segment_ids", ()) for segment in group)
        for group in groups
    )
    group_starts = tuple(_group_start(group) or (float("inf"), float("inf")) for group in groups)
    return (
        max(jumps) if jumps else 0.0,
        sum(jumps),
        sequence_ids,
        group_starts,
    )


def _group_signature(group: Sequence[dict[str, Any]]) -> tuple[Any, ...]:
    return tuple(
        (
            tuple(segment.get("source_segment_ids", ())),
            tuple(segment.get("points", ())),
        )
        for segment in group
    )
