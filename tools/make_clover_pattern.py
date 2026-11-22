"""Generate the Henderson / est. 2007 lettering with two small four-leaf clovers.

The clovers sit on the second line, one on each side of "est. 2007", and the
line is centred under "Henderson". Each clover is four heart-shaped leaves around a small
centre gap plus a short tapering stem that starts where the leaves end. The
stitch rows run the length of each leaf, so the four leaves read separately. Stitch order: "Henderson", right clover, left clover, "est. 2007" -- three colors, so the
machine stops twice for thread changes.

Writes a DST (Poolin) and a PES with Brother thread colors (Brother SE2000).

Usage:
    python3 tools/make_clover_pattern.py
"""

import math
import os

import pyembroidery
from shapely.affinity import rotate, scale, translate
from shapely.geometry import Polygon
from shapely.ops import unary_union

from make_text_pattern import OUT_DIR, layout_lines, stitch, write_dst, write_pes

# Thread colors, in stitch order: "Henderson", clovers, "est. 2007".
POOLIN_COLORS = [(0x1E5631, "Forest green"), (0x2E8B3A, "Kelly green"), (0x8B6B2E, "Old gold")]
# Brother embroidery thread chart colors, so the SE2000 names them on screen.
BROTHER_COLORS = [(0x00673E, "Emerald Green"), (0x66BA49, "Leaf Green"), (0xBA9800, "Brass")]

# All sizes in millimetres.
LEAF_LENGTH = 5.0       # centre to the top of a leaf's lobes
LEAF_WIDTH = 1.0        # leaf width as a share of its length
CENTER_GAP = 0.3        # leaves start this far out from the centre
STEM_WIDTH = 1.2
CLOVER_SPACE = 3.2      # space between each clover and "est. 2007"


def heart_leaf():
    """A heart pointing down: tip at (0, CENTER_GAP), two rounded lobes with a notch between them at the top."""
    pts = []
    for k in range(96):
        t = 2 * math.pi * k / 96
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 29 * LEAF_LENGTH * LEAF_WIDTH, CENTER_GAP + (y + 17) / 29 * LEAF_LENGTH))
    return Polygon(pts).buffer(0)


def stem():
    """A stem that tapers as it curves down and to the right from the centre."""
    left, right = [], []
    for i in range(21):
        t = i / 20
        x, y = 2.6 * t ** 1.8, -7.0 * t
        dx, dy = 2.6 * 1.8 * t ** 0.8, -7.0
        d = math.hypot(dx, dy)
        h = (STEM_WIDTH - 0.5 * t) / 2
        left.append((x - dy / d * h, y + dx / d * h))
        right.append((x + dy / d * h, y - dx / d * h))
    return Polygon(left + right[::-1]).buffer(0)


def clover():
    """Return [(shape, fill_angle), ...]: the four leaves, then the stem."""
    leaf = heart_leaf()
    # Leaves on the diagonals, like the classic St. Patrick's Day clover. The
    # stitch rows run the length of each leaf, out from the centre, so the four
    # leaves catch the light differently and read as separate.
    leaves = [(rotate(leaf, a - 90, origin=(0, 0)), a) for a in (45, 135, 225, 315)]
    # Only stitch the stem where it shows, so no area gets two layers of thread.
    covered = unary_union([s for s, _ in leaves]).buffer(0.3)
    parts = stem().difference(covered)
    visible = max(getattr(parts, "geoms", [parts]), key=lambda g: g.area)
    return leaves + [(visible, 0)]


def build(colors=POOLIN_COLORS):
    henderson, est = layout_lines()
    # Centre each clover's leaves on the middle of the "est. 2007" letters:
    # one to the left, and a mirror image (stem curving the other way) to the
    # right.
    items = clover()
    leaves = unary_union([sh for sh, _ in items[:-1]]).bounds
    ex0, ey0, ex1, ey1 = unary_union(est).bounds
    dy = (ey0 + ey1) / 2
    left = [(translate(sh, ex0 - CLOVER_SPACE - leaves[2], dy), a) for sh, a in items]
    right = [(translate(scale(sh, -1, 1, origin=(0, 0)), ex1 + CLOVER_SPACE - leaves[0], dy), -a)
             for sh, a in items]
    # "Henderson" ends on the right, so stitch the right clover first, then
    # the left one, which leaves the needle next to the start of "est. 2007".
    clovers = right + left

    # Re-centre the clover + "est. 2007" + clover line under "Henderson".
    line = unary_union([sh for sh, _ in clovers] + est).bounds
    shift = -(line[0] + line[2]) / 2
    clovers = [(translate(sh, shift, 0), a) for sh, a in clovers]
    est = [translate(sh, shift, 0) for sh in est]

    return stitch([
        (*colors[0], [(sh, 45) for sh in henderson]),
        (*colors[1], clovers),
        (*colors[2], [(sh, 45) for sh in est]),
    ])


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pattern, (w, h) = build()
    base = os.path.join(OUT_DIR, "henderson-est-2007-clover")
    write_dst(pattern, base + ".dst", "Henderson Clover")
    pyembroidery.write_png(pattern, base + ".png")
    print(f"size {w:.1f} x {h:.1f} mm, {pattern.count_stitches()} stitches")

    # Brother (e.g. SE2000) version, with Brother thread colors.
    pattern, _ = build(BROTHER_COLORS)
    write_pes(pattern, base + ".pes", "Henderson Clover")
    pyembroidery.write_png(pattern, base + "-brother.png")
