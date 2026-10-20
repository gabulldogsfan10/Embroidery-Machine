# Embroidery Machine

Patterns and tools for our Poolin EOC07 embroidery machine.

## Beginner's guide

Start here: [Poolin EOC07 Beginner's Guide](docs/Poolin-EOC07-Beginners-Guide.md)
([printable PDF](docs/Poolin-EOC07-Beginners-Guide.pdf)). It walks through setup,
threading, hooping, and stitching the Henderson pattern below.

## Patterns

| File | What it is | Size | Hoop |
| --- | --- | --- | --- |
| [`patterns/henderson-est-2007.dst`](patterns/henderson-est-2007.dst) | "Henderson" over "est. 2007", bold serif lettering | 106 x 29 mm (4.2" x 1.1") | 5.5" x 5.5" |

![Preview](patterns/henderson-est-2007.png)

The pattern has two thread colors: navy for "Henderson", then a stop for
a thread change, then old gold for "est. 2007". Use the same spool twice
for a one-color patch.

To load it, copy the `.dst` file onto a FAT32 USB flash drive, plug it into
the machine, and open it from the USB menu on the touchscreen.

## Making a new lettering pattern

Edit the `LINES` list at the top of `tools/make_text_pattern.py`, then run:

```
pip install pyembroidery fonttools shapely
python3 tools/make_text_pattern.py
```

It writes a `.dst` file and a `.png` preview to `patterns/`.
