# Chart rules

What the script does by itself, and what is left to the spec you write.

## Done by the script

- **Bars start at zero.** A bar's length is its value; a cut axis makes small differences look large. Lines may
  leave zero out with `"zero": false`. ([Datawrapper](https://www.datawrapper.de/academy/why-our-column-and-bar-charts-start-at-zero))
- **Labels on the data, not in a legend,** wherever they fit: values at the ends of single-series bars, series
  names at the ends of lines. A legend appears only for grouped and stacked bars.
  ([Datawrapper](https://www.datawrapper.de/blog/text-in-data-visualizations))
- **Round ticks:** steps of 1, 2, 2.5 or 5 times a power of ten, with only the decimals the step needs, and 12k,
  3.4M for large numbers.
- **Colour in a fixed order:** Reactor's series colours (violet, cyan, green, amber, orange, lilac). On the light
  theme each is a step darker, so it holds 3:1 on white
  ([WCAG 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)).
- **Never colour alone:** every series also has its name on the chart.
- **No rotated labels:** a long category name is shortened with an ellipsis; use `hbar` instead.
- **Values on all the columns or on none:** a few labelled bars among unlabelled ones read as a mistake.
- **`phone` is drawn for the phone.** A chat reply's picture spans the reply, 343 to 398 points, so the 360×450
  canvas reads at about its own size: title 19, subtitle 13, labels and values 12, source 11, a 20 margin, and a
  PNG at 3×. `hbar` names that would be cut at the left go on their own line above their bars, and one series then
  needs no axis; line names too long for the line ends become a legend.
- **A title keeps whole words:** two lines at most; one that does not fit is drawn up to 15% smaller, then ends at
  a whole word with an ellipsis.
- **The SVG carries the title and subtitle** as `<title>` and `<desc>`, for screen readers.

## Left to you

- **One takeaway, as the title.** The subtitle says what is measured, when, and in what unit.
- **The type follows the question:** time is a line, amounts are bars, a ranking is horizontal bars, a share of
  one whole with few parts is a donut. ([Datawrapper](https://www.datawrapper.de/blog/chart-types-guide))
- **Few colours.** Past 3 or 4 series a chart gets hard to read: show the ones that matter and group the rest as
  "Other", or use `highlight` to keep one category in colour and grey the rest.
  ([Datawrapper](https://www.datawrapper.de/blog/10-ways-to-use-fewer-colors-in-your-data-visualizations))
- **Donuts only for a few shares** that add up to a whole; slices are hard to compare except near a quarter or a
  half. For precise comparison use bars.
  ([Few](https://www.perceptualedge.com/articles/visual_business_intelligence/save_the_pies_for_dessert.pdf))
- **Order by value** unless the categories have their own order.
- **Short labels:** abbreviate months and days, and names a reader will know.
- **Name the source.**
