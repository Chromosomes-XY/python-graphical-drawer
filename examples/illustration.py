"""Render reusable pen illustrations to an SVG beside this script."""
from pathlib import Path
from constraint_cad import Drawing

pen = Drawing(60, 24, background=None)
pen.rect(0, 7, 42, 10, radius=4, fill="#5cc8ff", stroke="#172033", stroke_width=2)
pen.polygon([(42, 7), (58, 12), (42, 17)], fill="#f3c178", stroke="#172033", stroke_width=2)
page = Drawing(420, 100)
for x in (20, 90, 160, 230, 300):
    page.use(pen, (x, 30), rotate=-18)
output = Path(__file__).with_name("illustration.svg")
page.render_svg(output, title="A row of pens")
print(f"Wrote {output}")
