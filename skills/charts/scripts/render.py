"""The chart as SVG: a title that says the takeaway, the plot, direct labels where they fit, and the source."""

from __future__ import annotations

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape

from spec import SIZES, ChartType, Layout, Spec, nice_ticks, value_range
from theme import SANS, THEMES, Theme


def width_of(text: str, size: float, bold: bool = False) -> float:
    """About how wide Inter draws `text`: there is no font engine here, so layout leaves room to spare."""
    return len(text) * size * (0.6 if bold else 0.56)


def fit(text: str, size: float, room: float) -> str:
    if width_of(text, size) <= room:
        return text
    keep = max(int(room / (size * 0.56)) - 1, 1)
    return text[:keep].rstrip() + "…"


def wrap(text: str, size: float, room: float, lines: int, bold: bool = False) -> list[str]:
    """`text` in at most `lines` lines; what does not fit ends the last one at a whole word, with an ellipsis."""
    out: list[str] = []
    words = text.split()
    while words and len(out) < lines:
        line = words.pop(0)
        while words and width_of(f"{line} {words[0]}", size, bold) <= room:
            line = f"{line} {words.pop(0)}"
        out.append(line)
    if words:
        kept = out[-1].split()
        while len(kept) > 1 and width_of(" ".join(kept) + "…", size, bold) > room:
            kept.pop()
        line = " ".join(kept) + "…"
        out[-1] = line if width_of(line, size, bold) <= room else fit(line, size, room)
    return out


def title_lines(text: str, layout: Layout, room: float) -> tuple[float, list[str]]:
    """The title in two lines at most: at its size, or a little smaller when that keeps every word."""
    size = layout.title
    while size > round(layout.title * 0.85) and len(wrap(text, size, room, 3, bold=True)) > 2:
        size -= 1
    return size, wrap(text, size, room, 2, bold=True)


