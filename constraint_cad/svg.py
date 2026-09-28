"""Automatic view fitting and sanitizer-safe SVG rendering."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from math import atan2, cos, degrees, hypot, pi, sin

from .model import AngleDimension, Segment, Sketch
from .solver import SolveResult


Point = tuple[float, float]


def _distance(first: Point, second: Point) -> float:
    return hypot(first[0] - second[0], first[1] - second[1])


def _intersection(a: Point, b: Point, c: Point, d: Point) -> Point:
    denominator = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if abs(denominator) < 1e-10:
        raise ValueError("Cannot intersect parallel lines.")
    determinant_1 = a[0] * b[1] - a[1] * b[0]
    determinant_2 = c[0] * d[1] - c[1] * d[0]
    return (
        (determinant_1 * (c[0] - d[0]) - (a[0] - b[0]) * determinant_2) / denominator,
        (determinant_1 * (c[1] - d[1]) - (a[1] - b[1]) * determinant_2) / denominator,
    )


class _View:
    def __init__(self, points: dict[str, Point], width: int, height: int, padding: int = 90):
        xs = [point[0] for point in points.values()]
        ys = [point[1] for point in points.values()]
        minimum_x, maximum_x = min(xs), max(xs)
        minimum_y, maximum_y = min(ys), max(ys)
        span_x = max(maximum_x - minimum_x, 1e-6)
        span_y = max(maximum_y - minimum_y, 1e-6)
        self.scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)
        content_width, content_height = span_x * self.scale, span_y * self.scale
        self.left = (width - content_width) / 2
        self.bottom = (height - content_height) / 2
        self.minimum_x = minimum_x
        self.minimum_y = minimum_y
        self.height = height

    def point(self, model: Point) -> Point:
        x = self.left + (model[0] - self.minimum_x) * self.scale
        y_from_bottom = self.bottom + (model[1] - self.minimum_y) * self.scale
        return x, self.height - y_from_bottom


def _unit(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(hypot(dx, dy), 1e-9)
    return dx / length, dy / length


def _polygon(points: list[Point], *, fill: str = "#2563eb") -> str:
    data = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{data}" fill="{fill}" stroke="none"/>'


def _arrowhead(tip: Point, inward_direction: float, length: float = 9, width: float = 8) -> str:
    theta = inward_direction * pi / 180
    base = (tip[0] + length * cos(theta), tip[1] + length * sin(theta))
    normal = (-sin(theta), cos(theta))
    return _polygon(
        [
            tip,
            (base[0] + normal[0] * width / 2, base[1] + normal[1] * width / 2),
            (base[0] - normal[0] * width / 2, base[1] - normal[1] * width / 2),
        ]
    )


def _constraint_components(sketch: Sketch, kind: str) -> list[set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for constraint in sketch.constraints:
        if constraint.kind != kind:
            continue
        first, second = constraint.entities[:2]
        graph[first].add(second)
        graph[second].add(first)
    components: list[set[str]] = []
    unseen = set(graph)
    while unseen:
        root = unseen.pop()
        component, stack = {root}, [root]
        while stack:
            current = stack.pop()
            for neighbour in graph[current]:
                if neighbour not in component:
                    component.add(neighbour)
                    unseen.discard(neighbour)
                    stack.append(neighbour)
        components.append(component)
    marked = [set(group) for group in sketch.relation_mark_groups.get(kind, [])]
    return components + marked


def _relation_ticks(start: Point, end: Point, count: int) -> str:
    ux, uy = _unit(start, end)
    nx, ny = -uy, ux
    offsets = [0] if count == 1 else [7 * (index - (count - 1) / 2) for index in range(count)]
    parts = []
    for offset in offsets:
        cx = (start[0] + end[0]) / 2 + ux * offset
        cy = (start[1] + end[1]) / 2 + uy * offset
        parts.append(
            f'<line x1="{cx - nx * 9:.2f}" y1="{cy - ny * 9:.2f}" '
            f'x2="{cx + nx * 9:.2f}" y2="{cy + ny * 9:.2f}" '
            'stroke="#2563eb" stroke-width="4" stroke-linecap="round"/>'
        )
    return "".join(parts)


def _parallel_mark(start: Point, end: Point, count: int) -> str:
    ux, uy = _unit(start, end)
    nx, ny = -uy, ux
    parts = []
    for offset in ([0] if count == 1 else [-7, 7]):
        cx = (start[0] + end[0]) / 2 + ux * offset
        cy = (start[1] + end[1]) / 2 + uy * offset
        points = [
            (cx - ux * 9 + nx * 8, cy - uy * 9 + ny * 8),
            (cx, cy),
            (cx - ux * 9 - nx * 8, cy - uy * 9 - ny * 8),
        ]
        data = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(
            f'<polyline points="{data}" fill="none" stroke="#2563eb" '
            'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return "".join(parts)


def _right_marker(first: tuple[Point, Point], second: tuple[Point, Point]) -> str:
    vertex = _intersection(first[0], first[1], second[0], second[1])

    def target(line):
        return max(line, key=lambda point: _distance(point, vertex))

    first_unit = _unit(vertex, target(first))
    second_unit = _unit(vertex, target(second))
    size = 19
    p1 = (vertex[0] + first_unit[0] * size, vertex[1] + first_unit[1] * size)
    p3 = (vertex[0] + second_unit[0] * size, vertex[1] + second_unit[1] * size)
    p2 = (p1[0] + p3[0] - vertex[0], p1[1] + p3[1] - vertex[1])
    data = " ".join(f"{x:.2f},{y:.2f}" for x, y in (p1, p2, p3))
    return (
        f'<polyline points="{data}" fill="none" stroke="#2563eb" '
        'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _dimension_geometry(
    dimension: AngleDimension,
    sketch: Sketch,
    points: dict[str, Point],
    level: int,
) -> str:
    first_segment = sketch.segments[dimension.first]
    second_segment = sketch.segments[dimension.second]
    first = (points[first_segment.start], points[first_segment.end])
    second = (points[second_segment.start], points[second_segment.end])

    if dimension.vertex:
        vertex = points[dimension.vertex]
    else:
        shared = set((first_segment.start, first_segment.end)).intersection(
            (second_segment.start, second_segment.end)
        )
        vertex = points[next(iter(shared))] if shared else _intersection(*first, *second)

    def outward_target(line):
        if _distance(line[0], vertex) < 1e-5:
            return line[1]
        if _distance(line[1], vertex) < 1e-5:
            return line[0]
        return max(line, key=lambda point: _distance(point, vertex))

    first_target, second_target = outward_target(first), outward_target(second)
    start = degrees(atan2(first_target[1] - vertex[1], first_target[0] - vertex[0])) % 360
    end = degrees(atan2(second_target[1] - vertex[1], second_target[0] - vertex[0])) % 360
    clockwise_sweep = (end - start) % 360
    use_clockwise = clockwise_sweep <= 180
    if dimension.reflex:
        use_clockwise = not use_clockwise
    signed_sweep = clockwise_sweep if use_clockwise else -((start - end) % 360)
    sweep = abs(signed_sweep)
    sweep_flag = 1 if signed_sweep >= 0 else 0
    available = min(_distance(vertex, first_target), _distance(vertex, second_target))
    radius = min(available * 0.58, max(28, available * 0.20) + level * 20)

    def radial(direction):
        theta = direction * pi / 180
        return vertex[0] + radius * cos(theta), vertex[1] + radius * sin(theta)

    arc_start, arc_end = radial(start), radial(start + signed_sweep)
    large = 1 if sweep > 180 else 0
    tangent_offset = 90 if signed_sweep >= 0 else -90
    start_tangent = start + tangent_offset
    end_tangent = start + signed_sweep + tangent_offset
    middle = start + signed_sweep / 2
    label_radius = radius + (32 if sweep > 180 else 17)
    label = (
        vertex[0] + label_radius * cos(middle * pi / 180),
        vertex[1] + label_radius * sin(middle * pi / 180),
    )
    unknown = any(character.isalpha() for character in dimension.label)
    text_fill = "#b91c1c" if unknown else "#172033"
    text_family = "Georgia, serif" if unknown else "Arial, sans-serif"
    text_style = ' font-style="italic"' if unknown else ""
    return (
        f'<path d="M{arc_start[0]:.2f},{arc_start[1]:.2f} '
        f'A{radius:.2f},{radius:.2f} 0 {large} {sweep_flag} {arc_end[0]:.2f},{arc_end[1]:.2f}" '
        'fill="none" stroke="#2563eb" stroke-width="3.5" stroke-linecap="round"/>'
        + _arrowhead(arc_start, start_tangent)
        + _arrowhead(arc_end, end_tangent + 180)
        + f'<text x="{label[0]:.2f}" y="{label[1]:.2f}" fill="{text_fill}" '
        f'font-family="{text_family}" font-size="25" font-weight="700"{text_style} '
        f'text-anchor="middle" dominant-baseline="middle">{escape(dimension.label)}</text>'
    )


def render_svg(
    sketch: Sketch,
    solution: SolveResult,
    *,
    width: int,
    height: int,
    title: str,
    show_point_labels: bool = True,
    show_relation_marks: bool = True,
) -> str:
    view = _View(solution.points, width, height)
    points = {name: view.point(point) for name, point in solution.points.items()}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title>',
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    for segment in sketch.segments.values():
        if segment.construction:
            continue
        start, end = points[segment.start], points[segment.end]
        parts.append(
            f'<line id="{escape(segment.name)}" x1="{start[0]:.2f}" y1="{start[1]:.2f}" '
            f'x2="{end[0]:.2f}" y2="{end[1]:.2f}" stroke="#172033" '
            'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    if show_relation_marks:
        for group_index, component in enumerate(_constraint_components(sketch, "equal"), start=1):
            count = min(group_index, 3)
            for name in component:
                segment = sketch.segments[name]
                if segment.construction:
                    continue
                parts.append(_relation_ticks(points[segment.start], points[segment.end], count))

        for group_index, component in enumerate(_constraint_components(sketch, "parallel"), start=1):
            count = min(group_index, 2)
            for name in component:
                segment = sketch.segments[name]
                if segment.construction:
                    continue
                parts.append(_parallel_mark(points[segment.start], points[segment.end], count))

        for constraint in sketch.constraints:
            if constraint.kind != "perpendicular":
                continue
            first = sketch.segments[constraint.entities[0]]
            second = sketch.segments[constraint.entities[1]]
            try:
                parts.append(
                    _right_marker(
                        (points[first.start], points[first.end]),
                        (points[second.start], points[second.end]),
                    )
                )
            except ValueError:
                pass

    levels: dict[tuple[float, float], int] = defaultdict(int)
    for dimension in sketch.angle_dimensions:
        first = sketch.segments[dimension.first]
        second = sketch.segments[dimension.second]
        if dimension.vertex:
            vertex = points[dimension.vertex]
        else:
            shared = set((first.start, first.end)).intersection((second.start, second.end))
            vertex = points[next(iter(shared))] if shared else (0.0, 0.0)
        key = (round(vertex[0], 3), round(vertex[1], 3))
        parts.append(_dimension_geometry(dimension, sketch, points, levels[key]))
        levels[key] += 1

    if show_point_labels:
        centroid = (
            sum(point[0] for point in points.values()) / len(points),
            sum(point[1] for point in points.values()) / len(points),
        )
        for name, point in points.items():
            ux, uy = _unit(centroid, point)
            if _distance(centroid, point) < 1e-6:
                ux, uy = 0, 1
            label = (point[0] + ux * 30, point[1] + uy * 30)
            parts.append(
                f'<text x="{label[0]:.2f}" y="{label[1]:.2f}" fill="#172033" '
                'font-family="Arial, sans-serif" font-size="25" text-anchor="middle" '
                f'dominant-baseline="middle">{escape(name)}</text>'
            )

    parts.append("</svg>")
    return "".join(parts)
