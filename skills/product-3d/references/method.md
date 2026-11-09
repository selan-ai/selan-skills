# Why the method is this way

It is the method that rebuilt UAB HODA's frog pedal bin from one product photo (November 2026), with what that
run showed, generalised.

## Taken from img2threejs

[img2threejs](https://github.com/img2threejs/img2threejs) (Apache-2.0; read at commit 0c0c49b, no code copied)
rebuilds an object from a photo as a code-only, staged Three.js model. Kept:

- observation before code: parts big to small, materials, what one view hides, written down before the first line;
- the model is a `Group` factory with a pivot per moving part, so it can animate;
- every round is judged against the photo, side by side, and from views the photo does not have (a turntable),
  because one view passes a model with a hole in its back;
- a bounded number of correction rounds, then stop and say what is still off.

Left out: its 23-step state machine, the strict spec validator (it refused to generate until every material had
PBR maps extracted from the photo), and its code generator, which emits only boxes, cylinders and extrusions.
For a product on a web page, the agent writing the model directly, with a kit for the shapes it keeps needing,
matched the photo in four rounds, while the gates had not yet let any code be generated.

## From the HODA run

- The overlay is the fastest check. Fitting the render to the object's box in the photo makes every proportion
  error visible as an outline that does not line up, without judging two separate pictures.
- Four rounds were enough: proportions and camera, the lid's form, colours, details. The fifth would have
  polished things nobody notices while turning it.
- The likeness came from the marks more than from the geometry: the bin read as that bin once the eyes, the
  tongue and the printed arms were in place. Spend rounds on the marks people recognise.
- The review renders the open state too: a hinge in the wrong place only shows when the part moves.

## Why classic scripts and one file

Chrome refuses ES modules from `file://`, and a sales deck must open from disk. A classic script that sets
`window.THREE` works from disk and from a server alike, the export is plain concatenation with no bundler, and
the scripts need only Python and a Chrome the machine already has.
