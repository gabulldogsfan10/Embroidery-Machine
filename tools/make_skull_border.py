"""Generate an original skull, flower and vine border as a Brother PES.

The border follows a rounded rectangle set in from the hoop edge: a wavy
satin-stitch vine with leaves and curls, six skulls (four corners, top and
bottom centre) and fourteen five-petal flowers alternating pink and white.
Stitch order: green, pink, white, black -- so the machine stops three times.

Usage:
    python3 tools/make_skull_border.py
"""

import math
import os

import pyembroidery
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from make_text_pattern import OUT_DIR, Stitcher, fill_rows, run_along, underlay, write_pes

IN = 25.4
HOOP_W, HOOP_H = 8.5 * IN, 6.25 * IN   # hoop, landscape
MARGIN = 0.5 * IN                      # clear space from each hoop side
BAND = 14.0                            # vine centreline sits this far inside the design edge
CORNER_R = 16.0
WAVE_AMP = 3.5
VINE_W, CURL_W = 2.0, 1.4
SATIN_STEP = 0.4

# Brother embroidery thread chart colors.
GREEN = (0x2F7E20, "Moss Green")
PINK = (0xF64A8A, "Deep Rose")
WHITE = (0xFFFFFF, "White")
BLACK = (0x000000, "Black")


def skull():
    """An upright skull about 14 mm wide and 17 mm tall, centred near (0, 0)."""
    cranium = scale(Point(0, 2).buffer(7, 48), 1.0, 0.95)
    jaw = box(-4.2, -8.5, 4.2, -2).buffer(1.2)
    shape = cranium.union(jaw)
    eye = scale(Point(0, 0).buffer(2.3, 24), 1.0, 1.2)
    shape = shape.difference(translate(rotate(eye, 12), -3.1, 1.0))
    shape = shape.difference(translate(rotate(eye, -12), 3.1, 1.0))
    shape = shape.difference(Polygon([(0, -1.4), (-1.3, -4.0), (1.3, -4.0)]).buffer(0.3))
    for x in (-1.8, 1.8):
        shape = shape.difference(box(x - 0.45, -9.8, x + 0.45, -6.4))
    return shape


def flower():
    """Five round petals with an open centre; about 11.5 mm across."""
    petals = [Point(3.2 * math.cos(a), 3.2 * math.sin(a)).buffer(2.6, 24)
              for a in (math.radians(90 + 72 * i) for i in range(5))]
    return unary_union(petals).difference(Point(0, 0).buffer(1.2, 16))


def leaf(length=8.0, width=3.6):
    top = [(length * i / 16, width / 2 * math.sin(math.pi * i / 16)) for i in range(17)]
    return Polygon(top + [(x, -y) for x, y in reversed(top[1:-1])])


def satin(points, width):
    """Centre run out, then a zigzag column back along the same path."""
    line = LineString(points)
    n = max(2, int(line.length / SATIN_STEP))
    out = run_along(list(line.coords), 2.0)
    for i in range(n, -1, -1):
        p = line.interpolate(i / n, normalized=True)
        q = line.interpolate(min(1, (i + 0.5) / n), normalized=True)
        r = line.interpolate(max(0, (i - 0.5) / n), normalized=True)
        tx, ty = q.x - r.x, q.y - r.y
        d = math.hypot(tx, ty) or 1
        side = width / 2 if i % 2 else -width / 2
        out.append((p.x - ty / d * side, p.y + tx / d * side))
    return out


