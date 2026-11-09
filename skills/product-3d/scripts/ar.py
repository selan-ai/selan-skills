"""Writes a model's AR files, GLB and USDZ, checks them, and prints one JSON line.

    python3 ar.py model.js --out DIR [--metres 0.3] [--open 0]

DIR/<name>.glb opens in Android's Scene Viewer and in any 3D tool; DIR/<name>.usdz in AR Quick Look on an iPhone
or iPad. Both are the model in metres (`root.userData.metres`, one model unit in metres, or --metres), as it stands
at setOpen(--open). The GLB is read back with three.js's own loader and drawn beside the model in
DIR/<name>-ar-check.png; the USDZ is checked for what Quick Look needs (stored, 64-byte aligned, a USD layer
first) and, where Pixar's or Apple's `usdchecker` is installed (every Mac has it), by `usdchecker --arkit`.
Exit 2: a wrong argument. Exit 1: the export or a check failed; `errors` says what.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import chrome
from common import KIT, PRODUCT3D, THREE, InputError, model_name, page, read_info

EXPORTERS = KIT / "three-export.min.js"
SHEET = 360  # px, each of the check sheet's two views

CHECK = """
var o = OPTIONS, out = document.getElementById('p3d-info');
Product3D.exportAR(o.model, { metres: o.metres, open: o.open }).then(function (r) {
  [[Product3D.create(o.model), 'the model'], [r.scene, 'its GLB, read back']].forEach(function (pair) {
    var d = document.createElement('div'); d.className = 'p';
    var l = document.createElement('span'); l.textContent = pair[1]; d.appendChild(l);
    var rend = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    rend.setPixelRatio(1); rend.setSize(SIZE, SIZE);
    if (pair[0].userData.runtime && pair[0].userData.runtime.setOpen) pair[0].userData.runtime.setOpen(o.open);
    var st = Product3D.stage(rend, pair[0], { background: '#ffffff' });
    var cam = new THREE.PerspectiveCamera(26, 1, 0.001, 1000);
    Product3D.frame(cam, pair[0], { width: SIZE, height: SIZE, yaw: 22, elevation: 15, fill: 0.8 });
    rend.render(st.scene, cam);
    d.appendChild(rend.domElement); document.getElementById('row').appendChild(d);
  });
  out.textContent = JSON.stringify({ glb: r.glb, usdz: r.usdz, info: r.info, errors: __p3dErrors });
}).catch(function (e) {
  __p3dErrors.push(String(e && e.message || e));
  out.textContent = JSON.stringify({ errors: __p3dErrors });
});
"""
STYLE = (
    "body{background:#ecebe7;font:13px system-ui,sans-serif}#row{display:flex;gap:10px;padding:10px}"
    ".p{position:relative;background:#fff}.p canvas{display:block}.p span{position:absolute;left:6px;top:4px;"
    "padding:1px 6px;border-radius:4px;background:rgba(255,255,255,.88);color:#333}"
)


class CheckError(Exception):
    """An AR file that would not open: the message says what is wrong with it."""


def check_glb(data: bytes) -> dict:
    """The GLB container: magic, version 2, declared length, a JSON chunk first with at least one mesh."""
    if len(data) < 20 or data[:4] != b"glTF":
        raise CheckError("glb: not a binary glTF (no glTF magic)")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2 or length != len(data):
        raise CheckError(f"glb: version {version}, declared length {length} for {len(data)} bytes")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise CheckError("glb: the first chunk is not JSON")
    doc = json.loads(data[20:20 + chunk_length].decode("utf-8"))
    if doc.get("asset", {}).get("version") != "2.0" or not doc.get("meshes"):
        raise CheckError("glb: no glTF 2.0 asset, or no meshes")
    return {"bytes": len(data), "meshes": len(doc["meshes"]), "materials": len(doc.get("materials", [])),
            "nodes": len(doc.get("nodes", []))}


def check_usdz(path: Path) -> dict:
    """What AR Quick Look needs of a USDZ: a zip of stored (uncompressed) files, each one's data starting on a
    64-byte boundary, and a USD layer as the first file."""
    raw = path.read_bytes()
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise CheckError(f"usdz: not a zip ({error})") from error
    entries = archive.infolist()
    if not entries or not entries[0].filename.endswith((".usda", ".usdc")):
        raise CheckError("usdz: the first file is not a USD layer")
    for entry in entries:
        if entry.compress_type != zipfile.ZIP_STORED:
            raise CheckError(f"usdz: {entry.filename} is compressed; Quick Look reads stored files only")
        name_length, extra_length = struct.unpack_from("<HH", raw, entry.header_offset + 26)
        start = entry.header_offset + 30 + name_length + extra_length
        if start % 64:
            raise CheckError(f"usdz: {entry.filename} starts at byte {start}, not on a 64-byte boundary")
    return {"bytes": len(raw), "files": [entry.filename for entry in entries]}


def arkit(usdz: Path) -> str | None:
    """`usdchecker --arkit`, the USD project's check of what ARKit and Quick Look accept: "ok", or its complaints.
    None where no usdchecker is installed (macOS ships one in /usr/bin)."""
    checker = shutil.which("usdchecker")
    if not checker:
        return None
    try:
        done = subprocess.run([checker, "--arkit", str(usdz)], capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"usdchecker did not finish: {error}"
    if done.returncode == 0:
        return "ok"
    # Apple's build prints schema-registration noise as "Coding Error"; the findings are the other lines
    lines = [line for line in (done.stdout + done.stderr).splitlines() if line.strip() and "Coding Error" not in line]
    return "; ".join(lines[-6:]) or f"usdchecker exit {done.returncode}"


def run(model: Path, out: Path, metres: float | None = None, open_state: float = 0.0) -> dict:
    """Writes and checks the AR files; raises InputError, chrome.ChromeError or CheckError."""
    name = model_name(model)
    if metres is not None and not 0.001 <= metres <= 100:
        raise InputError("metres: one model unit in metres, 0.001 to 100")
    if not 0 <= open_state <= 1:
        raise InputError("open: 0 (closed) to 1 (open)")
    out.mkdir(parents=True, exist_ok=True)
    options = {"model": name, "metres": metres, "open": open_state}
    html_path = out / f"{name}-ar-check.html"
    call = CHECK.replace("OPTIONS", json.dumps(options)).replace("SIZE", str(SHEET))
    html_path.write_text(page([THREE, EXPORTERS, PRODUCT3D, model], '<div id="row"></div>', call, STYLE), encoding="utf-8")
    result = read_info(chrome.dump_dom(html_path, budget_ms=30000))
    if result.get("errors"):
        raise CheckError("; ".join(result["errors"]))
    glb, usdz = out / f"{name}.glb", out / f"{name}.usdz"
    glb.write_bytes(base64.b64decode(result["glb"]))
    usdz.write_bytes(base64.b64decode(result["usdz"]))
    report = {"glb": str(glb), "usdz": str(usdz), "glb_check": check_glb(glb.read_bytes()), "usdz_check": check_usdz(usdz)}
    sheet = out / f"{name}-ar-check.png"
    chrome.screenshot(html_path, sheet, 3 * 10 + 2 * SHEET, 2 * 10 + SHEET, budget_ms=30000)
    info = result["info"]
    verdict = arkit(usdz)
    if verdict not in (None, "ok"):
        raise CheckError(f"usdz: usdchecker --arkit: {verdict}")
    report.update({"check": str(sheet), "arkit": verdict, "metres": info["metres"],
                   "size_m": info["reread"]["size"], "triangles": info["reread"]["triangles"],
                   "converted": info["converted"], "warnings": info["warnings"]})
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write and check a product-3d model's AR files (GLB, USDZ).")
    parser.add_argument("model", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metres", type=float, help="one model unit in metres; root.userData.metres otherwise")
    parser.add_argument("--open", type=float, default=0.0, help="the moving parts' state, 0 closed to 1 open")
    args = parser.parse_args(argv)
    try:
        report = run(args.model, args.out, args.metres, args.open)
    except InputError as error:
        print(f"input: {error}", file=sys.stderr)
        return 2
    except (chrome.ChromeError, CheckError, ValueError, KeyError) as error:
        message = str(error)
        if "userData.metres" in message:
            print(f"input: {message}, or pass --metres", file=sys.stderr)
            return 2
        print(json.dumps({"errors": [message]}))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
