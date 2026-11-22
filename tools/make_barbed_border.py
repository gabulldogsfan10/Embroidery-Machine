"""Generate an original barbed-wire frame with skull-and-moon corners (Brother PES).

A portrait frame meant to go around lettering that is already stitched. The
sides are a single strand of barbed wire that stays inside a half-inch band at
the edge of the stitch field. Each corner has a black skull with orange eyes
in front of a yellow moon, with tapering black swirls running along both arms
and curling in toward the middle.

Stitch order: yellow, orange, black -- the machine stops twice.

Usage:
    python3 tools/make_barbed_border.py
"""

import math
import os

import pyembroidery
from shapely.affinity import scale, translate
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from make_skull_border import BAND, IN, preview, resample, skull
from make_text_pattern import OUT_DIR, Stitcher, fill_rows, underlay, write_pes

SATIN_STEP = 0.4
WIRE_INSET = 6.85       # wire centreline, from the field edge
BARB_REACH = 5.2        # how far a barb's spikes stand off the wire
CORNER_ARM = 34.0       # the corner motif owns this much of each side
SKULL_INSET = 13.0

# Brother embroidery thread chart colors.
YELLOW = (0xFFD911, "Harvest Gold")
ORANGE = (0xFE9900, "Orange")
BLACK = (0x000000, "Black")

# name -> stitch field (width, height) in mm, portrait.
VARIANTS = {
    "barbed-wire-skull-frame-5x7": (130.0, 180.0),
    "barbed-wire-skull-frame-6.25x8.5": (6.25 * IN, 8.5 * IN),
}


def satin(points, width):
    """Centre run out, then a zigzag column back. width is mm, or a function of 0..1."""
    wfun = width if callable(width) else (lambda t: width)
    line = LineString(points)
    n = max(2, int(line.length / SATIN_STEP))
    out = resample(points, 2.0)
    for i in range(n, -1, -1):
        p = line.interpolate(i / n, normalized=True)
        q = line.interpolate(min(1, (i + 0.5) / n), normalized=True)
        r = line.interpolate(max(0, (i - 0.5) / n), normalized=True)
        tx, ty = q.x - r.x, q.y - r.y
        d = math.hypot(tx, ty) or 1
        side = wfun(i / n) / 2 * (1 if i % 2 else -1)
        out.append((p.x - ty / d * side, p.y + tx / d * side))
    return out


def swirl(start, heading, stem, turn, radius=4.5):
    """A stem that sways gently, then winds into a spiral. Returns a point list."""
    x, y = start
    th = math.radians(heading)
    spiral = 2.2 * math.pi * radius * 0.62
    pts, s, step = [(x, y)], 0.0, 0.3
    while s < stem + spiral:
        if s < stem:
            k = -turn * 0.05 * math.cos(2 * math.pi * s / max(stem, 1))
        else:
            t = (s - stem) / spiral
            k = turn / (radius * (1 - 0.8 * t))
        th += k * step
        x, y = x + math.cos(th) * step, y + math.sin(th) * step
        pts.append((x, y))
        s += step
    return pts


def barb(cx, cy, ux, uy):
    """Wrap bars and four spikes for one barb centred on the wire. (ux, uy) runs along the wire."""
    vx, vy = -uy, ux
    at = lambda al, ac: (cx + ux * al + vx * ac, cy + uy * al + vy * ac)
    parts = []
    for k in range(4):  # the coil
        al = -3.3 + 2.2 * k
        parts.append(([at(al - 0.9, -2.3), at(al + 0.9, 2.3)], 1.25))
    taper = lambda t: 1.5 - 1.2 * t
    for end in (-1, 1):  # two spikes at each end of the coil
        for up in (-1, 1):
            parts.append(([at(end * 3.6, 0), at(end * (3.6 + 2.2), up * BARB_REACH)], taper))
    return parts


