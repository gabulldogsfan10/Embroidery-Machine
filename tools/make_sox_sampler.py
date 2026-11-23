"""Generate a "SOX" lettering sampler for a 5x7 hoop (Brother PES).

Four lines in Rye with letters 1/4, 1/2, 3/4 and 1 inch tall, then one line in
Nosifer at 1 inch with its drips in red. Everything else is black, so the
machine stops once for a thread change. Each line is also written as its own
file, for stitching a single one on a sock.

Fonts are in fonts/ (SIL Open Font License; see the LICENSE files there).

Usage:
    python3 tools/make_sox_sampler.py
"""

import os

import pyembroidery
from fontTools.ttLib import TTFont
from shapely.affinity import translate
from shapely.geometry import box
from shapely.ops import unary_union

from make_skull_border import preview
import make_text_pattern
from make_text_pattern import HERE, OUT_DIR, PolyPen, glyph_shape, stitch, write_pes

IN = 25.4
FONTS = os.path.join(HERE, "..", "fonts")
TEXT = "SOX"
LINE_GAP = 7.0
BLACK = (0x000000, "Black")
RED = (0xED171F, "Red")
# (font file, letter height in inches, split drips off in red?)
LINES = [("rye.ttf", 0.25, False), ("rye.ttf", 0.5, False), ("rye.ttf", 0.75, False), ("rye.ttf", 1.0, False),
         ("nosifer.ttf", 1.0, True)]


def letters(font_file, height):
    """Glyph shapes for TEXT, scaled so a capital X stands `height` mm above the baseline (y = 0)."""
    font = TTFont(os.path.join(FONTS, font_file))
    gs, cmap = font.getGlyphSet(), font.getBestCmap()

    def outline(ch):
        pen = PolyPen(gs)
        gs[cmap[ord(ch)]].draw(pen)
        return pen.contours

    x_pts = [p for c in outline("X") for p in c]
    k = height / max(y for _, y in x_pts)      # baseline to the top of the X, ignoring any drip below
    shapes, x = [], 0.0
    for ch in TEXT:
        shapes.append(glyph_shape([[((px + x) * k, py * k) for px, py in c] for c in outline(ch)]))
        x += gs[cmap[ord(ch)]].width
    return shapes


def line(font_file, inches, drips):
    """Return (black shapes, red shapes) for one line, centred on x = 0 with its top at y = 0."""
    height = inches * IN
    shapes = letters(font_file, height)
    x0, _, x1, y1 = unary_union(shapes).bounds
    shapes = [translate(s, -(x0 + x1) / 2, -y1) for s in shapes]
    if not drips:
        return shapes, []
    # Everything hanging below the foot of the letters is a drip.
    cut = -y1 - 0.03 * height      # y1 was the top; the baseline now sits at -y1
    far = 10 * height
    black = [s.intersection(box(-far, cut, far, far)) for s in shapes]
    red = [s.intersection(box(-far, -far, far, cut)) for s in shapes]
    parts = lambda gs: [q for g in gs for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 0.15]
    return parts(black), parts(red)


def build(lines, spacing=None):
    """Stitch the lines stacked top to bottom. spacing overrides the gap between fill rows (mm);
    a smaller gap means more rows, so more stitches and a more solid look."""
    normal = make_text_pattern.FILL_SPACING
    make_text_pattern.FILL_SPACING = spacing or normal
    try:
        return _build(lines)
    finally:
        make_text_pattern.FILL_SPACING = normal


def _build(lines):
    black, red, top = [], [], 0.0
    for font_file, inches, drips in lines:
        b, r = line(font_file, inches, drips)
        black += [(translate(s, 0, top), 45) for s in b]
        red += [(translate(s, 0, top), 0) for s in r]          # rows across each drip
        top = min(s.bounds[1] for s, _ in black + red) - LINE_GAP
    layers = [(*BLACK, black)] + ([(*RED, red)] if red else [])
    return stitch(layers)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = [("sox-sampler-5x7", LINES, None)]
    jobs += [(f"sox-{f.split('.')[0]}-{str(h).replace('.', '_')}in", [(f, h, d)], None) for f, h, d in LINES]
    # The 1-inch Rye again with the fill rows closer together (normal is 0.40 mm).
    jobs += [("sox-rye-1_0in-dense", [LINES[3]], 0.30), ("sox-rye-1_0in-extra-dense", [LINES[3]], 0.25)]
    for name, lines, spacing in jobs:
        base = os.path.join(OUT_DIR, name)
        pattern, (w, h) = build(lines, spacing)
        write_pes(pattern, base + ".pes", "SOX")
        pattern = pyembroidery.read(base + ".pes")
        if name.startswith("sox-sampler"):
            preview(pattern, 130.0, 180.0, base + ".png")
        print(f"{name}: {w:.1f} x {h:.1f} mm ({w / IN:.2f} x {h / IN:.2f} in), "
              f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} color(s)")
