"""Numerical relation solver for declarative 2D sketches."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, radians, sin

import numpy as np

from .model import Constraint, Segment, Sketch


class ConstraintError(RuntimeError):
    """Raised when a sketch cannot satisfy its declared relations."""


@dataclass(frozen=True)
class SolveResult:
    points: dict[str, tuple[float, float]]
    converged: bool
    iterations: int
    residual_norm: float
    maximum_error: float
    raw_degrees_of_freedom: int
    shape_degrees_of_freedom: int
    redundant_equations: int

    def __getitem__(self, point: str) -> tuple[float, float]:
        return self.points[point]


class _System:
    def __init__(self, sketch: Sketch):
        self.sketch = sketch
        self.index = {name: offset for offset, name in enumerate(sketch.point_names)}

    def point(self, vector: np.ndarray, name: str) -> np.ndarray:
        offset = self.index[name] * 2
        return vector[offset : offset + 2]

    def segment(self, vector: np.ndarray, name: str):
        segment = self.sketch.segments[name]
        return self.point(vector, segment.start), self.point(vector, segment.end)

    @staticmethod
    def direction(start: np.ndarray, end: np.ndarray) -> np.ndarray:
        return end - start

    @staticmethod
    def length(direction: np.ndarray) -> float:
        return max(float(np.linalg.norm(direction)), 1e-10)

    @staticmethod
    def cross(first: np.ndarray, second: np.ndarray) -> float:
        return float(first[0] * second[1] - first[1] * second[0])

    def point_line_residual(
        self, vector: np.ndarray, point_name: str, segment_name: str
    ) -> float:
        point = self.point(vector, point_name)
        start, end = self.segment(vector, segment_name)
        direction = end - start
        return self.cross(direction, point - start) / self.length(direction)

    def relation_residuals(self, vector: np.ndarray, relation: Constraint) -> list[float]:
        kind, entities = relation.kind, relation.entities
        if kind == "horizontal":
            start, end = self.segment(vector, entities[0])
            return [float(end[1] - start[1])]
        if kind == "vertical":
            start, end = self.segment(vector, entities[0])
            return [float(end[0] - start[0])]
        if kind == "coincident":
            first = self.point(vector, entities[0])
            second = self.point(vector, entities[1])
            return [float(first[0] - second[0]), float(first[1] - second[1])]
        if kind == "midpoint":
            point = self.point(vector, entities[0])
            start, end = self.segment(vector, entities[1])
            delta = point - (start + end) / 2
            return [float(delta[0]), float(delta[1])]
        if kind == "point_on_line":
            return [self.point_line_residual(vector, entities[0], entities[1])]
        if kind == "intersection":
            return [
                self.point_line_residual(vector, entities[0], entities[1]),
                self.point_line_residual(vector, entities[0], entities[2]),
            ]
        if kind in {"parallel", "perpendicular", "collinear"}:
            first_start, first_end = self.segment(vector, entities[0])
            second_start, second_end = self.segment(vector, entities[1])
            first_direction = first_end - first_start
            second_direction = second_end - second_start
            denominator = self.length(first_direction) * self.length(second_direction)
            if kind == "parallel":
                return [self.cross(first_direction, second_direction) / denominator]
            if kind == "perpendicular":
                return [float(np.dot(first_direction, second_direction) / denominator)]
            return [
                self.cross(first_direction, second_direction) / denominator,
                self.point_line_residual(
                    vector,
                    self.sketch.segments[entities[1]].start,
                    entities[0],
                ),
            ]
        if kind == "equal":
            first_start, first_end = self.segment(vector, entities[0])
            second_start, second_end = self.segment(vector, entities[1])
            return [
                float(
                    np.linalg.norm(first_end - first_start)
                    - np.linalg.norm(second_end - second_start)
                )
            ]
        if kind == "length":
            start, end = self.segment(vector, entities[0])
            return [float(np.linalg.norm(end - start) - float(relation.value))]
        if kind == "angle":
            first_segment = self.sketch.segments[entities[0]]
            second_segment = self.sketch.segments[entities[1]]
            named_vertex = entities[2]
            if named_vertex:
                vertex = self.point(vector, named_vertex)
            else:
                shared = set((first_segment.start, first_segment.end)).intersection(
                    (second_segment.start, second_segment.end)
                )
                if not shared:
                    first_start, first_end = self.segment(vector, entities[0])
                    second_start, second_end = self.segment(vector, entities[1])
                    # Infinite-line intersection for relation evaluation.
                    first_direction = first_end - first_start
                    second_direction = second_end - second_start
                    denominator = self.cross(first_direction, second_direction)
                    if abs(denominator) < 1e-10:
                        return [1.0]
                    parameter = self.cross(second_start - first_start, second_direction) / denominator
                    vertex = first_start + parameter * first_direction
                else:
                    vertex = self.point(vector, next(iter(shared)))

            def outward(segment_name: str, segment) -> np.ndarray:
                start = self.point(vector, segment.start)
                end = self.point(vector, segment.end)
                if np.linalg.norm(start - vertex) < 1e-7:
                    return end - vertex
                if np.linalg.norm(end - vertex) < 1e-7:
                    return start - vertex
                return max((start, end), key=lambda point: np.linalg.norm(point - vertex)) - vertex

            first_direction = outward(entities[0], first_segment)
            second_direction = outward(entities[1], second_segment)
            measured = atan2(
                abs(self.cross(first_direction, second_direction)),
                float(np.dot(first_direction, second_direction)),
            )
            return [float(measured - radians(float(relation.value)))]
        if kind == "fix":
            point = self.point(vector, entities[0])
            target = np.asarray(relation.value, dtype=float)
            return [float(point[0] - target[0]), float(point[1] - target[1])]
        if kind == "symmetric":
            first = self.point(vector, entities[0])
            second = self.point(vector, entities[1])
            axis_start, axis_end = self.segment(vector, entities[2])
            axis = axis_end - axis_start
            unit = axis / self.length(axis)
            projection = axis_start + unit * np.dot(first - axis_start, unit)
            reflected = 2 * projection - first
            delta = second - reflected
            return [float(delta[0]), float(delta[1])]
        if kind in {"above", "below", "left_of", "right_of"}:
            point = self.point(vector, entities[0])
            start, end = self.segment(vector, entities[1])
            centre = (start + end) / 2
            scale = max(float(np.linalg.norm(end - start)), 1.0)
            clearance = scale * 0.02
            signed = {
                "above": point[1] - centre[1],
                "below": centre[1] - point[1],
                "left_of": centre[0] - point[0],
                "right_of": point[0] - centre[0],
            }[kind]
            # Branch hints do not affect a satisfied sketch, but receive a
            # strong penalty while violated so the solver crosses away from a
            # mirrored local solution instead of settling on the wrong side.
            return [float(8.0 * max(0.0, clearance - signed))]
        raise ValueError(f"Unsupported constraint kind: {kind}")

    def user_residuals(self, vector: np.ndarray) -> np.ndarray:
        values: list[float] = []
        for relation in self.sketch.constraints:
            values.extend(self.relation_residuals(vector, relation))
        return np.asarray(values, dtype=float)

    def residuals_with_gauge(self, vector: np.ndarray) -> np.ndarray:
        values = list(self.user_residuals(vector))
        kinds = {constraint.kind for constraint in self.sketch.constraints}
        if "fix" not in kinds:
            coordinates = vector.reshape((-1, 2))
            values.extend(
                [float(coordinates[:, 0].mean()), float(coordinates[:, 1].mean())]
            )
        if not kinds.intersection({"horizontal", "vertical", "fix"}) and self.sketch.segments:
            first_segment = next(iter(self.sketch.segments))
            start, end = self.segment(vector, first_segment)
            values.append(float(end[1] - start[1]))
        if not kinds.intersection({"length", "fix"}) and self.sketch.segments:
            first_segment = next(iter(self.sketch.segments))
            start, end = self.segment(vector, first_segment)
            values.append(float(np.linalg.norm(end - start) - 1.0))
        return np.asarray(values, dtype=float)


def _initial_vector(sketch: Sketch) -> np.ndarray:
    count = len(sketch.point_names)
    if count == 0:
        raise ValueError("A sketch requires at least one point.")
    driving_lengths = [
        float(item.value) for item in sketch.constraints if item.kind == "length"
    ]
    radius = max(driving_lengths, default=2.0) * 0.55
    values: list[float] = []
    for index, name in enumerate(sketch.point_names):
        if name in sketch.initial_hints:
            values.extend(sketch.initial_hints[name])
            continue
        angle = pi / 2 - 2 * pi * index / max(count, 1)
        values.extend((radius * cos(angle), radius * sin(angle)))
    vector = np.asarray(values, dtype=float)
    index = {name: offset for offset, name in enumerate(sketch.point_names)}
    for constraint in sketch.constraints:
        if constraint.kind not in {"above", "below", "left_of", "right_of"}:
            continue
        point_name, segment_name = constraint.entities
        segment = sketch.segments[segment_name]
        point_offset = index[point_name] * 2
        start_offset = index[segment.start] * 2
        end_offset = index[segment.end] * 2
        centre = (
            vector[start_offset : start_offset + 2]
            + vector[end_offset : end_offset + 2]
        ) / 2
        if constraint.kind == "above":
            vector[point_offset : point_offset + 2] = (centre[0], centre[1] + radius)
        elif constraint.kind == "below":
            vector[point_offset : point_offset + 2] = (centre[0], centre[1] - radius)
        elif constraint.kind == "left_of":
            vector[point_offset : point_offset + 2] = (centre[0] - radius, centre[1])
        else:
            vector[point_offset : point_offset + 2] = (centre[0] + radius, centre[1])
    return vector


def _jacobian(function, vector: np.ndarray, residual: np.ndarray) -> np.ndarray:
    matrix = np.empty((len(residual), len(vector)), dtype=float)
    for column in range(len(vector)):
        step = 1e-6 * (1.0 + abs(float(vector[column])))
        shifted = vector.copy()
        shifted[column] += step
        matrix[:, column] = (function(shifted) - residual) / step
    return matrix


def solve_sketch(
    sketch: Sketch,
    *,
    tolerance: float = 1e-7,
    maximum_iterations: int = 300,
    raise_on_conflict: bool = True,
) -> SolveResult:
    """Solve a sketch with a damped finite-difference Gauss-Newton method."""
    system = _System(sketch)
    vector = _initial_vector(sketch)
    damping = 1e-3
    converged = False
    iteration = 0

    for iteration in range(1, maximum_iterations + 1):
        residual = system.residuals_with_gauge(vector)
        norm = float(np.linalg.norm(residual))
        jacobian = _jacobian(system.residuals_with_gauge, vector, residual)
        normal = jacobian.T @ jacobian + damping * np.eye(len(vector))
        gradient = jacobian.T @ residual
        try:
            delta = np.linalg.solve(normal, -gradient)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(normal, -gradient, rcond=None)[0]

        candidate = vector + delta
        candidate_norm = float(np.linalg.norm(system.residuals_with_gauge(candidate)))
        if candidate_norm < norm:
            vector = candidate
            damping = max(damping * 0.35, 1e-10)
            if candidate_norm < tolerance and float(np.linalg.norm(delta)) < tolerance:
                converged = True
                break
        else:
            damping = min(damping * 8.0, 1e12)

    user_residual = system.user_residuals(vector)
    residual_norm = float(np.linalg.norm(user_residual))
    maximum_error = float(np.max(np.abs(user_residual))) if len(user_residual) else 0.0
    user_jacobian = _jacobian(system.user_residuals, vector, user_residual)
    rank = int(np.linalg.matrix_rank(user_jacobian, tol=1e-7))
    raw_dof = max(0, len(vector) - rank)
    kinds = {constraint.kind for constraint in sketch.constraints}
    free_rigid = 0 if "fix" in kinds else 2
    if not kinds.intersection({"horizontal", "vertical", "fix"}):
        free_rigid += 1
    free_scale = 0 if kinds.intersection({"length", "fix"}) else 1
    shape_dof = max(0, raw_dof - free_rigid - free_scale)
    redundant = max(0, len(user_residual) - rank)

    if maximum_error <= tolerance * 10:
        converged = True
    if raise_on_conflict and maximum_error > 1e-4:
        raise ConstraintError(
            f"Sketch constraints conflict or did not converge; maximum error is {maximum_error:.6g}."
        )

    points = {
        name: tuple(float(value) for value in system.point(vector, name))
        for name in sketch.point_names
    }
    return SolveResult(
        points=points,
        converged=converged,
        iterations=iteration,
        residual_norm=residual_norm,
        maximum_error=maximum_error,
        raw_degrees_of_freedom=raw_dof,
        shape_degrees_of_freedom=shape_dof,
        redundant_equations=redundant,
    )
