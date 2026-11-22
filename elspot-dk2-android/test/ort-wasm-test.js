// Runs the exported ONNX model under onnxruntime-web (WASM backend — the same
// runtime the Android WebView app uses) and compares against the PyTorch reference.
// Run: node test/ort-wasm-test.js [28m|5m] [fp16|fp32]
const fs = require("fs");
const path = require("path");

const size = process.argv[2] || "28m";
const variant = process.argv[3] || "fp16";
const variantFile = variant === "fp32" ? `timestral-${size}.onnx` : `timestral-${size}-${variant}.onnx`;
const candidates = [path.join(__dirname, "..", "www", "assets", variantFile), path.join(__dirname, "..", "dist", variantFile)];
const modelPath = candidates.find(p => fs.existsSync(p));
const refPath = path.join(__dirname, `reference-${size}.json`);
if (!fs.existsSync(modelPath)) { console.error("missing model:", modelPath); process.exit(2); }

const ort = require("onnxruntime-web");
ort.env.wasm.wasmPaths = path.join(__dirname, "..", "node_modules", "onnxruntime-web", "dist") + path.sep;

async function main() {
    const ref = JSON.parse(fs.readFileSync(refPath, "utf8").replace(/NaN/g, "null"));
    const T = ref.T, H = ref.H;
    const nanMap = v => (v === null ? NaN : v);
    const context = new ort.Tensor("float32", Float32Array.from(ref.context.map(nanMap)), [1, 1, T]);
    const known = new ort.Tensor("float32", Float32Array.from(ref.known_covariates.flat().map(nanMap)), [1, ref.known_covariates.length, T + H]);
    const t0 = Date.now();
    const session = await ort.InferenceSession.create(modelPath, {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
    });
    const t1 = Date.now();
    const out = await session.run({ context, known_covariates: known });
    const t2 = Date.now();
    const q = out.quantiles; // (1,1,H,Q)
    const levels = ref.levels;
    const medI = levels.indexOf(0.5), q10I = levels.indexOf(0.1), q90I = levels.indexOf(0.9);
    const data = q.data;
    let maxDiff = 0, maeMed = 0;
    for (let h = 0; h < H; h++) {
        for (let qi = 0; qi < levels.length; qi++) {
            const got = data[h * levels.length + qi];
            const want = ref.quantiles[h][qi];
            maxDiff = Math.max(maxDiff, Math.abs(got - want));
        }
        maeMed += Math.abs(data[h * levels.length + medI] - ref.quantiles[h][medI]);
    }
    maeMed /= H;
    console.log(`model=${size}-${variant} load=${t1 - t0}ms run=${t2 - t1}ms`);
    console.log(`maxAbsDiff vs torch=${maxDiff.toFixed(4)} DKK/MWh  medianMAE=${maeMed.toFixed(4)} DKK/MWh`);
    console.log(`median[0..3]=${[0, 1, 2, 3].map(h => data[h * levels.length + medI].toFixed(2)).join(",")}  ref=${[0, 1, 2, 3].map(h => ref.quantiles[h][medI].toFixed(2)).join(",")}`);
    console.log(`q10[0]=${data[q10I].toFixed(2)} q90[0]=${data[q90I].toFixed(2)}  ref q10=${ref.quantiles[0][q10I].toFixed(2)} q90=${ref.quantiles[0][q90I].toFixed(2)}`);
    if (!(maxDiff < 50)) { console.error("FAIL: diff too large"); process.exit(1); }
    console.log("PASS");
}
main().catch(e => { console.error("FAIL:", e.message); process.exit(1); });
