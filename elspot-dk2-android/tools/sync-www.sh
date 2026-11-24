#!/usr/bin/env bash
# Build www/ from the Pages app: copy index.html and inject the onnxruntime-web
# loader (so `ort` exists on-device) plus the WASM binaries and the bundled model.
set -euo pipefail
cd "$(dirname "$0")/.."
cp ../elspot-dk2/index.html www/index.html
cp ../elspot-dk2/icon.svg www/icon.svg
cp ../elspot-dk2/chonck.svg www/chonck.svg
python3 - <<'PY'
import io
p = "www/index.html"
s = io.open(p, encoding="utf-8").read()
tag = '    <script src="vendor/ort/ort.min.js"></script>\n'
old = "    <script>\n"
assert s.count(old) == 1
s = s.replace(old, tag + old)
io.open(p, "w", encoding="utf-8").write(s)
print("injected ort loader into www/index.html")
PY
mkdir -p www/vendor/ort
cp node_modules/onnxruntime-web/dist/ort.min.js www/vendor/ort/
cp node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs www/vendor/ort/
cp node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm www/vendor/ort/
python3 tools/fetch_prices_snapshot.py || true
ls www/vendor/ort/
ls www/assets/
