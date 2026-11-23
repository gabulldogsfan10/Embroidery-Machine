"""Two original cardinal-at-the-window designs, drawn as vectors (SVG) and digitized (Brother PES).

Both are composed inside a 4.5 inch circle so they can be stitched in a 5x7
machine hoop and then displayed in a round hoop.

  cardinal-at-window   a cardinal perched on a sill, looking at its reflection in the glass
  cardinal-flying      a cardinal seen from indoors, wings spread, flying at the window

Usage:
    python3 tools/make_cardinal_designs.py
"""

import math
import os

import pyembroidery
from PIL import Image, ImageDraw
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import unary_union

import make_text_pattern
from make_barbed_border import satin
from make_text_pattern import OUT_DIR, Stitcher, fill_rows, underlay, write_pes

R = 57.0                                   # design circle radius, mm (4.5 inches across)
CIRCLE = Point(0, 0).buffer(R, 96)

RED = (0xED171F, "Red")
DARK_RED = (0xA01A24, "Dark Red")
ORANGE = (0xF58220, "Orange")
BLACK = (0x000000, "Black")
GRAY = (0x9A9DA1, "Gray")
PALE_BLUE = (0xA9C8E6, "Pale Blue")
GREEN = (0x66BA49, "Leaf Green")


def blob(points, rounds=3):
    """A smooth closed shape through roughly these points (corner-cutting)."""
    pts = list(points)
    for _ in range(rounds):
        nxt = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            nxt += [(a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25), (a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75)]
        pts = nxt
    return Polygon(pts).buffer(0)


def fill(shape, angle=45, spacing=0.4, edge=True):
    """A filled area. Wider spacing gives a sheer, see-through fill."""
    return ("fill", shape.intersection(CIRCLE), angle, spacing, edge)


def stroke(points, width=None):
    """A line: three passes of running stitch, or a satin column if a width is given."""
    return ("stroke", list(points), width)


def strokes_in(lines, region):
    """Clip straight guide lines to a region and return them as strokes."""
    out = []
    clipped = MultiLineString(lines).intersection(region)
    for g in getattr(clipped, "geoms", [clipped]):
        if g.geom_type == "LineString" and g.length > 2:
            out.append(stroke(g.coords))
    return out


# --------------------------------------------------------------------------
# 1. Perched on the sill, looking at its reflection
# --------------------------------------------------------------------------
def at_window():
    body = blob([(6, 6), (4, -2), (8, -10), (16, -15), (26, -15), (32, -10), (28, -2), (22, 6), (16, 12), (10, 13)])
    head = Point(10, 11).buffer(6.5, 32)
    crest = blob([(7, 15), (11, 20), (16.5, 26), (18, 21), (17, 14)], 2)
    wing = blob([(13, 6), (22, 4), (30, -6), (34, -13), (26, -11), (17, -5), (11, 0)])
    tail = blob([(27, -9), (34, -13), (50, -25.5), (47, -29), (29, -15.5)], 2)
    mask = blob([(3.6, 13.2), (7, 15), (9, 11.5), (7.8, 6.6), (4.6, 6.2), (3.2, 9.5)])
    beak = blob([(4.6, 12.8), (-3.2, 9.6), (4.8, 7.0)], 1)
    red = unary_union([body, head, crest]).difference(wing.buffer(-0.4)).difference(mask.buffer(-0.3))
    bird = unary_union([body, head, crest, wing, tail, beak])
    behind = bird.buffer(-0.4)                      # background stops just under the bird's edge

    # The bird's reflection in the glass: head, crest and chest, facing the real bird.
    r_head = Point(-21, 9.5).buffer(6.2, 32)
    r_crest = blob([(-18, 13.5), (-22, 19), (-27.5, 24), (-28.5, 19), (-27.5, 13)], 2)
    r_beak = blob([(-15.8, 11.5), (-9.2, 8.6), (-16, 6.2)], 1)
    r_chest = blob([(-17, 5), (-15.5, -1), (-17, -6), (-33, -6), (-33, 0), (-28, 6)], 2)
    reflection = unary_union([r_head, r_crest, r_beak, r_chest])

    glass = box(-37, -6, 2, R).difference(reflection).difference(behind)
    frame = [box(-42, -22, -37, R), box(2, -14, 8, R), box(-37, -14, 8, -6), box(30, -22, 36, R)]
    sill = box(-47, -30, 41, -22)
    brick_zone = unary_union([box(36, -30, R, R), box(-R, -22, -42, R), box(-R, -R, R, -31.5)]).intersection(CIRCLE).difference(behind)
    courses = [[(-R, y), (R, y)] for y in range(-52, 58, 10)]
    joints = []
    for i, y in enumerate(range(-52, 58, 10)):
        for x in range(-60 + (i % 2) * 9, 60, 18):
            joints.append([(x, y), (x, y + 10)])

    gray = [fill(g.difference(behind), 0 if g.bounds[2] - g.bounds[0] < 8 else 90) for g in frame]
    gray += [fill(sill.difference(behind), 90)] + strokes_in(courses + joints, brick_zone)
    legs = [stroke([(16.5, -14.5), (15.5, -22)]), stroke([(20, -15), (20.5, -22)]),
            stroke([(12.5, -22.6), (15.5, -22), (18, -22.8)]), stroke([(18, -22.6), (20.5, -22), (23.5, -22.9)])]
    return [
        (PALE_BLUE, [fill(glass, 60, 0.9, False)]),
        (GRAY, gray),
        (RED, [fill(reflection, 45, 0.85, False), fill(red, 35)]),
        (DARK_RED, [fill(wing, -20), fill(tail.difference(body.buffer(-0.3)), -38)]),
        (ORANGE, [fill(beak, 80)]),
        (BLACK, [fill(mask, 70)] + legs),
    ]


