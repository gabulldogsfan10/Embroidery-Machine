"""Draw an original barbed-wire frame as a vector (SVG) and digitize it (Brother PES).

A portrait frame meant to go around lettering that is already stitched. Two
strands twist around each other along a rounded rectangle; barbs (four slanted
wraps and four tapering spikes) sit at each corner, twice along the top and
bottom and three times down each side. Everything stays inside a half-inch band
at the edge of the stitch field.

The same geometry is written twice: as filled outlines in an SVG, and as satin
columns in a PES. Stitch order: gray wire, then black barbs -- one thread change.

Usage:
    python3 tools/make_barbed_wire_frame.py
"""

import math
import os

import pyembroidery
from shapely.geometry import LineString, Point, box

from make_barbed_border import satin
from make_skull_border import IN, preview
from make_text_pattern import OUT_DIR, Stitcher, write_pes

MARGIN = 1.5          # clear space inside the stitch field edge
REACH = 5.4           # how far a spike stands off the wire; band = MARGIN + 2 * REACH = 12.3 mm
CORNER_R = 9.0
TWIST = 13.0          # approximate length of one full twist of the two strands
STRAND_SWAY = 0.75    # how far each strand swings off the centreline
WRAP_HALF = 2.9       # half the length of a barb's coil along the wire

GRAY = (0x6E7278, "Gray")
BLACK = (0x000000, "Black")

# name -> stitch field (width, height) in mm, portrait.
VARIANTS = {
    "barbed-wire-frame-5x7": (130.0, 180.0),
    "barbed-wire-frame-6.25x8.5": (6.25 * IN, 8.5 * IN),
}


def envelope(points, width):
    """Outline of a satin column: the centre path thickened by its width function."""
    wfun = width if callable(width) else (lambda t: width)
    line = LineString(points)
    n = max(8, int(line.length / 0.5))
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        p = line.interpolate(t, normalized=True)
        q = line.interpolate(min(1, t + 0.01), normalized=True)
        r = line.interpolate(max(0, t - 0.01), normalized=True)
        tx, ty = q.x - r.x, q.y - r.y
        d = math.hypot(tx, ty) or 1
        h = wfun(t) / 2
        left.append((p.x - ty / d * h, p.y + tx / d * h))
        right.append((p.x + ty / d * h, p.y - tx / d * h))
    return left + right[::-1]


def design(field_w, field_h):
    """Return (wire, barbs): lists of (centre path, width) columns in mm, y up."""
    inset = MARGIN + REACH
    a, b = field_w / 2 - inset, field_h / 2 - inset
    ring = box(-(a - CORNER_R), -(b - CORNER_R), a - CORNER_R, b - CORNER_R).buffer(CORNER_R, 32).exterior
    L = ring.length

    def frame(s):
        p, q = ring.interpolate(s % L), ring.interpolate((s + 0.5) % L)
        tx, ty = q.x - p.x, q.y - p.y
        d = math.hypot(tx, ty)
        tx, ty = tx / d, ty / d
        nx, ny = ty, -tx
        if nx * p.x + ny * p.y < 0:
            nx, ny = -nx, -ny
        return (p.x, p.y), (tx, ty), (nx, ny)

    # Barbs: one on each corner, two along the top and bottom, three down each side.
    k = CORNER_R * (1 - 1 / math.sqrt(2))
    corners = sorted(ring.project(Point(sx * (a - k), sy * (b - k))) for sx in (-1, 1) for sy in (-1, 1))
    barb_s = list(corners)
    for i, c0 in enumerate(corners):
        c1 = corners[(i + 1) % 4] + (L if i == 3 else 0)
        mid = ring.interpolate(((c0 + c1) / 2) % L)
        n = 2 if abs(abs(mid.y) - b) < 1 else 3
        barb_s += [(c0 + (c1 - c0) * (j + 1) / (n + 1)) % L for j in range(n)]
    barb_s.sort()

    # Wire: two strands swaying in opposite directions; each is thicker where it passes in front.
    turns = round(L / TWIST)
    phase = lambda s: 2 * math.pi * turns * s / L
    wire = []
    for sign in (1, -1):
        for i, s0 in enumerate(barb_s):
            s1 = barb_s[(i + 1) % len(barb_s)] + (L if i == len(barb_s) - 1 else 0)
            lo, hi = s0 + WRAP_HALF - 0.6, s1 - WRAP_HALF + 0.6
            n = int((hi - lo) / 0.5)
            pts = []
            for j in range(n + 1):
                s = lo + (hi - lo) * j / n
                (x, y), _, (nx, ny) = frame(s)
                off = sign * STRAND_SWAY * math.sin(phase(s))
                pts.append((x + nx * off, y + ny * off))
            width = lambda t, lo=lo, hi=hi, sign=sign: 1.05 + 0.5 * max(0.0, sign * math.cos(phase(lo + (hi - lo) * t)))
            wire.append((pts, width))

    barbs = []
    for s in barb_s:
        (x, y), (ux, uy), (vx, vy) = frame(s)
        at = lambda al, ac: (x + ux * al + vx * ac, y + uy * al + vy * ac)
        for j in range(4):  # the coil: four slanted wraps
            al = -2.4 + 1.6 * j
            barbs.append(([at(al - 0.75, -2.0), at(al + 0.75, 2.0)], 1.2))
        taper = lambda t: 1.55 - 1.2 * t
        for end in (-1, 1):  # two spikes cross at each end of the coil
            for up in (-1, 1):
                barbs.append(([at(end * 2.3, -up * 1.0), at(end * (WRAP_HALF + 2.5), up * REACH)], taper))
    return wire, barbs


def write_svg(wire, barbs, field_w, field_h, path):
    def poly(column, color):
        pts = " ".join(f"{x + field_w / 2:.2f},{field_h / 2 - y:.2f}" for x, y in envelope(*column))
        return f'  <polygon points="{pts}" fill="{color}"/>'
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{field_w}mm" height="{field_h}mm" '
             f'viewBox="0 0 {field_w} {field_h}">']
    lines += [poly(c, "#6e7278") for c in wire] + [poly(c, "#000000") for c in barbs]
    with open(path, "w") as f:
        f.write("\n".join(lines + ["</svg>", ""]))


def digitize(wire, barbs):
    st = Stitcher()
    for i, (color, columns) in enumerate(((GRAY, wire), (BLACK, barbs))):
        st.p.add_thread({"color": color[0], "description": color[1]})
        st.p.threadlist[-1].catalog_number = ""
        if i:
            st.p.add_command(pyembroidery.COLOR_BREAK)
        for pts, width in columns:
            st.pos = None
            st.path(satin(pts, width), tie_in=True)
            st.end_block()
    st.p.add_command(pyembroidery.END)
    return st.p


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (fw, fh) in VARIANTS.items():
        base = os.path.join(OUT_DIR, name)
        wire, barbs = design(fw, fh)
        write_svg(wire, barbs, fw, fh, base + ".svg")
        write_pes(digitize(wire, barbs), base + ".pes", "Barbed Wire")
        pattern = pyembroidery.read(base + ".pes")
        preview(pattern, fw, fh, base + ".png")
        x0, y0, x1, y1 = pattern.bounds()
        print(f"{name}: {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm in a {fw:.1f} x {fh:.1f} field, "
              f"{pattern.count_stitches()} stitches, {len(pattern.threadlist)} colors, {len(barbs) // 8} barbs")
