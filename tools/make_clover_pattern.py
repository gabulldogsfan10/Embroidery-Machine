"""Generate the Henderson / est. 2007 lettering with a four-leaf clover above it.

The clover is four heart-shaped leaves around a small centre gap plus a curved
stem that starts where the leaves end. Each leaf is filled along its own axis so the four leaves read
separately in thread. Stitch order: clover (one green), "Henderson",
"est. 2007" -- three colors, so the machine stops twice for thread changes.

Usage:
    python3 tools/make_clover_pattern.py
"""

import os

import pyembroidery
from shapely.affinity import rotate
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from make_text_pattern import LINES, OUT_DIR, layout_lines, stitch

# All sizes in millimetres.
CLOVER_COLOR = (0x2E8B3A, "Kelly green")
TEXT_COLORS = [(0x1E5631, "Forest green"), (0x8B6B2E, "Old gold")]
LEAF_LENGTH = 15.0      # centre to the top of a leaf's lobes
LEAF_LOBE = 4.6         # radius of each of the two lobes of a heart leaf
CENTER_GAP = 0.9        # leaves start this far out from the centre
STEM_WIDTH = 1.8
CLOVER_GAP = 6.0        # space between the bottom of the clover and the text


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
        pts.append((9.0 * t ** 1.8, -25.0 * t))
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
    items = clover()
    bottom = unary_union([s for s, _ in items]).bounds[1]
    text = layout_lines(top=bottom - CLOVER_GAP)
    layers = [(*CLOVER_COLOR, items)]
    for (color, name), shapes in zip(TEXT_COLORS, text):
        layers.append((color, name, [(s, 45) for s in shapes]))
    return stitch(layers)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pattern, (w, h) = build()
    base = os.path.join(OUT_DIR, "henderson-est-2007-clover")
    pyembroidery.write_dst(pattern, base + ".dst")
    pyembroidery.write_png(pattern, base + ".png")
    print(f"size {w:.1f} x {h:.1f} mm, {pattern.count_stitches()} stitches")
