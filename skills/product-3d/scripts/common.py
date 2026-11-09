"""What review.py, sample.py and export.py share: the kit's paths, the model's name, the page they run in Chrome."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "kit"
THREE = KIT / "three.min.js"
PRODUCT3D = KIT / "product3d.js"

DEFINE = re.compile(r"""Product3D\.define\(\s*['"]([a-z0-9][a-z0-9-]{0,62})['"]""")
INFO = re.compile(r'<pre id="p3d-info">(.*?)</pre>', re.S)


class InputError(Exception):
    """A wrong argument or file: the message names it and what it may be."""


def model_name(model: Path) -> str:
    if not model.is_file():
        raise InputError(f"model: {model} is not a file")
    found = DEFINE.findall(model.read_text(encoding="utf-8"))
    if len(found) != 1:
        raise InputError("model: needs exactly one Product3D.define('name', function (THREE, kit) { ... }) call, "
                         "name in lowercase letters, digits and dashes")
    return found[0]


def page(scripts: list[Path], body: str, call: str, style: str = "") -> str:
    """A page that records every error, loads the scripts, then runs `call` once the reference photo (if any) loaded."""
    tags = "".join(f'<script src="{html.escape(p.resolve().as_uri())}"></script>' for p in scripts)
    return (
        '<!doctype html><meta charset="utf-8"><style>body{margin:0}#p3d-info{display:none}' + style + "</style>"
        "<script>window.__p3dErrors=[];addEventListener('error',function(e){__p3dErrors.push(String(e.message)+"
        "' ('+String(e.filename||'').split('/').pop()+':'+e.lineno+')')});</script>"
        + tags + body + '<pre id="p3d-info"></pre><script>'
        "function __go(){try{" + call + "}catch(e){__p3dErrors.push(String(e&&e.stack||e));"
        "document.getElementById('p3d-info').textContent=JSON.stringify({errors:__p3dErrors});}}"
        "var __ref=document.getElementById('p3d-ref');"
        "if(!__ref||__ref.complete)__go();else{__ref.onload=__go;__ref.onerror=function(){"
        "__p3dErrors.push('the reference photo did not load');__ref.remove();__go();};}"
        "</script>"
    )


def read_info(dom: str) -> dict:
    found = INFO.search(dom)
    if not found or not found.group(1).strip():
        raise InputError("page: Chrome finished without a result (the page did not run)")
    return json.loads(html.unescape(found.group(1)))


def image(path: Path) -> Path:
    if not path.is_file():
        raise InputError(f"reference: {path} is not a file")
    if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        raise InputError("reference: a .jpg, .png or .webp photo")
    return path
