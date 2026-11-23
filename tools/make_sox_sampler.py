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
from shapely.geometry import Polygon, box
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


# A tiny single-line alphabet for the size labels: strokes in a box 1 unit tall.
STICK = {
    "1": (0.45, [[(0.05, 0.75), (0.3, 1), (0.3, 0)]]),
    "2": (0.6, [[(0, 0.8), (0.15, 1), (0.45, 1), (0.6, 0.8), (0.6, 0.6), (0, 0), (0.6, 0)]]),
    "3": (0.6, [[(0, 1), (0.6, 1), (0.25, 0.58), (0.5, 0.55), (0.6, 0.35), (0.6, 0.15), (0.45, 0), (0.15, 0), (0, 0.15)]]),
    "4": (0.6, [[(0.45, 0), (0.45, 1), (0, 0.3), (0.6, 0.3)]]),
    "/": (0.5, [[(0, 0), (0.5, 1)]]),
    "M": (0.7, [[(0, 0), (0, 1), (0.35, 0.4), (0.7, 1), (0.7, 0)]]),
    "D": (0.6, [[(0, 0), (0, 1), (0.35, 1), (0.6, 0.75), (0.6, 0.25), (0.35, 0), (0, 0)]]),
    " ": (0.45, []),
}
LABEL_H = 4.5           # label letter height, mm
LABEL_X = -62.0         # labels start here, at the left of the hoop


def label(text, x, y):
    """Stroke paths for a label whose baseline starts at (x, y), each stitched three times over."""
    paths = []
    for ch in text:
        width, strokes = STICK[ch]
        for stroke in strokes:
            pts = make_text_pattern.run_along([(x + px * LABEL_H, y + py * LABEL_H) for px, py in stroke], 2.0)
            paths.append(pts + pts[-2::-1] + pts[1:])
        x += (width + 0.3) * LABEL_H
    return paths


def build_full():
    """Reference sampler for a 5x7 hoop, one size per row with its letter height stitched beside it:
    Rye at 1/4, 1/2 and 3/4 inch, the 3/4 inch again at medium (M) and dense (D) fill, Rye at 1 inch,
    and Nosifer at 1 inch with red drips."""
    rye = lambda inches: line("rye.ttf", inches, False)[0]
    nos_black, nos_red = line("nosifer.ttf", 1.0, True)
    rows = [(rye(0.25), None, "1/4"), (rye(0.5), None, "1/2"), (rye(0.75), None, "3/4"), (rye(0.75), 0.30, "3/4 M"),
            (rye(0.75), 0.25, "3/4 D"), (rye(1.0), None, "1"), (nos_black + nos_red, None, "1")]
    heights = [unary_union(r).bounds[3] - unary_union(r).bounds[1] for r, _, _ in rows]
    gap = min(LINE_GAP, (176.0 - sum(heights)) / (len(rows) - 1))
    black, red, labels, top = [], [], [], 0.0
    for (shapes, spacing, text), h in zip(rows, heights):
        y1 = unary_union(shapes).bounds[3]
        # The letters' own height, drips aside, sets where the label sits.
        foot = min(g.bounds[1] for g in shapes if not any(g.equals(r) for r in nos_red))
        for g in shapes:
            (red if any(g.equals(r) for r in nos_red) else black).append((translate(g, 0, top - y1), spacing))
        labels += label(text, LABEL_X, top - y1 + (foot + y1 - LABEL_H) / 2)      # centred on the letters' height
        top -= h + gap

    st = make_text_pattern.Stitcher()
    pts = [q for path in labels for q in path]
    everything = unary_union([g for g, _ in black + red]).bounds
    everything = (min(everything[0], min(x for x, _ in pts)), everything[1], everything[2], everything[3])
    ox, oy = -(everything[0] + everything[2]) / 2, -(everything[1] + everything[3]) / 2
    normal = make_text_pattern.FILL_SPACING
    for i, (color, items, angle) in enumerate(((BLACK, black, 45), (RED, red, 0))):
        st.p.add_thread({"color": color[0], "description": color[1]})
        st.p.threadlist[-1].catalog_number = ""
        if i:
            st.p.add_command(pyembroidery.COLOR_BREAK)
        for g, spacing in items:
            g = translate(g, ox, oy)
            make_text_pattern.FILL_SPACING = spacing or normal
            st.pos, first = None, True
            for path in make_text_pattern.underlay(g) + make_text_pattern.fill_rows(g, angle):
                if len(path) >= 2:
                    st.path(path, tie_in=first)
                    first = False
            st.end_block()
        if i == 0:
            for path in labels:
                st.pos = None
                st.path([(x + ox, y + oy) for x, y in path], tie_in=True)
                st.end_block()
    make_text_pattern.FILL_SPACING = normal
    st.p.add_command(pyembroidery.END)
    return st.p, (everything[2] - everything[0], everything[3] - everything[1]), gap


def build_solid(font_file, inches, close=0.55):
    """One line with its letters filled in solid, like Nosifer's: the thin decorative line inside
    each Rye letter is closed up, while the real openings (the middle of the O) stay open."""
    shapes, _ = line(font_file, inches, False)
    solid = []
    for g in shapes:
        g = g.buffer(close).buffer(-close)
        for part in getattr(g, "geoms", [g]):
            # Drop any small leftover openings; keep real ones such as the middle of the O.
            solid.append(Polygon(part.exterior, [h for h in part.interiors if Polygon(h).area > 6.0]))
    return stitch([(*BLACK, [(g, 45) for g in solid])])


if __name__ == "__main__":
    pattern, (w, h) = build_solid("rye.ttf", 0.75)
    base = os.path.join(OUT_DIR, "sox-rye-0_75in-solid")
    write_pes(pattern, base + ".pes", "SOX solid")
    pattern = pyembroidery.read(base + ".pes")
    print(f"sox-rye-0_75in-solid: {w:.1f} x {h:.1f} mm ({w / IN:.2f} x {h / IN:.2f} in), "
          f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} color(s)")

    pattern, (w, h), gap = build_full()
    base = os.path.join(OUT_DIR, "sox-sampler-full-5x7")
    write_pes(pattern, base + ".pes", "SOX full")
    pattern = pyembroidery.read(base + ".pes")
    preview(pattern, 130.0, 180.0, base + ".png")
    print(f"sox-sampler-full-5x7: {w:.1f} x {h:.1f} mm ({w / IN:.2f} x {h / IN:.2f} in), gaps {gap:.1f} mm, "
          f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} color(s)")

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
