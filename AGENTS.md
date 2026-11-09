# selan-skills

A Claude Code plugin of skills. What each does is in `README.md`; this file is what the code will not tell you.

## Commands

```sh
python3 -m unittest discover tests                          # every script, on made-up specs; no network
python3 skills/charts/scripts/chart.py examples/failed-runs.json --out /tmp/charts   # one chart, as the skill draws it
python3 skills/product-3d/scripts/review.py skills/product-3d/references/example-pedal-bin.js --yaw 22 --elevation 15   # a 3D review sheet
claude plugin validate .claude-plugin/plugin.json             # manifests and every SKILL.md
claude -p "chart this: ..." --plugin-dir . --model sonnet --output-format json   # the real test: does it trigger, and what it costs
```

## Rules

- **Scripts are standard-library Python 3.9.** macOS's own `python3` is 3.9; Node is not on `PATH` for everyone, and
  a dependency is one more thing to install before a skill works. Every module starts with
  `from __future__ import annotations`.
- **A script lives beside the skill that runs it** and is executed, never read: `SKILL.md` runs it as
  `python3 ${CLAUDE_SKILL_DIR}/scripts/...` and grants exactly that in `allowed-tools`.
- **Nothing is installed at run time.** A skill uses what the machine has and says what is missing; the Reactor agent
  image (selan-remote-agent, `agent/Dockerfile`) carries what Selan's own runs need.
- **The charts look is Reactor's.** Colours come from selan-reactor's `web/graphite.css` (`--g-series-1..6` on
  `--g-ink`); the light theme's are a step darker. `tests/` holds each series to 3:1 and text to 4.5:1 on its
  background: change a colour and that test says whether it still reads.
- **Look at the output.** A change to `render.py` is checked by drawing `examples/` and every type, and reading the
  PNGs, not only by the tests.
- **product-3d runs in Chrome, not Node.** `kit/three.min.js` is a prebuilt classic script (how: its
  `references/vendor.md`), so models are classic scripts too and a deck can open from `file://`; the scripts only
  write a page and run headless Chrome on it. Its tests that need Chrome skip without one.
- **Closed sets are enums** (`ChartType`, `Size`, `ThemeName`), and a spec error names the field and what it may be.

## Releasing

Bump `version` in both `.claude-plugin/plugin.json` and `marketplace.json`, then `gh release create vX.Y.Z`.
Installed copies stay on a version until it changes. `docs/` is gitignored on purpose: specs stay local.
