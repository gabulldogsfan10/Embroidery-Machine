"""Generate the Henderson / est. 2007 lettering with two small four-leaf clovers.

The clovers sit on the second line, one on each side of "est. 2007", and the
line is centred under "Henderson". Each clover is four heart-shaped leaves around a small
centre gap plus a short curved stem that starts where the leaves end. Each
leaf is filled along its own axis so the four leaves read separately in
thread. Stitch order: "Henderson", right clover, left clover, "est. 2007" -- three colors, so the
machine stops twice for thread changes.

Usage:
    python3 tools/make_clover_pattern.py
"""

import os

import pyembroidery
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from make_text_pattern import OUT_DIR, layout_lines, stitch, write_dst

# All sizes in millimetres.
TEXT_COLORS = [(0x1E5631, "Forest green"), (0x8B6B2E, "Old gold")]
CLOVER_COLOR = (0x2E8B3A, "Kelly green")
LEAF_LENGTH = 5.0       # centre to the top of a leaf's lobes
LEAF_LOBE = 1.6         # radius of each of the two lobes of a heart leaf
CENTER_GAP = 0.5        # leaves start this far out from the centre
STEM_WIDTH = 1.0
CLOVER_SPACE = 2.5      # space between each clover and "est. 2007"


def heart_leaf():
    """A heart pointing down: tip at (0, CENTER_GAP), lobes toward +y."""
    cy = LEAF_LENGTH - LEAF_LOBE
    off = LEAF_LOBE * 0.72
    tip = Point(0, CENTER_GAP)
    left = Point(-off, cy).buffer(LEAF_LOBE, 32)
    right = Point(off, cy).buffer(LEAF_LOBE, 32)
    # Each half is the hull of one lobe and the tip, so the notch between the
    # lobes stays open.
    return unary_union([left.union(tip).convex_hull, right.union(tip).convex_hull])


def stem():
    """A gently curved stem from the centre down and to the right."""
    pts = []
    for i in range(21):
        t = i / 20
        pts.append((2.4 * t ** 1.8, -6.5 * t))
    return LineString(pts).buffer(STEM_WIDTH / 2, cap_style=1)


def clover():
    """Return [(shape, fill_angle), ...]: the four leaves, then the stem."""
    leaf = heart_leaf()
    # Leaves on the diagonals, like the classic St. Patrick's Day clover.
    # Fill rows run across each leaf, perpendicular to its axis.
    leaves = [(rotate(leaf, a - 90, origin=(0, 0)), a) for a in (45, 135, 225, 315)]
    # Only stitch the stem where it shows, so no area gets two layers of thread.
    covered = unary_union([s for s, _ in leaves]).buffer(0.3)
    parts = stem().difference(covered)
    visible = max(getattr(parts, "geoms", [parts]), key=lambda g: g.area)
    return leaves + [(visible, 0)]


def build():
    henderson, est = layout_lines()
    # Centre each clover's leaves on the middle of the "est. 2007" letters:
    # one to the left, and a mirror image (stem curving the other way) to the
    # right.
    items = clover()
    leaves = unary_union([sh for sh, _ in items[:4]]).bounds
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
        (*TEXT_COLORS[0], [(sh, 45) for sh in henderson]),
        (*CLOVER_COLOR, clovers),
        (*TEXT_COLORS[1], [(sh, 45) for sh in est]),
    ])


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pattern, (w, h) = build()
    base = os.path.join(OUT_DIR, "henderson-est-2007-clover")
    write_dst(pattern, base + ".dst", "Henderson Clover")
    pyembroidery.write_png(pattern, base + ".png")
    print(f"size {w:.1f} x {h:.1f} mm, {pattern.count_stitches()} stitches")