def attr(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


@dataclass
class Canvas:
    spec: Spec
    theme: Theme
    layout: Layout

    def __post_init__(self) -> None:
        self.parts: list[str] = []
        self.width = self.layout.width
        self.height = self.layout.height

    def text(self, x: float, y: float, words: str, size: float, fill: str, weight: int = 400, anchor: str = "start") -> None:
        self.parts.append(
            f'<text x="{attr(x)}" y="{attr(y)}" font-size="{attr(size)}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{escape(words)}</text>'
        )

    def text_over_lines(self, x: float, y: float, words: str, size: float, fill: str, weight: int) -> None:
        """Text with a rim of the background around each letter, so gridlines under it stop short of it."""
        self.parts.append(
            f'<text x="{attr(x)}" y="{attr(y)}" font-size="{attr(size)}" font-weight="{weight}" fill="{fill}" '
            f'stroke="{self.theme.background}" stroke-width="4" stroke-linejoin="round" paint-order="stroke">{escape(words)}</text>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 1, dash: str = "") -> None:
        dashes = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{attr(x1)}" y1="{attr(y1)}" x2="{attr(x2)}" y2="{attr(y2)}" stroke="{stroke}" '
            f'stroke-width="{attr(width)}"{dashes}/>'
        )

    def bar(self, x: float, y: float, w: float, h: float, fill: str, end: str) -> None:
        """A bar rounded at its far end only: `end` is up, down or right, from the baseline."""
        r = min(3.0, w / 2, h / 2) if end != "right" else min(3.0, h / 2, w / 2)
        if w <= 0 or h <= 0:
            return
        if end == "up":
            d = f"M{attr(x)} {attr(y + h)}V{attr(y + r)}Q{attr(x)} {attr(y)} {attr(x + r)} {attr(y)}H{attr(x + w - r)}Q{attr(x + w)} {attr(y)} {attr(x + w)} {attr(y + r)}V{attr(y + h)}Z"
        elif end == "down":
            d = f"M{attr(x)} {attr(y)}V{attr(y + h - r)}Q{attr(x)} {attr(y + h)} {attr(x + r)} {attr(y + h)}H{attr(x + w - r)}Q{attr(x + w)} {attr(y + h)} {attr(x + w)} {attr(y + h - r)}V{attr(y)}Z"
        else:
            d = f"M{attr(x)} {attr(y)}H{attr(x + w - r)}Q{attr(x + w)} {attr(y)} {attr(x + w)} {attr(y + r)}V{attr(y + h - r)}Q{attr(x + w)} {attr(y + h)} {attr(x + w - r)} {attr(y + h)}H{attr(x)}Z"
        self.parts.append(f'<path d="{d}" fill="{fill}"/>')

    def svg(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" font-family="{escape(SANS)}" role="img">'
            f"<title>{escape(self.spec.title)}</title>"
        )
        if self.spec.subtitle:
            head += f"<desc>{escape(self.spec.subtitle)}</desc>"
        background = f'<rect width="{self.width}" height="{self.height}" fill="{self.theme.background}"/>'
        return head + background + "".join(self.parts) + "</svg>\n"


def colour(spec: Spec, theme: Theme, series: int, label: str) -> str:
    """A series' colour; with a highlight, the highlighted label keeps it and every other one fades."""
    if spec.highlight and label != spec.highlight:
        return theme.faded
    if len(spec.series) == 1 and spec.type in (ChartType.BAR, ChartType.HBAR):
        return theme.series[0]
    return theme.series[series % len(theme.series)]


def header(canvas: Canvas) -> float:
    """Title, subtitle and, for several series without direct labels, the legend; answers where the plot starts."""
    spec, theme, layout = canvas.spec, canvas.theme, canvas.layout
    pad, label = layout.pad, layout.label
    room = canvas.width - 2 * pad
    size, lines = title_lines(spec.title, layout, room)
    y = pad + size * 0.8
    for line in lines:
        canvas.text(pad, y, line, size, theme.text, 600)
        y += size * 1.25
    if spec.subtitle:
        y += 2
        for line in wrap(spec.subtitle, layout.subtitle, room, 2):
            canvas.text(pad, y, line, layout.subtitle, theme.muted)
            y += layout.subtitle * 1.4
    if legend_needed(canvas):
        y += 10
        x = pad
        for index, one in enumerate(spec.series):
            step = 12 + 6 + width_of(one.name, label) + 18
            if x + step > canvas.width - pad and x > pad:
                x, y = pad, y + label * 1.7
            canvas.parts.append(f'<rect x="{attr(x)}" y="{attr(y - 10)}" width="12" height="12" rx="3" fill="{theme.series[index % len(theme.series)]}"/>')
            canvas.text(x + 18, y, one.name, label, theme.text_2)
            x += step
    return y + 24


def footer(canvas: Canvas) -> float:
    """The source, bottom left; answers where the plot must end."""
    pad, size = canvas.layout.pad, canvas.layout.source
    if not canvas.spec.source:
        return canvas.height - pad
    canvas.text(pad, canvas.height - pad + size * 0.3, wrap(canvas.spec.source, size, canvas.width - 2 * pad, 1)[0], size, canvas.theme.muted)
    return canvas.height - pad - size - 14


def value_axis(canvas: Canvas, top: float, bottom: float, left: float, right: float, vertical: bool) -> tuple[list[float], float, float]:
    """Gridlines and tick labels; answers the ticks and the axis' low and high."""
    spec, theme, label = canvas.spec, canvas.theme, canvas.layout.label
    low, high = value_range(spec)
    ticks = nice_ticks(low, high)
    lo, hi = ticks[0], ticks[-1]
    for tick in ticks:
        words = spec.tick(tick, ticks)
        stroke = theme.baseline if tick == 0 else theme.grid
        if vertical:
            y = bottom - (tick - lo) / (hi - lo) * (bottom - top)
            canvas.line(left, y, right, y, stroke)
            canvas.text(left - 10, y + label * 0.35, words, label, theme.muted, anchor="end")
        else:
            x = left + (tick - lo) / (hi - lo) * (right - left)
            canvas.line(x, top, x, bottom, stroke)
            canvas.text(x, bottom + label + 8, words, label, theme.muted, anchor="middle")
    return ticks, lo, hi


def tick_room(canvas: Canvas) -> float:
    spec = canvas.spec
    ticks = nice_ticks(*value_range(spec))
    return max(width_of(spec.tick(tick, ticks), canvas.layout.label) for tick in ticks) + 14


def category_labels(canvas: Canvas, centres: list[float], y: float, room: float) -> None:
    spec, size = canvas.spec, canvas.layout.label
    widest = max(width_of(label, size) for label in spec.labels)
    every = max(1, math.ceil((widest + 12) / max(room, 1)))
    for index, (label, x) in enumerate(zip(spec.labels, centres)):
        if index % every == 0:
            fill = canvas.theme.text if label == spec.highlight else canvas.theme.muted
            canvas.text(x, y, fit(label, size, room * every - 6), size, fill, 600 if label == spec.highlight else 400, "middle")


def draw_columns(canvas: Canvas, top: float, bottom: float) -> None:
    """Bar (grouped) and stacked: columns up from zero, labels under, values on single-series tops when all of them fit."""
    spec, theme, label = canvas.spec, canvas.theme, canvas.layout.label
    left = canvas.layout.pad + tick_room(canvas)
    right = canvas.width - canvas.layout.pad
    bottom -= label + 12
    _, lo, hi = value_axis(canvas, top, bottom, left, right, vertical=True)

    def y_of(value: float) -> float:
        return bottom - (value - lo) / (hi - lo) * (bottom - top)

    zero = y_of(0)
    slot = (right - left) / len(spec.labels)
    inner = slot * 0.7
    stacked = spec.type == ChartType.STACKED
    width = inner if stacked else (inner - 2 * (len(spec.series) - 1)) / len(spec.series)
    totals = [sum(one.values[index] for one in spec.series) if stacked else spec.series[0].values[index] for index in range(len(spec.labels))]
    labelled = (stacked or len(spec.series) == 1) and all(width_of(spec.format(total), label) <= slot - 4 for total in totals)
    for index, name in enumerate(spec.labels):
        x0 = left + slot * index + (slot - inner) / 2
        base = 0.0
        for place, one in enumerate(spec.series):
            value = one.values[index]
            fill = colour(spec, theme, place, name)
            if stacked:
                y1, y2 = y_of(base + value), y_of(base)
                last = place == len(spec.series) - 1
                if last:
                    canvas.bar(x0, y1, width, y2 - y1, fill, "up")
                else:
                    canvas.parts.append(f'<rect x="{attr(x0)}" y="{attr(y1)}" width="{attr(width)}" height="{attr(y2 - y1)}" fill="{fill}"/>')
                base += value
            else:
                x = x0 + place * (width + 2)
                end = y_of(value)
                canvas.bar(x, min(end, zero), width, abs(zero - end), fill, "up" if value >= 0 else "down")
        if labelled:
            total = totals[index]
            y = y_of(total) - 8 if total >= 0 else y_of(total) + label + 6
            canvas.text(x0 + inner / 2, y, spec.format(total), label, theme.text_2, 600, "middle")
    centres = [left + slot * (index + 0.5) for index in range(len(spec.labels))]
    category_labels(canvas, centres, bottom + label + 10, slot)


@dataclass(frozen=True)
class Scale:
    low: float
    high: float
    left: float
    right: float

    def x(self, value: float) -> float:
        return self.left + (value - self.low) / (self.high - self.low) * (self.right - self.left)


def row_bars(canvas: Canvas, scale: Scale, index: int, y0: float, thick: float) -> None:
    """One category's bars from zero, each single-series one with its value at its end."""
    spec, theme, label = canvas.spec, canvas.theme, canvas.layout.label
    name = spec.labels[index]
    zero = scale.x(0)
    for place, one in enumerate(spec.series):
        value = one.values[index]
        y = y0 + place * (thick + 2)
        end = scale.x(value)
        fill = colour(spec, theme, place, name)
        if value >= 0:
            canvas.bar(zero, y, end - zero, thick, fill, "right")
        else:
            canvas.parts.append(f'<rect x="{attr(end)}" y="{attr(y)}" width="{attr(zero - end)}" height="{attr(thick)}" fill="{fill}"/>')
        if len(spec.series) == 1:
            anchor, x = ("start", end + 8) if value >= 0 else ("end", end - 8)
            canvas.text(x, y + thick / 2 + label * 0.35, spec.format(value), label, theme.text_2, 600, anchor)


def names_above(canvas: Canvas, top: float, bottom: float) -> bool:
    """On a narrow canvas, names wider than three tenths of it go above their bars, while each row has room for a line."""
    spec, label = canvas.spec, canvas.layout.label
    widest = max(width_of(name, label) for name in spec.labels)
    row = (bottom - top) / len(spec.labels)
    return canvas.layout.names_above and widest + 14 > canvas.width * 0.3 and row >= label * (2 + len(spec.series) / 2)


def value_room(canvas: Canvas, values: list[float]) -> float:
    """What the widest of these values needs beside its bar's end; values show only on single-series bars."""
    spec = canvas.spec
    if len(spec.series) > 1 or not values:
        return 0.0
    return max(width_of(spec.format(value), canvas.layout.label, bold=True) for value in values) + 10


def draw_rows(canvas: Canvas, top: float, bottom: float) -> None:
    """Horizontal bars: a category per row, its name at the left, its value at the bar's end."""
    if names_above(canvas, top, bottom):
        draw_rows_named_above(canvas, top, bottom)
        return
    spec, theme, layout = canvas.spec, canvas.theme, canvas.layout
    label = layout.label
    names = min(max(width_of(name, label) for name in spec.labels) + 14, canvas.width * 0.38)
    left = layout.pad + names
    right = canvas.width - layout.pad - value_room(canvas, list(spec.series[0].values))
    bottom -= label + 14
    _, lo, hi = value_axis(canvas, top, bottom, left, right, vertical=False)
    scale = Scale(lo, hi, left, right)
    row = (bottom - top) / len(spec.labels)
    inner = row * 0.68
    thick = (inner - 2 * (len(spec.series) - 1)) / len(spec.series)
    for index, name in enumerate(spec.labels):
        strong = name == spec.highlight
        canvas.text(left - 12, top + row * (index + 0.5) + label * 0.35, fit(name, label, names - 14), label, theme.text if strong else theme.text_2, 600 if strong else 400, "end")
        row_bars(canvas, scale, index, top + row * index + (row - inner) / 2, thick)


def draw_rows_named_above(canvas: Canvas, top: float, bottom: float) -> None:
    """Each name on its own line over its bar. One series carries its values on the bars and needs no axis."""
    spec, theme, layout = canvas.spec, canvas.theme, canvas.layout
    label = layout.label
    values = spec.series[0].values
    left = layout.pad + value_room(canvas, [value for value in values if value < 0])
    right = canvas.width - layout.pad - value_room(canvas, [value for value in values if value >= 0])
    if len(spec.series) == 1:
        low, high = value_range(spec)
        scale = Scale(low, max(high, low + 1), left, right)
        if low < 0:
            canvas.line(scale.x(0), top, scale.x(0), bottom, theme.baseline)
    else:
        bottom -= label + 14
        _, lo, hi = value_axis(canvas, top, bottom, left, right, vertical=False)
        scale = Scale(lo, hi, left, right)
    row = (bottom - top) / len(spec.labels)
    named = label + 5
    count = len(spec.series)
    inner = min((row - named) * 0.62, count * label * 1.6 + 2 * (count - 1))
    thick = (inner - 2 * (count - 1)) / count
    for index, name in enumerate(spec.labels):
        y0 = top + row * index + named
        strong = name == spec.highlight
        words = fit(name, label, canvas.width - 2 * layout.pad)
        canvas.text_over_lines(layout.pad, y0 - 5, words, label, theme.text if strong else theme.text_2, 600 if strong else 400)
        row_bars(canvas, scale, index, y0, thick)


def end_names_fit(canvas: Canvas) -> bool:
    """A line's series are named at their last points unless the names would take three tenths of the width."""
    widest = max(width_of(one.name, canvas.layout.label, bold=True) for one in canvas.spec.series)
    return widest + 12 <= canvas.width * 0.3


def legend_needed(canvas: Canvas) -> bool:
    """Several series get a legend where their names cannot sit on the data."""
    spec = canvas.spec
    if len(spec.series) < 2:
        return False
    if spec.type == ChartType.LINE:
        return not end_names_fit(canvas)
    return spec.type in (ChartType.BAR, ChartType.HBAR, ChartType.STACKED)


def draw_lines(canvas: Canvas, top: float, bottom: float) -> None:
    """Lines over even steps; each series named at its last point, or a single one's last value shown there."""
    spec, theme, layout = canvas.spec, canvas.theme, canvas.layout
    label = layout.label
    single = len(spec.series) == 1
    if single:
        ends = [spec.format(spec.series[0].values[-1])]
    else:
        ends = [one.name for one in spec.series] if end_names_fit(canvas) else []
    left = layout.pad + tick_room(canvas)
    right = canvas.width - layout.pad - (max(width_of(words, label, bold=True) for words in ends) + 12 if ends else 6)
    bottom -= label + 12
    _, lo, hi = value_axis(canvas, top, bottom, left, right, vertical=True)
    count = len(spec.labels)
    step = (right - left) / max(count - 1, 1)
    xs = [left + step * index if count > 1 else (left + right) / 2 for index in range(count)]

    def y_of(value: float) -> float:
        return bottom - (value - lo) / (hi - lo) * (bottom - top)

    if spec.highlight:
        x = xs[spec.labels.index(spec.highlight)]
        canvas.line(x, top, x, bottom, theme.baseline, 1, "4 4")
    marks = count <= 12
    placed: list[tuple[float, int]] = []
    for place, one in enumerate(spec.series):
        stroke = theme.series[place % len(theme.series)]
        points = " ".join(f"{attr(x)},{attr(y_of(value))}" for x, value in zip(xs, one.values))
        canvas.parts.append(f'<polyline points="{points}" fill="none" stroke="{stroke}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
        for index, (x, value) in enumerate(zip(xs, one.values)):
            if marks or index == count - 1 or spec.labels[index] == spec.highlight:
                canvas.parts.append(f'<circle cx="{attr(x)}" cy="{attr(y_of(value))}" r="4" fill="{stroke}" stroke="{theme.background}" stroke-width="2"/>')
        placed.append((y_of(one.values[-1]), place))
    placed.sort()
    last = -math.inf
    for y, place in placed if ends else []:
        y = max(y, last + label + 4)
        last = y
        canvas.text(xs[-1] + 10, y + label * 0.35, ends[place], label, theme.series[place % len(theme.series)], 600)
    category_labels(canvas, xs, bottom + label + 10, step if count > 1 else right - left)


def slice_path(cx: float, cy: float, outer: float, inner: float, start: float, end: float) -> str:
    def point(radius: float, angle: float) -> str:
        return f"{attr(cx + radius * math.sin(angle))} {attr(cy - radius * math.cos(angle))}"

    big = 1 if end - start > math.pi else 0
    return (
        f"M{point(outer, start)}A{attr(outer)} {attr(outer)} 0 {big} 1 {point(outer, end)}"
        f"L{point(inner, end)}A{attr(inner)} {attr(inner)} 0 {big} 0 {point(inner, start)}Z"
    )


def draw_donut(canvas: Canvas, top: float, bottom: float) -> None:
    """One series as slices from twelve o'clock, the total in the middle, each slice's name, value and share beside."""
    spec, theme, layout = canvas.spec, canvas.theme, canvas.layout
    pad, label = layout.pad, layout.label
    values = spec.series[0].values
    total = sum(values)
    rows = len(spec.labels)
    beside = canvas.width >= 900
    if beside:
        radius = min((bottom - top) / 2, (canvas.width - 2 * pad) * 0.25)
        cx, cy = pad + radius, (top + bottom) / 2
    else:
        legend = rows * layout.legend_row
        radius = min((bottom - top - legend - 28) / 2, (canvas.width - 2 * pad) / 2)
        cx, cy = canvas.width / 2, top + radius
    start = 0.0
    for index, (name, value) in enumerate(zip(spec.labels, values)):
        share = value / total
        if share <= 0:
            continue
        fill = colour(spec, theme, index, name)
        end = start + share * 2 * math.pi
        if share >= 0.9999:
            half = start + math.pi
            path = slice_path(cx, cy, radius, radius * 0.62, start, half) + slice_path(cx, cy, radius, radius * 0.62, half, start + 2 * math.pi)
        else:
            path = slice_path(cx, cy, radius, radius * 0.62, start, end)
        canvas.parts.append(f'<path d="{path}" fill="{fill}" stroke="{theme.background}" stroke-width="2"/>')
        start = end
    hole = radius * 0.62
    words = spec.format(total, compact=True)
    size = min(layout.total, hole * 1.8 / width_of(words, 1, bold=True))
    canvas.text(cx, cy + size * 3 / 14, words, size, theme.text, 600, "middle")
    name = spec.series[0].name
    if name and width_of(name, label) <= min(radius * 1.1, 2 * math.sqrt(max(hole ** 2 - (size + 2) ** 2, 0)) - 8):
        canvas.text(cx, cy + size, name, label, theme.muted, anchor="middle")
    if beside:
        x = cx + radius + 48
        gap = min(40.0, (bottom - top) / rows)
        y = cy - gap * (rows - 1) / 2
    else:
        x = pad
        gap = layout.legend_row
        y = cy + radius + 28 + 14
    room = canvas.width - pad - x - 22
    for index, (name, value) in enumerate(zip(spec.labels, values)):
        fill = colour(spec, theme, index, name)
        canvas.parts.append(f'<rect x="{attr(x)}" y="{attr(y - 11)}" width="14" height="14" rx="3" fill="{fill}"/>')
        figures = f"{spec.format(value)}  ·  {value / total * 100:.0f}%"
        canvas.text(x + 22, y, fit(name, layout.legend, room - width_of(figures, label) - 12), layout.legend, theme.text_2, 600 if name == spec.highlight else 400)
        canvas.text(canvas.width - pad, y, figures, label, theme.muted, anchor="end")
        y += gap


DRAW = {
    ChartType.BAR: draw_columns,
    ChartType.STACKED: draw_columns,
    ChartType.HBAR: draw_rows,
    ChartType.LINE: draw_lines,
    ChartType.DONUT: draw_donut,
}


def render(spec: Spec) -> str:
    canvas = Canvas(spec, THEMES[spec.theme], SIZES[spec.size])
    top = header(canvas)
    bottom = footer(canvas)
    DRAW[spec.type](canvas, top, bottom)
    return canvas.svg()
