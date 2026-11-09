"""Measures a reference photo before any model exists, and prints one JSON line.

    python3 sample.py photo.jpg [--point name:X,Y ...]

`box` is the object's box in px (pixels that differ from the border's colour; null on a busy background),
`fill` its height over the photo's, `aspect` its height over its width, `tilt` how many degrees its long axis
leans from vertical (+ when the top leans right; null for a round or squat object): give it to review.py as
--roll. `points` is the average colour of a 5x5 patch at each point. Exit 2: a wrong argument. Exit 1: Chrome failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import chrome
from common import PRODUCT3D, THREE, InputError, image, page, read_info
from review import numbers

CALL = (
    "var im=document.getElementById('p3d-ref'),b=Product3D.photoBox(im),o={width:im.naturalWidth,height:im.naturalHeight,"
    "box:b.box,tilt:b.tilt,background:'#'+b.background.map(function(v){return('0'+v.toString(16)).slice(-2)}).join('')};"
    "if(b.box){o.fill=Math.round((b.box[3]-b.box[1])/im.naturalHeight*1000)/1000;"
    "o.aspect=Math.round((b.box[3]-b.box[1])/(b.box[2]-b.box[0])*1000)/1000;}"
    "o.points=Product3D.samplePhoto(im,POINTS,2);o.errors=__p3dErrors;"
    "document.getElementById('p3d-info').textContent=JSON.stringify(o);"
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Measure a reference photo: object box and colours.")
    parser.add_argument("photo", type=Path)
    parser.add_argument("--point", action="append", default=[], help="name:X,Y in px")
    args = parser.parse_args(argv)
    try:
        photo = image(args.photo)
        points = {}
        for item in args.point:
            label, _, xy = item.partition(":")
            if not label or not xy:
                raise InputError("point: name:X,Y, for example lid:300,215")
            points[label] = [int(v) for v in numbers(xy, 2, f"point {label}")]
    except InputError as error:
        print(f"input: {error}", file=sys.stderr)
        return 2
    folder = Path(tempfile.mkdtemp(prefix="selan-product-3d-"))
    html_path = folder / "sample.html"
    body = f'<img id="p3d-ref" src="{photo.resolve().as_uri()}">'
    html_path.write_text(page([THREE, PRODUCT3D], body, CALL.replace("POINTS", json.dumps(points))), encoding="utf-8")
    try:
        info = read_info(chrome.dump_dom(html_path))
    except (chrome.ChromeError, InputError, ValueError) as error:
        print(json.dumps({"errors": [str(error)]}))
        return 1
    if info.get("errors"):
        print(json.dumps({"errors": info["errors"]}))
        return 1
    info.pop("errors", None)
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
