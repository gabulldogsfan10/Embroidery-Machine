"""Trace the cardinal-and-reflection line drawing into a vector (SVG) and a Brother PES.

The drawing (art/cardinal-reflection-drawing.jpg) is split into its flat colors.
Each color becomes filled shapes; the dark outlines are thinned to their centre
lines and stitched as a doubled running stitch. The white window frame is left
as bare fabric. The design is scaled so its outer ring is 4.5 inches across,
for stitching in a 5x7 hoop and displaying in a round one.

Stitch order: cream, gray, red, orange, black, dark red -- five thread changes.

Usage:
    python3 tools/trace_cardinal_drawing.py
"""

import math
import os

import cv2
import numpy as np
import pyembroidery
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from skimage.morphology import skeletonize

import make_text_pattern
from make_cardinal_designs import preview
from make_text_pattern import HERE, OUT_DIR, Stitcher, fill_rows, underlay, write_pes

ART = os.path.join(HERE, "..", "art", "cardinal-reflection-drawing.jpg")
UP = 2                                       # the drawing is enlarged this much before tracing, for smoother curves
CX, CY, RING_PX = 511.5 * UP, 513.0 * UP, 456.5 * UP      # centre and radius of the outer ring, in pixels
MM = 57.0 / RING_PX                          # millimetres per pixel: the ring becomes 114 mm (4.5 in) across
STEP = 1.7                                   # outline stitch length, mm

# Thread colors chosen for a real cardinal rather than the drawing's orange one.
CREAM = (0xF0E4BE, "Cream")
GRAY = (0x8E9196, "Gray")
RED = (0xD3222A, "Red")
DARK_RED = (0x8E1B22, "Dark Red")
ORANGE = (0xF28C28, "Orange")
BLACK = (0x000000, "Black")
EYES = [(403 * UP, 444 * UP), (578 * UP, 446 * UP)]      # pixel positions of the two eyes


def to_mm(x, y):
    return ((x - CX) * MM, -(y - CY) * MM)


def classify():
    """Label every pixel: 0 bare, 1 cream, 2 gray, 3 outline, 4 face mask, 5 shading, 6 body, 7 beak."""
    im = cv2.imread(ART)
    im = cv2.resize(im, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    im = cv2.bilateralFilter(im, 9, 40, 9)
    gray_im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
    s, v = hsv[..., 1], hsv[..., 2]
    yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]]
    inside = (xx - CX) ** 2 + (yy - CY) ** 2 < (RING_PX + 4) ** 2
    cls = np.zeros(im.shape[:2], np.uint8)
    # An outline is anything clearly darker than what surrounds it, so faint pencil-gray lines count too.
    blackhat = cv2.morphologyEx(gray_im, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23)))
    dark = (((v < 150) & (s < 110)) | ((blackhat > 42) & (s < 110))) & inside
    # The soft edge of every outline reads as gray, so gray only counts away from the outlines.
    near_dark = cv2.dilate(dark.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    gray = (v >= 165) & (v < 222) & (s < 40) & inside & ~near_dark
    gray = cv2.morphologyEx(gray.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
    cls[(v > 225) & (rgb[..., 0] - rgb[..., 2] > 14) & (s < 60) & inside] = 1
    cls[gray] = 2
    cls[dark] = 3
    vivid = (s > 110) & inside
    # Bird colors, matched to the nearest of the drawing's own: maroon, red, and two oranges.
    refs = np.array([[114, 27, 18], [188, 53, 41], [233, 102, 43], [213, 107, 63]], np.float32)
    nearest = np.argmin(((rgb[vivid][:, None, :] - refs[None]) ** 2).sum(2), axis=1)
    cls[vivid] = np.array([4, 5, 6, 7], np.uint8)[nearest]
    # The lighter orange is the beak only where it sits beside an eye; elsewhere it is body.
    n, labels, _, centres = cv2.connectedComponentsWithStats((cls == 7).astype(np.uint8), connectivity=8)
    for k in range(1, n):
        if min(math.dist(centres[k], e) for e in EYES) > 62 * UP:
            cls[labels == k] = 6
    # The birds are outlined in maroon, not black. Broad maroon areas (the face masks) stay as
    # fills; anything thin is an outline or a feather line and joins the outlines.
    maroon = (cls == 4).astype(np.uint8)
    broad = cv2.dilate(cv2.erode(maroon, np.ones((13, 13), np.uint8)), np.ones((17, 17), np.uint8)) & maroon
    cls[(maroon > 0) & (broad == 0)] = 3
    return cls


def smooth(ring, rounds=2):
    """Round off the pixel steps in an outline."""
    pts = list(ring.coords)[:-1]
    for _ in range(rounds):
        pts = [q for a, b in zip(pts, pts[1:] + pts[:1])
               for q in ((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25), (a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))]
    return pts


def shapes(mask, grow=7, min_area=1.0):
    """Filled regions of a pixel mask as polygons in mm, grown slightly to tuck under the outlines."""
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))     # drop specks
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))                     # heal pinholes
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, c in enumerate(contours):
        if hierarchy[0][i][3] != -1 or len(c) < 4:
            continue
        holes, j = [], hierarchy[0][i][2]
        while j != -1:
            if len(contours[j]) >= 4:
                holes.append([to_mm(*p[0]) for p in contours[j]])
            j = hierarchy[0][j][0]
        poly = Polygon([to_mm(*p[0]) for p in c], holes).buffer(0).simplify(0.15)
        for g in getattr(poly, "geoms", [poly]):
            if g.area < min_area:
                continue
            g = Polygon(smooth(g.exterior), [smooth(h) for h in g.interiors if Polygon(h).area > 0.8]).buffer(0)
            g = max(getattr(g, "geoms", [g]), key=lambda q: q.area)
            if g.area >= min_area:
                out.append(g)
    return out