def build(field_w, field_h):
    hw, hh = field_w / 2, field_h / 2
    fills = {"moon": [], "eyes": [], "skull": []}
    lines = []  # (points, width) in black

    for sx in (-1, 1):
        for sy in (-1, 1):
            ix, iy = -sx, -sy  # pointing in toward the middle
            kx, ky = sx * hw + ix * SKULL_INSET, sy * hh + iy * SKULL_INSET
            sk = translate(scale(skull(), 1.2 * ix, 1.2, origin=(0, 0)), kx, ky)
            solid = Polygon(sk.exterior)
            moon = Point(kx + ix * 6.5, ky + iy * 6.5).buffer(10.5, 48)
            fills["moon"].append(moon.difference(solid.buffer(-0.5)))
            fills["eyes"] += [Polygon(h).buffer(0.25) for h in sk.interiors]
            fills["skull"].append(sk)

            # Swirls: one along each arm, two fanning in past the moon.
            along_x = 0 if ix > 0 else 180
            along_y = 90 if iy > 0 else -90
            diag = math.degrees(math.atan2(iy, ix))
            mirror = ix * iy
            specs = [
                # The arm swirls curl inward, so nothing comes near the field edge.
                ((kx + ix * 8.5, sy * hh + iy * WIRE_INSET), along_x, 13, mirror, 4.6, 2.5),
                ((sx * hw + ix * WIRE_INSET, ky + iy * 9.5), along_y, 11, -mirror, 4.6, 2.5),
                ((kx + ix * 13, ky + iy * 14), diag + 28 * mirror, 7, -mirror, 3.6, 2.0),
                ((kx + ix * 14.5, ky + iy * 11), diag - 30 * mirror, 9, mirror, 3.2, 1.9),
            ]
            for start, heading, stem, turn, radius, base in specs:
                lines.append((swirl(start, heading, stem, turn, radius), lambda t, b=base: b - (b - 0.5) * t))

    # Barbed wire on each side, between the corner motifs.
    runs = [((-hw + CORNER_ARM, sy * (hh - WIRE_INSET)), (hw - CORNER_ARM, sy * (hh - WIRE_INSET))) for sy in (1, -1)]
    runs += [((sx * (hw - WIRE_INSET), -hh + CORNER_ARM), (sx * (hw - WIRE_INSET), hh - CORNER_ARM)) for sx in (-1, 1)]
    for (x0, y0), (x1, y1) in runs:
        length = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        n = max(1, round(length / 30))
        stops = [0.0] + [length * (i + 0.5) / n for i in range(n)] + [length]
        for i, (a, b) in enumerate(zip(stops, stops[1:])):
            a2 = a + (4.2 if i > 0 else 0)
            b2 = b - (4.2 if i < n else 0)
            wire = [(x0 + ux * a2, y0 + uy * a2), (x0 + ux * b2, y0 + uy * b2)]
            bumps = max(1, round((b2 - a2) / 7))
            lines.append((wire, lambda t, k=bumps: 1.3 + 0.8 * math.sin(math.pi * k * t) ** 2))
        for c in stops[1:-1]:
            lines += barb(x0 + ux * c, y0 + uy * c, ux, uy)

    st = Stitcher()

    def start_color(color, first=False):
        st.p.add_thread({"color": color[0], "description": color[1]})
        st.p.threadlist[-1].catalog_number = ""
        if not first:
            st.p.add_command(pyembroidery.COLOR_BREAK)

    def stitch_fill(shape, angle):
        shape = shape.simplify(0.2)
        st.pos = None
        first = True
        for path in underlay(shape) + fill_rows(shape, angle):
            if len(path) >= 2:
                st.path(path, tie_in=first)
                first = False
        st.end_block()

    start_color(YELLOW, first=True)
    for shape in fills["moon"]:
        for part in getattr(shape, "geoms", [shape]):
            stitch_fill(part, 30)
    start_color(ORANGE)
    for shape in fills["eyes"]:
        stitch_fill(shape, 90)
    start_color(BLACK)
    for shape in fills["skull"]:
        stitch_fill(shape, 0)
    # Go round the frame once, so the needle doesn't criss-cross the lettering.
    lines.sort(key=lambda item: math.atan2(item[0][0][1], item[0][0][0]))
    for pts, width in lines:
        st.pos = None
        st.path(satin(pts, width), tie_in=True)
        st.end_block()
    st.p.add_command(pyembroidery.END)
    return st.p


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (fw, fh) in VARIANTS.items():
        base = os.path.join(OUT_DIR, name)
        write_pes(build(fw, fh), base + ".pes", "Barbed Frame")
        pattern = pyembroidery.read(base + ".pes")
        preview(pattern, fw, fh, base + ".png")
        x0, y0, x1, y1 = pattern.bounds()
        print(f"{name}: {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm in a {fw:.1f} x {fh:.1f} field, "
              f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} colors")
