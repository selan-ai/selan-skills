---
name: selan-site-design
description: How a Selan Modernise website looks, and how to choose its template and check it before anyone sees it. Use when building, rebuilding or restyling a company's site or preview (the Site Rebuilder, rebuild/template), choosing one of the templates for a company, adding a new template, or doing visual QA of a preview. Not for Selan's own product pages.
---

# Selan site design

The template code, tools and stock photos live in gitlab.com/selan.ai/web/selan-modernise-web-project (`rebuild/`);
the paths below are relative to that repository. This copy is the same skill for people building sites by hand.

Every Modernise site is built from `rebuild/template` and drawn with one of a small set of **templates**. They are one
family: a real photo leads, a big clean sans in sentence case, a calm light page, generous space, soft cards and pill
buttons. They differ in layout, type and accent, so two companies rarely look alike. The bar is atomis.lt's preview,
which the owner liked: every template must look at least as finished as that.

## The craft (from Anthropic's frontend-design, applied to our sites)

- **Start from the company's world.** Its field, materials and customers decide the photo, the accent and which
  template fits. A forestry firm opens on a pine forest, a feeder line on a ship at sea.
- **One memorable thing per page, everything else quiet.** Usually the hero photo with the headline. A second
  ornament competes with it; take one accessory off before publishing.
- **Typography carries the personality.** Each template has its own family and type scale. Headings are set
  tight and large. Never put one word of a heading in another colour or in italics.
- **Avoid what reads as generated:** a cream page with a serif and a terracotta accent, near-black with one acid
  colour, newspaper hairlines everywhere, identical cards with the same grey shadow, an ALL-CAPS label above every
  heading, meta joined with middle dots, monospace labels, "→" or "↗" after link text, numbered markers on things
  that are not a sequence.
- **Motion: one load moment only** (the hero text rises, the photo settles), nothing that moves on its own after,
  and none at all with reduced motion. Screenshots use `--force-prefers-reduced-motion`.
- **Words are design.** Plain verbs, sentence case, the company's own texts first. A button says what happens
  ("Susisiekti", "Rašyti el. laišką").

## Hard rules (the owner's; `check.py` enforces most of them)

1. Modern 2026 quality, sentence-case headings, at most about 8 words (80 characters) each. A long old heading
   becomes a lead paragraph under a short new one.
2. Photos: the company's own first; else thematic stock from Unsplash or Pexels (`rebuild/stock/`, else found by
   search), self-hosted WebP via `tools/stock_photos.py`. No people's faces, no other companies' logos, nothing that
   passes as the company's own work. **No credit on the page**; photographers and "illustrative" go in `REPORT.md`
   section 6.
3. No em or en dash in visible text, and no " - " used as a dash. Ranges are "3-6".
4. Logo: the company's SVG, a clean vector trace (`tools/trace_logo.py`), or a typographic wordmark (`"logo": ""`).
   Never a raster.
5. No internal notes, preview-only remarks or masked contacts on the page. People appear by role only when the
   company allowed it; until then they are left out.
6. No rounded box inside a rounded box. Icons are bare, never in a tinted tile inside a card.
7. No closing call-to-action block when the page has a contact section (`build.py` merges it into the contact
   heading). The footer is one line: legal name, company code, VAT code, privacy link, copyright.
8. No `ch` caps on text width: the grid sets it.
9. The map is a pre-rendered Mapbox static image (`tools/staticmap.py`, `MAPBOX_TOKEN`, also in Secret Manager
   selan-prod `mapbox-static-token`), never a script or iframe, and the token never reaches the HTML.
   `MAPBOX_ZOOM` 14 to 15 in a town, 11 to 12 in the countryside.
10. Company data only, nothing invented. Every new sentence is listed in `REPORT.md` section 3.

## Choosing a template

`python3 tools/pick_design.py <site> --code <company code> --field <field> [--brand <logo hex>] [--template <name>]`
writes `site.json` `design` and prints the line for `REPORT.md` section 6. The rule:

| Field | Templates, best first |
|---|---|
| forestry | panorama |
| farming, tourism | panorama, split |
| food, retail | split, panorama |
| beauty, health, creative | split |
| construction | panorama, harbour |
| industrial | harbour, panorama |
| transport | harbour |
| auto, tech | harbour, split |
| professional | split, harbour |
| other | panorama, split, harbour |

With more than one template for the field, the company code chooses: `code mod count` picks the position, so the
same company always gets the same design and neighbours in a field split between them. `--template` is a person's
override. The accent is the logo's colour when white text on it passes 4.5:1, else the template's accent for the
field (`ACCENTS` in `pick_design.py`).

## The catalogue