def outlines(mask, min_len=3.0):
    """Centre lines of the dark outlines. Each connected set of lines becomes one continuous
    route that goes out along every branch and back, so it is stitched twice with no trims."""
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))    # join hairline breaks
    skel = skeletonize(mask > 0)
    # Each centre-line pixel is nudged to the average of its neighbours on the line, which irons out pixel steps.
    f = skel.astype(np.float32)
    yy, xx = np.mgrid[0:f.shape[0], 0:f.shape[1]].astype(np.float32)
    weight = cv2.blur(f, (9, 9)) + 1e-9
    sx, sy = cv2.blur(f * xx, (9, 9)) / weight, cv2.blur(f * yy, (9, 9)) / weight
    at = lambda p: to_mm(float(sx[p]), float(sy[p]))
    n, labels = cv2.connectedComponents(skel.astype(np.uint8), connectivity=8)
    routes = []
    for k in range(1, n):
        pix = set(zip(*np.where(labels == k)))
        if len(pix) * MM < min_len:
            continue
        nbrs = lambda p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (p[0] + dy, p[1] + dx) in pix]
        start = next((p for p in pix if len(nbrs(p)) == 1), next(iter(pix)))
        stack, seen, walk = [start], {start}, [start]
        while stack:
            nxt = next((q for q in nbrs(stack[-1]) if q not in seen), None)
            if nxt is None:
                stack.pop()
                if stack:
                    walk.append(stack[-1])
            else:
                seen.add(nxt); stack.append(nxt); walk.append(nxt)
        # Thin the pixel-by-pixel walk to stitch-length steps, keeping every turning-back point.
        pts = [at(walk[0])]
        for i in range(1, len(walk) - 1):
            p = at(walk[i])
            if walk[i - 1] == walk[i + 1] or math.dist(p, pts[-1]) >= STEP:
                if math.dist(p, pts[-1]) > 0.25:
                    pts.append(p)
        pts.append(at(walk[-1]))
        routes.append(pts)
    # Stitch neighbouring routes one after another.
    ordered, pos = [], (0.0, 60.0)
    while routes:
        i = min(range(len(routes)), key=lambda j: math.dist(pos, routes[j][0]))
        ordered.append(routes.pop(i)); pos = ordered[-1][-1]
    return ordered


def design():
    cls = classify()
    # Stitches on the birds run from head toward tail, the way the feathers lie.
    layers = [(CREAM, shapes(cls == 1), 75, 0.5), (GRAY, shapes(cls == 2, min_area=5.0), 90, 0.5), (RED, shapes(cls == 6), -42, 0.4),
              (ORANGE, shapes(cls == 7), 10, 0.4), (BLACK, shapes(cls == 4), 80, 0.4), (DARK_RED, shapes(cls == 5), -30, 0.4)]
    # Outlines on a bird are stitched in dark red, so they read as shading and feather edges;
    # the window's outlines, the ring and the legs are gray.
    birds = unary_union([g for layer in layers[2:] for g in layer[1]]).buffer(0.7)
    on_bird, off_bird = [], []
    for route in outlines(cls == 3):
        run, flag = [], None
        for q in route + [None]:
            inside = birds.contains(Point(q)) if q is not None else None
            if inside != flag and run:
                if len(run) >= 2:
                    (on_bird if flag else off_bird).append(run)
                run = run[-1:] if q is not None else []
            if q is not None:
                run.append(q); flag = inside
    # Scraps shorter than 3 mm only add a trim and a thread tail, so leave them out.
    length = lambda r: sum(math.dist(p, q) for p, q in zip(r, r[1:]))
    return layers, ([r for r in off_bird if length(r) >= 3.0], [r for r in on_bird if length(r) >= 3.0])


