"""Headless Chrome for the product-3d scripts: find it, dump a page's DOM, screenshot it. Nothing is installed."""

from __future__ import annotations

import glob
import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path

TIMEOUT = 180

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

# WebGL without a GPU (SwiftShader), and file:// pages that may read the photo's pixels.
FLAGS = [
    "--headless=new", "--no-first-run", "--no-sandbox", "--hide-scrollbars", "--mute-audio", "--disable-dev-shm-usage",
    "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files", "--disable-extensions",
]

MISSING = "no Chrome or Chromium found (Google Chrome, Chromium, Edge or Playwright's Chromium); install one"


class ChromeError(Exception):
    pass


def find() -> str | None:
    named = os.environ.get("CHROME")  # what a setup script found, such as selan-modernise-web-project's setup_vm.sh
    if named and os.path.isfile(named):
        return named
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


def _run(args: list[str], budget_ms: int) -> subprocess.CompletedProcess:
    chrome = find()
    if not chrome:
        raise ChromeError(MISSING)
    with tempfile.TemporaryDirectory() as profile:
        command = [chrome, *FLAGS, f"--user-data-dir={profile}", f"--virtual-time-budget={budget_ms}", *args]
        try:
            return subprocess.run(command, capture_output=True, timeout=TIMEOUT, check=False, text=True)
        except subprocess.TimeoutExpired as error:
            raise ChromeError(f"Chrome did not finish in {TIMEOUT} s") from error


def collect(page: Path, timeout_s: int = TIMEOUT) -> bytes:
    """Opens `page` and waits, in real time, for it to POST its result to the address in its #hash, in parts
    (`?part=i&of=n`: one large body from a busy page fails to send, 1 MB parts do); answers the parts joined.
    For work that --dump-dom's virtual time does not wait for, such as canvases encoded to images."""
    chrome = find()
    if not chrome:
        raise ChromeError(MISSING)
    parts: dict = {}
    expected: list = []
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (http.server's name)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(204)
            self.end_headers()
            index, total = int(query.get("part", ["0"])[0]), int(query.get("of", ["1"])[0])
            parts[index] = body
            expected[:] = [total]
            if len(parts) == total:
                done.set()

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"{page.resolve().as_uri()}#http://127.0.0.1:{server.server_address[1]}/result"
    with tempfile.TemporaryDirectory() as profile:
        process = subprocess.Popen([chrome, *FLAGS, f"--user-data-dir={profile}", url],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if not done.wait(timeout_s):
                raise ChromeError(f"the page sent no result in {timeout_s} s")
        finally:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
            server.shutdown()
    return b"".join(parts[index] for index in range(expected[0]))


def dump_dom(page: Path, budget_ms: int = 15000) -> str:
    return _run(["--dump-dom", page.resolve().as_uri()], budget_ms).stdout


def screenshot(page: Path, png: Path, width: int, height: int, budget_ms: int = 15000) -> None:
    png.unlink(missing_ok=True)
    _run([f"--window-size={width},{height}", f"--screenshot={png}", page.resolve().as_uri()], budget_ms)
    if not png.is_file() or png.stat().st_size == 0:
        raise ChromeError("Chrome wrote no screenshot")
