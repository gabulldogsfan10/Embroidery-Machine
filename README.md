# Embroidery Machine

Patterns and tools for our Poolin EOC07 and Brother SE2000 embroidery machines.

## Beginner's guides

- **Brother SE2000:** [Brother SE2000 Beginner's Guide](docs/Brother-SE2000-Beginners-Guide.md)
  ([printable PDF](docs/Brother-SE2000-Beginners-Guide.pdf)). Setup, embroidery foot,
  bobbin, threading, hooping, and stitching the Henderson clover patch (PES file).
- **Brother SE2000, animated:** [walkthrough/SE2000-First-Stitch.html](walkthrough/SE2000-First-Stitch.html),
  an interactive step-by-step walkthrough that plays like a video.
- **Poolin EOC07:** [Poolin EOC07 Beginner's Guide](docs/Poolin-EOC07-Beginners-Guide.md)
  ([printable PDF](docs/Poolin-EOC07-Beginners-Guide.pdf)). The same steps for the
  Poolin, using the DST files.

## Patterns

| File | What it is | Size | Hoop |
| --- | --- | --- | --- |
| [`patterns/henderson-est-2007.dst`](patterns/henderson-est-2007.dst) | "Henderson" over "est. 2007", bold serif lettering | 106 x 29 mm (4.2" x 1.1") | 5.5" x 5.5" |
| [`patterns/henderson-est-2007-clover.dst`](patterns/henderson-est-2007-clover.dst) | Same lettering with a small four-leaf clover on each side of "est. 2007" | 106 x 32 mm (4.2" x 1.3") | 5.5" x 5.5" |
| [`patterns/henderson-est-2007-clover.pes`](patterns/henderson-est-2007-clover.pes) | Clover design for Brother machines (SE2000), with Brother thread colors: Emerald Green, Leaf Green, Brass | 106 x 32 mm (4.2" x 1.3") | 5" x 7" |
| [`patterns/skull-flower-border-5x7.pes`](patterns/skull-flower-border-5x7.pes) | Tall skull, flower and vine frame for a 5" x 7" stitch field (Brother SE2000); sides stay within 0.5" of the edge | 127 x 177 mm (5.0" x 7.0") | 5" x 7" |
| [`patterns/skull-flower-border-6.25x8.5.pes`](patterns/skull-flower-border-6.25x8.5.pes) | The same frame for a 6.25" x 8.5" stitch field | 156 x 213 mm (6.1" x 8.4") | 6.25" x 8.5" |
| [`patterns/barbed-wire-skull-frame-5x7.pes`](patterns/barbed-wire-skull-frame-5x7.pes) | Tall barbed-wire frame with a skull, moon and swirls in each corner, for a 5" x 7" stitch field (Brother SE2000) | 127 x 177 mm (5.0" x 7.0") | 5" x 7" |
| [`patterns/barbed-wire-skull-frame-6.25x8.5.pes`](patterns/barbed-wire-skull-frame-6.25x8.5.pes) | The same frame for a 6.25" x 8.5" stitch field | 156 x 213 mm (6.1" x 8.4") | 6.25" x 8.5" |

![Preview](patterns/henderson-est-2007.png)

![Clover preview](patterns/henderson-est-2007-clover.png)

The pattern has two thread colors: navy for "Henderson", then a stop for
a thread change, then old gold for "est. 2007". Use the same spool twice
for a one-color patch. The clover version adds a third color (forest green
for "Henderson", kelly green for the clovers, old gold for "est. 2007").

To load it, copy the `.dst` file (Poolin) or `.pes` file (Brother) onto a FAT32 USB flash drive, plug it into
the machine, and open it from the USB menu on the touchscreen.

## Making a new lettering pattern

Edit the `LINES` list at the top of `tools/make_text_pattern.py`, then run:

```
pip install pyembroidery fonttools shapely
python3 tools/make_text_pattern.py
```

It writes a `.dst` file and a `.png` preview to `patterns/`. Run
`python3 tools/make_clover_pattern.py` for the clover version (`.dst` and `.pes`).
