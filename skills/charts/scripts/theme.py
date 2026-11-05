"""Selan's chart look: Reactor's graphite tokens (selan-reactor web/graphite.css), and a light twin for documents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThemeName(str, Enum):
    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class Theme:
    background: str
    text: str
    text_2: str
    muted: str
    grid: str
    baseline: str
    faded: str
    series: tuple[str, ...]


SANS = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

THEMES: dict[ThemeName, Theme] = {
    # Graphite: --g-ink behind, --g-series-1..6 in order, --g-line for the grid.
    ThemeName.DARK: Theme(
        background="#171b22",
        text="#ffffff",
        text_2="#d7dee7",
        muted="#8f9bab",
        grid="#2b313b",
        baseline="#5b6676",
        faded="#4a5363",
        series=("#8b6cff", "#4fc9f0", "#3ddc97", "#ffc857", "#f08a61", "#d98bff"),
    ),
    # The same hues a step darker, each at least 3:1 on white (WCAG 1.4.11 for graphics).
    ThemeName.LIGHT: Theme(
        background="#ffffff",
        text="#171b22",
        text_2="#2b313b",
        muted="#5b6676",
        grid="#e6e9ee",
        baseline="#8f9bab",
        faded="#c2c8d1",
        series=("#6b4ee6", "#0e86ad", "#118a5c", "#a86f00", "#c4532a", "#9b4fd1"),
    ),
}
