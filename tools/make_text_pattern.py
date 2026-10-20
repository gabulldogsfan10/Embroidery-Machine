"""Generate a two-line lettering embroidery pattern (DST) from a TrueType font.

Each glyph is stitched as: tie-in, edge-run underlay, fill rows, tie-off, trim.
Line 1 and line 2 are separate colors, so the machine stops for a thread change
between them (use the same spool twice for a one-color patch).

Usage:
    python3 tools/make_text_pattern.py
"""

import math
import os

import pyembroidery
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely.affinity import rotate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "patterns")
FONT = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"

# All sizes in millimetres.
LINES = [
    {"text": "Henderson", "cap_height": 15.0, "color": 0x1F2A44, "name": "Navy"},
    {"text": "est. 2007", "cap_height": 7.5, "color": 0x8B6B2E, "name": "Old gold"},
]
LINE_GAP = 5.0          # space between the baseline of line 1 and top of line 2
FILL_SPACING = 0.40     # distance between fill rows
FILL_ANGLE = 45         # degrees; diagonal rows look better on lettering
MAX_STITCH = 3.0        # longest stitch inside a fill row
RUN_STITCH = 2.0        # edge underlay stitch length
TRIM_DISTANCE = 2.0     # jumps longer than this get trimmed


class PolyPen(BasePen):
    """Collects a glyph outline as flattened point lists."""

    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.contours = []
        self.cur = []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8
            mt = 1 - t
            self.cur.append((
                mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
                mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1],
            ))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 7):
            t = i / 6
            mt = 1 - t
            self.cur.append((
                mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0],
                mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1],
            ))

    def _closePath(self):
        if len(self.cur) >= 3:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def glyph_shape(contours):
    """Build a polygon with holes using the even-odd rule."""
    shape = Polygon()
    for c in contours:
        p = Polygon(c).buffer(0)
        shape = shape.symmetric_difference(p)
    return shape.buffer(0)


def text_shapes(font, text, cap_height):
    """Return one shapely geometry per visible glyph, in mm, y pointing up."""
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    cap = font["OS/2"].sCapHeight or font["head"].unitsPerEm * 0.7
    scale = cap_height / cap
    x = 0.0
    shapes = []
    for ch in text:
        gname = cmap[ord(ch)]
        pen = PolyPen(gs)
        gs[gname].draw(pen)
        if pen.contours:
            pts = [[((px + x) * scale, py * scale) for px, py in c] for c in pen.contours]
            shapes.append(glyph_shape(pts))
        x += gs[gname].width
    return shapes


def run_along(points, step):
    """Split a polyline into stitches no longer than step."""
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        d = math.dist(a, b)
        n = max(1, math.ceil(d / step))
        for i in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
    return out


def fill_rows(shape):
    """Scanline fill at FILL_ANGLE; returns a list of stitch blocks.

    Segments on neighbouring rows that overlap are chained into one block so
    the needle zig-zags back and forth; a new block starts where the shape
    branches (e.g. the two legs of an 'n').
    """
    cx, cy = shape.centroid.x, shape.centroid.y
    rot = rotate(shape, -FILL_ANGLE, origin=(cx, cy))
    minx, miny, maxx, maxy = rot.bounds
    rows = []
    y = miny + FILL_SPACING / 2
    while y < maxy:
        cut = rot.intersection(LineString([(minx - 1, y), (maxx + 1, y)]))
        segs = []
        for g in getattr(cut, "geoms", [cut]):
            if g.is_empty or g.geom_type != "LineString":
                continue
            xs = sorted(p[0] for p in g.coords)
            if xs[-1] - xs[0] > 0.3:
                segs.append((xs[0], xs[-1], y))
        rows.append(sorted(segs))
        y += FILL_SPACING

    used = [[False] * len(r) for r in rows]
    blocks = []
    for r0 in range(len(rows)):
        for s0 in range(len(rows[r0])):
            if used[r0][s0]:
                continue
            chain = []
            r, s, forward = r0, s0, True
            while True:
                used[r][s] = True
                x1, x2, yy = rows[r][s]
                chain.append(((x1, yy), (x2, yy)) if forward else ((x2, yy), (x1, yy)))
                forward = not forward
                nxt = None
                if r + 1 < len(rows):
                    for j, (a, b, _) in enumerate(rows[r + 1]):
                        if not used[r + 1][j] and a < x2 and b > x1:
                            nxt = j
                            break
                if nxt is None:
                    break
                r, s = r + 1, nxt
            pts = []
            for a, b in chain:
                pts.extend(run_along([a, b], MAX_STITCH) if not pts else run_along([pts[-1], a, b], MAX_STITCH)[1:])
            back = rotate(LineString(pts), FILL_ANGLE, origin=(cx, cy)) if len(pts) > 1 else None
            if back is not None:
                blocks.append(list(back.coords))
    return blocks


