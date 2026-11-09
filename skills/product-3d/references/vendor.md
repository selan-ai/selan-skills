# kit/three.min.js

three.js 0.187.0 (MIT, `kit/three.LICENSE`) with `OrbitControls` and `RoomEnvironment`, bundled once into one
classic script that sets `window.THREE`. A classic script, not an ES module, because Chrome refuses module scripts
from `file://`, and a deck must open from disk; it also lets the export be plain concatenation, with no bundler at
run time. Full library, not tree-shaken: a model may use any class. About 770 KB, 195 KB gzip.

Rebuilt only to move to a newer three.js, on a machine with Node:

```sh
mkdir /tmp/three-kit && cd /tmp/three-kit && npm init -y >/dev/null && npm i three@0.187.0 esbuild@0.28.2
cat > entry.js <<'JS'
import * as NS from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
globalThis.THREE = Object.assign({}, NS, { OrbitControls, RoomEnvironment });
JS
npx esbuild entry.js --bundle --minify --format=iife --target=es2020 --legal-comments=none --outfile=three.min.js
```

Then put the one-line header back on top, copy `node_modules/three/LICENSE` to `kit/three.LICENSE`, and run the tests.
