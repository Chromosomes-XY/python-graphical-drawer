"""Declarative sketch entities, constraints, and dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Segment:
    name: str
    start: str
    end: str
    construction: bool = False


@dataclass(frozen=True)
class Constraint:
    kind: str
    entities: tuple[str, ...]
    value: float | tuple[float, float] | None = None


@dataclass(frozen=True)
class AngleDimension:
    first: str
    second: str
    label: str
    vertex: str | None = None
    reflex: bool = False


class Sketch:
    """A 2D sketch described by topology, relations, and dimensions.

    Point coordinates are solver output. Optional initial values are only
    numerical hints and never control final SVG placement.
    """

    def __init__(self):
        self.point_names: list[str] = []
        self.initial_hints: dict[str, tuple[float, float]] = {}
        self.segments: dict[str, Segment] = {}
        self.constraints: list[Constraint] = []
        self.angle_dimensions: list[AngleDimension] = []
        self.relation_mark_groups: dict[str, list[tuple[str, ...]]] = {
            "equal": [],
            "parallel": [],
        }

    def point(self, name: str, *, initial: tuple[float, float] | None = None):
        if name in self.point_names:
            raise ValueError(f"Point {name!r} already exists.")
        self.point_names.append(name)
        if initial is not None:
            self.initial_hints[name] = (float(initial[0]), float(initial[1]))
        return self

    def points(self, *names: str):
        for name in names:
            self.point(name)
        return self

    def segment(self, name: str, start: str, end: str, *, construction: bool = False):
        self._require_points(start, end)
        if name in self.segments:
            raise ValueError(f"Segment {name!r} already exists.")
        if start == end:
            raise ValueError("A segment requires two different points.")
        self.segments[name] = Segment(name, start, end, construction=construction)
        return self

    def horizontal(self, segment: str):
        return self._add("horizontal", segment)

    def vertical(self, segment: str):
        return self._add("vertical", segment)

    def collinear(self, *segments: str):
        self._require_segments(*segments)
        for second in segments[1:]:
            self.constraints.append(Constraint("collinear", (segments[0], second)))
        return self

    def coincident(self, first_point: str, second_point: str):
        self._require_points(first_point, second_point)
        self.constraints.append(Constraint("coincident", (first_point, second_point)))
        return self

    merge_points = coincident

    def midpoint(self, point: str, segment: str):
        self._require_points(point)
        self._require_segments(segment)
        self.constraints.append(Constraint("midpoint", (point, segment)))
        return self

    def intersection(self, point: str, first: str, second: str):
        self._require_points(point)
        self._require_segments(first, second)
        self.constraints.append(Constraint("intersection", (point, first, second)))
        return self

    def point_on_line(self, point: str, segment: str):
        self._require_points(point)
        self._require_segments(segment)
        self.constraints.append(Constraint("point_on_line", (point, segment)))
        return self

    def parallel(self, *segments: str):
        self._require_segments(*segments)
        for second in segments[1:]:
            self.constraints.append(Constraint("parallel", (segments[0], second)))
        return self

    def perpendicular(self, first: str, second: str):
        self._require_segments(first, second)
        self.constraints.append(Constraint("perpendicular", (first, second)))
        return self

    def equal(self, *segments: str):
        self._require_segments(*segments)
        for second in segments[1:]:
            self.constraints.append(Constraint("equal", (segments[0], second)))
        return self

    def mark_equal(self, *segments: str):
        """Display one equal-length mark group without adding solver equations."""
        self._require_segments(*segments)
        if len(segments) < 2:
            raise ValueError("An equal-length mark group needs at least two segments.")
        self.relation_mark_groups["equal"].append(tuple(segments))
        return self

    def mark_parallel(self, *segments: str):
        """Display one parallel mark group without adding solver equations."""
        self._require_segments(*segments)
        if len(segments) < 2:
            raise ValueError("A parallel mark group needs at least two segments.")
        self.relation_mark_groups["parallel"].append(tuple(segments))
        return self

    def symmetric(self, first_point: str, second_point: str, about: str):
        self._require_points(first_point, second_point)
        self._require_segments(about)
        self.constraints.append(
            Constraint("symmetric", (first_point, second_point, about))
        )
        return self

    def fix(self, point: str, location: tuple[float, float]):
        self._require_points(point)
        self.constraints.append(
            Constraint("fix", (point,), (float(location[0]), float(location[1])))
        )
        return self

    def length(self, segment: str, value: float):
        self._require_segments(segment)
        if value <= 0:
            raise ValueError("A length dimension must be positive.")
        self.constraints.append(Constraint("length", (segment,), float(value)))
        return self

    def angle(
        self,
        first: str,
        second: str,
        value: float,
        *,
        vertex: str | None = None,
    ):
        """Add a driving angle dimension between two segments.

        The relation constrains the smaller angle between the selected rays.
        A named vertex removes ambiguity when the segments intersect away from
        their endpoints.
        """
        self._require_segments(first, second)
        if vertex is not None:
            self._require_points(vertex)
        if not 0 < value <= 180:
            raise ValueError("A driving angle must be greater than 0 and at most 180 degrees.")
        self.constraints.append(
            Constraint("angle", (first, second, vertex or ""), float(value))
        )
        return self

    def orientation(
        self,
        point: str,
        *,
        above: str | None = None,
        below: str | None = None,
        left_of: str | None = None,
        right_of: str | None = None,
    ):
        choices = {
            "above": above,
            "below": below,
            "left_of": left_of,
            "right_of": right_of,
        }
        selected = [(kind, segment) for kind, segment in choices.items() if segment]
        if len(selected) != 1:
            raise ValueError("Specify exactly one orientation branch.")
        kind, segment = selected[0]
        self._require_points(point)
        self._require_segments(segment)
        self.constraints.append(Constraint(kind, (point, segment)))
        return self

    def dimension_angle(
        self,
        first: str,
        second: str,
        label: str,
        *,
        vertex: str | None = None,
        reflex: bool = False,
    ):
        self._require_segments(first, second)
        if vertex is not None:
            self._require_points(vertex)
        self.angle_dimensions.append(
            AngleDimension(first, second, label, vertex=vertex, reflex=reflex)
        )
        return self

    def solve(self, **options):
        from .solver import solve_sketch

        return solve_sketch(self, **options)

    def render_svg(
        self,
        path: str | Path,
        *,
        width: int = 900,
        height: int = 700,
        title: str = "Constraint CAD sketch",
        solution=None,
        show_point_labels: bool = True,
        show_relation_marks: bool = True,
    ):
        from .svg import render_svg

        solution = solution or self.solve()
        svg = render_svg(
            self,
            solution,
            width=width,
            height=height,
            title=title,
            show_point_labels=show_point_labels,
            show_relation_marks=show_relation_marks,
        )
        Path(path).write_text(svg)
        return svg

    def _add(self, kind: str, segment: str):
        self._require_segments(segment)
        self.constraints.append(Constraint(kind, (segment,)))
        return self

    def _require_points(self, *names: str):
        missing = [name for name in names if name not in self.point_names]
        if missing:
            raise KeyError(f"Unknown point(s): {', '.join(missing)}")

    def _require_segments(self, *names: str):
        missing = [name for name in names if name not in self.segments]
        if missing:
            raise KeyError(f"Unknown segment(s): {', '.join(missing)}")