def underlay(shape):
    """Edge run just inside the outline so the fill has a firm base."""
    inner = shape.buffer(-0.5)
    paths = []
    for poly in getattr(inner, "geoms", [inner]):
        if poly.is_empty:
            continue
        paths.append(run_along(list(poly.exterior.coords), RUN_STITCH))
        for hole in poly.interiors:
            paths.append(run_along(list(hole.coords), RUN_STITCH))
    return paths


class Stitcher:
    def __init__(self):
        self.p = pyembroidery.EmbPattern()
        self.pos = None

    def _add(self, cmd, x, y):
        # pyembroidery units are 0.1 mm with y pointing down.
        self.p.add_stitch_absolute(cmd, round(x * 10), round(-y * 10))
        self.pos = (x, y)

    def tie(self, pts):
        a, b = pts[0], pts[min(1, len(pts) - 1)]
        for q in (b, a, b, a):
            self._add(pyembroidery.STITCH, *q)

    def path(self, pts, tie_in=False):
        if self.pos is None or math.dist(self.pos, pts[0]) > 0.01:
            if self.pos is not None and math.dist(self.pos, pts[0]) > TRIM_DISTANCE:
                self.tie_off()
                self.p.add_command(pyembroidery.TRIM)
                tie_in = True
            self._add(pyembroidery.JUMP, *pts[0])
            self._add(pyembroidery.STITCH, *pts[0])
        if tie_in:
            self.tie(pts)
        for q in pts[1:]:
            self._add(pyembroidery.STITCH, *q)

    def tie_off(self):
        if self.pos is None:
            return
        x, y = self.pos
        for dx in (0.3, 0, 0.3, 0):
            self._add(pyembroidery.STITCH, x + dx, y)

    def end_block(self):
        self.tie_off()
        self.p.add_command(pyembroidery.TRIM)


def build():
    font = TTFont(FONT)
    lines = [text_shapes(font, L["text"], L["cap_height"]) for L in LINES]

    # Centre each line horizontally; stack them with LINE_GAP between.
    placed = []
    top = 0.0
    for L, shapes in zip(LINES, lines):
        u = unary_union(shapes)
        minx, miny, maxx, maxy = u.bounds
        dx = -(minx + maxx) / 2
        dy = top - maxy
        placed.append([_shift(s, dx, dy) for s in shapes])
        top = top - (maxy - miny) - LINE_GAP

    # Centre the whole design on the hoop centre (0, 0).
    allu = unary_union([s for line in placed for s in line])
    minx, miny, maxx, maxy = allu.bounds
    oy = -(miny + maxy) / 2
    placed = [[_shift(s, 0, oy) for s in line] for line in placed]

    st = Stitcher()
    for i, (L, shapes) in enumerate(zip(LINES, placed)):
        st.p.add_thread({"color": L["color"], "description": L["name"]})
        if i > 0:
            st.p.add_command(pyembroidery.COLOR_BREAK)
            st.pos = None
        for shape in shapes:
            first = True
            for path in underlay(shape) + fill_rows(shape):
                if len(path) < 2:
                    continue
                st.path(path, tie_in=first)
                first = False
            st.end_block()
            st.pos = None
    st.p.add_command(pyembroidery.END)
    return st.p, (maxx - minx, maxy - miny)


def _shift(shape, dx, dy):
    from shapely.affinity import translate
    return translate(shape, dx, dy)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pattern, (w, h) = build()
    base = os.path.join(OUT_DIR, "henderson-est-2007")
    pyembroidery.write_dst(pattern, base + ".dst")
    pyembroidery.write_png(pattern, base + ".png")
    print(f"size {w:.1f} x {h:.1f} mm, {pattern.count_stitches()} stitches, "
          f"{pattern.count_color_changes() + 1} colors")
