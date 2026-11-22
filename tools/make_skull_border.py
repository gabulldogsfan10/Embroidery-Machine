"""Generate an original skull, flower and vine border as a Brother PES.

A portrait frame meant to go around lettering that is already stitched, so it
hugs the edge of the stitch field: the side runs stay inside a half-inch band
(a slim wavy vine with small leaves and flowers alternating pink and white),
and each corner carries a fuller spray -- a cream skull on a collar of three
leaves, a flower on each arm and two curls. Flowers, skulls and the corner
leaves get a black outline so pale thread still reads on white fabric.

Stitch order: green, pink, white, cream, black -- the machine stops four times.

Usage:
    python3 tools/make_skull_border.py
"""

import math
import os

import pyembroidery
from PIL import Image, ImageDraw
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from make_text_pattern import OUT_DIR, Stitcher, fill_rows, underlay, write_pes

IN = 25.4
BAND = 0.5 * IN         # side runs stay within this distance of the field edge
SAFETY = 1.0            # keep stitches this far inside the field edge
CORNER_R = 9.0
WAVE_AMP = 2.0
VINE_W, CURL_W = 1.6, 1.3
SATIN_STEP = 0.4

# Brother embroidery thread chart colors.
GREEN = (0x2F7E20, "Moss Green")
PINK = (0xFFB2BE, "Pink")
WHITE = (0xFFFFFF, "White")
CREAM = (0xFFF0C5, "Cream Yellow")
BLACK = (0x000000, "Black")

# name -> stitch field (width, height) in mm, portrait.
VARIANTS = {
    "skull-flower-border-5x7": (130.0, 180.0),
    "skull-flower-border-6.25x8.5": (6.25 * IN, 8.5 * IN),
}


def skull():
    """An upright skull about 12 mm wide and 15 mm tall, centred near (0, 0)."""
    cranium = scale(Point(0, 2).buffer(7, 48), 1.0, 0.95)
    jaw = box(-4.2, -8.5, 4.2, -2).buffer(1.2)
    shape = cranium.union(jaw)
    eye = scale(Point(0, 0).buffer(2.3, 24), 1.0, 1.2)
    shape = shape.difference(translate(rotate(eye, 12), -3.1, 1.0))
    shape = shape.difference(translate(rotate(eye, -12), 3.1, 1.0))
    shape = shape.difference(Polygon([(0, -1.4), (-1.3, -4.0), (1.3, -4.0)]).buffer(0.3))
    return scale(shape, 0.85, 0.85, origin=(0, 0))


def flower(size=1.0):
    """Five round petals with an open centre; 11.6 mm across at size 1."""
    petals = [Point(3.2 * math.cos(a), 3.2 * math.sin(a)).buffer(2.6, 24)
              for a in (math.radians(90 + 72 * i) for i in range(5))]
    shape = unary_union(petals).difference(Point(0, 0).buffer(1.0, 16))
    return scale(shape, size, size, origin=(0, 0))


def leaf(length, width):
    top = [(length * i / 16, width / 2 * math.sin(math.pi * i / 16)) for i in range(17)]
    return Polygon(top + [(x, -y) for x, y in reversed(top[1:-1])])


def resample(points, step):
    """Evenly spaced points along a path, so dense outlines don't become tiny stitches."""
    line = LineString(points)
    n = max(2, round(line.length / step))
    return [line.interpolate(i / n, normalized=True).coords[0] for i in range(n + 1)]


def satin(points, width):
    """Centre run out, then a zigzag column back along the same path."""
    line = LineString(points)
    n = max(2, int(line.length / SATIN_STEP))
    out = resample(points, 2.0)
    for i in range(n, -1, -1):
        p = line.interpolate(i / n, normalized=True)
        q = line.interpolate(min(1, (i + 0.5) / n), normalized=True)
        r = line.interpolate(max(0, (i - 0.5) / n), normalized=True)
        tx, ty = q.x - r.x, q.y - r.y
        d = math.hypot(tx, ty) or 1
        side = width / 2 if i % 2 else -width / 2
        out.append((p.x - ty / d * side, p.y + tx / d * side))
    return out


def bean(points):
    """A triple run (out, back, out) so a thin outline reads as a solid line."""
    pts = resample(points, 1.5)
    return pts + pts[-2::-1] + pts[1:]


