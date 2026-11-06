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
from render import render, width_of  # noqa: E402
from spec import SIZES, ChartType, Size, SpecError, nice_ticks, parse  # noqa: E402
from theme import THEMES, ThemeName  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"


def spec_of(**fields: object) -> dict:
    base = {"type": "bar", "title": "Thursday failed most", "labels": ["Mon", "Tue", "Thu"],
            "series": [{"name": "Failed", "values": [6, 8, 14]}]}
    base.update(fields)
    return base


def texts(svg: str) -> list[str]:
    return [node.text or "" for node in ElementTree.fromstring(svg).iter(f"{SVG}text")]


def text_nodes(svg: str) -> list[ElementTree.Element]:
    return list(ElementTree.fromstring(svg).iter(f"{SVG}text"))


class SpecTests(unittest.TestCase):
    def test_each_type_draws_valid_svg_with_its_title_at_each_size(self) -> None:
        for chart in ChartType:
            series = [{"name": "Runs", "values": [6, 8, 14]}]
            if chart not in (ChartType.DONUT,):
                series.append({"name": "Retried", "values": [1, 2, 3]})
            for size in Size:
                svg = render(parse(spec_of(type=chart.value, series=series, size=size.value)))
                root = ElementTree.fromstring(svg)
                self.assertEqual(root.find(f"{SVG}title").text, "Thursday failed most", (chart, size))
                self.assertIn("Thursday failed most", texts(svg), (chart, size))

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
                self.assertIsNone(raster.to_png(svg, Path(out) / "a.png", SIZES[Size.WIDE]))

    def test_the_phone_png_is_drawn_at_three_times_and_the_others_at_two(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            svg = Path(out) / "a.svg"
            svg.write_text(render(parse(spec_of(size="phone"))))
            for size, scale in ((Size.PHONE, "3"), (Size.WIDE, "2")):
                with mock.patch.object(raster.shutil, "which", return_value="/usr/bin/rsvg-convert"), \
                        mock.patch.object(raster, "_run", return_value=True) as run, \
                        mock.patch.object(raster, "_found", return_value=True):
                    self.assertEqual(raster.to_png(svg, Path(out) / "a.png", SIZES[size]), "rsvg-convert")
                    self.assertEqual(run.call_args.args[0][1:3], ["-z", scale], size.value)


class PhoneTests(unittest.TestCase):
    def test_the_page_sizes_keep_their_canvas_and_type(self) -> None:
        self.assertEqual([(SIZES[size].width, SIZES[size].height, SIZES[size].scale, SIZES[size].title, SIZES[size].label)
                          for size in (Size.WIDE, Size.SQUARE, Size.TALL)],
                         [(960, 540, 2, 26, 13), (760, 760, 2, 26, 13), (640, 800, 2, 26, 13)])

    def test_phone_is_a_360_by_450_canvas_with_type_set_for_a_phone(self) -> None:
        root = ElementTree.fromstring(render(parse(spec_of(size="phone"))))
        self.assertEqual((root.get("width"), root.get("height")), ("360", "450"))
        sizes = {node.text: node.get("font-size") for node in root.iter(f"{SVG}text")}
        self.assertEqual(sizes["Thursday failed most"], "19")
        self.assertEqual(sizes["Mon"], "12")

    def test_a_long_title_takes_two_lines_at_most_and_keeps_whole_words(self) -> None:
        title = "Weekend runs dropped sharply because the nightly maintenance agents were paused for the whole migration week"
        for size in Size:
            svg = render(parse(spec_of(title=title, size=size.value)))
            layout = SIZES[size]
            lines = [node for node in text_nodes(svg) if node.get("font-weight") == "600" and float(node.get("font-size")) > layout.subtitle]
            self.assertLessEqual(len(lines), 2, size.value)
            for node in lines:
                words = node.text.rstrip("…").split()
                self.assertTrue(all(word in title.split() for word in words), f"{size.value}: {node.text}")
                self.assertLessEqual(width_of(node.text, float(node.get("font-size")), bold=True), layout.width - 2 * layout.pad)

    def test_a_short_title_keeps_its_size(self) -> None:
        sizes = [node.get("font-size") for node in text_nodes(render(parse(spec_of(size="phone"))))]
        self.assertEqual(sizes[0], "19")

    def test_long_names_go_above_their_bars_and_one_series_needs_no_axis(self) -> None:
        names = ["Security Agent", "Trigger Watch Agent", "Website Docs Agent", "UX Agent"]
        svg = render(parse(spec_of(type="hbar", size="phone", labels=names, series=[{"name": "Spend", "values": [48, 31, 22, 18]}])))
        drawn = {node.text: node for node in text_nodes(svg)}
        for name in names:
            self.assertEqual(drawn[name].get("x"), "20", name)
        self.assertNotIn("0", drawn)
        short = render(parse(spec_of(type="hbar", size="phone")))
        self.assertEqual({node.text: node for node in text_nodes(short)}["Mon"].get("text-anchor"), "end")

    def test_too_many_rows_for_a_line_each_keep_names_beside(self) -> None:
        names = [f"Agent number {index}" for index in range(12)]
        svg = render(parse(spec_of(type="hbar", size="phone", labels=names, series=[{"name": "Runs", "values": list(range(12, 0, -1))}])))
        anchors = {node.get("text-anchor") for node in text_nodes(svg) if (node.text or "").startswith("Agent")}
        self.assertEqual(anchors, {"end"})


class LabelTests(unittest.TestCase):
    def test_column_values_show_on_every_bar_or_on_none(self) -> None:
        labels = [f"W{week}" for week in range(10)]
        values = [18400, 15200, 12900, 6400, 5100, 3900, 2800, 1900, 900, 400]
        svg = render(parse(spec_of(size="phone", labels=labels, series=[{"name": "Runs", "values": values}])))
        self.assertFalse({"900", "400"} & set(texts(svg)))

    def test_a_donut_names_its_total_only_when_the_name_fits_whole(self) -> None:
        raw = spec_of(type="donut", size="phone", labels=list("ABCDEF"), series=[{"name": "Support tickets opened", "values": [5, 4, 3, 2, 1, 1]}])
        self.assertFalse([words for words in texts(render(parse(raw))) if words.startswith("Support")])

    def test_line_names_too_long_for_the_end_become_a_legend(self) -> None:
        series = [{"name": "Growth and marketing", "values": [1, 2, 3]}, {"name": "Customer support", "values": [2, 2, 1]}]
        svg = render(parse(spec_of(type="line", size="phone", series=series)))
        self.assertEqual(len(list(ElementTree.fromstring(svg).iter(f"{SVG}rect"))), 3)
        self.assertIn("Growth and marketing", texts(svg))


if __name__ == "__main__":
    unittest.main()
