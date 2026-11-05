---
name: charts
description: Draws a chart from numbers in Selan's style (Reactor's graphite colours, Inter) as a PNG and an SVG, with the numbers beside it as a CSV. Use whenever someone asks for a chart, graph, plot or visual of data, or when a picture would answer a question about a trend, a ranking, a share or a comparison better than a table, including when an agent should attach a chart to its reply. Do not use for diagrams, flowcharts, mockups or pictures that are not data.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/chart.py *)
---

# Charts

A chart says one thing. Work out that thing first; the rest follows from it.

## 1. The takeaway

Write the one sentence the chart should leave in the reader's head: "Thursday failed most: 14 runs, twice the
week's average", not "Failed runs per day". That sentence is the `title`. What is measured, the period and the
unit go in the `subtitle`. If the data does not show a takeaway, say so to the person rather than drawing one.

## 2. The type

| The question | `type` |
|---|---|
| How did it change over time? | `line` (or `bar` for 7 or fewer periods of counts) |
| Which is bigger, for 12 or fewer short-named categories? | `bar` |
| A ranking, long names, or more than 7 categories | `hbar`, sorted largest first |
| What is each total made of, across categories? | `stacked` |
| What share of one whole is each part, 6 parts or fewer? | `donut` (more parts: `hbar`) |

Bars always start at zero; the script does it. A line may leave zero out (`"zero": false`) when the change is
the point and zero is far below. More than 6 series, or a donut over 6 slices, is refused: group the small ones
as "Other". Order categories by value unless they have their own order (days, months, steps).

## 3. The spec

```json
{
  "type": "bar",
  "title": "Thursday failed most: 14 runs, twice the week's average",
  "subtitle": "Failed Reactor runs per day, week 45",
  "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  "series": [{ "name": "Failed runs", "values": [6, 8, 5, 14, 7, 2, 3] }],
  "highlight": "Thu",
  "source": "Source: Reactor runs, 2–8 Nov 2026"
}
```

| Field | What it holds |
|---|---|
| `type` | `bar`, `hbar`, `line`, `stacked` or `donut`; `bar` if left out |
| `title` | the takeaway, required, two lines at most |
| `subtitle` | what is measured, over when, in what unit |
| `labels` | the categories or dates, in the order drawn |
| `series` | up to 6 of `{ "name", "values" }`, one value per label; a donut takes one |
| `highlight` | one label to keep in colour while the others go grey: use it when one bar or point is the story |
| `prefix`, `suffix`, `decimals` | how values read: `"$"`, `"%"`, `" ms"`; decimals 0 to 4, 0 if left out |
| `theme` | `dark` (default, as Reactor and the app look) or `light` (for documents and slides) |
| `size` | `wide` 960×540 (default), `square` 760×760, `tall` 640×800 for a phone; the PNG is twice that |
| `source` | where the numbers come from, shown small at the bottom |
| `zero` | `false` lets a line's axis leave zero out; bars ignore it |

## 4. Draw it

Write the spec to a file and run:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/chart.py spec.json --out <folder>
```

It needs only Python 3. It prints one JSON line: `svg`, `png`, `csv` (the paths it wrote) and `drawer` (what
turned the SVG into the PNG). Without `--out` it writes to a `selan-charts` folder in the temporary directory;
when the person wants the files in their project, pass that folder. Exit 2 with `spec: ...` names what is wrong
with the spec: fix it and run again. `png` is null when the machine has no SVG drawer (rsvg-convert, resvg, Chrome
or Chromium); the SVG and CSV are still written, and `note` says what to install.

## 5. Look before you hand it over

Read the PNG. Check that the title fits, that no label is cut or overlaps another, and that the takeaway can be
seen without reading the subtitle. If not, shorten the labels, change the type or the size, and draw it again.

## 6. Hand it over

In a Selan Reactor chat, attach the PNG with the `attach_file` tool, and the CSV too when the person may want the
numbers; say the takeaway in your reply in one line. Elsewhere, give the paths. Say where the numbers came from.

The rules behind these choices, with their sources: [references/rules.md](references/rules.md).
