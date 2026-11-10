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

# kit/three-export.min.js

three.js's own `GLTFExporter`, `USDZExporter` and `GLTFLoader` (MIT, the same release), added to the `window.THREE`
that `three.min.js` set, for `ar.py` only: pages never load it. About 110 KB. Built in the same folder, with
`three` pointed at that global so the library is not bundled twice:

```sh
echo 'module.exports = globalThis.THREE;' > three-global.cjs
cat > export-entry.js <<'JS'
import { GLTFExporter } from './node_modules/three/examples/jsm/exporters/GLTFExporter.js';
import { USDZExporter } from './node_modules/three/examples/jsm/exporters/USDZExporter.js';
import { GLTFLoader } from './node_modules/three/examples/jsm/loaders/GLTFLoader.js';
Object.assign(globalThis.THREE, { GLTFExporter, USDZExporter, GLTFLoader });
JS
npx esbuild export-entry.js --bundle --minify --format=iife --target=es2020 --legal-comments=none \
  --alias:three=./three-global.cjs --outfile=three-export.min.js
```

Check it holds no second copy of the library: `grep -c WebGLRenderer three-export.min.js` prints 0.

# kit/qrcodegen.min.js

Project Nayuki's QR Code generator library (MIT; its notice is the file's first line), the TypeScript version at
github.com/nayuki/QR-Code-generator `bcfe1b018cec`, `typescript-javascript/qrcodegen.ts`, compiled once to a classic
script that sets `window.qrcodegen` (12 KB). The export puts it in a snippet with AR, for the QR code a computer
shows:

```sh
npx esbuild qrcodegen.ts --minify --target=es2020 > qr.min.js   # then the notice line on top
```