def build(field_w, field_h):
    inset = (SAFETY + BAND) / 2      # vine centreline, from the field edge
    a, b = field_w / 2 - inset, field_h / 2 - inset
    ring = box(-(a - CORNER_R), -(b - CORNER_R), a - CORNER_R, b - CORNER_R).buffer(CORNER_R, 32).exterior
    L = ring.length

    def frame(s):
        """Point on the ring at distance s, with unit tangent and outward normal."""
        p, q = ring.interpolate(s % L), ring.interpolate((s + 0.5) % L)
        tx, ty = q.x - p.x, q.y - p.y
        d = math.hypot(tx, ty)
        tx, ty = tx / d, ty / d
        nx, ny = ty, -tx
        if nx * p.x + ny * p.y < 0:
            nx, ny = -nx, -ny
        return (p.x, p.y), (tx, ty), (nx, ny)

    def gap(s, o):
        return min(abs(s - o) % L, L - abs(s - o) % L)

    k = CORNER_R * (1 - 1 / math.sqrt(2))
    corners = sorted(ring.project(Point(sx * (a - k), sy * (b - k))) for sx in (-1, 1) for sy in (-1, 1))

    # Each side between two corners: flowers evenly spaced, one full wave of
    # the vine between neighbours so the vine crosses the centreline at each.
    sides = []
    for i, c0 in enumerate(corners):
        c1 = corners[(i + 1) % 4] + (L if i == 3 else 0)
        lo, hi = c0 + 34, c1 - 34
        n = max(1, round((hi - lo) / 30))
        d = (hi - lo) / n
        sides.append((c0, c1, lo + d / 2, d, n))

    def side_of(s):
        s = s % L
        for c0, c1, s0, d, n in sides:
            for t in (s, s + L):
                if c0 <= t < c1:
                    return t, s0, d, n
        raise ValueError(s)

    def vine_point(s):
        (x, y), _, (nx, ny) = frame(s)
        t, s0, d, _ = side_of(s)
        env = max(0.0, min(1.0, (min(gap(s, c) for c in corners) - 22) / 10))
        off = WAVE_AMP * env * math.sin(2 * math.pi * (t - s0) / d)
        return (x + nx * off, y + ny * off)

    # --- Motifs ---------------------------------------------------------
    flower_s = [(c + dc) % L for c in corners for dc in (-19, 19)]
    for c0, c1, s0, d, n in sides:
        flower_s += [(s0 + d * i) % L for i in range(n)]
    flower_s.sort()
    flowers = [translate(rotate(flower(0.95), 24 * i, origin=(0, 0)), *vine_point(s)) for i, s in enumerate(flower_s)]

    skulls, collars = [], []
    for c in corners:
        (x, y), _, (nx, ny) = frame(c)
        cx, cy = x - nx * 5, y - ny * 5
        skulls.append(translate(rotate(skull(), -20 * (1 if x > 0 else -1), origin=(0, 0)), cx, cy))
        out = math.degrees(math.atan2(ny, nx))
        for da in (-55, 0, 55):
            collars.append((c + da / 100, translate(rotate(leaf(11.0, 6.5), out + da, origin=(0, 0)), cx, cy), out + da))
    solid = lambda g: Polygon(g.exterior)
    skull_mask = unary_union([solid(g) for g in skulls]).buffer(0.4)
    collars = [(s, shp.difference(skull_mask), ang) for s, shp, ang in collars]
    motifs = unary_union([solid(g) for g in skulls + flowers] + [shp for _, shp, _ in collars])

    # --- Green: vine, curls, leaves -------------------------------------
    green = []  # (s, kind, data)
    vine = LineString([vine_point(L * i / 1600) for i in range(1601)])
    pieces = vine.difference(motifs.buffer(0.6))
    for piece in getattr(pieces, "geoms", [pieces]):
        if piece.length > 3:
            green.append((ring.project(Point(piece.coords[0])), "satin", (list(piece.coords), VINE_W)))

    for c in corners:  # a curl on the inside of each arm
        for dc in (-30, 30):
            s = (c + dc) % L
            (_, _), _, (nx, ny) = frame(s)
            vx, vy = vine_point(s)
            cx, cy = vx - nx * 5.5, vy - ny * 5.5
            a0 = math.atan2(vy - cy, vx - cx)
            turn = 1 if dc > 0 else -1
            pts = [(cx + (5.5 - 4.5 * i / 40) * math.cos(a0 + turn * 2.6 * math.pi * i / 40),
                    cy + (5.5 - 4.5 * i / 40) * math.sin(a0 + turn * 2.6 * math.pi * i / 40)) for i in range(41)]
            shown = LineString(pts).difference(motifs.buffer(0.8))
            shown = max(getattr(shown, "geoms", [shown]), key=lambda g: g.length)
            if shown.length > 6:
                green.append((s, "satin", (list(shown.coords), CURL_W)))

    for c0, c1, s0, d, n in sides:  # a small leaf on each wave peak
        for i in range(-1, 2 * n + 1):
            s = (s0 - d / 4 + i * d / 2) % L
            if min(gap(s, c) for c in corners) < 36:
                continue
            (_, _), (tx, ty), (nx, ny) = frame(s)
            side = 1 if i % 2 == 0 else -1
            ang = math.degrees(math.atan2(ny * side, nx * side)) - 35 * side
            green.append((s, "fill", (translate(rotate(leaf(4.8, 2.6), ang, origin=(0, 0)), *vine_point(s)), ang + 90)))
    for s, shp, ang in collars:
        if shp.geom_type == "Polygon" and shp.area > 8:
            green.append((s, "fill", (shp, ang + 90)))
    green.sort(key=lambda g: g[0])

    # --- Stitch ---------------------------------------------------------
    st = Stitcher()

    def start_color(color, first=False):
        st.p.add_thread({"color": color[0], "description": color[1]})
        st.p.threadlist[-1].catalog_number = ""
        if not first:
            st.p.add_command(pyembroidery.COLOR_BREAK)

    def stitch_fill(shape, angle):
        st.pos = None
        first = True
        shape = shape.simplify(0.2)  # round shapes carry far more outline points than stitches need
        for path in underlay(shape) + fill_rows(shape, angle):
            if len(path) >= 2:
                st.path(path, tie_in=first)
                first = False
        st.end_block()

    def stitch_line(points):
        st.pos = None
        st.path(points, tie_in=True)
        st.end_block()

    start_color(GREEN, first=True)
    for _, kind, data in green:
        stitch_fill(*data) if kind == "fill" else stitch_line(satin(*data))

    for color, group in ((PINK, flowers[0::2]), (WHITE, flowers[1::2])):
        start_color(color)
        for i, f in enumerate(group):
            stitch_fill(f, 45 if i % 2 else -45)

    start_color(CREAM)
    for g in skulls:
        stitch_fill(g, 0)

    # Black details, travelling once around the loop.
    start_color(BLACK)
    black = []
    for s, f in zip(flower_s, flowers):
        black.append((s, lambda f=f, s=s: (stitch_line(bean(f.exterior.coords)),
                                           stitch_fill(Point(vine_point(s)).buffer(1.3, 16), 0))))
    for c, g in zip(corners, skulls):
        def details(g=g):
            stitch_line(bean(g.exterior.coords))
            for hole in g.interiors:
                stitch_fill(Polygon(hole), 0)
        black.append((c, details))
    for s, shp, ang in collars:
        if shp.geom_type == "Polygon" and shp.area > 8:
            black.append((s, lambda shp=shp: stitch_line(bean(shp.exterior.coords))))
    for _, draw in sorted(black, key=lambda item: item[0]):
        draw()
    st.p.add_command(pyembroidery.END)
    return st.p


