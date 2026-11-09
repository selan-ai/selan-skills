/* product3d.js: the Selan product-3d kit. A classic script (no modules, so it also runs from file://); needs
   window.THREE from three.min.js first. A model file calls Product3D.define(name, (THREE, kit) => group). */
(function () {
  'use strict';
  var T = window.THREE;
  if (!T) throw new Error('product3d.js: load three.min.js first');
  if (window.Product3D) return; // a second copy on the same page keeps the first one's models

  var models = {};

  // ---------------------------------------------------------------- geometry

  // Rounded rectangle in XZ, angle increasing from the (+X,+Z) corner, so lofted quads face outward.
  function roundedRect(w, d, r, seg) {
    seg = seg || 10;
    r = Math.max(0.0001, Math.min(r, w / 2 - 0.0001, d / 2 - 0.0001));
    var pts = [];
    var corners = [[1, 1, 0], [-1, 1, Math.PI / 2], [-1, -1, Math.PI], [1, -1, 1.5 * Math.PI]];
    for (var c = 0; c < 4; c++) {
      var cx = corners[c][0] * (w / 2 - r);
      var cz = corners[c][1] * (d / 2 - r);
      for (var i = 0; i <= seg; i++) {
        var a = corners[c][2] + (i / seg) * (Math.PI / 2);
        pts.push([cx + r * Math.cos(a), cz + r * Math.sin(a)]);
      }
    }
    return pts;
  }

  // Loft through rounded-rectangle rings [{y, w, d, r}], bottom to top; flat caps keep a hard edge.
  // A ring with w = d = 2r is a circle, so the same call makes cylinders, cones and tapered tubs.
  function loft(rings, opts) {
    opts = opts || {};
    var seg = opts.seg || 10;
    var n = 4 * (seg + 1);
    var pos = [];
    var idx = [];
    rings.forEach(function (ring) {
      roundedRect(ring.w, ring.d, ring.r, seg).forEach(function (p) { pos.push(p[0], ring.y, p[1]); });
    });
    for (var i = 0; i < rings.length - 1; i++) {
      for (var j = 0; j < n; j++) {
        var a = i * n + j, b = i * n + ((j + 1) % n), c = (i + 1) * n + j, d = (i + 1) * n + ((j + 1) % n);
        idx.push(a, c, b, b, c, d);
      }
    }
    function cap(ring, up) {
      var base = pos.length / 3;
      pos.push(0, ring.y, 0);
      roundedRect(ring.w, ring.d, ring.r, seg).forEach(function (p) { pos.push(p[0], ring.y, p[1]); });
      for (var j = 0; j < n; j++) {
        var p = base + 1 + j, q = base + 1 + ((j + 1) % n);
        if (up) idx.push(base, q, p); else idx.push(base, p, q);
      }
    }
    if (opts.capTop) cap(rings[rings.length - 1], true);
    if (opts.capBottom) cap(rings[0], false);
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  }

  // Rings for a rounded shoulder: a quarter ellipse from (y0, inset 0) to (y0 + rise, inset `inset`).
  function shoulder(y0, rise, inset, w, d, r, steps) {
    var out = [];
    steps = steps || 7;
    for (var i = 1; i <= steps; i++) {
      var a = (i / steps) * (Math.PI / 2);
      var k = inset * (1 - Math.cos(a));
      out.push({ y: y0 + rise * Math.sin(a), w: w - 2 * k, d: d - 2 * k, r: Math.max(0.001, r - k * 0.6) });
    }
    return out;
  }

  // Rounded slab: rounded rectangle w x d in plan, height h, bevelled edges, centred on the origin.
  function roundedSlab(w, d, h, r) {
    var bevel = Math.min(h * 0.45, 0.015);
    var x = w / 2 - bevel, z = d / 2 - bevel;
    var rr = Math.max(0.001, Math.min(r, x, z));
    var s = new T.Shape();
    s.moveTo(-x + rr, -z);
    s.lineTo(x - rr, -z);
    s.absarc(x - rr, -z + rr, rr, -Math.PI / 2, 0, false);
    s.lineTo(x, z - rr);
    s.absarc(x - rr, z - rr, rr, 0, Math.PI / 2, false);
    s.lineTo(-x + rr, z);
    s.absarc(-x + rr, z - rr, rr, Math.PI / 2, Math.PI, false);
    s.lineTo(-x, -z + rr);
    s.absarc(-x + rr, -z + rr, rr, Math.PI, 1.5 * Math.PI, false);
    var g = new T.ExtrudeGeometry(s, {
      depth: Math.max(0.0001, h - 2 * bevel), bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel,
      bevelSegments: 4, curveSegments: 10,
    });
    g.rotateX(Math.PI / 2);
    g.translate(0, h / 2 - bevel, 0);
    g.computeVertexNormals();
    return g;
  }

  // Lathe from [[radius, y], ...] bottom to top: bottles, cups, knobs, screws, anchors.
  function lathe(profile, segments) {
    return new T.LatheGeometry(profile.map(function (p) { return new T.Vector2(p[0], p[1]); }), segments || 64);
  }

  // A bar wound round the Y axis: screw flights, springs, coils, threads. o = { y0, y1, turns, radius, bar, phase }:
  // `radius` is the bar's centre distance from the axis, a number or radius(y, t) with t 0..1 along the bar (so it
  // can follow a taper or fade into a shaft at its ends), `bar` the bar's own radius, `phase` the start angle.
  function helix(o) {
    var radius = typeof o.radius === 'function' ? o.radius : function () { return o.radius; };
    class Helix extends T.Curve {
      getPoint(t, target) {
        var y = o.y0 + (o.y1 - o.y0) * t, a = (o.phase || 0) + t * o.turns * Math.PI * 2, r = radius(y, t);
        return (target || new T.Vector3()).set(Math.cos(a) * r, y, Math.sin(a) * r);
      }
    }
    return new T.TubeGeometry(new Helix(), Math.max(64, Math.ceil(o.turns * 110)), o.bar, 12, false);
  }

  // A wall made by loft(): w(y), d(y), r(y) functions. at(s, y) is the surface point and outward normal at
  // perimeter distance s (0 = front centre, + toward +X, negative mirrors to -X) and height y; wrap() lays a
  // flat (s, y) shape onto it, which is how printed marks, labels and recesses follow corners.
  function wall(fn) {
    var e = 0.001;
    function dims(y) { return { w: fn.w(y), d: fn.d(y), r: Math.max(0.0001, Math.min(fn.r(y), fn.w(y) / 2, fn.d(y) / 2)) }; }
    function at(s, y) {
      var m = dims(y);
      var dw = (fn.w(y + e) - fn.w(y - e)) / (2 * e);
      var dd = (fn.d(y + e) - fn.d(y - e)) / (2 * e);
      var sign = s < 0 ? -1 : 1;
      var t = Math.abs(s);
      var a1 = m.w / 2 - m.r, arc = (Math.PI / 2) * m.r, side = m.d - 2 * m.r;
      var p = new T.Vector3(), n = new T.Vector3(), ang;
      if (t <= a1) { p.set(t, y, m.d / 2); n.set(0, -dd / 2, 1); }
      else if ((t -= a1) <= arc) {
        ang = Math.PI / 2 - t / m.r;
        p.set(a1 + m.r * Math.cos(ang), y, m.d / 2 - m.r + m.r * Math.sin(ang));
        n.set(Math.cos(ang), -(Math.cos(ang) * dw + Math.sin(ang) * dd) / 2, Math.sin(ang));
      } else if ((t -= arc) <= side) { p.set(m.w / 2, y, m.d / 2 - m.r - t); n.set(1, -dw / 2, 0); }
      else if ((t -= side) <= arc) {
        ang = -t / m.r;
        p.set(a1 + m.r * Math.cos(ang), y, -(m.d / 2 - m.r) + m.r * Math.sin(ang));
        n.set(Math.cos(ang), -(Math.cos(ang) * dw - Math.sin(ang) * dd) / 2, Math.sin(ang));
      } else { t -= arc; p.set(Math.max(0, a1 - t), y, -m.d / 2); n.set(0, dd / 2, -1); }
      n.normalize();
      p.x *= sign; n.x *= sign;
      return { p: p, n: n };
    }
    // perimeter distance of the point on the +X side at depth z
    function side(z, y) { var m = dims(y); return m.w / 2 - m.r + (Math.PI / 2) * m.r + (m.d / 2 - m.r - z); }
    // perimeter distance of the front corner's middle
    function corner(y) { var m = dims(y); return m.w / 2 - m.r + (Math.PI / 4) * m.r; }
    function wrap(geometry, lift) {
      lift = lift === undefined ? 0.004 : lift;
      var pos = geometry.getAttribute('position');
      for (var i = 0; i < pos.count; i++) {
        var hit = at(pos.getX(i), pos.getY(i));
        hit.p.addScaledVector(hit.n, lift);
        pos.setXYZ(i, hit.p.x, hit.p.y, hit.p.z);
      }
      geometry.computeVertexNormals();
      return geometry;
    }
    return { at: at, side: side, corner: corner, wrap: wrap };
  }

  // 2D shapes for decals, in the (s, y) plane of a wall or the XY plane of a flat face.
  var shapes = {
    circle: function (cx, cy, r) { var s = new T.Shape(); s.absarc(cx, cy, r, 0, Math.PI * 2, false); return s; },
    ellipse: function (cx, cy, rx, ry) { var s = new T.Shape(); s.absellipse(cx, cy, rx, ry, 0, Math.PI * 2, false, 0); return s; },
    rect: function (x0, y0, x1, y1) { var s = new T.Shape(); s.moveTo(x0, y0); s.lineTo(x1, y0); s.lineTo(x1, y1); s.lineTo(x0, y1); s.lineTo(x0, y0); return s; },
    // capsule outline from (x0,y0) to (x1,y1), half-width hw
    stroke: function (x0, y0, x1, y1, hw) {
      var a = Math.atan2(y1 - y0, x1 - x0), s = new T.Shape();
      s.absarc(x1, y1, hw, a - Math.PI / 2, a + Math.PI / 2, false);
      s.absarc(x0, y0, hw, a + Math.PI / 2, a + 1.5 * Math.PI, false);
      return s;
    },
    // smooth band through [[x, y], ...]: a chain of short capsules
    path: function (points, hw, steps) {
      var curve = new T.SplineCurve(points.map(function (p) { return new T.Vector2(p[0], p[1]); }));
      var pts = curve.getSpacedPoints(steps || 24), out = [];
      for (var i = 0; i < pts.length - 1; i++) out.push(shapes.stroke(pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y, hw));
      return out;
    },
    // arch (door-like): flat bottom at y0, half-width hw, top of the round at y1
    arch: function (cx, y0, hw, y1) {
      var s = new T.Shape();
      s.moveTo(cx - hw, y0); s.lineTo(cx - hw, y1 - hw);
      s.absarc(cx, y1 - hw, hw, Math.PI, 0, true);
      s.lineTo(cx + hw, y0); s.lineTo(cx - hw, y0);
      return s;
    },
  };

  // Split every triangle until no edge is longer than maxEdge, so a flat shape can bend around a corner.
  function refine(geometry, maxEdge) {
    var g = geometry.index ? geometry.toNonIndexed() : geometry;
    var src = g.getAttribute('position'), out = [];
    var a = new T.Vector3(), b = new T.Vector3(), c = new T.Vector3();
    function put(i, j, n) { // point at barycentric grid (i, j) of triangle a, b, c
      out.push(a.x + (b.x - a.x) * i / n + (c.x - a.x) * j / n, a.y + (b.y - a.y) * i / n + (c.y - a.y) * j / n,
        a.z + (b.z - a.z) * i / n + (c.z - a.z) * j / n);
    }
    for (var t = 0; t < src.count; t += 3) {
      a.fromBufferAttribute(src, t); b.fromBufferAttribute(src, t + 1); c.fromBufferAttribute(src, t + 2);
      var n = Math.max(1, Math.ceil(Math.max(a.distanceTo(b), b.distanceTo(c), c.distanceTo(a)) / maxEdge));
      for (var i = 0; i < n; i++) for (var j = 0; i + j < n; j++) {
        put(i, j, n); put(i + 1, j, n); put(i, j + 1, n);
        if (i + j + 2 <= n) { put(i + 1, j, n); put(i + 1, j + 1, n); put(i, j + 1, n); }
      }
    }
    var r = new T.BufferGeometry();
    r.setAttribute('position', new T.Float32BufferAttribute(out, 3));
    r.computeVertexNormals();
    return r;
  }

  // A decal on a wall: flat shapes wrapped onto the surface, drawn over it.
  function decal(onWall, list, material, lift) {
    var m = new T.Mesh(onWall.wrap(refine(new T.ShapeGeometry(list, 12), 0.02), lift), material);
    m.renderOrder = 1;
    return m;
  }

  // ---------------------------------------------------------------- materials

  function plastic(color, o) {
    o = o || {};
    return new T.MeshPhysicalMaterial({
      color: color, metalness: 0, roughness: o.roughness === undefined ? 0.3 : o.roughness,
      clearcoat: o.clearcoat === undefined ? 0.6 : o.clearcoat, clearcoatRoughness: 0.18,
      transparent: !!o.opacity, opacity: o.opacity || 1,
    });
  }
  function metal(color, o) {
    o = o || {};
    return new T.MeshPhysicalMaterial({ color: color, metalness: 1, roughness: o.roughness === undefined ? 0.3 : o.roughness });
  }
  // printed or painted mark: no clearcoat (it turns reds pink under the studio lights), drawn over its surface
  function paint(color, o) {
    o = o || {};
    return new T.MeshStandardMaterial({
      color: color, roughness: o.roughness === undefined ? 0.55 : o.roughness, metalness: 0,
      polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    });
  }
  // a hole or cavity seen from outside: unlit near-black
  function dark(color) { return new T.MeshBasicMaterial({ color: color || '#060606' }); }

  // ---------------------------------------------------------------- registry

  function define(name, create) { models[name] = create; }

  function create(name) {
    var fn = models[name];
    if (!fn) throw new Error('no model "' + name + '" (defined: ' + Object.keys(models).join(', ') + ')');
    var root = fn(T, kit);
    if (!root || !root.isObject3D) throw new Error('model "' + name + '" must return a THREE.Group');
    root.traverse(function (o) { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    return root;
  }

  // ---------------------------------------------------------------- stage and camera

  var TONE = { aces: 'ACESFilmicToneMapping', agx: 'AgXToneMapping', neutral: 'NeutralToneMapping' };

  // The model may set root.userData.look = { toneMapping: 'aces' | 'agx' | 'neutral', exposure, environment }:
  // 'agx' or 'neutral' keep saturated reds and oranges that ACES pushes toward pink. `o` (the caller) wins over it.
  function stage(renderer, model, o) {
    o = o || {};
    var look = (model.userData && model.userData.look) || {};
    renderer.outputColorSpace = T.SRGBColorSpace;
    renderer.toneMapping = T[TONE[o.toneMapping || look.toneMapping || 'aces']] || T.ACESFilmicToneMapping;
    renderer.toneMappingExposure = o.exposure || look.exposure || 1;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = T.PCFSoftShadowMap;
    var scene = new T.Scene();
    if (o.background) scene.background = new T.Color(o.background);
    var pmrem = new T.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = o.environment !== undefined ? o.environment : look.environment !== undefined ? look.environment : 0.75;
    scene.add(model);
    model.updateMatrixWorld(true);
    var box = new T.Box3().setFromObject(model);
    var size = box.getSize(new T.Vector3());
    var span = Math.max(size.x, size.y, size.z);
    var key = new T.DirectionalLight('#ffffff', 1.6);
    key.position.set(-0.6 * span * 2.5, box.max.y + span * 2, span * 2);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    var c = key.shadow.camera;
    c.left = -span; c.right = span; c.top = span * 1.5; c.bottom = -span * 0.5; c.near = 0.01; c.far = span * 10;
    key.shadow.radius = 6;
    key.shadow.bias = -0.0005;
    scene.add(key);
    var rim = new T.DirectionalLight('#ffffff', 0.8);
    rim.position.set(span * 2, box.max.y + span, -span * 2);
    scene.add(rim);
    // soft contact shadow under the footprint
    var cv = document.createElement('canvas');
    cv.width = cv.height = 128;
    var ctx = cv.getContext('2d');
    var grad = ctx.createRadialGradient(64, 64, 4, 64, 64, 64);
    grad.addColorStop(0, 'rgba(0,0,0,0.45)');
    grad.addColorStop(0.55, 'rgba(0,0,0,0.18)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 128, 128);
    if (o.shadow === false) return { scene: scene, box: box }; // a review view matched to a photo has no floor
    var foot = Math.max(size.x, size.z) * 1.8;
    var cx = (box.min.x + box.max.x) / 2, cz = (box.min.z + box.max.z) / 2;
    var shadow = new T.Mesh(new T.PlaneGeometry(foot, foot).rotateX(-Math.PI / 2),
      new T.MeshBasicMaterial({ map: new T.CanvasTexture(cv), transparent: true, depthWrite: false }));
    shadow.position.set(cx, box.min.y + 0.002, cz);
    scene.add(shadow);
    // No floor catching the key light's shadow: from this light a tall object casts a long, cut-off one.
    return { scene: scene, box: box };
  }

  // Screen-space box of every vertex of the model, in pixels of a w x h view.
  function screenBox(model, camera, w, h) {
    var v = new T.Vector3(), b = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
    camera.updateMatrixWorld();
    model.traverse(function (o) {
      if (!o.isMesh || !o.visible) return;
      var pos = o.geometry.getAttribute('position');
      var step = Math.max(1, Math.floor(pos.count / 4000));
      for (var i = 0; i < pos.count; i += step) {
        v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld).project(camera);
        var x = (v.x + 1) / 2 * w, y = (1 - v.y) / 2 * h;
        if (x < b.x0) b.x0 = x; if (x > b.x1) b.x1 = x; if (y < b.y0) b.y0 = y; if (y > b.y1) b.y1 = y;
      }
    });
    return b;
  }

  // Point the camera at the model from yaw/elevation (degrees; yaw 0 = straight at the front, + toward the
  // model's +X side), at the distance where the model's height on screen is `fill` of the view; with `box`
  // (target pixels [x0, y0, x1, y1] in a w x h view) the model is also moved to sit exactly there.
  function frame(camera, model, o) {
    var w = o.width, h = o.height;
    camera.aspect = w / h;
    camera.clearViewOffset();
    camera.updateProjectionMatrix();
    model.updateMatrixWorld(true);
    var box = new T.Box3().setFromObject(model);
    var target = box.getCenter(new T.Vector3());
    var az = T.MathUtils.degToRad(o.yaw || 0), el = T.MathUtils.degToRad(o.elevation || 0);
    var roll = T.MathUtils.degToRad(o.roll || 0);
    var want = o.box ? (o.box[3] - o.box[1]) / h : (o.fill || 0.72);
    var dist = box.getSize(new T.Vector3()).length() * 1.5;
    function place() {
      camera.position.set(target.x + Math.sin(az) * Math.cos(el) * dist, target.y + Math.sin(el) * dist,
        target.z + Math.cos(az) * Math.cos(el) * dist);
      camera.lookAt(target);
      if (roll) camera.rotateZ(roll); // rolling the camera one way leans the picture the other
    }
    for (var i = 0; i < 4; i++) {
      place();
      var sb = screenBox(model, camera, w, h);
      var fillNow = (sb.y1 - sb.y0) / h;
      var across = (sb.x1 - sb.x0) / w;
      var k = Math.max(fillNow / want, o.box ? 0 : across / 0.9);
      dist *= k;
    }
    place();
    if (o.box) {
      var s2 = screenBox(model, camera, w, h);
      var dx = (s2.x0 + s2.x1) / 2 - (o.box[0] + o.box[2]) / 2;
      var dy = (s2.y0 + s2.y1) / 2 - (o.box[1] + o.box[3]) / 2;
      camera.setViewOffset(w, h, dx, dy, w, h);
    }
    camera.updateProjectionMatrix();
    return target;
  }

  // ---------------------------------------------------------------- viewer for a page or a deck

  // `hidden` alone loses to any page rule that sets display on the element (a .btn or .chip class does)
  function hide(el) { el.hidden = true; el.style.display = 'none'; }

  // <figure class="p3d" data-model data-press data-release data-label data-yaw data-elevation>
  //   <div class="p3d-stage">poster img</div> ... <button class="p3d-btn"> ... </figure>
  function mount(fig, name) {
    var stageEl = fig.querySelector('.p3d-stage');
    var btn = fig.querySelector('.p3d-btn');
    var renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    var model = create(name || fig.dataset.model);
    var st = stage(renderer, model, {});
    var camera = new T.PerspectiveCamera(26, 1, 0.01, 1000);
    var canvas = renderer.domElement;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', fig.dataset.label || '');
    var controls = new T.OrbitControls(camera, canvas);
    controls.enableZoom = false; // never take the page's scroll
    controls.enablePan = false;
    controls.enableDamping = true;
    controls.minPolarAngle = T.MathUtils.degToRad(50);
    controls.maxPolarAngle = T.MathUtils.degToRad(90);
    var turn = !window.matchMedia('(prefers-reduced-motion: reduce)').matches, idle = 0;
    controls.autoRotate = turn;
    controls.autoRotateSpeed = 1.5;
    // a drag stops the turntable; it starts again after 6 s left alone
    controls.addEventListener('start', function () { controls.autoRotate = false; idle = -1; });
    controls.addEventListener('end', function () { idle = turn ? 6 : -1; });
    canvas.style.touchAction = 'pan-y'; // a vertical swipe still scrolls the page
    var runtime = model.userData.runtime;
    var want = 0, t = 0;
    function setWant(v) {
      want = v;
      if (!btn) return;
      btn.setAttribute('aria-pressed', String(v === 1));
      btn.textContent = (v ? fig.dataset.release : fig.dataset.press) || '';
    }
    if (btn) {
      if (runtime && runtime.setOpen) {
        setWant(0);
        btn.hidden = false;
        btn.disabled = false;
        btn.addEventListener('click', function (e) {
          setWant(want ? 0 : 1);
          if (e.detail > 0) btn.blur(); // in a deck, Space must keep moving to the next slide
        });
      } else hide(btn);
    }
    if (runtime && runtime.setOpen) {
      var down = null;
      canvas.addEventListener('pointerdown', function (e) { down = [e.clientX, e.clientY]; });
      canvas.addEventListener('pointerup', function (e) {
        if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5) setWant(want ? 0 : 1);
        down = null;
      });
    }
    function resize() {
      var w = stageEl.clientWidth, h = stageEl.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      if (runtime && runtime.setOpen) runtime.setOpen(1); // frame the open state, so what opens stays in view
      var target = frame(camera, model, {
        width: w, height: h, yaw: Number(fig.dataset.yaw || 22), elevation: Number(fig.dataset.elevation || 15),
        fill: Number(fig.dataset.fill || 0.72),
      });
      if (runtime && runtime.setOpen) runtime.setOpen(t);
      controls.target.copy(target);
      controls.update();
    }
    stageEl.replaceChildren(canvas);
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
    fig.classList.add('is-live');
    resize();
    new ResizeObserver(resize).observe(stageEl);
    var clock = new T.Clock(), visible = true, raf = 0;
    function tick() {
      if (!visible) return;
      var dt = Math.min(clock.getDelta(), 0.05);
      if (runtime && runtime.setOpen && t !== want) {
        t += Math.sign(want - t) * Math.min(Math.abs(want - t), dt * 2.5);
        runtime.setOpen(t);
      }
      if (idle > 0 && (idle -= dt) <= 0) controls.autoRotate = true;
      controls.update(dt);
      renderer.render(st.scene, camera);
      raf = requestAnimationFrame(tick);
    }
    new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting;
      cancelAnimationFrame(raf);
      if (visible) { clock.getDelta(); tick(); }
    }).observe(stageEl);
    return { model: model, camera: camera, controls: controls };
  }

  // ---------------------------------------------------------------- review sheet (scripts/review.py)

  // Object box in a photo: pixels that differ from the border's median colour. Null when the background is busy.
  function photoBox(img) {
    var w = img.naturalWidth, h = img.naturalHeight, cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    var ctx = cv.getContext('2d');
    ctx.drawImage(img, 0, 0);
    var data = ctx.getImageData(0, 0, w, h).data;
    function px(x, y) { var i = (y * w + x) * 4; return [data[i], data[i + 1], data[i + 2]]; }
    var border = [];
    for (var x = 0; x < w; x += 4) { border.push(px(x, 0), px(x, h - 1)); }
    for (var y = 0; y < h; y += 4) { border.push(px(0, y), px(w - 1, y)); }
    var bg = [0, 1, 2].map(function (c) { var v = border.map(function (p) { return p[c]; }).sort(function (a, b) { return a - b; }); return v[v.length >> 1]; });
    var spread = border.filter(function (p) { return Math.abs(p[0] - bg[0]) + Math.abs(p[1] - bg[1]) + Math.abs(p[2] - bg[2]) > 60; }).length / border.length;
    if (spread > 0.25) return { box: null, background: bg };
    var x0 = w, y0 = h, x1 = -1, y1 = -1, n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
    for (var yy = 0; yy < h; yy += 2) for (var xx = 0; xx < w; xx += 2) {
      var p = px(xx, yy);
      if (Math.abs(p[0] - bg[0]) + Math.abs(p[1] - bg[1]) + Math.abs(p[2] - bg[2]) > 60) {
        if (xx < x0) x0 = xx; if (xx > x1) x1 = xx; if (yy < y0) y0 = yy; if (yy > y1) y1 = yy;
        n++; sx += xx; sy += yy; sxx += xx * xx; syy += yy * yy; sxy += xx * yy;
      }
    }
    // tilt: degrees the object's long axis leans from vertical, + when its top leans right; null when it has no
    // long axis to speak of (round, or about as wide as tall)
    var tilt = null;
    if (n > 10) {
      var mx = sx / n, my = sy / n, a = sxx / n - mx * mx, c = syy / n - my * my, b = sxy / n - mx * my;
      var l1 = (a + c) / 2 + Math.sqrt(((a - c) / 2) * ((a - c) / 2) + b * b);
      var l2 = (a + c) / 2 - Math.sqrt(((a - c) / 2) * ((a - c) / 2) + b * b);
      if (l2 > 0 && l1 / l2 > 2.25) {
        var theta = 0.5 * Math.atan2(2 * b, a - c) * 180 / Math.PI; // the long axis, from +x, image y down
        tilt = Math.round((((theta + 180) % 180) - 90) * 10) / 10;
        if (tilt === -90) tilt = 90;
      }
    }
    return { box: x1 < 0 ? null : [x0, y0, x1, y1], background: bg, tilt: tilt };
  }

  function hex(rgb) { return '#' + rgb.map(function (v) { return ('0' + Math.round(v).toString(16)).slice(-2); }).join(''); }

  // Average colour of a (2r+1)^2 patch at each [x, y].
  function samplePhoto(img, points, r) {
    var cv = document.createElement('canvas');
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    var ctx = cv.getContext('2d');
    ctx.drawImage(img, 0, 0);
    var out = {};
    Object.keys(points).forEach(function (k) {
      var x = points[k][0], y = points[k][1], s = 2 * r + 1;
      var d = ctx.getImageData(Math.max(0, x - r), Math.max(0, y - r), s, s).data, sum = [0, 0, 0], n = 0;
      for (var i = 0; i < d.length; i += 4) { sum[0] += d[i]; sum[1] += d[i + 1]; sum[2] += d[i + 2]; n++; }
      out[k] = hex(sum.map(function (v) { return v / n; }));
    });
    return out;
  }

  function review(o) {
    var info = { model: o.model, errors: window.__p3dErrors || [] };
    var out = document.getElementById('p3d-info');
    function done() { out.textContent = JSON.stringify(info); document.title = 'done'; }
    try {
      var model = create(o.model);
      model.updateMatrixWorld(true);
      var size = new T.Box3().setFromObject(model).getSize(new T.Vector3());
      var tris = 0;
      model.traverse(function (m) { if (m.isMesh) { var g = m.geometry; tris += (g.index ? g.index.count : g.getAttribute('position').count) / 3; } });
      info.size = [size.x, size.y, size.z].map(function (v) { return Math.round(v * 1000) / 1000; });
      info.triangles = Math.round(tris);
      info.moving = !!(model.userData.runtime && model.userData.runtime.setOpen);
      var refImg = document.getElementById('p3d-ref');
      var rw = 600, rh = 800, box = o.box || null;
      if (refImg && refImg.naturalWidth) {
        rw = refImg.naturalWidth; rh = refImg.naturalHeight;
        if (!box) { var pb = photoBox(refImg); box = pb.box; info.background = hex(pb.background); info.tilt = pb.tilt; }
        info.reference = { width: rw, height: rh, box: box };
      }
      var H = o.panel || 620, W = Math.round(H * rw / rh);
      function view(el, opts, w, h) {
        var r = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, alpha: !!opts.alpha });
        r.setPixelRatio(1);
        r.setSize(w, h);
        if (model.userData.runtime && model.userData.runtime.setOpen) model.userData.runtime.setOpen(opts.open || 0);
        var st = stage(r, model, { background: opts.alpha ? null : '#ffffff', shadow: !opts.matched });
        var cam = new T.PerspectiveCamera(o.fov || 26, w / h, 0.01, 1000);
        // the matched view is fitted in the photo's own pixels, then scaled to the panel
        var fitBox = opts.matched && box ? box.map(function (v, i) { return v * (i % 2 ? h / rh : w / rw); }) : null;
        frame(cam, model, { width: w, height: h, yaw: (o.yaw || 0) + (opts.turn || 0), elevation: o.elevation || 0,
          roll: opts.matched ? o.roll || 0 : 0,
          box: fitBox, fill: opts.fill || (box ? (box[3] - box[1]) / rh : 0.72) });
        r.render(st.scene, cam);
        st.scene.remove(model);
        el.appendChild(r.domElement);
      }
      var row1 = document.getElementById('p3d-row1'), row2 = document.getElementById('p3d-row2');
      function panel(row, label, w, h) {
        var d = document.createElement('div'); d.className = 'p';
        d.style.width = w + 'px'; d.style.height = h + 'px';
        var l = document.createElement('span'); l.textContent = label; d.appendChild(l);
        row.appendChild(d); return d;
      }
      if (refImg && refImg.naturalWidth) {
        var p1 = panel(row1, 'reference', W, H); var im = refImg.cloneNode(); im.removeAttribute('id'); im.style.display = 'block'; p1.appendChild(im);
        var p2 = panel(row1, 'overlay: render at 50% over the reference', W, H); var im2 = refImg.cloneNode(); im2.removeAttribute('id'); im2.style.display = 'block'; p2.appendChild(im2);
        var ov = document.createElement('div'); ov.className = 'ov'; p2.appendChild(ov);
        view(ov, { matched: true, alpha: true }, W, H);
      }
      view(panel(row1, 'render, yaw ' + (o.yaw || 0) + '°, elevation ' + (o.elevation || 0) + '°' + (o.roll ? ', roll ' + o.roll + '°' : ''), W, H), { matched: true }, W, H);
      var S = Math.round(H * 0.62);
      [90, 180, 270].forEach(function (turn) { view(panel(row2, '+' + turn + '°', S, S), { turn: turn, fill: 0.8 }, S, S); });
      if (info.moving) view(panel(row2, 'open (setOpen 1)', S, S), { open: 1, fill: 0.8 }, S, S);
      if (o.samples && refImg && refImg.naturalWidth) info.samples = samplePhoto(refImg, o.samples, 2);
    } catch (e) {
      info.errors.push(String(e && e.stack || e));
    }
    done();
  }

  // ---------------------------------------------------------------- AR files (scripts/ar.py; needs three-export.min.js)

  // A copy of the model in metres, with what AR viewers do not draw turned into what they do: an unlit material
  // becomes a matte standard one, and a decal's polygon offset (a renderer trick, not geometry) is dropped.
  function arCopy(model, metres) {
    var copy = model.clone(true);
    copy.scale.multiplyScalar(metres);
    var changed = 0;
    copy.traverse(function (o) {
      if (!o.isMesh) return;
      var m = o.material;
      if (m.isMeshBasicMaterial) {
        o.material = new T.MeshStandardMaterial({ color: m.color.clone(), map: m.map || null, roughness: 1, metalness: 0 });
        changed++;
      } else if (m.polygonOffset) {
        o.material = m.clone();
        o.material.polygonOffset = false;
        changed++;
      }
    });
    var scene = new T.Scene();
    scene.add(copy);
    scene.updateMatrixWorld(true);
    return { scene: scene, changed: changed };
  }

  function base64(bytes) {
    var out = '', chunk = 0x8000;
    for (var i = 0; i < bytes.length; i += chunk) out += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    return btoa(out);
  }

  // GLB (Android Scene Viewer, and any 3D tool) and USDZ (iPhone and iPad AR Quick Look) of the model as it stands
  // at setOpen(open). metres: one model unit in metres (root.userData.metres when not given). Resolves to
  // { glb, usdz } in base64 and `info`; the GLB is read back with GLTFLoader, so `info.reread` proves it loads.
  function exportAR(name, o) {
    o = o || {};
    if (!T.GLTFExporter || !T.USDZExporter) return Promise.reject(new Error('load three-export.min.js after three.min.js'));
    var model = create(name);
    var metres = o.metres || model.userData.metres;
    if (!(metres > 0)) return Promise.reject(new Error('model "' + name + '": set root.userData.metres (one unit in metres)'));
    if (model.userData.runtime && model.userData.runtime.setOpen) model.userData.runtime.setOpen(o.open || 0);
    model.updateMatrixWorld(true);
    var ar = arCopy(model, metres);
    var warnings = [], warn = console.warn;
    console.warn = function () { warnings.push(Array.prototype.join.call(arguments, ' ')); };
    var info = { metres: metres, converted: ar.changed };
    var glb;
    return new T.GLTFExporter().parseAsync(ar.scene, { binary: true, onlyVisible: true })
      .then(function (buffer) {
        glb = new Uint8Array(buffer);
        return new T.USDZExporter().parseAsync(ar.scene, { quickLookCompatible: true, maxTextureSize: 1024 });
      })
      .then(function (usdz) {
        return new Promise(function (resolve, reject) {
          new T.GLTFLoader().parse(glb.buffer.slice(0), '', function (gltf) {
            var box = new T.Box3().setFromObject(gltf.scene), size = box.getSize(new T.Vector3()), meshes = 0, tris = 0;
            gltf.scene.traverse(function (m) {
              if (!m.isMesh) return;
              meshes++;
              tris += (m.geometry.index ? m.geometry.index.count : m.geometry.getAttribute('position').count) / 3;
            });
            info.reread = { meshes: meshes, triangles: Math.round(tris), size: [size.x, size.y, size.z].map(function (v) { return Math.round(v * 1000) / 1000; }) };
            resolve({ glb: base64(glb), usdz: base64(usdz), info: info, scene: gltf.scene });
          }, reject);
        });
      })
      .finally(function () { console.warn = warn; info.warnings = warnings; });
  }

  var kit = {
    roundedRect: roundedRect, loft: loft, shoulder: shoulder, roundedSlab: roundedSlab, lathe: lathe, helix: helix, wall: wall,
    shapes: shapes, decal: decal, refine: refine, plastic: plastic, metal: metal, paint: paint, dark: dark,
  };

  window.Product3D = {
    define: define, create: create, kit: kit, stage: stage, frame: frame, mount: mount,
    review: review, photoBox: photoBox, samplePhoto: samplePhoto, exportAR: exportAR,
  };
})();
