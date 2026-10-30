"""Deterministic, crossing-aware layout search for native Word relationship diagrams.

Only node placement is optimized. Node identity, relationships, DrawingML
shapes/connector attachment, diagram semantics and canvas size are unchanged.
A metric-based safeguard retains the historical layout when it scores better.
"""

from __future__ import annotations

import hashlib
import math
import random
import typing
from collections import Counter

MAX_VISIBLE = 20


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def cross(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab1, ab2 = cross(a, b, c), cross(a, b, d)
    cd1, cd2 = cross(c, d, a), cross(c, d, b)
    return ab1 * ab2 < -1e-7 and cd1 * cd2 < -1e-7


def _ports(
    a: tuple[float, float],
    b: tuple[float, float],
    aw: float,
    ah: float,
    bw: float,
    bh: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    def endpoint(x: float, y: float, w: float, h: float, target: tuple[float, float]) -> tuple[float, float]:
        dx, dy = target[0] - x, target[1] - y
        if not (dx or dy):
            return x, y
        t = min(w / 2 / abs(dx) if dx else math.inf, h / 2 / abs(dy) if dy else math.inf)
        return x + dx * t, y + dy * t

    return endpoint(*a, aw, ah, b), endpoint(*b, bw, bh, a)


def _segment_hits_box(
    a: tuple[float, float],
    b: tuple[float, float],
    box: tuple[float, float],
    w: float,
    h: float,
) -> bool:
    # Liang–Barsky against an inset rectangle; touching an outline does not
    # count as a connector visibly passing through a different table.
    xmin, xmax = box[0] - w * 0.44, box[0] + w * 0.44
    ymin, ymax = box[1] - h * 0.42, box[1] + h * 0.42
    dx, dy = b[0] - a[0], b[1] - a[1]
    u0, u1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - xmin), (dx, xmax - a[0]), (-dy, a[1] - ymin), (dy, ymax - a[1])):
        if abs(p) < 1e-9:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                u0 = max(u0, t)
            else:
                u1 = min(u1, t)
            if u0 > u1:
                return False
    return True


def layout_metrics(
    points: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    anchor: str,
    roles: dict[str, str],
) -> dict[str, float]:
    """Geometry independent of Word rendering, useful for baseline comparisons."""
    widths = {n: 1.62 if n == anchor else 1.16 for n in points}
    heights = {n: 0.56 if n == anchor else 0.45 for n in points}
    nodes = sorted(points)
    node_overlaps = 0
    out_of_bounds = 0
    for i, a in enumerate(nodes):
        x, y = points[a]
        if (x - widths[a] / 2 < 0.45 or x + widths[a] / 2 > 9.72
                or y - heights[a] / 2 < 0.52 or y + heights[a] / 2 > 5.08):
            out_of_bounds += 1
        for b in nodes[i + 1 :]:
            xx, yy = points[b]
            if (abs(x - xx) < (widths[a] + widths[b]) / 2 + 0.09
                    and abs(y - yy) < (heights[a] + heights[b]) / 2 + 0.06):
                node_overlaps += 1

    # Only unique endpoint pairs. Multiple relationships between the same
    # tables share the same geometric segment but retain their source meaning.
    segments: list[tuple[str, str, tuple[float, float], tuple[float, float]]] = []
    seen: set[tuple[str, str]] = set()
    length = 0.0
    box_hits = 0
    for a, b in edges:
        if a not in points or b not in points or a == b:
            continue
        key = (a, b) if a < b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        start, end = _ports(points[a], points[b], widths[a], heights[a], widths[b], heights[b])
        segments.append((a, b, start, end))
        length += math.dist(start, end)
        for n in nodes:
            if n != a and n != b and _segment_hits_box(start, end, points[n], widths[n], heights[n]):
                box_hits += 1
    crossings = 0
    for i, (a, b, start, end) in enumerate(segments):
        for c, d, start2, end2 in segments[i + 1 :]:
            if {a, b}.isdisjoint({c, d}) and _segments_intersect(start, end, start2, end2):
                crossings += 1

    # Role-aware positions avoid grouping every node into a tight hairball.
    # We still allow cross-lane swaps when geometry benefits materially.
    misplaced = 0
    for n, (x, _y) in points.items():
        if n == anchor:
            continue
        dimension = roles[n] in ("dim", "date")
        side = x < 2.0 or x > 8.1
        if dimension != side:
            misplaced += 1

    return {
        "node_overlaps": float(node_overlaps),
        "connector_box_hits": float(box_hits),
        "connector_crossings": float(crossings),
        "out_of_bounds": float(out_of_bounds),
        "total_edge_length": round(length, 3),
        "role_mismatch": float(misplaced),
    }


def layout_cost(metrics: dict[str, float]) -> float:
    return round(
        120 * metrics["node_overlaps"]
        + 85 * metrics["connector_box_hits"]
        + 18 * metrics["connector_crossings"]
        + 150 * metrics["out_of_bounds"]
        + 0.75 * metrics["total_edge_length"]
        + 6 * metrics["role_mismatch"],
        4,
    )