# --------------------------------------------------------------------------
# 2. Flying at the window, seen from indoors
# --------------------------------------------------------------------------
def flying():
    body = blob([(-9, 12), (-11, 0), (-8, -10), (0, -15), (8, -11), (12, 0), (11, 12), (2, 17)])
    head = Point(2, 22).buffer(8.2, 40)
    crest = blob([(-3, 28), (2, 33.5), (7, 28)], 2)
    mask = blob([(-3.6, 23.2), (2, 22.2), (7.6, 23.2), (8.6, 17.5), (5, 12.8), (-1, 12.8), (-4.6, 17.5)])
    beak = blob([(-1.6, 22.4), (5.6, 22.4), (2, 15.2)], 1)
    left_wing = blob([(-6, 15), (-12, 23), (-24, 37), (-35, 44), (-31, 31), (-23, 17), (-13, 6), (-8, 5)])
    right_wing = blob([(8, 14), (16, 17), (25, 23), (33, 27), (22, 15), (11, 6)])
    tail = blob([(-3, -10), (6, -10), (23, -33), (20.5, -38.5), (12, -39.5), (6.5, -35.5)], 2)
    core = unary_union([body, head, crest])
    red = core.difference(mask.buffer(-0.3))
    bird = unary_union([core, left_wing, right_wing, tail])
    behind = bird.buffer(-0.4)

    # Window frame: a stile each side and the bottom rail, with leaves and spots of light outside.
    frame = [box(-50, -46, -44, R), box(38, -46, 44, R), box(-R, -46, R, -40)]
    spots = [(-30, 8, 4), (-22, -18, 3.2), (-34, -28, 3), (-12, 44, 3.4), (20, 44, 3), (28, 6, 3.6), (22, -20, 2.6),
             (-36, 24, 2.6), (10, 34, 2.2), (-14, -32, 3.4), (30, -30, 3), (-24, 48, 2.4), (32, 40, 2.8), (-2, -30, 2.4)]
    leaves = box(-44, -40, 38, R).difference(bird.buffer(1.2))
    leaves = leaves.difference(unary_union([Point(x, y).buffer(r, 24) for x, y, r in spots]))

    feathers = [stroke([(-9, 12), q]) for q in ((-33.5, 42), (-30.5, 34), (-26, 25), (-20, 16.5))]
    feathers += [stroke([(9, 12), q]) for q in ((31.5, 26.5), (26, 20), (19, 13.5))]
    feathers += [stroke([(1.5, -13), q]) for q in ((19.5, -35.5), (13, -37.5))]
    feet = []
    for cx, cy in ((-4.5, -7.5), (5.5, -8.5)):
        feet += [stroke([(cx, cy + 2.5), (cx + dx, cy - 1.5)]) for dx in (-1.6, 0, 1.6)]
    eyes = [fill(Point(x, 25.6).buffer(1.1, 12), 0) for x in (-2.2, 6.2)]
    return [
        (GREEN, [fill(leaves, 30, 0.85, False)]),
        (GRAY, [fill(g.difference(behind), 0 if g.bounds[2] - g.bounds[0] < 8 else 90) for g in frame]),
        (RED, [fill(left_wing.difference(core.buffer(-0.3)), 55, 0.7, False), fill(right_wing.difference(core.buffer(-0.3)), -40, 0.7, False), fill(red, 80)]),
        (DARK_RED, [fill(tail.difference(body.buffer(-0.3)), -55)] + feathers[:7]),
        (ORANGE, [fill(beak, 0)]),
        (BLACK, [fill(mask.difference(beak.buffer(-0.2)), 90)] + eyes + feet + feathers[7:]),
    ]


