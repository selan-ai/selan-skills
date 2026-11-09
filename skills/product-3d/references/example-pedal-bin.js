// A pedal bin, written with the product-3d kit: tapered body lofted from rounded rectangles, a lid whose top rises
// toward the back, a printed band that follows the corners, an arched pedal recess, and two moving parts.
// Frame: Y up, front +Z, the bin's own right +X; units: body width at the rim = 1.
Product3D.define('pedal-bin', function (THREE, kit) {
  var root = new THREE.Group();
  root.name = 'pedal-bin';

  var body = kit.plastic('#2a2a2e', { roughness: 0.3, clearcoat: 0.75 });
  var green = kit.plastic('#1f5c33', { roughness: 0.28, clearcoat: 0.8 });

  // ---- body: measured from the photo as 1.6 tall, 1.0 wide at the rim, tapering 10% to the floor
  var H = 1.6;
  var w = function (y) { return THREE.MathUtils.lerp(0.9, 1.0, y / H); };
  var d = function (y) { return THREE.MathUtils.lerp(0.86, 0.96, y / H); };
  var r = function (y) { return THREE.MathUtils.lerp(0.13, 0.16, y / H); };
  var rings = [0, 0.2, 0.215, 0.23, 0.8, H].map(function (y) {
    var groove = y === 0.215 ? 0.006 : 0; // shallow groove where the base meets the wall
    return { y: y, w: w(y) - groove, d: d(y) - groove, r: r(y) };
  });
  root.add(new THREE.Mesh(kit.loft(rings, { capBottom: true }), body));
  var wall = kit.wall({ w: w, d: d, r: r });

  // printed band around the front and both sides, wrapping the corners
  var band = [];
  [1, -1].forEach(function (side) { band.push(kit.shapes.rect(0, 0.98, side * wall.side(-0.35, 1.0), 1.06)); });
  root.add(kit.decal(wall, band, kit.paint('#d9dcd6')));

  // arched recess at the front of the base, with the pedal in it
  root.add(kit.decal(wall, [kit.shapes.arch(0, 0.005, 0.2, 0.44)], kit.paint('#151517', { roughness: 0.8 })));
  root.add(kit.decal(wall, [kit.shapes.arch(0, 0.005, 0.165, 0.405)], kit.dark(), 0.006));
  var pedal = new THREE.Group(); // hinge inside the recess
  pedal.position.set(0, 0.035, d(0.035) / 2 - 0.06);
  var tab = new THREE.Mesh(kit.roundedSlab(0.34, 0.2, 0.035, 0.03), green);
  tab.position.z = 0.1;
  pedal.add(tab);
  root.add(pedal);

  // ---- lid: skirt over the rim, rounded shoulder, top rising toward the back
  var lid = new THREE.Group();
  lid.position.y = H - 0.06;
  root.add(lid);
  var LW = 1.12, LD = 1.08, LR = 0.2, SLOPE = 0.12;
  var lr = [
    { y: 0, w: LW, d: LD, r: LR },
    { y: 0.03, w: LW + 0.01, d: LD + 0.01, r: LR },
    { y: 0.1, w: LW, d: LD, r: LR },
    { y: 0.11, w: LW - 0.014, d: LD - 0.014, r: LR }, // crease across the skirt
    { y: 0.125, w: LW - 0.004, d: LD - 0.004, r: LR },
    { y: 0.22, w: LW - 0.02, d: LD - 0.02, r: LR },
  ].concat(kit.shoulder(0.22, 0.13, 0.15, LW - 0.02, LD - 0.02, LR));
  var topY = lr[lr.length - 1].y;
  var lidGeo = kit.loft(lr, { capTop: true });
  var p = lidGeo.getAttribute('position'); // shear: the rear rises by SLOPE, the front stays
  for (var i = 0; i < p.count; i++) {
    var y = p.getY(i);
    if (y > 0.125) p.setY(i, y + Math.min(1, (y - 0.125) / (topY - 0.125)) * SLOPE * (0.5 - p.getZ(i) / LD));
  }
  lidGeo.computeVertexNormals();
  lid.add(new THREE.Mesh(lidGeo, green));

  // a frame lying on the sloped top: local y = 0 is the surface
  var top = new THREE.Group();
  top.position.y = topY + SLOPE * 0.5;
  top.rotation.x = Math.atan(SLOPE / LD);
  lid.add(top);
  var hole = new THREE.Mesh(new THREE.ShapeGeometry(kit.shapes.ellipse(0, 0, 0.21, 0.27), 32).rotateX(-Math.PI / 2), kit.dark());
  hole.position.set(0, 0.003, 0.08);
  top.add(hole);
  var flap = new THREE.Group(); // hinge at its rear edge
  flap.position.z = -0.26;
  top.add(flap);
  var panel = new THREE.Mesh(kit.roundedSlab(0.5, 0.66, 0.03, 0.08), kit.plastic('#1a5a30', { roughness: 0.2, clearcoat: 0.9 }));
  panel.position.set(0, 0.012, 0.33);
  flap.add(panel);

  root.userData.metres = 0.3; // the body is about 30 cm wide
  root.userData.runtime = {
    setOpen: function (t) {
      var k = THREE.MathUtils.clamp(t, 0, 1);
      pedal.rotation.x = 0.22 * k;
      flap.rotation.x = -1.15 * THREE.MathUtils.smoothstep(k, 0.1, 1);
    },
  };
  return root;
});