def _slots(dim_count: int, other_count: int) -> list[tuple[float, float]]:
    """Build collision-free slots inside the fixed landscape Word canvas."""
    left = min(6, (dim_count + 1) // 2)
    right = min(6, dim_count - left)
    # Use unused outer slots for overflow fact/domain nodes and inner
    # top/bottom slots for overflow dimensions; never exceed 20 places.
    extra_dim = dim_count - left - right
    other_to_side = max(0, other_count - (8 - extra_dim))
    if other_to_side:
        for _ in range(other_to_side):
            if left <= right and left < 6:
                left += 1
            elif right < 6:
                right += 1
            else:
                raise ValueError("More than 20 visible tables")

    def vertical(n: int) -> list[float]:
        return [2.68] if n == 1 else [1.0 + (4.70 - 1.0) * i / (n - 1) for i in range(n)]

    slots: list[tuple[float, float]] = []
    slots += [(1.13, y) for y in vertical(left)]
    slots += [(9.05, y) for y in vertical(right)]
    remaining = dim_count + other_count - len(slots)
    top_n = min(4, (remaining + 1) // 2)
    bot_n = remaining - top_n

    def horizontal(n: int) -> list[float]:
        return [5.10] if n == 1 else [2.72 + (7.48 - 2.72) * i / (n - 1) for i in range(n)]

    slots += [(x, 0.88) for x in horizontal(top_n)]
    slots += [(x, 4.68) for x in horizontal(bot_n)]
    return slots


def optimize_layout(
    base: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    anchor: str,
    roles: dict[str, str],
) -> tuple[dict[str, tuple[float, float]], dict[str, typing.Any]]:
    """Best of baseline and deterministic crossing-aware local-search layouts."""
    nodes = sorted(n for n in base if n != anchor)
    if len(nodes) == 0 or len(nodes) > MAX_VISIBLE - 1:
        return dict(base), {"selected": "legacy", "reason": "node count outside search bound"}
    unique_edges = sorted({(a, b) if a < b else (b, a) for a, b in edges if a != b})
    baseline_metrics = layout_metrics(base, unique_edges, anchor, roles)
    baseline_cost = layout_cost(baseline_metrics)
    dim = [n for n in nodes if roles[n] in ("dim", "date")]
    other = [n for n in nodes if n not in dim]
    slots = _slots(len(dim), len(other))
    if len(slots) != len(nodes):
        raise ValueError("Unexpected schema layout slot count")

    best = dict(base)
    best_cost = baseline_cost
    best_metrics = baseline_metrics
    seed = int(hashlib.sha256(("|".join(nodes) + repr(unique_edges)).encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)

    # Twelve deterministic restarts, with graph-degree seeding and alternate
    # rotations. Swaps cover both ordering and lane assignment; crossings
    # are computed against the actual connector-to-box endpoints.
    degree: Counter[str] = Counter()
    for a, b in unique_edges:
        degree[a] += 1
        degree[b] += 1
    ordered = sorted(dim, key=lambda n: (-degree[n], n)) + sorted(other, key=lambda n: (-degree[n], n))
    for restart in range(12):
        permutation = list(ordered)
        if restart:
            rng.shuffle(permutation)
        placement = dict(zip(permutation, slots, strict=True))
        placement[anchor] = base[anchor]
        score = layout_cost(layout_metrics(placement, unique_edges, anchor, roles))
        for _ in range(8):
            improvement = False
            # Best-improvement 2-opt on node-to-slot assignments.
            move: tuple[str, str] | None = None
            next_cost = score
            for i, a in enumerate(nodes):
                for b in nodes[i + 1 :]:
                    placement[a], placement[b] = placement[b], placement[a]
                    candidate = layout_cost(layout_metrics(placement, unique_edges, anchor, roles))
                    placement[a], placement[b] = placement[b], placement[a]
                    if candidate < next_cost - 1e-5:
                        move, next_cost = (a, b), candidate
            if move:
                a, b = move
                placement[a], placement[b] = placement[b], placement[a]
                score = next_cost
                improvement = True
            if not improvement:
                break
        if score < best_cost - 0.001:
            best_cost = score
            best = dict(placement)
            best_metrics = layout_metrics(best, unique_edges, anchor, roles)

    # Preserve already-good small layouts: tiny numerical improvements
    # do not justify moving every table in a familiar diagram.
    minimum_gain = max(2.0, baseline_cost * 0.03)
    if baseline_cost - best_cost < minimum_gain:
        best = dict(base)
        best_cost = baseline_cost
        best_metrics = baseline_metrics
    return best, {
        "selected": "optimized" if best_cost < baseline_cost - 0.001 else "legacy",
        "baseline_cost": baseline_cost,
        "selected_cost": best_cost,
        "baseline_metrics": baseline_metrics,
        "selected_metrics": best_metrics,
        "relative_improvement": round((baseline_cost - best_cost) / max(baseline_cost, 1e-9), 4),
    }