def preview(pattern, field_w, field_h, path):
    """Draw the stitches on white fabric, with the stitch field and half-inch band marked."""
    w, h = int(field_w * 10) + 200, int(field_h * 10) + 200
    im = Image.new("RGB", (w, h), (232, 233, 236))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 100, w - 100, h - 100], fill=(250, 250, 250), outline=(120, 125, 130), width=3)
    t = 100 + BAND * 10
    d.rectangle([t, t, w - t, h - t], outline=(205, 208, 212), width=2)
    color, prev = 0, None
    for x, y, cmd in pattern.stitches:
        cmd &= 0xFF
        if cmd == pyembroidery.COLOR_CHANGE:
            color, prev = color + 1, None
        elif cmd != pyembroidery.STITCH:
            prev = None
        else:
            pt = (x + w / 2, y + h / 2)
            if prev:
                d.line([prev, pt], fill=pattern.threadlist[color].hex_color(), width=4)
            prev = pt
    im.resize((w // 2, h // 2), Image.LANCZOS).save(path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (fw, fh) in VARIANTS.items():
        base = os.path.join(OUT_DIR, name)
        write_pes(build(fw, fh), base + ".pes", "Skull Border")
        pattern = pyembroidery.read(base + ".pes")
        preview(pattern, fw, fh, base + ".png")
        x0, y0, x1, y1 = pattern.bounds()
        print(f"{name}: {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm in a {fw:.1f} x {fh:.1f} field, "
              f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} colors")