# --------------------------------------------------------------------------
def write_svg(layers, path):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * R + 6}mm" height="{2 * R + 6}mm" viewBox="{-R - 3} {-R - 3} {2 * R + 6} {2 * R + 6}">',
           f'  <circle cx="0" cy="0" r="{R}" fill="none" stroke="#bbbbbb" stroke-width="0.3"/>']
    for (rgb, _), items in layers:
        color = f"#{rgb:06x}"
        for item in items:
            if item[0] == "fill":
                sheer = ' fill-opacity="0.45"' if item[3] > 0.6 else ""
                for g in getattr(item[1], "geoms", [item[1]]):
                    if g.geom_type != "Polygon" or g.is_empty:
                        continue
                    rings = [g.exterior] + list(g.interiors)
                    d = " ".join("M" + " L".join(f"{x:.2f},{-y:.2f}" for x, y in r.coords) + " Z" for r in rings)
                    out.append(f'  <path d="{d}" fill="{color}" fill-rule="evenodd"{sheer}/>')
            else:
                pts = " ".join(f"{x:.2f},{-y:.2f}" for x, y in item[1])
                out.append(f'  <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{item[2] or 0.5}" stroke-linecap="round"/>')
    with open(path, "w") as f:
        f.write("\n".join(out + ["</svg>", ""]))


def digitize(layers):
    st = Stitcher()
    normal = make_text_pattern.FILL_SPACING
    for i, ((rgb, name), items) in enumerate(layers):
        st.p.add_thread({"color": rgb, "description": name})
        st.p.threadlist[-1].catalog_number = ""
        if i:
            st.p.add_command(pyembroidery.COLOR_BREAK)
        for item in items:
            if item[0] == "fill":
                _, shape, angle, spacing, edge = item
                make_text_pattern.FILL_SPACING = spacing
                for g in getattr(shape, "geoms", [shape]):
                    if g.geom_type != "Polygon" or g.area < 0.4:
                        continue
                    g = g.simplify(0.1)
                    st.pos, first = None, True
                    for path in (underlay(g) if edge else []) + fill_rows(g, angle):
                        if len(path) >= 2:
                            st.path(path, tie_in=first)
                            first = False
                    if not first:
                        st.end_block()
            else:
                _, pts, width = item
                run = make_text_pattern.run_along(pts, 2.2)
                st.pos = None
                st.path(satin(pts, width) if width else run + run[-2::-1] + run[1:], tie_in=True)
                st.end_block()
    make_text_pattern.FILL_SPACING = normal
    st.p.add_command(pyembroidery.END)
    return st.p


def preview(pattern, path):
    """Stitches at about thread width, inside the 5x7 field, with the display circle marked."""
    k = 8                                                  # pixels per mm
    w, h = int(130 * k) + 80, int(180 * k) + 80
    im = Image.new("RGB", (w, h), (232, 233, 236))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 40, w - 40, h - 40], fill=(250, 250, 250), outline=(120, 125, 130), width=3)
    d.ellipse([w / 2 - (R + 3) * k, h / 2 - (R + 3) * k, w / 2 + (R + 3) * k, h / 2 + (R + 3) * k], outline=(170, 175, 180), width=3)
    color, prev = 0, None
    for x, y, cmd in pattern.stitches:
        cmd &= 0xFF
        if cmd == pyembroidery.COLOR_CHANGE:
            color, prev = color + 1, None
        elif cmd != pyembroidery.STITCH:
            prev = None
        else:
            pt = (x * k / 10 + w / 2, y * k / 10 + h / 2)
            if prev:
                d.line([prev, pt], fill=pattern.threadlist[color].hex_color(), width=3)
            prev = pt
    im.crop((0, h // 2 - int((R + 12) * k), w, h // 2 + int((R + 12) * k))).save(path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, design in (("cardinal-at-window", at_window), ("cardinal-flying", flying)):
        base = os.path.join(OUT_DIR, name)
        layers = design()
        write_svg(layers, base + ".svg")
        write_pes(digitize(layers), base + ".pes", name.replace("cardinal-", "Cardinal ")[:16])
        pattern = pyembroidery.read(base + ".pes")
        preview(pattern, base + ".png")
        x0, y0, x1, y1 = pattern.bounds()
        print(f"{name}: {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm, {pattern.count_stitches()} stitches, "
              f"colors {[t.description for t in pattern.threadlist]}")