All three share `build.py`'s section types and `styles.css`'s shared rules; a template is a `body.t-<name>` block in
`styles.css`, its hero in `r_hero`, and its fonts in `FONTS`. Screenshots (1440 and 390) are in `templates/`.

### 1. Panorama (`templates/panorama.jpg`, penki-arai)
- **For** land, nature, outdoor trades, building: forestry, farming, construction.
- **Hero:** a big headline left with the lead and pills beside it, the photo wide below (16:7, rounded), the first key
  facts under the photo as short ruled columns.
- **Type:** Archivo, headings set wide (112%) at 640 weight; one family.
- **Palette:** pale sage page #f3f5f0, ink #17221b, pine accent #24402f, a resin dot #b98a3a.
- **Sections:** what we do as a list beside a sticky heading (no cards); photos as a mosaic (one big, two tall);
  a topic as a photo beside its text; contact as the map with a white card beside it.

### 2. Split (`templates/split.jpg`, cevaita)
- **For** people-facing trades and services: food, retail, beauty, health, professional services.
- **Hero:** text, pills and key facts on the left, a tall rounded photo on the right; `p.badge` (three short lines,
  e.g. a veterinary approval number) adds an oval stamp on the photo's edge.
- **Type:** Epilogue, 700, tight tracking; the wordmark in the accent.
- **Palette:** near-white #f6f6f3, white header bar, ink-violet accent #3d3a78, hay #d9b35b for small marks.
- **Sections:** soft white cards with bare icons; photos as one full-width band; a topic as a square photo beside
  its text; contact as text beside a square map.

### 3. Harbour (`templates/harbour.jpg`, seaconnect)
- **For** logistics, industry, technology, anything with machines and distance: transport, industrial, auto, tech.
- **Hero:** the photo full-bleed under a transparent header, the headline over it in white, the key facts as a strip
  along its foot. A sub-page without a photo gets the same text on a deep accent band. A site with a logo image gets
  a white header bar instead, so the logo keeps its colours.
- **Type:** Sofia Sans Condensed for headings, Sofia Sans for text.
- **Palette:** cool grey page #f2f5f7, navy #0b2b45, harbour blue #0a6aa6, signal orange #e8532f for focus only.
- **Sections:** soft cards, alternating photo rows (`panel` with `flip`), a wide `picture` (route map) with short
  cards under it, `news` as cards with the archive folded; a navy footer.

### Sections every template draws
`stats` (the first one sits in the hero), `features`, `services` (cards to service pages), `listings` (cards with a
price), `partners`, `shops`, `panel` (photo beside text, or a tinted block without a photo), `scenes`, `picture`,
`text` (heading column beside the body), `rich`, `table`, `faq`, `gallery`, `documents`, `news`, `contact` (a page's
`map` joins it), `map` (alone, the same block), `model3d`. A one-page site's menu comes from its short section
headings unless content has `menu`. A new section type is written once in `build.py` and styled for all templates.

## Visual QA (before anything is published or mailed)

Build, `check.py`, then full-page screenshots at 1440 and at 390 with real mobile emulation (Playwright,
`tools/qa_shots.js`), every image opened and looked at. Fix and repeat until all hold:

- `sw` is 390 at 390 px: nothing scrolls sideways (a menu row scrolling inside itself is fine).
- The hero text reads clearly on its photo; the photo's subject is not hidden behind the text.
- Every section starts on the same left edge; no gap bigger than one section's padding; no empty block, broken image
  or map that did not load.
- The last section before the footer keeps a full section's padding below it (buttons and map never touch the
  footer); `qa_shots.js` measures it and exits 1 when the gap is smaller.
- No heading wraps into a lone word; no card text cut off; buttons readable.
- No placeholder, preview note, masked contact, photo credit or internal remark visible.
- Header on a phone: logo, phone pill, then the menu row; it does not cover the content.
- The mail's screenshots (`mail.py`) show the settled page, not one mid-animation.

## Adding a template

1. Plan it the frontend-design way: subject, audience, palette as 4 to 6 hex values, one or two typefaces with roles,
   a layout sketch, the one memorable thing. Check the plan against the "generated" list above and the existing
   templates; change whatever looks like either.
2. Build it on a real company's content at a test path (`public/fd-<slug>/` in selan-previews), screenshot at 1440 and
   390, and have the owner approve it.
3. Add `t-<name>` to `TEMPLATES` and `FONTS`/`PRELOAD_FONT` in `build.py`, its hero branch in `r_hero`, its block in
   `styles.css` (every section type must look right), its fields in `pick_design.py`, and its entry and screenshot
   here.

**Next templates:** the first three are close siblings. Each new one should bring noticeably more variety (layout,
hero, rhythm, type, colour) while staying as modern, calm and photo-led as these.
