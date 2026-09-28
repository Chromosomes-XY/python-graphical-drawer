from __future__ import annotations

import math
import re
import unittest

from constraint_cad import ConstraintError, Drawing, Sketch


class ConstraintCadTests(unittest.TestCase):
    def reference_sketch(self):
        sketch = Sketch().points("A", "B", "C", "D", "E")
        for name, start, end in (
            ("AC", "A", "C"),
            ("AB", "A", "B"),
            ("CB", "C", "B"),
            ("AE", "A", "E"),
            ("EB", "E", "B"),
            ("AD", "A", "D"),
            ("DB", "D", "B"),
            ("ED", "E", "D"),
        ):
            sketch.segment(name, start, end)
        sketch.horizontal("CB")
        sketch.midpoint("E", "CB")
        sketch.vertical("AE")
        sketch.equal("AE", "EB")
        sketch.point_on_line("D", "AB")
        sketch.perpendicular("ED", "AB")
        sketch.perpendicular("AE", "CB")
        sketch.equal("AD", "ED")
        sketch.length("CB", 10)
        sketch.orientation("A", above="CB")
        return sketch

    def test_reference_shape_is_solved_without_coordinates(self):
        sketch = self.reference_sketch()
        solution = sketch.solve()
        self.assertTrue(solution.converged)
        self.assertLess(solution.maximum_error, 1e-6)
        self.assertEqual(solution.shape_degrees_of_freedom, 0)
        self.assertAlmostEqual(solution["E"][0], (solution["C"][0] + solution["B"][0]) / 2, places=5)
        self.assertAlmostEqual(solution["E"][1], (solution["C"][1] + solution["B"][1]) / 2, places=5)
        self.assertGreater(solution["A"][1], solution["E"][1])

    def test_equal_and_perpendicular_relations_hold(self):
        solution = self.reference_sketch().solve()

        def distance(first, second):
            return math.dist(solution[first], solution[second])

        self.assertAlmostEqual(distance("A", "E"), distance("E", "B"), places=5)
        self.assertAlmostEqual(distance("A", "D"), distance("E", "D"), places=5)
        ab = (solution["B"][0] - solution["A"][0], solution["B"][1] - solution["A"][1])
        ed = (solution["D"][0] - solution["E"][0], solution["D"][1] - solution["E"][1])
        self.assertAlmostEqual(ab[0] * ed[0] + ab[1] * ed[1], 0, places=4)

    def test_svg_is_inline_safe_and_automatically_fitted(self):
        sketch = self.reference_sketch()
        sketch.dimension_angle("AB", "CB", "m°", vertex="B")
        from constraint_cad.svg import render_svg

        svg = render_svg(sketch, sketch.solve(), width=900, height=720, title="Test")
        self.assertNotIn("<style", svg)
        self.assertIsNone(re.search(r"\sstyle=|\sclass=", svg))
        self.assertIn("m°", svg)
        self.assertIn('stroke="#2563eb"', svg)

    def test_conflicting_dimensions_are_reported(self):
        sketch = Sketch().points("A", "B").segment("AB", "A", "B")
        sketch.length("AB", 5)
        sketch.length("AB", 7)
        with self.assertRaises(ConstraintError):
            sketch.solve(maximum_iterations=80)

    def test_midpoint_and_intersection_are_computed(self):
        sketch = Sketch().points("A", "B", "C", "D", "M", "X")
        sketch.segment("AB", "A", "B")
        sketch.segment("CD", "C", "D")
        sketch.fix("A", (-4, 0)).fix("B", (4, 0))
        sketch.fix("C", (0, -3)).fix("D", (0, 3))
        sketch.midpoint("M", "AB")
        sketch.intersection("X", "AB", "CD")
        solution = sketch.solve()
        self.assertAlmostEqual(solution["M"][0], 0, places=5)
        self.assertAlmostEqual(solution["M"][1], 0, places=5)
        self.assertAlmostEqual(solution["X"][0], 0, places=5)
        self.assertAlmostEqual(solution["X"][1], 0, places=5)

    def test_parallel_collinear_and_symmetric_relations(self):
        sketch = Sketch().points("A", "B", "C", "D", "P", "Q", "U", "V")
        sketch.segment("AB", "A", "B")
        sketch.segment("CD", "C", "D")
        sketch.segment("axis", "U", "V")
        sketch.fix("A", (-4, 0)).fix("B", (4, 0))
        sketch.fix("C", (-2, 2)).length("CD", 3).parallel("AB", "CD")
        sketch.orientation("D", right_of="CD")
        sketch.fix("U", (0, -4)).fix("V", (0, 4))
        sketch.fix("P", (-3, 1)).symmetric("P", "Q", about="axis")
        solution = sketch.solve()
        cd = (solution["D"][0] - solution["C"][0], solution["D"][1] - solution["C"][1])
        self.assertAlmostEqual(cd[1], 0, places=5)
        self.assertAlmostEqual(math.hypot(*cd), 3, places=5)
        self.assertAlmostEqual(solution["Q"][0], 3, places=5)
        self.assertAlmostEqual(solution["Q"][1], 1, places=5)

    def test_driving_angle_calculates_unknown_ray(self):
        sketch = Sketch().points("O", "A", "B")
        sketch.segment("OA", "O", "A")
        sketch.segment("OB", "O", "B")
        sketch.length("OA", 4).length("OB", 4)
        sketch.horizontal("OA")
        sketch.angle("OA", "OB", 60, vertex="O")
        sketch.orientation("B", above="OA")
        solution = sketch.solve()
        first = (solution["A"][0] - solution["O"][0], solution["A"][1] - solution["O"][1])
        second = (solution["B"][0] - solution["O"][0], solution["B"][1] - solution["O"][1])
        cosine = (first[0] * second[0] + first[1] * second[1]) / (
            math.hypot(*first) * math.hypot(*second)
        )
        self.assertAlmostEqual(math.degrees(math.acos(cosine)), 60, places=4)

    def test_construction_geometry_is_solved_but_not_drawn(self):
        sketch = Sketch().points("O", "A", "B")
        sketch.segment("visible", "A", "B")
        sketch.segment("guide", "O", "A", construction=True)
        sketch.length("visible", 4).length("guide", 3).perpendicular("visible", "guide")
        from constraint_cad.svg import render_svg

        svg = render_svg(sketch, sketch.solve(), width=500, height=400, title="Construction")
        self.assertIn('id="visible"', svg)
        self.assertNotIn('id="guide"', svg)

    def test_display_only_relation_marks_do_not_add_equations(self):
        sketch = Sketch().points("A", "B", "C", "D")
        sketch.segment("AB", "A", "B").segment("CD", "C", "D")
        sketch.fix("A", (0, 0)).fix("B", (4, 0)).fix("C", (0, 2)).fix("D", (4, 2))
        initial_count = len(sketch.constraints)
        sketch.mark_equal("AB", "CD").mark_parallel("AB", "CD")
        self.assertEqual(len(sketch.constraints), initial_count)
        from constraint_cad.svg import render_svg

        svg = render_svg(sketch, sketch.solve(), width=500, height=400, title="Marks")
        self.assertIn('stroke="#2563eb"', svg)

    def test_drawing_layer_supports_shapes_text_paths_and_reusable_glyphs(self):
        glyph = Drawing(20, 20, background=None)
        glyph.circle((10, 10), 8, fill="#22c55e", stroke="#166534", stroke_width=2)
        glyph.path("M5 10 L15 10", stroke="#ffffff", stroke_width=2)

        drawing = Drawing(160, 80)
        drawing.rect(5, 5, 150, 70, radius=8, fill="#eff6ff", stroke="#2563eb")
        drawing.star((30, 40), 16, fill="#facc15", stroke="#a16207")
        drawing.use(glyph, (65, 30), scale=1.25, rotate=15, element_id="badge")
        drawing.text((125, 40), "12", font_size=22)
        svg = drawing.render_svg(title="Drawing primitives")

        self.assertIn("<path", svg)
        self.assertIn("<polygon", svg)
        self.assertIn('id="badge"', svg)
        self.assertIn("transform=", svg)
        self.assertIn(">12</text>", svg)
        self.assertIn('<rect width="160" height="80" fill="#ffffff"', svg)
        self.assertNotIn('width="100%"', svg)
        self.assertNotIn("<style", svg)
        self.assertNotIn("<script", svg)
        self.assertIsNone(re.search(r"\sstyle=|\sclass=|\son[a-z]+=", svg))

    def test_drawing_rejects_invalid_canvas_and_star(self):
        with self.assertRaises(ValueError):
            Drawing(0, 20)
        with self.assertRaises(ValueError):
            Drawing(20, 20).star((10, 10), 8, points=2)

    def test_plot_clips_a_function_to_its_coordinate_window(self):
        drawing = Drawing(100, 100, background=None)
        drawing.plot(
            lambda x: 2 * x,
            "x",
            (-1, 1),
            (-0.5, 0.5),
            project=lambda x, y: (x, y),
            samples=8,
        )
        svg = drawing.render_svg()
        polylines = re.findall(r'<polyline[^>]+points="([^"]+)"', svg)
        self.assertTrue(polylines)
        for points in polylines:
            for point in points.split():
                x, y = map(float, point.split(","))
                self.assertGreaterEqual(x, -1)
                self.assertLessEqual(x, 1)
                self.assertGreaterEqual(y, -0.5)
                self.assertLessEqual(y, 0.5)
        with self.assertRaises(ValueError):
            drawing.plot(lambda x: x, "", (-1, 1), (-1, 1))

    def test_assessment_primitives_render_without_external_references(self):
        drawing = Drawing(420, 220)
        drawing.arrow((20, 30), (130, 30), both=True)
        drawing.grid(20, 60, 3, 2, 30, fills={(1, 0): "#8b7bd8"})
        drawing.clock((220, 90), 65, hour=10, minute=20)
        drawing.isometric_cube((340, 90), 30)
        svg = drawing.render_svg(title="Assessment primitives")

        self.assertGreaterEqual(svg.count("<polygon"), 5)
        self.assertGreaterEqual(svg.count("<rect"), 7)
        self.assertIn(">10</text>", svg)
        self.assertNotIn("href=", svg)

    def test_assessment_primitives_validate_inputs(self):
        drawing = Drawing(100, 100)
        with self.assertRaises(ValueError):
            drawing.arrow((1, 1), (1, 1))
        with self.assertRaises(ValueError):
            drawing.grid(0, 0, 0, 2, 10)
        with self.assertRaises(ValueError):
            drawing.clock((50, 50), 30, hour=3, minute=60)


if __name__ == "__main__":
    unittest.main()
