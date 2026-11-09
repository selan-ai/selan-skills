# The kit

`model.js` gets `THREE` (three.js 0.187, the whole library) and `kit`. All sizes are in model units; the main
body's width is 1.

## Shapes

| Call | Makes |
|---|---|
| `kit.loft(rings, {capTop, capBottom, seg})` | a closed wall through rounded-rectangle rings `[{y, w, d, r}]`, bottom to top. Tapered bodies, lids, tubs. `w = d = 2r` gives a circle, so also cylinders and cones. Caps are flat with a hard edge |
| `kit.shoulder(y0, rise, inset, w, d, r, steps)` | the rings of a rounded shoulder (a quarter ellipse): append them to a loft's rings to round its top edge into the top |
| `kit.roundedRect(w, d, r, seg)` | the `[x, z]` points of one ring |
| `kit.roundedSlab(w, d, h, r)` | a rounded box with bevelled edges, centred on the origin: pedals, buttons, panels, flaps |
| `kit.lathe([[radius, y], ...], segments)` | a turned profile, bottom to top: bottles, cups, knobs, screws, anchors |
| `kit.wall({w, d, r})` | the surface of a loft whose rings are `w(y)`, `d(y)`, `r(y)` functions. `.at(s, y)` is the point and outward normal at perimeter distance `s` (0 = front centre, + toward +X, − toward −X) and height `y`; `.side(z, y)` is the `s` of a point on the +X side at depth `z`; `.corner(y)` the `s` of the front corner's middle |
| `kit.decal(wall, shapes, material, lift)` | flat shapes drawn in `(s, y)` and laid on the wall, bending round its corners: printed marks, labels, painted bands, outlines of recesses. `lift` (default 0.004) holds it off the surface |
| `kit.refine(geometry, maxEdge)` | splits triangles until no edge is longer than `maxEdge`; `decal` does it for you |

`kit.shapes`, in the `(s, y)` plane of a wall or the XY plane of a flat face: `circle(cx, cy, r)`,
`ellipse(cx, cy, rx, ry)`, `rect(x0, y0, x1, y1)`, `stroke(x0, y0, x1, y1, halfWidth)` (a capsule),
`path([[x, y], ...], halfWidth)` (a smooth band, as an array of shapes), `arch(cx, y0, halfWidth, y1)` (a doorway).
On a flat face, `new THREE.Mesh(new THREE.ShapeGeometry(shape, 24), material)` turned to lie on it.

## Materials

| Call | For |
|---|---|
| `kit.plastic(color, {roughness, clearcoat, opacity})` | moulded plastic; gloss is low `roughness` (0.2–0.3) and high `clearcoat` (0.6–0.9), matte the reverse |
| `kit.metal(color, {roughness})` | bare metal: steel `#b8bcc2`, zinc-plated `#c9cdd2`, brass `#c8a256` |
| `kit.paint(color, {roughness})` | printed and painted marks; drawn over the surface it sits on |
| `kit.dark(color)` | holes, slots and cavities: unlit near-black, reads as depth |

## Moving parts

A moving part is a `THREE.Group` placed at its hinge, with the part's meshes inside it offset from the hinge.
`root.userData.runtime = { setOpen(t) }` turns all of them for `t` from 0 (closed) to 1 (open); the viewer's
button and a click on the model play it, and the review renders it at 1.

## Traps, each seen once

- **Decide the camera before the shape.** A wrong `--elevation` makes a right lid look too tall or too flat, and
  you end up fixing a shape that was never wrong. Line up the overlay's outline first.
- **A top that rises toward the back** (a lid, a head) is the flat loft sheared after building: add
  `slope * (0.5 - z / depth)` to `y` of the vertices above the shoulder's start, then `computeVertexNormals()`.
  Anything sitting on that top goes in a `Group` rotated by `Math.atan(slope / depth)` about X, so its local
  `y = 0` is the surface.
- **Marks on a sheared or curved surface** go on with the same transform, or they end up under it.
- **Red under clearcoat turns pink** in the studio light: printed marks use `kit.paint`, which has none.
- **Photo colours include the light.** Take the colour from a lit area away from highlights, then darken a little
  if the render still reads lighter than the photo.
- **A decal wider than a face** needs the wall, not a flat plane, or it cuts through the corner: draw it in
  `(s, y)` and use `kit.decal`.
- **Mirror, never rotate,** a left/right pair: build one side with `side = ±1` and multiply X by it.
