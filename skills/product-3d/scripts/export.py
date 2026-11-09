"""Packs a model for a web page or a slide deck: one script file and an HTML snippet. Prints one JSON line.

    python3 export.py model.js --out DIR [--poster photo.jpg] [--lang lt|en] [--load click|near] [--label TEXT] [--ar]

DIR/<name>.js is three.js, the kit and the model as one classic script (about 200 KB gzip), so it runs from a
web server and from file:// (a deck opened from disk) alike. DIR/<name>.html is the markup, style and loader to
paste where the model goes: the poster photo shows first, the script loads on a click (`click`, for web pages)
or when the figure comes near the screen (`near`, for decks). With --ar it also writes the AR files (ar.py) and
the snippet gets a "view in your space" link, shown only on an iPhone or iPad (AR Quick Look, the USDZ) and on
Android (Scene Viewer, the GLB, which needs the page on a public https address). Exit 2: a wrong argument.
Exit 1: the AR export failed.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import urllib.parse
from enum import Enum
from pathlib import Path

import ar
import chrome
from common import PRODUCT3D, THREE, InputError, image, model_name


class Load(str, Enum):
    CLICK = "click"
    NEAR = "near"


WORDS = {
    "lt": {"show": "Rodyti 3D", "loading": "Kraunamas 3D modelis", "open": "Atidaryti", "close": "Uždaryti",
           "hint": "Tempkite, kad pasuktumėte.", "ar": "Žiūrėti savo erdvėje"},
    "en": {"show": "Show in 3D", "loading": "Loading the 3D model", "open": "Open", "close": "Close",
           "hint": "Drag to turn it.", "ar": "View in your space"},
}

STYLE = """<style>
.p3d { margin: 0; }
.p3d-stage { position: relative; aspect-ratio: 4 / 5; background: #fff; border-radius: 10px; overflow: hidden; }
.p3d-stage > * { position: absolute; inset: 0; width: 100%; height: 100%; }
.p3d-stage img { object-fit: contain; }
.p3d-stage canvas { cursor: grab; }
.p3d-stage canvas:active { cursor: grabbing; }
.p3d figcaption { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; margin-top: 12px; }
.p3d-btn[hidden], .p3d-ar[hidden] { display: none !important; }
.p3d-ar { display: inline-flex; line-height: 0; }
.p3d-ar img { height: 44px; width: auto; }
.p3d-hint { display: none; opacity: .7; font-size: .95em; }
.p3d.is-live .p3d-hint { display: inline; }
</style>"""

LOADER = """<script>
(function () {
  var figs = document.querySelectorAll('figure.p3d[data-model="NAME"]');
  var gl = document.createElement('canvas').getContext('webgl2');
  Array.prototype.forEach.call(figs, function (fig) {
    var btn = fig.querySelector('.p3d-btn');
    // AR: Quick Look on iPhone and iPad (rel="ar", the USDZ), Scene Viewer on Android (the GLB); hidden elsewhere; it needs no WebGL
    var ar = fig.querySelector('.p3d-ar');
    if (ar) {
      var a = document.createElement('a');
      if (a.relList && a.relList.supports && a.relList.supports('ar')) ar.hidden = false;
      else if (/Android/i.test(navigator.userAgent)) {
        var glb = new URL(ar.dataset.glb, location.href).href;
        ar.removeAttribute('rel');
        ar.href = 'intent://arvr.google.com/scene-viewer/1.0?file=' + encodeURIComponent(glb) + '&mode=ar_preferred&title='
          + encodeURIComponent(fig.dataset.label || '') + '#Intent;scheme=https;package=com.google.android.googlequicksearchbox;'
          + 'action=android.intent.action.VIEW;S.browser_fallback_url=' + encodeURIComponent(location.href) + ';end;';
        ar.hidden = false;
      }
    }
    function hide(el) { el.hidden = true; el.style.display = 'none'; }
    if (!gl) { if (btn) hide(btn); return; }
    function load() {
      if (btn) { btn.disabled = true; btn.textContent = fig.dataset.loading; }
      function go() { window.Product3D.mount(fig, fig.dataset.model); }
      if (window.Product3D && document.querySelector('script[data-p3d="NAME"]')) return go();
      var s = document.createElement('script');
      s.src = fig.dataset.src;
      s.setAttribute('data-p3d', 'NAME');
      s.onload = go;
      s.onerror = function () { if (btn) hide(btn); };
      document.head.appendChild(s);
    }
    if (fig.dataset.load === 'near') {
      var io = new IntersectionObserver(function (es) {
        if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); load(); }
      }, { rootMargin: '100% 0px' });
      io.observe(fig);
    } else if (btn) btn.addEventListener('click', load, { once: true });
  });
})();
</script>"""


def ar_badge(text: str) -> str:
    """The AR link's picture, as a data: SVG. Quick Look wants the link's one child to be an <img>, so the words are
    drawn into it rather than written beside it."""
    width = 56 + round(len(text) * 7.7)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="44" viewBox="0 0 {width} 44">'
           f'<rect x="1" y="1" width="{width - 2}" height="42" rx="21" fill="#fff" stroke="#cfd3d1"/>'
           '<g fill="none" stroke="#1d2124" stroke-width="1.8" stroke-linejoin="round">'
           '<path d="M22 12l9 5v10l-9 5-9-5V17z"/><path d="M13 17l9 5 9-5M22 22v10"/></g>'
           f'<text x="42" y="27.5" font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif" font-size="15" '
           f'font-weight="600" fill="#1d2124">{html.escape(text)}</text></svg>')
    return "data:image/svg+xml," + urllib.parse.quote(svg)


def snippet(name: str, src: str, poster: str | None, label: str, words: dict, load: Load, ar_files: dict | None = None) -> str:
    def attr(value: str) -> str:
        return html.escape(value, quote=True)

    picture = f'<img src="{attr(poster)}" alt="{attr(label)}">' if poster else ""
    first = words["loading"] if load is Load.NEAR else words["show"]
    disabled = " disabled" if load is Load.NEAR else ""
    return (
        f'<figure class="p3d" data-model="{name}" data-src="{attr(src)}" data-load="{load.value}" '
        f'data-label="{attr(label)}" data-loading="{attr(words["loading"])}" data-press="{attr(words["open"])}" '
        f'data-release="{attr(words["close"])}">\n'
        f'  <div class="p3d-stage">{picture}</div>\n'
        f'  <figcaption><button type="button" class="p3d-btn"{disabled}>{html.escape(first)}</button>'
        f'<span class="p3d-hint">{html.escape(words["hint"])}</span>'
        + (f'<a class="p3d-ar" rel="ar" href="{attr(ar_files["usdz"])}" data-glb="{attr(ar_files["glb"])}" hidden>'
           f'<img src="{ar_badge(words["ar"])}" alt="{attr(words["ar"])}"></a>' if ar_files else "")
        + '</figcaption>\n'
        "</figure>\n" + STYLE + "\n" + LOADER.replace("NAME", name) + "\n"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pack a product-3d model for a web page or a deck.")
    parser.add_argument("model", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--poster", type=Path, help="the photo shown until the model loads; copied beside the script")
    parser.add_argument("--lang", default="lt", help="lt or en: the button and hint words")
    parser.add_argument("--load", default="click", help="click (web page) or near (deck)")
    parser.add_argument("--label", help="what the model is, for screen readers; the model's name if left out")
    parser.add_argument("--ar", action="store_true", help="also write the AR files and add the AR link")
    args = parser.parse_args(argv)
    try:
        name = model_name(args.model)
        if args.lang not in WORDS:
            raise InputError("lang: lt or en")
        try:
            load = Load(args.load)
        except ValueError:
            raise InputError("load: click or near") from None
        poster = image(args.poster) if args.poster else None
    except InputError as error:
        print(f"input: {error}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    script = args.out / f"{name}.js"
    parts = [THREE.read_text(encoding="utf-8"), PRODUCT3D.read_text(encoding="utf-8"), args.model.read_text(encoding="utf-8")]
    script.write_text("\n;\n".join(parts) + "\n", encoding="utf-8")
    poster_name = None
    if poster:
        poster_name = f"{name}-poster{poster.suffix.lower()}"
        shutil.copyfile(poster, args.out / poster_name)
    ar_report = None
    if args.ar:
        try:
            ar_report = ar.run(args.model, args.out)
        except InputError as error:
            print(f"input: {error}", file=sys.stderr)
            return 2
        except (chrome.ChromeError, ar.CheckError, ValueError, KeyError) as error:
            message = str(error)
            if "userData.metres" in message:
                print(f"input: {message} before --ar", file=sys.stderr)
                return 2
            print(json.dumps({"errors": [message]}))
            return 1
    ar_files = {"glb": f"{name}.glb", "usdz": f"{name}.usdz"} if ar_report else None
    markup = args.out / f"{name}.html"
    markup.write_text(snippet(name, script.name, poster_name, args.label or name, WORDS[args.lang], load, ar_files),
                      encoding="utf-8")
    print(json.dumps({"script": str(script), "snippet": str(markup), "poster": str(args.out / poster_name) if poster_name else None,
                      "bytes": script.stat().st_size, "ar": ar_report}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
