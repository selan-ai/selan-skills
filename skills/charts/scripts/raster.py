"""SVG to PNG at twice the size, with the first drawer this machine has. Nothing is installed: none found is said."""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

SCALE = 2
TIMEOUT = 60

CHROMES = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

# Playwright's own Chromium, as the Reactor image and many developer machines have it.
PLAYWRIGHT = [
    "~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "/ms-playwright/chromium-*/chrome-linux*/chrome",
]


def _run(command: list[str]) -> bool:
    try:
        done = subprocess.run(command, capture_output=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def _found(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _chrome() -> str | None:
    for name in CHROMES:
        found = shutil.which(name) or (name if os.path.isfile(name) else None)
        if found:
            return found
    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    patterns = PLAYWRIGHT + ([f"{browsers}/chromium-*/chrome-*/chrome"] if browsers else [])
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.expanduser(pattern)), reverse=True)
        if matches:
            return matches[0]
    return None


def _with_chrome(chrome: str, svg: Path, png: Path, width: int, height: int) -> bool:
    with tempfile.TemporaryDirectory() as profile:
        return _run([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-sandbox",
            f"--user-data-dir={profile}", f"--force-device-scale-factor={SCALE}", f"--window-size={width},{height}",
            f"--screenshot={png}", svg.resolve().as_uri(),
        ]) and _found(png)


def _with_quick_look(svg: Path, png: Path, width: int, height: int) -> bool:
    with tempfile.TemporaryDirectory() as out:
        if not _run(["qlmanage", "-t", "-s", str(max(width, height) * SCALE), "-o", out, str(svg)]):
            return False
        made = Path(out) / f"{svg.name}.png"
        if not _found(made):
            return False
        shutil.move(made, png)
        return True


def to_png(svg: Path, png: Path, width: int, height: int) -> str | None:
    """Draws `svg` into `png`; answers the drawer used, or None when this machine has none."""
    png.unlink(missing_ok=True)
    if shutil.which("rsvg-convert") and _run(["rsvg-convert", "-z", str(SCALE), "-o", str(png), str(svg)]) and _found(png):
        return "rsvg-convert"
    if shutil.which("resvg") and _run(["resvg", "--zoom", str(SCALE), str(svg), str(png)]) and _found(png):
        return "resvg"
    chrome = _chrome()
    if chrome and _with_chrome(chrome, svg, png, width, height):
        return "chrome"
    if platform.system() == "Darwin" and shutil.which("qlmanage") and _with_quick_look(svg, png, width, height):
        return "quick-look"
    return None
