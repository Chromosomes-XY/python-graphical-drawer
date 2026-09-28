"""Small declarative vector-drawing layer for educational illustrations."""

from __future__ import annotations

from html import escape
from math import atan2, cos, hypot, isfinite, pi, sin
from pathlib import Path
from typing import Callable, Iterable


Number = int | float
Point = tuple[Number, Number]


def _number(value: Number) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def _attributes(values: dict[str, object | None]) -> str:
    return " ".join(
        f'{name.replace("_", "-")}="{escape(str(value), quote=True)}"'
        for name, value in values.items()
        if value is not None
    )


class Drawing:
    """Declarative SVG drawing in logical coordinates.

    A drawing can also be reused as a glyph with :meth:`use`.  Glyph instances
    are expanded into ordinary SVG groups, avoiding external assets, embedded
    CSS, scripts, and ``<use>`` references that some learning-platform
    sanitizers remove.
    """

    def __init__(
        self,
        width: Number,
        height: Number,
        *,
        background: str | None = "#ffffff",
    ):
        if width <= 0 or height <= 0:
            raise ValueError("Drawing width and height must be positive.")
        self.width = float(width)
        self.height = float(height)
        self.background = background
        self._elements: list[str] = []

    def _shape(
        self,
        tag: str,
        geometry: dict[str, object],
        *,
        fill: str = "none",
        stroke: str = "none",
        stroke_width: Number = 0,
        opacity: Number | None = None,
        linecap: str | None = None,
        linejoin: str | None = None,
        dasharray: str | None = None,
        element_id: str | None = None,
    ):
        attributes = {
            "id": element_id,
            **geometry,
            "fill": fill,
            "stroke": stroke,
            "stroke_width": _number(stroke_width),
            "opacity": _number(opacity) if opacity is not None else None,
            "stroke_linecap": linecap,
            "stroke_linejoin": linejoin,
            "stroke_dasharray": dasharray,
        }
        self._elements.append(f"<{tag} {_attributes(attributes)}/>")
        return self

    def line(
        self,
        start: Point,
        end: Point,
        *,
        stroke: str = "#172033",
        stroke_width: Number = 3,
        linecap: str = "round",
        dasharray: str | None = None,
        element_id: str | None = None,
    ):
        return self._shape(
            "line",
            {"x1": _number(start[0]), "y1": _number(start[1]), "x2": _number(end[0]), "y2": _number(end[1])},
            stroke=stroke,
            stroke_width=stroke_width,
            linecap=linecap,
            dasharray=dasharray,
            element_id=element_id,
        )

    def arrow(
        self,
        start: Point,
        end: Point,
        *,
        stroke: str = "#172033",
        stroke_width: Number = 3,
        head_length: Number = 14,
        head_width: Number = 12,
        both: bool = False,
        element_id: str | None = None,
    ):
        """Draw a line with a filled arrowhead at one or both ends."""
        dx, dy = float(end[0] - start[0]), float(end[1] - start[1])
        length = hypot(dx, dy)
        if length <= 0:
            raise ValueError("An arrow requires two different points.")
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        def head(tip: Point, direction: int):
            base = (
                tip[0] - direction * ux * float(head_length),
                tip[1] - direction * uy * float(head_length),
            )
            return [
                tip,
                (base[0] + nx * float(head_width) / 2, base[1] + ny * float(head_width) / 2),
                (base[0] - nx * float(head_width) / 2, base[1] - ny * float(head_width) / 2),
            ]

        line_start = (
            start[0] + ux * float(head_length) * 0.7,
            start[1] + uy * float(head_length) * 0.7,
        ) if both else start
        line_end = (
            end[0] - ux * float(head_length) * 0.7,
            end[1] - uy * float(head_length) * 0.7,
        )
        self.line(line_start, line_end, stroke=stroke, stroke_width=stroke_width, element_id=element_id)
        self.polygon(head(end, 1), fill=stroke, stroke=stroke, stroke_width=1)
        if both:
            self.polygon(head(start, -1), fill=stroke, stroke=stroke, stroke_width=1)
        return self

    def rect(
        self,
        x: Number,
        y: Number,
        width: Number,
        height: Number,
        *,
        radius: Number = 0,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        element_id: str | None = None,
    ):
        return self._shape(
            "rect",
            {
                "x": _number(x), "y": _number(y), "width": _number(width), "height": _number(height),
                "rx": _number(radius) if radius else None, "ry": _number(radius) if radius else None,
            },
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            element_id=element_id,
        )

    def circle(
        self,
        center: Point,
        radius: Number,
        *,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        element_id: str | None = None,
    ):
        return self._shape(
            "circle",
            {"cx": _number(center[0]), "cy": _number(center[1]), "r": _number(radius)},
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            element_id=element_id,
        )

    def ellipse(
        self,
        center: Point,
        radius_x: Number,
        radius_y: Number,
        *,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        element_id: str | None = None,
    ):
        return self._shape(
            "ellipse",
            {
                "cx": _number(center[0]), "cy": _number(center[1]),
                "rx": _number(radius_x), "ry": _number(radius_y),
            },
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            element_id=element_id,
        )

    def polygon(
        self,
        points: Iterable[Point],
        *,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        linejoin: str = "round",
        element_id: str | None = None,
    ):
        data = " ".join(f"{_number(x)},{_number(y)}" for x, y in points)
        return self._shape(
            "polygon", {"points": data}, fill=fill, stroke=stroke,
            stroke_width=stroke_width, opacity=opacity, linejoin=linejoin,
            element_id=element_id,
        )

    def polyline(
        self,
        points: Iterable[Point],
        *,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        linecap: str = "round",
        linejoin: str = "round",
        dasharray: str | None = None,
        element_id: str | None = None,
    ):
        data = " ".join(f"{_number(x)},{_number(y)}" for x, y in points)
        return self._shape(
            "polyline", {"points": data}, fill=fill, stroke=stroke,
            stroke_width=stroke_width, opacity=opacity, linecap=linecap,
            linejoin=linejoin, dasharray=dasharray, element_id=element_id,
        )

    def plot(
        self,
        func: Callable[[float], float],
        var: str,
        domain: tuple[Number, Number],
        ran: tuple[Number, Number],
        *,
        project: Callable[[float, float], Point] | None = None,
        samples: int = 240,
        stroke: str = "#2563eb",
        stroke_width: Number = 3,
        linecap: str = "round",
        linejoin: str = "round",
        element_id: str | None = None,
    ):
        """Plot ``func(var)`` clipped to a mathematical coordinate window.

        ``domain`` and ``ran`` are the visible x and y intervals, respectively.
        ``project`` converts model coordinates to SVG coordinates; omitting it
        draws directly in SVG coordinates.  Segments are clipped before
        projection, which keeps a graph within its axes even when the function
        crosses a range boundary between sample points.
        """
        if not callable(func):
            raise TypeError("func must be callable.")
        if not isinstance(var, str) or not var:
            raise ValueError("var must be a non-empty variable name.")
        if samples < 2:
            raise ValueError("samples must be at least 2.")
        xmin, xmax = map(float, domain)
        ymin, ymax = map(float, ran)
        if not xmin < xmax or not ymin < ymax:
            raise ValueError("domain and ran must each have increasing bounds.")
        mapper = project or (lambda x, y: (x, y))

        def clipped_segment(first: Point, second: Point) -> tuple[Point, Point] | None:
            """Clip a data-coordinate segment to the plot rectangle."""
            x0, y0 = first
            dx, dy = second[0] - x0, second[1] - y0
            low, high = 0.0, 1.0
            for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
                if abs(p) < 1e-12:
                    if q < 0:
                        return None
                    continue
                t = q / p
                if p < 0:
                    if t > high:
                        return None
                    low = max(low, t)
                else:
                    if t < low:
                        return None
                    high = min(high, t)
            return ((x0 + low * dx, y0 + low * dy), (x0 + high * dx, y0 + high * dy))

        previous: Point | None = None
        paths: list[list[Point]] = []
        for index in range(samples):
            x = xmin + (xmax - xmin) * index / (samples - 1)
            try:
                y = float(func(x))
            except (ArithmeticError, ValueError, TypeError):
                previous = None
                continue
            current = (x, y)
            if not isfinite(y):
                previous = None
                continue
            if previous is not None and abs(y - previous[1]) <= 2 * (ymax - ymin):
                clipped = clipped_segment(previous, current)
                if clipped is not None:
                    start, end = mapper(*clipped[0]), mapper(*clipped[1])
                    # Join adjacent samples into a compact SVG polyline, but
                    # retain a separate path after a gap or a sharp jump.
                    if paths and hypot(paths[-1][-1][0] - start[0], paths[-1][-1][1] - start[1]) < 1e-8:
                        paths[-1].append(end)
                    else:
                        paths.append([start, end])
            previous = current

        for index, path in enumerate(paths):
            self.polyline(
                path, stroke=stroke, stroke_width=stroke_width,
                linecap=linecap, linejoin=linejoin,
                element_id=element_id if len(paths) == 1 else (f"{element_id}-{index}" if element_id else None),
            )
        return self

    def path(
        self,
        data: str,
        *,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        opacity: Number | None = None,
        linecap: str = "round",
        linejoin: str = "round",
        dasharray: str | None = None,
        element_id: str | None = None,
    ):
        return self._shape(
            "path", {"d": data}, fill=fill, stroke=stroke,
            stroke_width=stroke_width, opacity=opacity, linecap=linecap,
            linejoin=linejoin, dasharray=dasharray, element_id=element_id,
        )

    def text(
        self,
        position: Point,
        value: str,
        *,
        fill: str = "#172033",
        font_size: Number = 18,
        font_weight: int | str = 600,
        anchor: str = "middle",
        baseline: str = "middle",
        font_family: str = "Arial, sans-serif",
        element_id: str | None = None,
    ):
        attributes = {
            "id": element_id,
            "x": _number(position[0]), "y": _number(position[1]), "fill": fill,
            "font_family": font_family, "font_size": _number(font_size),
            "font_weight": font_weight, "text_anchor": anchor,
            "dominant_baseline": baseline,
        }
        self._elements.append(f"<text {_attributes(attributes)}>{escape(value)}</text>")
        return self

    def star(
        self,
        center: Point,
        outer_radius: Number,
        *,
        inner_radius: Number | None = None,
        points: int = 5,
        rotation: Number = -90,
        fill: str = "none",
        stroke: str = "#172033",
        stroke_width: Number = 3,
        element_id: str | None = None,
    ):
        if points < 3:
            raise ValueError("A star needs at least three points.")
        inner = float(inner_radius) if inner_radius is not None else float(outer_radius) * 0.46
        vertices = []
        for index in range(points * 2):
            radius = float(outer_radius) if index % 2 == 0 else inner
            angle = (float(rotation) + index * 180 / points) * pi / 180
            vertices.append((center[0] + radius * cos(angle), center[1] + radius * sin(angle)))
        return self.polygon(
            vertices, fill=fill, stroke=stroke, stroke_width=stroke_width,
            element_id=element_id,
        )

    def grid(
        self,
        x: Number,
        y: Number,
        columns: int,
        rows: int,
        cell_width: Number,
        cell_height: Number | None = None,
        *,
        fills: dict[tuple[int, int], str] | None = None,
        fill: str = "#ffffff",
        stroke: str = "#172033",
        stroke_width: Number = 2,
    ):
        """Draw a rectangular cell grid, optionally colouring selected cells."""
        if columns <= 0 or rows <= 0:
            raise ValueError("Grid columns and rows must be positive.")
        height = float(cell_height if cell_height is not None else cell_width)
        coloured = fills or {}
        for row in range(rows):
            for column in range(columns):
                self.rect(
                    x + column * float(cell_width),
                    y + row * height,
                    cell_width,
                    height,
                    fill=coloured.get((column, row), fill),
                    stroke=stroke,
                    stroke_width=stroke_width,
                )
        return self

    def clock(
        self,
        center: Point,
        radius: Number,
        *,
        hour: int,
        minute: int,
        face_fill: str = "#ffffff",
        stroke: str = "#172033",
        accent: str = "#3b82f6",
        show_numbers: bool = True,
    ):
        """Draw a clear analogue clock with hour and minute hands."""
        if not 0 <= minute < 60:
            raise ValueError("Clock minute must be between 0 and 59.")
        cx, cy, r = float(center[0]), float(center[1]), float(radius)
        self.circle((cx, cy), r, fill=face_fill, stroke=stroke, stroke_width=max(2, r * 0.06))
        for value in range(60):
            angle = (value * 6 - 90) * pi / 180
            outer = (cx + cos(angle) * r * 0.89, cy + sin(angle) * r * 0.89)
            inner_ratio = 0.75 if value % 5 == 0 else 0.82
            inner = (cx + cos(angle) * r * inner_ratio, cy + sin(angle) * r * inner_ratio)
            self.line(inner, outer, stroke=stroke, stroke_width=2.8 if value % 5 == 0 else 1.2, linecap="round")
        if show_numbers:
            for value in range(1, 13):
                angle = (value * 30 - 90) * pi / 180
                self.text(
                    (cx + cos(angle) * r * 0.61, cy + sin(angle) * r * 0.61),
                    str(value), font_size=max(10, r * 0.19), font_weight=650,
                )
        minute_angle = (minute * 6 - 90) * pi / 180
        hour_angle = (((hour % 12) + minute / 60) * 30 - 90) * pi / 180
        self.line((cx, cy), (cx + cos(minute_angle) * r * 0.67, cy + sin(minute_angle) * r * 0.67), stroke=accent, stroke_width=max(3, r * 0.055))
        self.line((cx, cy), (cx + cos(hour_angle) * r * 0.48, cy + sin(hour_angle) * r * 0.48), stroke=stroke, stroke_width=max(4, r * 0.075))
        self.circle((cx, cy), max(3, r * 0.06), fill=stroke, stroke="none")
        return self

    def isometric_cube(
        self,
        origin: Point,
        size: Number,
        *,
        top_fill: str = "#dbeafe",
        left_fill: str = "#93c5fd",
        right_fill: str = "#60a5fa",
        stroke: str = "#17324d",
        stroke_width: Number = 2,
    ):
        """Draw one isometric cube with independently coloured visible faces."""
        x, y, s = float(origin[0]), float(origin[1]), float(size)
        top = [(x, y), (x + s, y - s / 2), (x, y - s), (x - s, y - s / 2)]
        left = [(x - s, y - s / 2), (x, y), (x, y + s), (x - s, y + s / 2)]
        right = [(x, y), (x + s, y - s / 2), (x + s, y + s / 2), (x, y + s)]
        self.polygon(left, fill=left_fill, stroke=stroke, stroke_width=stroke_width)
        self.polygon(right, fill=right_fill, stroke=stroke, stroke_width=stroke_width)
        self.polygon(top, fill=top_fill, stroke=stroke, stroke_width=stroke_width)
        return self

    def use(
        self,
        glyph: "Drawing",
        position: Point,
        *,
        scale: Number = 1,
        rotate: Number = 0,
        opacity: Number | None = None,
        element_id: str | None = None,
    ):
        transforms = [f"translate({_number(position[0])} {_number(position[1])})"]
        if rotate:
            transforms.append(f"rotate({_number(rotate)})")
        if scale != 1:
            transforms.append(f"scale({_number(scale)})")
        attributes = {
            "id": element_id,
            "transform": " ".join(transforms),
            "opacity": _number(opacity) if opacity is not None else None,
        }
        self._elements.append(f"<g {_attributes(attributes)}>{''.join(glyph._elements)}</g>")
        return self

    def render_svg(self, path: str | Path | None = None, *, title: str = "Educational illustration") -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_number(self.width)}" '
            f'height="{_number(self.height)}" viewBox="0 0 {_number(self.width)} {_number(self.height)}" '
            f'role="img"><title>{escape(title)}</title>'
        ]
        if self.background is not None:
            parts.append(
                # Explicit dimensions are more portable than percentages here.
                # In particular, several SVG-to-PNG importers interpret ``100%``
                # as 100 user units rather than the outer SVG viewport.
                f'<rect width="{_number(self.width)}" height="{_number(self.height)}" '
                f'fill="{escape(self.background, quote=True)}" stroke="none"/>'
            )
        parts.extend(self._elements)
        parts.append("</svg>")
        svg = "".join(parts)
        if path is not None:
            Path(path).write_text(svg, encoding="utf-8")
        return svg