def digitize(layers, lines):
    off_bird, on_bird = lines
    extra = {GRAY[1]: off_bird, DARK_RED[1]: on_bird}
    st = Stitcher()
    normal = make_text_pattern.FILL_SPACING
    for i, ((rgb, name), polys, angle, spacing) in enumerate(layers):
        st.p.add_thread({"color": rgb, "description": name})
        st.p.threadlist[-1].catalog_number = ""
        if i:
            st.p.add_command(pyembroidery.COLOR_BREAK)
        make_text_pattern.FILL_SPACING = spacing
        polys = sorted(polys, key=lambda g: (round(g.centroid.x / 25), g.centroid.y))
        for g in polys:
            st.pos, first, st.shape = None, True, g
            for path in underlay(g) + fill_rows(g, angle):
                if len(path) >= 2:
                    st.path(path, tie_in=first)
                    first = False
            if not first:
                st.end_block()
        for pts in extra.get(name, []):
            st.pos, st.shape = None, None
            st.path(pts, tie_in=True)
            st.end_block()
        if name == BLACK[1]:
            for ex, ey in EYES:                       # each eye is a small solid dot
                dot = Point(to_mm(ex, ey)).buffer(0.75, 8)
                st.pos, st.shape = None, dot
                st.path([q for row in fill_rows(dot, 0) for q in row], tie_in=True)
                st.end_block()
    make_text_pattern.FILL_SPACING = normal
    st.p.add_command(pyembroidery.END)
    return st.p


def write_svg(layers, lines, path):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="120mm" viewBox="-60 -60 120 120">']
    for (rgb, _), polys, _, _ in layers:
        for g in polys:
            d = " ".join("M" + " L".join(f"{x:.2f},{-y:.2f}" for x, y in r.coords) + " Z" for r in [g.exterior] + list(g.interiors))
            out.append(f'  <path d="{d}" fill="#{rgb:06x}" fill-rule="evenodd"/>')
    for group, (rgb, _) in zip(lines, (GRAY, DARK_RED)):
        for pts in group:
            out.append('  <polyline points="' + " ".join(f"{x:.2f},{-y:.2f}" for x, y in pts) + f'" fill="none" stroke="#{rgb:06x}" stroke-width="0.35"/>')
    for ex, ey in EYES:
        x, y = to_mm(ex, ey)
        out.append(f'  <circle cx="{x:.2f}" cy="{-y:.2f}" r="0.75" fill="#000"/>')
    with open(path, "w") as f:
        f.write("\n".join(out + ["</svg>", ""]))


def compare(layers, lines, path):
    """The vector drawn beside the original drawing."""
    from PIL import Image, ImageDraw
    k, size = 9.0, 1100                               # pixels per mm
    im = Image.new("RGB", (size, size), (252, 251, 247))
    d = ImageDraw.Draw(im)
    px = lambda q: (size / 2 + q[0] * k, size / 2 - q[1] * k)
    for (rgb, _), polys, _, _ in layers:
        for g in polys:
            d.polygon([px(q) for q in g.exterior.coords], fill="#%06x" % rgb)
            for h in g.interiors:
                d.polygon([px(q) for q in h.coords], fill=(252, 251, 247))
    for group, (rgb, _) in zip(lines, (GRAY, DARK_RED)):
        for pts in group:
            d.line([px(q) for q in pts], fill="#%06x" % rgb, width=3)
    for ex, ey in EYES:
        x, y = px(to_mm(ex, ey))
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(0, 0, 0))
    orig = Image.open(ART).convert("RGB").resize((size, size))
    sheet = Image.new("RGB", (size * 2 + 20, size), "white")
    sheet.paste(orig, (0, 0)); sheet.paste(im, (size + 20, 0))
    sheet.save(path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    layers, lines = design()
    base = os.path.join(OUT_DIR, "cardinal-reflection")
    write_svg(layers, lines, base + ".svg")
    compare(layers, lines, base + "-vector-check.png")
    write_pes(digitize(layers, lines), base + ".pes", "Cardinal mirror")
    pattern = pyembroidery.read(base + ".pes")
    preview(pattern, base + ".png")
    x0, y0, x1, y1 = pattern.bounds()
    counts = [0]
    for s in pattern.stitches:
        if s[2] & 0xFF == pyembroidery.COLOR_CHANGE:
            counts.append(0)
        elif s[2] & 0xFF == pyembroidery.STITCH:
            counts[-1] += 1
    trims = sum(1 for s in pattern.stitches if s[2] & 0xFF == pyembroidery.TRIM)
    print(f"cardinal-reflection: {(x1 - x0) / 10:.1f} x {(y1 - y0) / 10:.1f} mm, {pattern.count_stitches()} stitches, {trims} trims")
    print(list(zip([t.description for t in pattern.threadlist], counts)), "outline runs:", len(lines[0]) + len(lines[1]))
