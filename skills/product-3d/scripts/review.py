"""Renders a model next to its reference photo, so the agent can compare them, and prints one JSON line.

    python3 review.py model.js [--reference photo.jpg] [--yaw 22] [--elevation 15] [--roll 0] [--fov 26]
                               [--box X0,Y0,X1,Y1] [--sample name:X,Y ...] [--out sheet.png]

The sheet: the photo; the render over the photo at 50%; the render alone, from the photo's camera and fitted to
the object's box in the photo (no floor shadow, as the photo has none); then the model turned 90, 180 and 270
degrees, and opened when it has moving parts. `tilt` in the output is how far the object in the photo leans from
vertical: pass it as --roll so the render leans the same way.
Exit 2: a wrong argument. Exit 1: the model threw, or Chrome failed; `errors` says what.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import chrome
from common import PRODUCT3D, THREE, InputError, image, model_name, page, read_info

PANEL = 620  # height of the top row's panels, px
GAP = 10
STYLE = (
    "body{background:#ecebe7;font:13px system-ui,sans-serif}.row{display:flex;gap:10px;padding:10px 10px 0}"
    ".p{position:relative;background:#fff;overflow:hidden;flex:none}.p img{width:100%;height:100%;display:block}"
    ".p canvas{position:absolute;inset:0}.p span{position:absolute;left:6px;top:4px;z-index:3;padding:1px 6px;"
    "border-radius:4px;background:rgba(255,255,255,.88);color:#333}.ov{position:absolute;inset:0;opacity:.5}"
)


def numbers(text: str, count: int, what: str) -> list[float]:
    try:
        values = [float(v) for v in text.split(",")]
    except ValueError:
        values = []
    if len(values) != count:
        raise InputError(f"{what}: {count} numbers separated by commas")
    return values


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a product-3d model beside its reference photo.")
    parser.add_argument("model", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--yaw", type=float, default=0.0, help="degrees; + turns the camera toward the model's +X side")
    parser.add_argument("--elevation", type=float, default=10.0, help="degrees above the horizon")
    parser.add_argument("--roll", type=float, default=0.0, help="degrees the picture leans, + top to the right: the photo's tilt")
    parser.add_argument("--fov", type=float, default=26.0, help="vertical field of view, degrees")
    parser.add_argument("--box", help="X0,Y0,X1,Y1: the object's box in the photo, px; found by itself on a plain background")
    parser.add_argument("--sample", action="append", default=[], help="name:X,Y: the photo's colour there, in the output")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if not -180 <= args.yaw <= 180:
        raise InputError("yaw: -180 to 180 degrees")
    if not -20 <= args.elevation <= 85:
        raise InputError("elevation: -20 to 85 degrees")
    if not -90 <= args.roll <= 90:
        raise InputError("roll: -90 to 90 degrees")
    if not 10 <= args.fov <= 80:
        raise InputError("fov: 10 to 80 degrees")
    if args.box and not args.reference:
        raise InputError("box: only with --reference")
    if args.sample and not args.reference:
        raise InputError("sample: only with --reference")
    return args


def main(argv: list[str]) -> int:
    try:
        args = parse(argv)
        name = model_name(args.model)
        reference = image(args.reference) if args.reference else None
        box = numbers(args.box, 4, "box") if args.box else None
        samples = {}
        for item in args.sample:
            label, _, xy = item.partition(":")
            if not label or not xy:
                raise InputError("sample: name:X,Y, for example lid:300,215")
            samples[label] = [int(v) for v in numbers(xy, 2, f"sample {label}")]
    except InputError as error:
        print(f"input: {error}", file=sys.stderr)
        return 2

    options = {"model": name, "yaw": args.yaw, "elevation": args.elevation, "roll": args.roll, "fov": args.fov, "panel": PANEL,
               "box": box, "samples": samples or None}
    body = '<div class="row" id="p3d-row1"></div><div class="row" id="p3d-row2"></div>'
    if reference:
        body += f'<img id="p3d-ref" src="{reference.resolve().as_uri()}" style="display:none">'
    out = args.out or Path(tempfile.gettempdir()) / "selan-product-3d" / f"{name}-review.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    html_path.write_text(page([THREE, PRODUCT3D, args.model], body, f"Product3D.review({json.dumps(options)})", STYLE),
                         encoding="utf-8")
    try:
        info = read_info(chrome.dump_dom(html_path))
        if info.get("errors"):
            print(json.dumps({"errors": info["errors"], "page": str(html_path)}))
            return 1
        ref = info.get("reference")
        width = round(PANEL * ref["width"] / ref["height"]) if ref else round(PANEL * 0.75)
        small = round(PANEL * 0.62)
        row1 = GAP + (width + GAP) * (3 if ref else 1)
        row2 = GAP + (small + GAP) * (4 if info.get("moving") else 3)
        chrome.screenshot(html_path, out, max(row1, row2), GAP + PANEL + GAP + small + GAP)
    except (chrome.ChromeError, InputError, ValueError) as error:
        print(json.dumps({"errors": [str(error)], "page": str(html_path)}))
        return 1
    info.pop("errors", None)
    print(json.dumps({"png": str(out), "page": str(html_path), **info}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
