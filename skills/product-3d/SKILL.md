---
name: product-3d
description: Rebuilds a physical product from one photo as a turnable 3D model written in code (Three.js), checks it against the photo, and packs it for a web page or a slide deck, where it loads only when needed and also works offline, with GLB and USDZ files to view it in AR on a phone. Use when someone wants a product, part or object from a photo shown in 3D, to turn on a website or in a presentation. Do not use for people, animals, plants, food, fabric, glass, rooms or scenes, or when exact dimensions matter (ask for the CAD file instead).
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/sample.py *), Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/review.py *), Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/export.py *), Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/ar.py *)
---

# Product in 3D

You write the model as code, from simple shapes, and compare it with the photo until they match. It is a
stylised likeness, not a scan: say so, and never promise exact dimensions.

## 1. Does the photo fit?

Go on only with one whole object on a plain background, made of hard surfaces (plastic, metal, wood, ceramic)
whose parts are boxes, rounded boxes, cylinders, turned profiles or flat cut-outs: bins, boxes, bottles, tools,
fasteners, housings, furniture, packaging. Say no to people, animals, plants, food, fabric, glass and scenes.
When exact dimensions matter, ask for the CAD file instead: a STEP file converted to GLB is exact, and this skill
does not do that. One photo hides the back and one side: tell the person they will be mirrored or guessed, and
ask for a second photo when the hidden side is different.

## 2. Measure the photo

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/sample.py photo.jpg --point lid:230,340 --point body:250,450
```

It prints one JSON line: `box` (the object's pixels), `fill` and `aspect` (its height over the photo's, and over
its own width), `tilt` (how far a long object leans from vertical: a product shot at a slant), and the colour at
each point. Then look at the photo and write down, before any code:

- the parts, big to small: the main masses, the parts on them, the printed marks; which ones move (lid, door,
  pedal, drawer) and where each one's hinge is;
- proportions in pixels turned into units, with the main body's width = 1;
- each material: its colour from `--point` on a lit area away from highlights, glossy or matte, metal or not;
- the camera: `yaw` (0 = straight at the front, + when the photo shows the object's right side) and `elevation`
  (how much of the top shows), as a first guess for step 4.

## 3. Write the model

One file, `model.js`, a classic script (no `import`):

```js
Product3D.define('acme-bin', function (THREE, kit) {
  var root = new THREE.Group();
  // ... meshes from kit.loft / kit.lathe / kit.roundedSlab / THREE geometries, decals from kit.decal
  root.userData.runtime = { setOpen: function (t) { /* t 0..1: rotate the moving parts' pivot groups */ } };
  return root;
});
```

Y up, the front faces +Z, the object's own right is +X, the floor is y = 0. Set `root.userData.metres` to one
unit in metres (from the product's name, a datasheet or a known part), so AR shows it at its real size. Each moving part is a `Group` whose
origin is its hinge, and `setOpen(t)` turns them; leave `runtime` out when nothing moves. Printed marks are
`kit.decal` with `kit.paint`, holes and cavities `kit.dark`. Every kit call and the traps they avoid:
[references/kit.md](references/kit.md). A worked model with a tapered body, a sloped lid, a band round the
corners and two moving parts: [references/example-pedal-bin.js](references/example-pedal-bin.js).

## 4. Compare, fix, repeat

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/review.py model.js --reference photo.jpg --yaw 22 --elevation 15 --out review.png
```

A product shot at a slant: add `--roll <tilt>` with the `tilt` from step 2, and the render leans with it.

Read the PNG. Top row: the photo, the render at 50% over it, the render alone, from the photo's camera and
fitted to the object's box. Bottom row: turned 90°, 180° and 270°, and opened. Exit 1 prints `errors` (a
JavaScript error in the model, with its line): fix it and run again.

Fix one thing per round, in this order, and run again: the camera (`--yaw`, `--elevation` until the overlay's
outline sits on the photo's), the silhouette and proportions, every part from step 2 present and in place,
colours and gloss, then the marks. Five rounds at most; stop when the overlay lines up and no part is missing.
Check the other views too: nothing floating, no holes, no part inside another.

## 5. Pack it

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/export.py model.js --out <folder> --poster photo.jpg --lang lt --load click
```

`<name>.js` holds three.js, the kit and the model in one file (about 200 KB gzip); `<name>.html` is the markup,
style and loader to paste where the model goes. The photo shows first. `--load click` loads the model when the
visitor presses the button (web pages: nothing extra loads with the page); `--load near` loads it as the figure
comes near the screen (slide decks; it works from a deck opened from disk). Give the button the page's own button
class. `--lang en` for English words.

`--ar` also writes `<name>.glb` and `<name>.usdz` (with `ar.py`, which checks both: the GLB read back, the USDZ by
`usdchecker --arkit` where it is installed, as on every Mac) and adds a "view in your space" link. It shows only on
an iPhone or iPad (AR Quick Look) and on Android (Scene Viewer, which needs the page on a public https address).
Serve `.usdz` as `model/vnd.usdz+zip`. The USDZ is text and runs to several MB: keep a model meant for AR under
about 30 000 triangles.

## 6. Hand it over

Give the review PNG and the paths, and say what is approximate: the hidden sides, the dimensions, any mechanism
the photo does not show. In a Selan Reactor chat, attach the review PNG with `attach_file`. Ask before publishing
a model of a company's product anywhere public.

Why the method is this way, and what it took from img2threejs: [references/method.md](references/method.md).
