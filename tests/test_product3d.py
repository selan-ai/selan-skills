import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
import zlib
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "product-3d"
SCRIPTS = SKILL / "scripts"
EXAMPLE = SKILL / "references" / "example-pedal-bin.js"
sys.path.insert(0, str(SCRIPTS))

import ar  # noqa: E402
import chrome  # noqa: E402
import export  # noqa: E402
from common import InputError, model_name  # noqa: E402

HAS_CHROME = chrome.find() is not None


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=300)


def png(path: Path, width: int, height: int, box: tuple, color: tuple, lean: float = 0.0) -> None:
    """A white picture with one filled rectangle, written with the standard library; `lean` turns the rectangle
    about its centre by that many degrees, + its top to the right."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    c, s = math.cos(math.radians(lean)), math.sin(math.radians(lean))
    rows = b""
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            # the point turned back by the lean, then tested against the upright rectangle
            dx, dy = x - cx, y - cy
            ux, uy = cx + dx * c + dy * s, cy - dx * s + dy * c
            inside = box[0] <= ux <= box[2] and box[1] <= uy <= box[3]
            row += bytes(color if inside else (255, 255, 255))
        rows += bytes(row)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class ModelFileTests(unittest.TestCase):
    def test_the_name_comes_from_the_one_define_call(self) -> None:
        self.assertEqual(model_name(EXAMPLE), "pedal-bin")

    def test_a_file_without_one_lowercase_define_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for text in ("var x = 1;", "Product3D.define('Bad Name', function () {});",
                         "Product3D.define('a', f); Product3D.define('b', f);"):
                model = Path(folder) / "model.js"
                model.write_text(text)
                with self.assertRaises(InputError):
                    model_name(model)

    def test_the_vendored_three_sets_one_global_with_controls_and_environment(self) -> None:
        text = (SKILL / "kit" / "three.min.js").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("/*! three.js 0.187.0"))
        self.assertIn("globalThis.THREE", text)
        self.assertIn("OrbitControls", text)
        self.assertIn("RoomEnvironment", text)
        self.assertNotIn("import ", text[:2000])
        self.assertTrue((SKILL / "kit" / "three.LICENSE").is_file())


class ChromeFindTests(unittest.TestCase):
    def test_a_chrome_named_in_the_environment_comes_first_and_a_missing_one_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            named = Path(folder) / "chrome"
            named.write_text("")
            with unittest.mock.patch.dict("os.environ", {"CHROME": str(named)}):
                self.assertEqual(chrome.find(), str(named))
            with unittest.mock.patch.dict("os.environ", {"CHROME": str(named) + "-gone"}):
                self.assertNotEqual(chrome.find(), str(named) + "-gone")


class ExportTests(unittest.TestCase):
    def test_one_script_holds_three_then_the_kit_then_the_model(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = run("export.py", str(EXAMPLE), "--out", folder)
            self.assertEqual(done.returncode, 0, done.stderr)
            out = json.loads(done.stdout)
            text = Path(out["script"]).read_text(encoding="utf-8")
            three, kit, model = text.index("globalThis.THREE"), text.index("window.Product3D ="), text.index("Product3D.define('pedal-bin'")
            self.assertLess(three, kit)
            self.assertLess(kit, model)
            self.assertNotIn("<script", text)

    def test_the_snippet_names_the_model_escapes_words_and_copies_the_poster(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            poster = Path(folder) / "photo.png"
            png(poster, 20, 20, (5, 5, 14, 14), (30, 90, 50))
            done = run("export.py", str(EXAMPLE), "--out", folder + "/out", "--poster", str(poster),
                       "--label", 'Bin "A" <green>', "--load", "near", "--lang", "en")
            self.assertEqual(done.returncode, 0, done.stderr)
            markup = (Path(folder) / "out" / "pedal-bin.html").read_text(encoding="utf-8")
            self.assertIn('data-model="pedal-bin"', markup)
            self.assertIn('data-load="near"', markup)
            self.assertIn("Bin &quot;A&quot; &lt;green&gt;", markup)
            self.assertNotIn('<green>', markup)
            self.assertIn('src="pedal-bin-poster.png"', markup)
            self.assertIn("Loading the 3D model", markup)
            self.assertTrue((Path(folder) / "out" / "pedal-bin-poster.png").is_file())

    def test_a_hidden_button_stays_hidden_whatever_display_the_page_gives_it(self) -> None:
        markup = export.snippet("x", "x.js", None, "x", export.WORDS["lt"], export.Load.CLICK)
        self.assertIn(".p3d-btn[hidden], .p3d-ar[hidden] { display: none !important; }", markup)
        self.assertIn("function hide(el) { el.hidden = true; el.style.display = 'none'; }", markup)
        self.assertNotIn("btn.hidden = true", markup)

    def test_click_starts_with_the_show_button_and_near_with_it_disabled(self) -> None:
        words = export.WORDS["lt"]
        click = export.snippet("x", "x.js", None, "x", words, export.Load.CLICK)
        near = export.snippet("x", "x.js", None, "x", words, export.Load.NEAR)
        self.assertIn('class="p3d-btn">Rodyti 3D</button>', click)
        self.assertIn('class="p3d-btn" disabled>Kraunamas 3D modelis</button>', near)

    def test_wrong_choices_exit_2_and_say_what_they_may_be(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for args, said in ((["--lang", "de"], "lang: lt or en"), (["--load", "soon"], "load: click or near"),
                               (["--poster", "nope.gif"], "reference:")):
                done = run("export.py", str(EXAMPLE), "--out", folder, *args)
                self.assertEqual(done.returncode, 2)
                self.assertIn(said, done.stderr)


class ArFileTests(unittest.TestCase):
    def test_a_glb_needs_its_magic_version_length_and_a_mesh(self) -> None:
        doc = json.dumps({"asset": {"version": "2.0"}, "meshes": [{}], "nodes": [{}]}).encode()
        doc += b" " * (-len(doc) % 4)
        good = b"glTF" + struct.pack("<II", 2, 20 + len(doc)) + struct.pack("<II", len(doc), 0x4E4F534A) + doc
        self.assertEqual(ar.check_glb(good)["meshes"], 1)
        for bad in (b"nope" + good[4:], good[:8] + struct.pack("<I", 9) + good[12:], good + b"x"):
            with self.assertRaises(ar.CheckError):
                ar.check_glb(bad)

    def test_a_usdz_must_be_stored_aligned_and_start_with_a_usd_layer(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            cases = (([("model.usda", zipfile.ZIP_DEFLATED)], "compressed"),
                     ([("texture.png", zipfile.ZIP_STORED), ("model.usda", zipfile.ZIP_STORED)], "first file"),
                     ([("model.usda", zipfile.ZIP_STORED)], "64-byte"))
            for index, (entries, said) in enumerate(cases):
                path = Path(folder) / f"{index}.usdz"
                with zipfile.ZipFile(path, "w") as archive:
                    for name, how in entries:
                        archive.writestr(zipfile.ZipInfo(name), "#usda 1.0\n", compress_type=how)
                with self.assertRaises(ar.CheckError) as raised:
                    ar.check_usdz(path)
                self.assertIn(said, str(raised.exception))

    def test_the_snippet_has_a_hidden_ar_link_whose_one_child_is_its_picture(self) -> None:
        markup = export.snippet("x", "x.js", None, "Bin", export.WORDS["lt"], export.Load.CLICK, {"glb": "x.glb", "usdz": "x.usdz"})
        link = markup[markup.index('<a class="p3d-ar"'):markup.index("</a>", markup.index('<a class="p3d-ar"')) + 4]
        self.assertIn('rel="ar" href="x.usdz" data-glb="x.glb" hidden>', link)
        self.assertEqual(link.count("<"), 3)  # <a>, its one <img>, </a>: what Quick Look asks for
        self.assertIn('alt="Žiūrėti savo erdvėje"', link)
        self.assertIn("scene-viewer", markup)
        self.assertIn("/iPad|iPhone|iPod/.test(navigator.userAgent)", markup)  # Chrome on iOS too, not only Safari
        self.assertNotIn("p3d-ar", export.snippet("x", "x.js", None, "Bin", export.WORDS["lt"], export.Load.CLICK).split("<style>")[0])


class ReviewArgumentTests(unittest.TestCase):
    def test_out_of_range_angles_and_a_bad_box_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "p.png"
            png(photo, 10, 10, (2, 2, 7, 7), (0, 0, 0))
            for args, said in ((["--yaw", "200"], "yaw:"), (["--elevation", "90"], "elevation:"), (["--roll", "120"], "roll:"),
                               (["--reference", str(photo), "--box", "1,2,3"], "box: 4 numbers"),
                               (["--box", "1,2,3,4"], "box: only with --reference"),
                               (["--reference", str(photo), "--sample", "lid"], "sample:")):
                done = run("review.py", str(EXAMPLE), *args)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn(said, done.stderr)


@unittest.skipUnless(HAS_CHROME, "no Chrome or Chromium on this machine")
class ChromeTests(unittest.TestCase):
    def test_review_draws_the_example_with_its_turns_and_open_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = run("review.py", str(EXAMPLE), "--yaw", "22", "--elevation", "15", "--out", folder + "/r.png")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            out = json.loads(done.stdout)
            self.assertTrue(out["moving"])
            self.assertGreater(out["triangles"], 1000)
            self.assertAlmostEqual(out["size"][0], 1.13, delta=0.05)
            self.assertGreater(Path(out["png"]).stat().st_size, 20000)

    def test_review_finds_the_object_in_a_plain_photo_and_reads_its_colour(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "photo.png"
            png(photo, 300, 400, (100, 80, 200, 360), (31, 92, 51))
            done = run("review.py", str(EXAMPLE), "--reference", str(photo), "--sample", "body:150,200",
                       "--out", folder + "/r.png")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            out = json.loads(done.stdout)
            for found, want in zip(out["reference"]["box"], (100, 80, 200, 360)):
                self.assertLessEqual(abs(found - want), 2)
            self.assertEqual(out["samples"]["body"], "#1f5c33")

    def test_a_model_that_throws_exits_1_with_the_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "m.js"
            model.write_text("Product3D.define('broken', function (THREE, kit) { throw new Error('no lid yet'); });")
            done = run("review.py", str(model), "--out", folder + "/r.png")
            self.assertEqual(done.returncode, 1)
            self.assertIn("no lid yet", done.stdout)

    def test_a_syntax_error_is_reported_with_its_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "m.js"
            model.write_text("Product3D.define('broken', function (THREE, kit) { return new THREE.Group( ; });")
            done = run("review.py", str(model), "--out", folder + "/r.png")
            self.assertEqual(done.returncode, 1)
            self.assertIn("m.js", done.stdout)

    def test_sample_says_how_far_a_long_object_leans_and_nothing_for_a_square(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for lean, box, want in ((30, (130, 60, 170, 340), 30), (-20, (130, 60, 170, 340), -20), (0, (130, 60, 170, 340), 0),
                                    (0, (100, 150, 200, 250), None)):
                photo = Path(folder) / f"lean{lean}-{box[0]}.png"
                png(photo, 300, 400, box, (40, 40, 40), lean=lean)
                out = json.loads(run("sample.py", str(photo)).stdout)
                if want is None:
                    self.assertIsNone(out["tilt"])
                else:
                    self.assertAlmostEqual(out["tilt"], want, delta=2.0)

    def test_a_model_with_a_helix_and_its_own_look_renders(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "m.js"
            model.write_text(
                "Product3D.define('spring', function (THREE, kit) { var g = new THREE.Group();"
                " g.add(new THREE.Mesh(kit.helix({ y0: 0, y1: 2, turns: 6, bar: 0.05, radius: function (y, t) { return 0.4 + 0.1 * t; } }),"
                " kit.metal('#c9cdd2'))); g.userData.look = { toneMapping: 'agx', environment: 1.1 }; return g; });")
            done = run("review.py", str(model), "--out", folder + "/r.png")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertGreater(json.loads(done.stdout)["triangles"], 1000)

    def test_the_viewer_hides_its_button_for_a_model_that_does_not_move_even_on_a_btn_class(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = run("export.py", str(EXAMPLE), "--out", folder)
            self.assertEqual(done.returncode, 0, done.stderr)
            still = Path(folder) / "still.js"
            still.write_text("Product3D.define('still', function (THREE, kit) { var g = new THREE.Group();"
                             " g.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), kit.plastic('#888'))); return g; });")
            page = Path(folder) / "page.html"
            page.write_text(
                '<!doctype html><style>.btn{display:inline-block}</style>'
                '<figure class="p3d" style="width:300px;height:300px"><div class="p3d-stage" style="width:300px;height:300px"></div>'
                '<button class="btn p3d-btn">Rodyti 3D</button></figure><pre id="p3d-info"></pre>'
                f'<script src="{(Path(folder) / "pedal-bin.js").as_uri()}"></script><script src="{still.as_uri()}"></script>'
                "<script>var f=document.querySelector('.p3d');try{Product3D.mount(f,'still');"
                "document.getElementById('p3d-info').textContent=getComputedStyle(f.querySelector('.p3d-btn')).display}"
                "catch(e){document.getElementById('p3d-info').textContent='error '+e}</script>")
            self.assertIn('<pre id="p3d-info">none</pre>', chrome.dump_dom(page))

    def test_ar_writes_a_glb_and_usdz_in_metres_that_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = run("ar.py", str(EXAMPLE), "--out", folder)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            out = json.loads(done.stdout)
            self.assertGreater(out["glb_check"]["meshes"], 3)
            self.assertEqual(out["usdz_check"]["files"][0], "model.usda")
            self.assertAlmostEqual(out["size_m"][1], 0.6, delta=0.05)  # 2 units tall at 0.3 m a unit
            self.assertIn(out["arkit"], ("ok", None))
            self.assertTrue(Path(out["check"]).is_file())

    def test_ar_waits_for_textures_that_the_exporters_encode_asynchronously(self) -> None:
        # a canvas texture is encoded with canvas.toBlob, which --dump-dom's virtual time does not wait for
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "m.js"
            model.write_text(
                "Product3D.define('label', function (THREE, kit) { var c = document.createElement('canvas'); c.width = c.height = 64;"
                " var g = c.getContext('2d'); g.fillStyle = '#c33'; g.fillRect(0, 0, 64, 64); var t = new THREE.CanvasTexture(c);"
                " var root = new THREE.Group(); root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1),"
                " new THREE.MeshStandardMaterial({ map: t }))); root.userData.metres = 0.1; return root; });")
            done = run("ar.py", str(model), "--out", folder)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            out = json.loads(done.stdout)
            self.assertTrue(any(name.startswith("textures/") for name in out["usdz_check"]["files"]))
            self.assertIn(out["arkit"], ("ok", None))

    def test_ar_without_a_size_in_metres_exits_2_and_says_how_to_give_one(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "m.js"
            model.write_text("Product3D.define('box', function (THREE, kit) { var g = new THREE.Group();"
                             " g.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), kit.plastic('#888'))); return g; });")
            done = run("ar.py", str(model), "--out", folder)
            self.assertEqual(done.returncode, 2)
            self.assertIn("userData.metres", done.stderr)
            self.assertEqual(run("ar.py", str(model), "--out", folder, "--metres", "0.2").returncode, 0)

    def test_sample_measures_box_fill_aspect_and_colours(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "photo.png"
            png(photo, 300, 400, (100, 80, 200, 360), (200, 40, 30))
            done = run("sample.py", str(photo), "--point", "red:150,200", "--point", "bg:10,10")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            out = json.loads(done.stdout)
            self.assertEqual(out["points"], {"red": "#c8281e", "bg": "#ffffff"})
            self.assertAlmostEqual(out["fill"], 0.7, delta=0.01)
            self.assertAlmostEqual(out["aspect"], 2.8, delta=0.06)


if __name__ == "__main__":
    unittest.main()
