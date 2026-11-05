import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "charts" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import raster  # noqa: E402
from render import render  # noqa: E402
from spec import ChartType, SpecError, nice_ticks, parse  # noqa: E402
from theme import THEMES, ThemeName  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"


def spec_of(**fields: object) -> dict:
    base = {"type": "bar", "title": "Thursday failed most", "labels": ["Mon", "Tue", "Thu"],
            "series": [{"name": "Failed", "values": [6, 8, 14]}]}
    base.update(fields)
    return base


def texts(svg: str) -> list[str]:
    return [node.text or "" for node in ElementTree.fromstring(svg).iter(f"{SVG}text")]


class SpecTests(unittest.TestCase):
    def test_each_type_draws_valid_svg_with_its_title(self) -> None:
        for chart in ChartType:
            series = [{"name": "Runs", "values": [6, 8, 14]}]
            if chart not in (ChartType.DONUT,):
                series.append({"name": "Retried", "values": [1, 2, 3]})
            svg = render(parse(spec_of(type=chart.value, series=series)))
            root = ElementTree.fromstring(svg)
            self.assertEqual(root.find(f"{SVG}title").text, "Thursday failed most", chart)
            self.assertIn("Thursday failed most", texts(svg), chart)

    def test_refuses_what_it_cannot_draw_and_says_why(self) -> None:
        cases = {
            "must hold 3 numbers": spec_of(series=[{"name": "A", "values": [1, 2]}]),
            "one of: bar, hbar": spec_of(type="pie"),
            "title": spec_of(title=""),
            "not one of the labels": spec_of(highlight="Sun"),
            "at most 6": spec_of(series=[{"name": str(n), "values": [1, 2, 3]} for n in range(7)]),
            "donut shows one series": spec_of(type="donut", series=[{"name": "A", "values": [1, 2, 3]}] * 2),
            "negative": spec_of(type="stacked", series=[{"name": "A", "values": [1, -2, 3]}]),
            "not a number": spec_of(series=[{"name": "A", "values": [1, "2", 3]}]),
        }
        for words, raw in cases.items():
            with self.assertRaises(SpecError, msg=words) as caught:
                parse(raw)
            self.assertIn(words, str(caught.exception))

    def test_bars_start_at_zero_and_a_line_may_not(self) -> None:
        bars = render(parse(spec_of(series=[{"name": "A", "values": [90, 95, 100]}])))
        self.assertIn("0", texts(bars))
        line = render(parse(spec_of(type="line", zero=False, series=[{"name": "A", "values": [90, 95, 100]}])))
        self.assertNotIn("0", texts(line))

    def test_ticks_are_round_and_carry_only_the_decimals_they_need(self) -> None:
        self.assertEqual(nice_ticks(0, 14), [0, 5, 10, 15])
        self.assertEqual(nice_ticks(0, 96.4), [0, 25, 50, 75, 100])
        spec = parse(spec_of(prefix="$", decimals=1))
        self.assertEqual(spec.tick(25, [0, 25, 50]), "$25")
        self.assertEqual(spec.tick(0.25, [0, 0.25, 0.5]), "$0.25")
        self.assertEqual(spec.format(96.4), "$96.4")
        self.assertEqual(spec.format(12_500, compact=True), "$12.5k")
        self.assertEqual(spec.format(-3), "-$3.0")

    def test_highlight_keeps_one_label_in_colour(self) -> None:
        svg = render(parse(spec_of(highlight="Thu")))
        fills = [node.get("fill") for node in ElementTree.fromstring(svg).iter(f"{SVG}path")]
        theme = THEMES[ThemeName.DARK]
        self.assertEqual(fills.count(theme.series[0]), 1)
        self.assertEqual(fills.count(theme.faded), 2)

    def test_text_is_escaped(self) -> None:
        svg = render(parse(spec_of(title="Q&A <spend>", labels=["a<b", "c&d", "e"])))
        self.assertIn("Q&A <spend>", texts(svg))


def contrast(a: str, b: str) -> float:
    def luminance(colour: str) -> float:
        channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ThemeTests(unittest.TestCase):
    def test_series_hold_3_to_1_and_text_4_5_to_1_on_their_background(self) -> None:
        for name, theme in THEMES.items():
            for colour in theme.series:
                self.assertGreaterEqual(contrast(colour, theme.background), 3, f"{name.value} {colour}")
            for colour in (theme.text, theme.text_2, theme.muted):
                self.assertGreaterEqual(contrast(colour, theme.background), 4.5, f"{name.value} {colour}")


class ScriptTests(unittest.TestCase):
    def run_script(self, raw: str, out: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "chart.py"), "-", "--out", out],
                              input=raw, capture_output=True, text=True, check=False)

    def test_writes_svg_and_csv_and_names_them(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            done = self.run_script(json.dumps(spec_of()), out)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(done.stdout)
            self.assertTrue(result["svg"].endswith("thursday-failed-most.svg"))
            self.assertEqual(Path(result["csv"]).read_text().splitlines(), ["label,Failed", "Mon,6", "Tue,8", "Thu,14"])

    def test_a_bad_spec_exits_2_with_the_reason(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            done = self.run_script(json.dumps(spec_of(type="pie")), out)
            self.assertEqual(done.returncode, 2)
            self.assertIn("spec: `type` is 'pie'", done.stderr)
            done = self.run_script("{not json", out)
            self.assertEqual(done.returncode, 2)
            self.assertIn("spec: cannot read it", done.stderr)

    def test_no_drawer_leaves_the_png_out_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            svg = Path(out) / "a.svg"
            svg.write_text(render(parse(spec_of())))
            with mock.patch.object(raster.shutil, "which", return_value=None), \
                    mock.patch.object(raster, "_chrome", return_value=None), \
                    mock.patch.object(raster.platform, "system", return_value="Linux"):
                self.assertIsNone(raster.to_png(svg, Path(out) / "a.png", 960, 540))


if __name__ == "__main__":
    unittest.main()