def build():
    w, h = HOOP_W - 2 * MARGIN, HOOP_H - 2 * MARGIN
    a, b = w / 2 - BAND, h / 2 - BAND
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

    waves = round(L / 34)

    def vine_point(s):
        (x, y), _, (nx, ny) = frame(s)
        off = WAVE_AMP * math.sin(2 * math.pi * waves * s / L)
        return (x + nx * off, y + ny * off)

    # Skulls: corners lean outward but stay upright; top and bottom centre are straight.
    c = CORNER_R * (1 - 1 / math.sqrt(2))
    skulls = [((0, b), 0), ((0, -b), 0)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            skulls.append(((sx * (a - c), sy * (b - c)), -35 * sx))
    skull_shapes = [translate(rotate(skull(), rot, origin=(0, 0)), x, y) for (x, y), rot in skulls]
    skull_s = [ring.project(Point(xy)) for xy, _ in skulls]

    # Flowers sit on the vine between the skulls, alternating around the loop.
    spots = [(sx * x, sy * b) for x in (27, 54) for sx in (-1, 1) for sy in (-1, 1)]
    spots += [(sx * a, y) for y in (-26, 0, 26) for sx in (-1, 1)]
    flower_s = sorted(ring.project(Point(xy)) for xy in spots)
    flowers = [translate(rotate(flower(), 20 * i, origin=(0, 0)), *vine_point(s)) for i, s in enumerate(flower_s)]

    # Solid outlines (eye holes and flower centres filled in), so no vine shows through a hole.
    motifs = unary_union([Polygon(g.exterior) for g in skull_shapes + flowers])

    # Green: vine pieces between motifs, curls beside each skull, leaves on the wave peaks.
    green = []  # (s, kind, geometry)
    vine = LineString([vine_point(L * i / 1600) for i in range(1601)])
    pieces = vine.difference(motifs.buffer(0.6))
    for piece in getattr(pieces, "geoms", [pieces]):
        if piece.length > 3:
            green.append((ring.project(Point(piece.coords[0])), "satin", (list(piece.coords), VINE_W)))

    curl_s = []
    for s0 in skull_s:
        for k, side in ((-13, 1), (13, -1)):
            s = (s0 + k) % L
            curl_s.append(s)
            (_, _), _, (nx, ny) = frame(s)
            vx, vy = vine_point(s)
            cx, cy = vx + nx * side * 5.5, vy + ny * side * 5.5
            a0 = math.atan2(vy - cy, vx - cx)
            pts = []
            for i in range(41):
                t = i / 40
                r = 5.5 - 4.5 * t
                ang = a0 + side * (1 if k > 0 else -1) * 2.6 * math.pi * t
                pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
            # Keep only the part of the curl that shows, so nothing stitches under a motif.
            shown = LineString(pts).difference(motifs.buffer(0.8))
            shown = max(getattr(shown, "geoms", [shown]), key=lambda g: g.length)
            if shown.length > 6:
                green.append((s, "satin", (list(shown.coords), CURL_W)))

    def near(s, others, gap):
        return any(min(abs(s - o), L - abs(s - o)) < gap for o in others)

    for i in range(2 * waves):
        s = L * (i + 0.5) / (2 * waves)
        if near(s, skull_s, 12) or near(s, flower_s, 9) or near(s, curl_s, 6):
            continue
        (_, _), (tx, ty), (nx, ny) = frame(s)
        side = 1 if i % 2 == 0 else -1
        ang = math.degrees(math.atan2(ny * side, nx * side)) - 40 * side
        shape = translate(rotate(leaf(), ang, origin=(0, 0)), *vine_point(s))
        green.append((s, "fill", (shape, ang + 90)))
    # A pair of small leaves tucked beside each flower.
    for s in flower_s:
        (_, _), (tx, ty), (nx, ny) = frame(s)
        fx, fy = vine_point(s)
        for fwd, side in ((1, 1), (-1, -1)):
            ang = math.degrees(math.atan2(ty * fwd, tx * fwd)) + 50 * side * fwd * (1 if nx * ty - ny * tx < 0 else -1)
            dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            shape = translate(rotate(leaf(6.5, 3.2), ang, origin=(0, 0)), fx + dx * 5.2, fy + dy * 5.2)
            shape = shape.difference(motifs.buffer(0.5))
            if shape.geom_type == "Polygon" and shape.area > 8:
                green.append((s, "fill", (shape, ang + 90)))
    green.sort(key=lambda g: g[0])

    st = Stitcher()

    def start_color(color, first=False):
        st.p.add_thread({"color": color[0], "description": color[1]})
        st.p.threadlist[-1].catalog_number = ""
        if not first:
            st.p.add_command(pyembroidery.COLOR_BREAK)

    def stitch_fill(shape, angle):
        st.pos = None
        first = True
        for path in underlay(shape) + fill_rows(shape, angle):
            if len(path) >= 2:
                st.path(path, tie_in=first)
                first = False
        st.end_block()

    start_color(GREEN, first=True)
    for _, kind, data in green:
        if kind == "fill":
            stitch_fill(*data)
        else:
            st.pos = None
            st.path(satin(*data), tie_in=True)
            st.end_block()

    for color, group in ((PINK, flowers[0::2]), (WHITE, flowers[1::2])):
        start_color(color)
        for i, f in enumerate(group):
            stitch_fill(f, 45 if i % 2 else -45)

    start_color(BLACK)
    order = sorted(range(len(skull_shapes)), key=lambda i: skull_s[i])
    for i in order:
        stitch_fill(skull_shapes[i], 0)
    for s in flower_s:  # flower centres
        stitch_fill(Point(vine_point(s)).buffer(1.5, 16), 0)
    st.p.add_command(pyembroidery.END)
    return st.p


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pattern = build()
    base = os.path.join(OUT_DIR, "skull-flower-border")
    write_pes(pattern, base + ".pes", "Skull Border")
    x0, y0, x1, y1 = pattern.bounds()
    print(f"size {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm "
          f"({(x1 - x0) / 254:.2f} x {(y1 - y0) / 254:.2f} in), "
          f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} colors")
