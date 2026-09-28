"""Build the reference triangle using relations and one driving dimension."""

from pathlib import Path

from constraint_cad import Sketch


HERE = Path(__file__).parent

sketch = Sketch()
sketch.points("A", "B", "C", "D", "E")

sketch.segment("AC", "A", "C")
sketch.segment("AB", "A", "B")
sketch.segment("CB", "C", "B")
sketch.segment("AE", "A", "E")
sketch.segment("EB", "E", "B")
sketch.segment("AD", "A", "D")
sketch.segment("DB", "D", "B")
sketch.segment("ED", "E", "D")

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

sketch.dimension_angle("AB", "CB", "m°", vertex="B")

solution = sketch.solve()
output = HERE / "complex_relations.svg"
sketch.render_svg(
    output,
    width=900,
    height=720,
    title="Constraint-solved geometric construction",
    solution=solution,
)

print(f"Wrote {output}")
print(f"Iterations: {solution.iterations}")
print(f"Maximum constraint error: {solution.maximum_error:.3g}")
print(f"Shape degrees of freedom: {solution.shape_degrees_of_freedom}")
for name, point in solution.points.items():
    print(f"{name}: ({point[0]:.6f}, {point[1]:.6f})")
