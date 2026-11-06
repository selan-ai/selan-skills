"""The chart spec: read from JSON, checked, and the numbers' format and axis ticks it implies."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from enum import Enum

from theme import ThemeName


class ChartType(str, Enum):
    BAR = "bar"
    HBAR = "hbar"
    LINE = "line"
    STACKED = "stacked"
    DONUT = "donut"


class Size(str, Enum):
    WIDE = "wide"
    SQUARE = "square"
    TALL = "tall"
    PHONE = "phone"


@dataclass(frozen=True)
class Layout:
    """A size's canvas in CSS pixels, the scale its PNG is drawn at, and the type sizes and margin that read there."""

    width: int
    height: int
    scale: int
    pad: float
    title: float
    subtitle: float
    label: float
    source: float
    total: float
    legend: float
    legend_row: float
    names_above: bool


WIDE = Layout(width=960, height=540, scale=2, pad=32, title=26, subtitle=16, label=13, source=12, total=28, legend=15,
              legend_row=34, names_above=False)

# `phone` is drawn for the width of a reply in the Selan app's chat (343 to 398 points), so it reads at about 1:1;
# its PNG is three times the canvas, as a phone's screen is.
SIZES: dict[Size, Layout] = {
    Size.WIDE: WIDE,
    Size.SQUARE: replace(WIDE, width=760, height=760),
    Size.TALL: replace(WIDE, width=640, height=800),
    Size.PHONE: Layout(width=360, height=450, scale=3, pad=20, title=19, subtitle=13, label=12, source=11, total=22,
                       legend=13, legend_row=24, names_above=True),
}

MAX_SERIES = 6
MAX_DONUT_SLICES = 6


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Series:
    name: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class Spec:
    type: ChartType
    title: str
    subtitle: str
    labels: tuple[str, ...]
    series: tuple[Series, ...]
    prefix: str
    suffix: str
    decimals: int
    highlight: str
    theme: ThemeName
    size: Size
    source: str
    zero: bool

    @property
    def name(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return slug[:60].rstrip("-") or "chart"

    def format(self, value: float, compact: bool = False, decimals: int | None = None) -> str:
        sign = "-" if value < 0 else ""
        magnitude = abs(value)
        if compact and magnitude >= 10_000:
            for limit, letter in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
                if magnitude >= limit:
                    shown = f"{magnitude / limit:.1f}".rstrip("0").rstrip(".")
                    return f"{sign}{self.prefix}{shown}{letter}{self.suffix}"
        places = self.decimals if decimals is None else decimals
        return f"{sign}{self.prefix}{magnitude:,.{places}f}{self.suffix}"

    def tick(self, value: float, ticks: list[float]) -> str:
        """An axis tick, with only the decimals its step needs: 25, not 25.0."""
        step = abs(ticks[1] - ticks[0]) if len(ticks) > 1 else 1.0
        places = len(f"{step:.4f}".rstrip("0").split(".")[1])
        return self.format(value, compact=True, decimals=places)


def _text(raw: dict, key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise SpecError(f"`{key}` must be text")
    return value.strip()


def _choice(raw: dict, key: str, kind: type[Enum], default: Enum) -> Enum:
    value = raw.get(key, default.value)
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(member.value for member in kind)
        raise SpecError(f"`{key}` is {value!r}; it must be one of: {allowed}") from None


def _series(raw: dict, count: int) -> tuple[Series, ...]:
    items = raw.get("series")
    if not isinstance(items, list) or not items:
        raise SpecError("`series` must be a list of {name, values}, at least one")
    if len(items) > MAX_SERIES:
        raise SpecError(f"{len(items)} series; at most {MAX_SERIES} stay readable: group the rest as Other")
    parsed = []
    for place, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise SpecError(f"series {place} must be an object with `name` and `values`")
        name = item.get("name", "")
        values = item.get("values")
        if not isinstance(name, str):
            raise SpecError(f"series {place}: `name` must be text")
        if not isinstance(values, list) or len(values) != count:
            raise SpecError(f"series {place} ({name or 'unnamed'}): `values` must hold {count} numbers, one per label")
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SpecError(f"series {place} ({name or 'unnamed'}): {value!r} is not a number")
        parsed.append(Series(name.strip(), tuple(float(value) for value in values)))
    return tuple(parsed)


def parse(raw: object) -> Spec:
    """A spec from its JSON, or SpecError naming the first thing wrong with it."""
    if not isinstance(raw, dict):
        raise SpecError("the spec must be a JSON object")
    chart = _choice(raw, "type", ChartType, ChartType.BAR)
    title = _text(raw, "title", "")
    if not title:
        raise SpecError("`title` is required: say the takeaway, not the measure")
    labels = raw.get("labels")
    if not isinstance(labels, list) or not labels or not all(isinstance(label, (str, int, float)) for label in labels):
        raise SpecError("`labels` must be a list of category or date names, at least one")
    series = _series(raw, len(labels))
    decimals = raw.get("decimals", 0)
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 4:
        raise SpecError("`decimals` must be a whole number from 0 to 4")
    highlight = _text(raw, "highlight", "")
    names = [str(label) for label in labels]
    if highlight and highlight not in names:
        raise SpecError(f"`highlight` is {highlight!r}, which is not one of the labels")
    if chart == ChartType.DONUT:
        if len(series) != 1:
            raise SpecError("a donut shows one series: its slices are the labels")
        if len(labels) > MAX_DONUT_SLICES:
            raise SpecError(f"{len(labels)} slices; a donut holds at most {MAX_DONUT_SLICES}: use hbar instead")
        if any(value < 0 for value in series[0].values) or sum(series[0].values) <= 0:
            raise SpecError("a donut's values must be zero or more, and not all zero")
    if chart == ChartType.STACKED and any(value < 0 for one in series for value in one.values):
        raise SpecError("stacked bars cannot show negative values: use bar instead")
    zero = raw.get("zero", True)
    if not isinstance(zero, bool):
        raise SpecError("`zero` must be true or false")
    return Spec(
        type=chart,
        title=title,
        subtitle=_text(raw, "subtitle", ""),
        labels=tuple(names),
        series=series,
        prefix=_text(raw, "prefix", ""),
        suffix=_text(raw, "suffix", ""),
        decimals=decimals,
        highlight=highlight,
        theme=_choice(raw, "theme", ThemeName, ThemeName.DARK),
        size=_choice(raw, "size", Size, Size.WIDE),
        source=_text(raw, "source", ""),
        zero=zero,
    )


def nice_ticks(low: float, high: float, wanted: int = 5) -> list[float]:
    """Round ticks covering low..high: steps of 1, 2, 2.5 or 5 times a power of ten."""
    if high < low:
        low, high = high, low
    if high == low:
        high = low + (abs(low) or 1)
    raw_step = (high - low) / max(wanted - 1, 1)
    power = 10 ** math.floor(math.log10(raw_step))
    step = next(power * factor for factor in (1, 2, 2.5, 5, 10) if power * factor >= raw_step)
    start = math.floor(low / step) * step
    end = math.ceil(high / step) * step
    count = round((end - start) / step)
    return [round(start + step * index, 10) for index in range(count + 1)]


def value_range(spec: Spec) -> tuple[float, float]:
    """The values the value axis must hold: stacked totals for stacked bars, and zero where bars need it."""
    if spec.type == ChartType.STACKED:
        values = [sum(one.values[index] for one in spec.series) for index in range(len(spec.labels))]
    else:
        values = [value for one in spec.series for value in one.values]
    low, high = min(values), max(values)
    if spec.type != ChartType.LINE or spec.zero:
        low, high = min(low, 0), max(high, 0)
    return low, high
