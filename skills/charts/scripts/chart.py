"""Draws a chart spec (JSON, see ../SKILL.md) as SVG, PNG and CSV, and prints their paths as one JSON line.

    python3 chart.py spec.json [--out DIR]
    python3 chart.py - [--out DIR] < spec.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

from raster import to_png
from render import render
from spec import SIZES, Spec, SpecError, parse


def write_csv(spec: Spec, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        out = csv.writer(file)
        out.writerow(["label", *[one.name or f"series {index + 1}" for index, one in enumerate(spec.series)]])
        for index, label in enumerate(spec.labels):
            out.writerow([label, *[f"{one.values[index]:g}" for one in spec.series]])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Draw a chart in Selan's style as SVG, PNG and CSV.")
    parser.add_argument("spec", help="the spec's JSON file, or - to read it from standard input")
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "selan-charts"), help="the folder to write into")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text(encoding="utf-8")
        spec = parse(json.loads(text))
    except (OSError, json.JSONDecodeError) as error:
        print(f"spec: cannot read it: {error}", file=sys.stderr)
        return 2
    except SpecError as error:
        print(f"spec: {error}", file=sys.stderr)
        return 2
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    svg, png, table = (out / f"{spec.name}.{kind}" for kind in ("svg", "png", "csv"))
    svg.write_text(render(spec), encoding="utf-8")
    write_csv(spec, table)
    drawer = to_png(svg, png, SIZES[spec.size])
    result = {"svg": str(svg), "png": str(png) if drawer else None, "csv": str(table), "drawer": drawer}
    if not drawer:
        result["note"] = "no SVG drawer here (rsvg-convert, resvg, Chrome or Chromium): hand over the SVG, or install librsvg"
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
