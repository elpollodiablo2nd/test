// Node tests for the pure functions embedded in index.html.
// Run: node test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) throw new Error("no inline <script> found in index.html");
const moduleShim = { exports: {} };
new Function("module", match[1])(moduleShim);
const Core = moduleShim.exports;

let passed = 0, failed = 0;
function check(name, cond) {
    if (cond) { passed++; console.log("ok - " + name); }
    else { failed++; console.log("FAIL - " + name); }
}
function close(a, b, eps) { return Math.abs(a - b) <= (eps || 1e-9); }

// aggregateHourlyUtc: quarter-hourly records average into one hourly bucket
const records = [
    { TimeUTC: "2026-11-20T10:15:00", DayAheadPriceDKK: 100 },
    { TimeUTC: "2026-11-20T10:45:00", DayAheadPriceDKK: 200 },
    { TimeUTC: "2026-11-20T11:00:00", DayAheadPriceDKK: 300 },
    { TimeUTC: "2026-11-20T10:30:00", DayAheadPriceDKK: null },
    { TimeUTC: null, DayAheadPriceDKK: 999 },
];
const agg = Core.aggregateHourlyUtc(records);
check("aggregate buckets + averages", agg.length === 2 && close(agg[0].price, 150) && close(agg[1].price, 300));
check("aggregate floors to the hour", agg[0].utc.getUTCHours() === 10 && agg[0].utc.getUTCMinutes() === 0);
check("aggregate sorts by time", agg[0].utc < agg[1].utc);

// dkLabel: UTC -> Europe/Copenhagen
const winter = Core.dkLabel(Core.parseHourUtc("2026-11-20T22:00:00"));
const summer = Core.dkLabel(Core.parseHourUtc("2026-07-20T22:00:00"));
check("dkLabel winter CET (+1)", winter === "2026-11-20 23:00");
check("dkLabel summer CEST (+2, next day)", summer === "2026-07-21 00:00");

// dkWeekday: short weekday in Europe/Copenhagen
check("dkWeekday winter CET", Core.dkWeekday(Core.parseHourUtc("2026-11-20T22:00:00")) === "Fri");
check("dkWeekday summer CEST (next day)", Core.dkWeekday(Core.parseHourUtc("2026-07-20T22:00:00")) === "Tue");

// zones: DK2 east default, DK1 west with TREFOR DSO
check("ZONES DK2 east default", Core.ZONES.DK2.label === "EAST" && Core.ZONES.DK2.gln === "5790001089030" && Core.ZONES.DK2.area === "DK2");
check("ZONES DK1 west TREFOR", Core.ZONES.DK1.label === "WEST" && Core.ZONES.DK1.gln === "5790000392261" && Core.ZONES.DK1.area === "DK1");
check("zoneConfig falls back to DK2", Core.zoneConfig("XX").area === "DK2" && Core.zoneConfig("DK1").area === "DK1");
check("per-zone snapshots differ", Core.ZONES.DK1.snapshot !== Core.ZONES.DK2.snapshot);
check("DK1 default TREFOR tariff (night 0.0429, peak 0.3863)", Core.DEFAULT_TARIFFS.DK1["Nettarif C"][0].Price1 === 0.0429 && Core.DEFAULT_TARIFFS.DK1["Nettarif C"][0].Price18 === 0.3863);
check("national fees present in both zones", !!(Core.DEFAULT_TARIFFS.DK1["Systemtarif"] && Core.DEFAULT_TARIFFS.DK1["Elafgift"] && Core.DEFAULT_TARIFFS.DK2["Transmissions nettarif"]));

// xAxisDateLine: weekday+date only when the DK-local date changes between ticks
// (2026-11-20T23:00Z = 2026-11-21 00:00 DK = Saturday; 2026-11-21T23:00Z = Sunday 2026-11-22)
const xa = Core.xAxisDateLine(Date.UTC(2026, 10, 20, 23), null);
check("xAxisDateLine first tick of DK day", xa.line === "Sat 21/11" && xa.date === "2026-11-21");
const xb = Core.xAxisDateLine(Date.UTC(2026, 10, 21, 6), xa.date); // 07:00 DK, same DK day
check("xAxisDateLine same DK day -> empty line", xb.line === "" && xb.date === "2026-11-21");
const xc = Core.xAxisDateLine(Date.UTC(2026, 10, 21, 23), xb.date); // 2026-11-22 00:00 DK
check("xAxisDateLine next DK day", xc.line === "Sun 22/11" && xc.date === "2026-11-22");

// dkDay / dkShort: DD/MM display format
check("dkDay DD/MM", Core.dkDay("2026-11-26 14:00") === "26/11");
check("dkShort DD/MM HH:00", Core.dkShort("2026-11-26 14:00") === "26/11 14:00");

// fresherPoints: pick the series ending later
const fpA = [{ utc: new Date(Date.UTC(2026, 10, 20, 10)), price: 1 }, { utc: new Date(Date.UTC(2026, 10, 21, 10)), price: 2 }];
const fpB = [{ utc: new Date(Date.UTC(2026, 10, 22, 10)), price: 3 }];
check("fresherPoints picks later last point", Core.fresherPoints(fpA, fpB) === fpB && Core.fresherPoints(fpB, fpA) === fpB);
check("fresherPoints null-safe", Core.fresherPoints(null, fpA) === fpA && Core.fresherPoints(fpA, null) === fpA && Core.fresherPoints(null, null) == null);

// nearestSeriesEntry / tipLines (chart hover tooltip)
const tsA = { t: Date.UTC(2026, 10, 22, 10), dk: "2026-11-22 11:00", v: 1.234, kind: "pub", lo: null, hi: null };
const tsB = { t: Date.UTC(2026, 10, 22, 11), dk: "2026-11-22 12:00", v: 1.5, kind: "fc", lo: 1.1, hi: 1.9 };
const tipS = [tsA, tsB];
check("nearestSeriesEntry exact", Core.nearestSeriesEntry(tipS, Date.UTC(2026, 10, 22, 10)) === tsA);
check("nearestSeriesEntry between rounds to nearest", Core.nearestSeriesEntry(tipS, Date.UTC(2026, 10, 22, 10) + 30 * 60e3) === tsA && Core.nearestSeriesEntry(tipS, Date.UTC(2026, 10, 22, 10) + 31 * 60e3) === tsB);
check("nearestSeriesEntry empty -> null", Core.nearestSeriesEntry([], 0) == null);
const tlF = Core.tipLines(tsB, 1.4);
check("tipLines forecast = label + median + q10-q90 + baseline", tlF[0][0] === "22/11 12:00" && tlF[1][0].indexOf("median") > 0 && tlF[2][0].indexOf("q10") === 0 && tlF[3][0].indexOf("baseline") === 0);
check("tipLines published", Core.tipLines(tsA, null)[1][0].indexOf("published") > 0 && Core.tipLines(tsA, null).length === 2);

// modelCacheKey: bundled models are not cached, downloadable ones are
check("modelCacheKey 5M bundled -> null", Core.modelCacheKey("5M") === null);
check("modelCacheKey 28M parts -> cache URL", /28M\.h168\.onnx$/.test(Core.modelCacheKey("28M")));

// parseHourUtc treats naive timestamps as UTC
check("parseHourUtc naive = UTC", Core.parseHourUtc("2026-11-20T22:00:00").toISOString() === "2026-11-20T22:00:00.000Z");

// corrLag1 = 1 when each day repeats the previous one
const day = Array.from({ length: 24 }, (_, h) => 300 + 50 * h);
const points = [];
for (let i = 0; i < 3 * 24; i++) points.push({ utc: new Date(Date.UTC(2026, 10, 1) + i * 3600e3), price: day[i % 24] });
check("corrLag1 = 1 for repeated days", close(Core.corrLag1(points), 1));
check("corrLag1 = 0 for a single day", Core.corrLag1(points.slice(0, 24)) === 0);

// lag1Forecast repeats the last 24h
const f = Core.lag1Forecast(points, 24);
check("lag1Forecast length", f.length === 24);
check("lag1Forecast values = last day", f.every((v, i) => v === day[i]));

// mae
check("mae", close(Core.mae([1, 2], [1, 4]), 1));
check("mae empty", Core.mae([], []) === 0);

// backtestMae: constant series -> lag-1 is perfect; too-short history -> null
const flat = Array.from({ length: 10 * 24 }, (_, i) => ({ utc: new Date(Date.UTC(2026, 10, 1) + i * 3600e3), price: 400 }));
check("backtestMae perfect lag-1 = 0", Core.backtestMae(flat, Core.lag1Forecast, 3, 24) === 0);
const short = flat.slice(0, 7 * 24);
check("backtestMae null without context", Core.backtestMae(short, Core.lag1Forecast, 5, 24) === null);
const longSeries = [];
for (let i = 0; i < 10 * 24; i++) longSeries.push({ utc: new Date(Date.UTC(2026, 10, 1) + i * 3600e3), price: day[i % 24] + (i % 7) });
const shifted = Core.backtestMae(longSeries, Core.lag1Forecast, 2, 24);
check("backtestMae returns a number", typeof shifted === "number" && shifted >= 0);

// summarizeWeather: next-24h window from "now", null-safe
const now = Core.parseHourUtc("2026-11-21T12:00:00").getTime();
const hourly = {
    time: ["2026-11-21T11:00", "2026-11-21T12:00", "2026-11-21T13:00", "2026-11-21T14:00"],
    wind_speed_10m: [10, 20, 30, null],
    temperature_2m: [1, 2, 3, 4],
    shortwave_radiation: [0, 100, 500, 300],
};
const ws = Core.summarizeWeather(hourly, now);
check("summarizeWeather next-24h window", ws.windAvg === 20 && ws.tempMin === 1 && ws.tempMax === 4 && ws.solarPeak === 500);
check("summarizeWeather null when empty", Core.summarizeWeather({}, now) === null);

// fmtKwh: DKK/MWh -> kr/kWh
check("fmtKwh divides by 1000", Core.fmtKwh(1234) === "1.23");
check("fmtKwh rounds to 2 decimals", Core.fmtKwh(500.55) === "0.50");
check("fmtKwh negative prices", Core.fmtKwh(-250) === "-0.25");

// bestWindow: cheapest contiguous window by median
const fc = [
    { hour_dk: "2026-11-22 00:00", median: 900 },
    { hour_dk: "2026-11-22 01:00", median: 100 },
    { hour_dk: "2026-11-22 02:00", median: 50 },
    { hour_dk: "2026-11-22 03:00", median: 80 },
    { hour_dk: "2026-11-22 04:00", median: 700 },
];
const bw = Core.bestWindow(fc, 3);
check("bestWindow finds cheapest 3h run", bw.start === "2026-11-22 01:00" && bw.end === "2026-11-22 03:00");
check("bestWindow avg", close(bw.avg, (100 + 50 + 80) / 3));
check("bestWindow clamps to forecast length", Core.bestWindow(fc, 99).end === "2026-11-22 04:00");
check("bestWindow empty -> null", Core.bestWindow([], 6) === null && Core.bestWindow(null, 6) === null);

// historyFromResult: workflow payload history -> sorted {utc, price} points
const res = { history: [
    { hour_utc: "2026-11-21T02:00:00", hour_dk: "2026-11-21 03:00", price_dkk: 500 },
    { hour_utc: "2026-11-21T00:00:00", hour_dk: "2026-11-21 01:00", price_dkk: 300 },
    { hour_utc: "bogus", hour_dk: "", price_dkk: 1 },
    { hour_utc: "2026-11-21T01:00:00", hour_dk: "2026-11-21 02:00", price_dkk: null },
]};
const hp = Core.historyFromResult(res);
check("historyFromResult maps+sorts, skips bad rows", hp.length === 2 && hp[0].price === 300 && hp[1].price === 500);
check("historyFromResult utc is a Date", hp[0].utc.toISOString() === "2026-11-21T00:00:00.000Z");
check("historyFromResult empty/missing", Core.historyFromResult({}).length === 0 && Core.historyFromResult(null).length === 0);

// tariff helpers (N1 Nettarif C 2026-10 profile: night 00-06 low, peak 17-21 high)
const TARIFFS = {
    "Elafgift": [{ ValidFrom: "2026-01-01T00:00:00", ValidTo: "2027-01-01T00:00:00", Price1: 0.008 }],
    "Systemtarif": [{ ValidFrom: "2026-01-01T00:00:00", ValidTo: "2027-01-01T00:00:00", Price1: 0.072 }],
    "Transmissions nettarif": [{ ValidFrom: "2026-01-01T00:00:00", ValidTo: "2027-01-01T00:00:00", Price1: 0.043 }],
    "Nettarif C": [{ ValidFrom: "2026-10-01T00:00:00", ValidTo: "2027-01-01T00:00:00",
        Price1: 0.0879, Price2: 0.0879, Price3: 0.0879, Price4: 0.0879, Price5: 0.0879, Price6: 0.0879,
        Price7: 0.2636, Price8: 0.2636, Price9: 0.2636, Price10: 0.2636, Price11: 0.2636, Price12: 0.2636,
        Price13: 0.2636, Price14: 0.2636, Price15: 0.2636, Price16: 0.2636, Price17: 0.2636,
        Price18: 0.7907, Price19: 0.7907, Price20: 0.7907, Price21: 0.7907,
        Price22: 0.2636, Price23: 0.2636, Price24: 0.2636 }],
};
check("pickTariffRecord inside window", Core.pickTariffRecord(TARIFFS["Elafgift"], "2026-11-21T14:00:00").Price1 === 0.008);
check("pickTariffRecord at ValidTo is out", Core.pickTariffRecord(TARIFFS["Elafgift"], "2027-01-01T00:00:00") === null);
check("pickTariffRecord empty -> null", Core.pickTariffRecord([], "2026-11-21T14:00:00") === null);
check("tariffPriceOfHour peak 17 -> Price18", Core.tariffPriceOfHour(TARIFFS["Nettarif C"][0], 17) === 0.7907);
check("tariffPriceOfHour night 0 -> Price1", Core.tariffPriceOfHour(TARIFFS["Nettarif C"][0], 0) === 0.0879);
check("tariffPriceOfHour falls back to Price1", Core.tariffPriceOfHour(TARIFFS["Elafgift"][0], 13) === 0.008);
check("tariffPriceOfHour null record", Core.tariffPriceOfHour(null, 3) === null);
// 2026-11-21T16:00Z = 17:00 DK (CET) -> peak; 2026-11-21T23:00Z = 00:00 DK next day -> night
const feePeak = Core.feeKwhAt(TARIFFS, Core.parseHourUtc("2026-11-21T16:00:00").getTime());
check("feeKwhAt evening peak", close(feePeak, 0.008 + 0.072 + 0.043 + 0.7907, 1e-9));
const feeNight = Core.feeKwhAt(TARIFFS, Core.parseHourUtc("2026-11-21T23:00:00").getTime());
check("feeKwhAt night low", close(feeNight, 0.008 + 0.072 + 0.043 + 0.0879, 1e-9));
check("feeKwhAt no data -> null", Core.feeKwhAt({}, 0) === null);
check("allInDkkMwh = (spot+fees)*1.25", close(Core.allInDkkMwh(500, 0.2109), (0.5 + 0.2109) * 1.25 * 1000, 1e-9));
check("dispDkkMwh spot when fees off", Core.dispDkkMwh(500, 0, TARIFFS, false) === 500);
check("dispDkkMwh all-in when fees on", close(Core.dispDkkMwh(500, Core.parseHourUtc("2026-11-21T23:00:00").getTime(), TARIFFS, true), Core.allInDkkMwh(500, feeNight), 1e-9));

// combinedSeries (from now on: published + forecast) and bestWindowEntries over it
const nowMs = Core.parseHourUtc("2026-11-21T12:00:00").getTime();
const hist2 = [
    { utc: new Date(nowMs - 2 * 3600e3), price: 900 },
    { utc: new Date(nowMs + 1 * 3600e3), price: 300 },
    { utc: new Date(nowMs + 2 * 3600e3), price: 700 },
];
const fc2 = [
    { hour_utc: "2026-11-21T15:00:00", hour_dk: "2026-11-21 16:00", median: 100, q10: 50, q90: 200 },
    { hour_utc: "2026-11-21T16:00:00", hour_dk: "2026-11-21 17:00", median: 80, q10: 40, q90: 150 },
    { hour_utc: "2026-11-21T17:00:00", hour_dk: "2026-11-21 18:00", median: 600, q10: 500, q90: 700 },
];
const ser = Core.combinedSeries(hist2, fc2, nowMs, TARIFFS, false);
check("combinedSeries drops past hours, sorted", ser.length === 5 && ser.every((e, i) => i === 0 || e.t > ser[i - 1].t));
check("combinedSeries kinds", ser[0].kind === "pub" && ser[2].kind === "fc");
check("combinedSeries spot values when fees off", ser[0].v === 300 && ser[2].v === 100);
const bw2 = Core.bestWindowEntries(ser, 2);
check("bestWindowEntries cheapest pair", bw2.idx === 2 && bw2.len === 2 && close(bw2.avg, 90));
check("bestWindowEntries endT is hour end", bw2.endT === Core.parseHourUtc("2026-11-21T16:00:00").getTime() + 3600e3);
check("bestWindowEntries empty -> null", Core.bestWindowEntries([], 4) === null);

// xAxisStep: finest step that fits maxTicks labels in the window
check("xAxisStep 24h window -> 2h", Core.xAxisStep(24 * 3600e3, 12) === 2);
check("xAxisStep 48h window -> 4h", Core.xAxisStep(48 * 3600e3, 12) === 4);
check("xAxisStep 72h window -> 6h", Core.xAxisStep(72 * 3600e3, 12) === 6);
check("xAxisStep 8d window -> 24h", Core.xAxisStep(8 * 24 * 3600e3, 12) === 24);
check("xAxisStep 1h window -> 1h", Core.xAxisStep(3600e3, 12) === 1);
check("xAxisStep huge window -> 96h cap", Core.xAxisStep(400 * 24 * 3600e3, 12) === 96);

// chart zoom/pan view math
const F0 = 0, F1 = 168 * 3600e3, MINS = 6 * 3600e3;
const cv = Core.clampView({ start: -1e15, span: 1e15 }, F0, F1, MINS);
check("clampView clamps to full window", cv.span === F1 - F0 && cv.start === F0);
check("clampView enforces min span", Core.clampView({ start: 1e12, span: 1 }, F0, F1, MINS).span === MINS);
const zv = Core.zoomView({ start: F0, span: F1 - F0 }, F0, F1, MINS, 2, F1 / 2);
check("zoomView halves span around center", zv.span === (F1 - F0) / 2 && zv.start === F1 / 2 - (F1 - F0) / 4);
const zEdge = Core.zoomView(zv, F0, F1, MINS, 100, 0);
check("zoomView clamps at left edge, min span", zEdge.span === MINS && zEdge.start === F0);
const pv = Core.panView(zv, F0, F1, MINS, -10 * 3600e3);
check("panView shifts start", pv.start === zv.start - 10 * 3600e3 && pv.span === zv.span);
check("panView clamps at right edge", Core.panView(zv, F0, F1, MINS, 1e15).start === F1 - zv.span);
check("clampView tiny full window", (function () { const c = Core.clampView({ start: 5, span: 99 }, 0, MINS - 1, MINS); return c.start === 0 && c.span === MINS - 1; })());

// axis label size scales with zoom, capped; pads grow to fit
check("axisFontPx 1x = 34", Core.axisFontPx(1) === 34);
check("axisFontPx grows with zoom", Core.axisFontPx(2) === 42 && Core.axisFontPx(2) < Core.axisFontPx(4));
check("axisFontPx capped at 44", Core.axisFontPx(100) === 44 && Core.axisFontPx(4) === 44);
const cp = Core.chartPads(Core.axisFontPx(4));
check("chartPads bigger font -> bigger pads", cp.padL > Core.chartPads(34).padL && cp.padB > Core.chartPads(34).padB);
check("xMaxTicks shrinks with bigger labels", Core.xMaxTicks(34, 660) === 6 && Core.xMaxTicks(44, 656) === 4 && Core.xMaxTicks(44, 656) < Core.xMaxTicks(34, 660));
check("xMaxTicks floor 3", Core.xMaxTicks(44, 100) === 3);

// utcHourKey / weekdayMon0
check("utcHourKey", Core.utcHourKey(new Date(Date.UTC(2026, 10, 21, 7, 30))) === "2026-11-21T07:00");
check("weekdayMon0 monday=0", Core.weekdayMon0(new Date(Date.UTC(2026, 10, 23))) === 0);
check("weekdayMon0 saturday=5", Core.weekdayMon0(new Date(Date.UTC(2026, 10, 21))) === 5);

// targetEncode vs python timestral.covariate_encoding.target_encode reference
const enc = Core.targetEncode([100, 200, 300, NaN, 150, 250], [0, 1, 0, 1, NaN, 1], 1);
const encVals = [0, 1, 0, 1, NaN, 1, 0, 2, NaN].map(c => enc(c));
check("targetEncode matches python", close(encVals[0], 200) && close(encVals[1], 216.666672, 1e-4) && close(encVals[2], 200) && close(encVals[4], 175) && close(encVals[7], 200) && close(encVals[8], 175));

// buildOnnxInputs: shapes, left NaN padding, weather/encoding rows
const h0 = Date.UTC(2026, 10, 20, 0, 0, 0);
const hist = [];
for (let i = 0; i < 800; i++) hist.push({ utc: new Date(h0 + i * 3600e3), price: 400 + (i % 24) * 10 });
const wmap = {};
const nmap = {};
for (let i = 0; i < 900; i++) { const d = new Date(h0 + i * 3600e3); wmap[Core.utcHourKey(d)] = [5, 2, 100]; nmap[Core.utcHourKey(d)] = [300, 350]; }
const inp = Core.buildOnnxInputs(hist, wmap, nmap);
check("buildOnnxInputs context len", inp.context.length === 768);
check("buildOnnxInputs known len", inp.known.length === 13 * 936);
check("buildOnnxInputs hours len", inp.hours.length === 936);
check("buildOnnxInputs no pad when 800h", isFinite(inp.context[0]));
check("buildOnnxInputs last ctx price", close(inp.context[767], hist[799].price, 1e-3));
check("buildOnnxInputs weather row", inp.known[0] === 5 && inp.known[936] === 2 && inp.known[2 * 936] === 100);
check("buildOnnxInputs neighbor rows DE/SE3", inp.known[3 * 936 + 700] === 300 && inp.known[4 * 936 + 700] === 350);
check("buildOnnxInputs enc rows finite", isFinite(inp.known[11 * 936 + 700]) && isFinite(inp.known[12 * 936 + 700]));
check("buildOnnxInputs deWx rows NaN without deWxMap", isNaN(inp.known[5 * 936 + 700]) && isNaN(inp.known[10 * 936 + 700]));
const inp2 = Core.buildOnnxInputs(hist.slice(0, 100), {});
check("buildOnnxInputs left-pads NaN", isNaN(inp2.context[0]) && isFinite(inp2.context[668]));
check("buildOnnxInputs weather NaN when missing", isNaN(inp2.known[0]) && isNaN(inp2.known[936]));
check("buildOnnxInputs neighbor NaN when missing", isNaN(inp2.known[3 * 936 + 700]) && isNaN(inp2.known[4 * 936 + 700]));
check("buildOnnxInputs enc NaN in padding", isNaN(inp2.known[11 * 936 + 10]) && isFinite(inp2.known[11 * 936 + 700]));

// conformal band calibration (q10-q90 recalibration)
check("quantileOf median", Core.quantileOf([1, 2, 3, 4], 0.5) === 2.5 && Core.quantileOf([], 0.5) === null);
const pairs = [];
for (let i = 0; i < 100; i++) pairs.push({ med: 100, q10: 80, q90: 120, act: 100 + (i % 10) * 2 }); // act within band
check("bandRatios all finite >= 0", Core.bandRatios(pairs).length === 100 && Core.bandRatios(pairs).every(r => r >= 0 && r <= 1));
check("bandRatios skips bad rows", Core.bandRatios([{ med: NaN, q10: 1, q90: 2, act: 1 }, { med: 1, q10: 2, q90: 3, act: 1 }]).length === 0);
const k = Core.conformalK(pairs, 0.85);
check("conformalK ~1 when actuals inside band", k !== null && k >= 1 && k < 1.2);
check("conformalK null when few samples", Core.conformalK(pairs.slice(0, 5), 0.85) === null);
const wide = pairs.map(p => ({ ...p, act: p.med + 40 })); // all 40 above median (half-width 20) -> r = 2
check("conformalK = 2 when all overshoot 2x", Math.abs(Core.conformalK(wide, 0.85) - 2) < 1e-9);
check("scaleBand widens by k", JSON.stringify(Core.scaleBand(100, 80, 120, 2)) === JSON.stringify([60, 140]));
check("scaleBand no k -> unchanged", JSON.stringify(Core.scaleBand(100, 80, 120, NaN)) === JSON.stringify([80, 120]));

// applyCalibration: level bias translates the whole curve; median always inside [q10, q90]
const ac = Core.applyCalibration(100, 80, 120, 1, 50); // big +50 bias
check("applyCalibration translates curve", ac.med === 150 && ac.q10 === 130 && ac.q90 === 170);
check("applyCalibration median inside band (big bias)", ac.q10 <= ac.med && ac.med <= ac.q90);
const ac2 = Core.applyCalibration(100, 80, 120, 2, -300); // big negative bias
check("applyCalibration negative bias, median inside", ac2.med === -200 && ac2.q10 <= ac2.med && ac2.med <= ac2.q90 && ac2.q10 === -240 && ac2.q90 === -160);
const ac3 = Core.applyCalibration(100, 80, 120, 1, 0);
check("applyCalibration zero bias unchanged", ac3.med === 100 && ac3.q10 === 80 && ac3.q90 === 120);
const ac4 = Core.applyCalibration(100, 130, 140, 1, 0); // non-monotone raw (q10 > med) -> clamped
check("applyCalibration clamps non-monotone raw", ac4.q10 === 100 && ac4.q90 === 140);
const biased = Array.from({length: 20}, (_, i) => ({ med: 100 + i, act: 90 + i })); // med-act = +10 always
check("medianError = +10 constant bias", Core.medianError(biased) === 10);
check("medianError null when few", Core.medianError(biased.slice(0, 5)) === null);
check("horizonBucket", Core.horizonBucket(0) === 24 && Core.horizonBucket(23) === 24 && Core.horizonBucket(24) === 48 && Core.horizonBucket(71) === 72
    && Core.horizonBucket(72) === 96 && Core.horizonBucket(95) === 96 && Core.horizonBucket(96) === 120 && Core.horizonBucket(143) === 144
    && Core.horizonBucket(144) === 168 && Core.horizonBucket(500) === 168);
check("K_BUCKETS 24..168", Array.isArray(Core.K_BUCKETS) && Core.K_BUCKETS.join(",") === "24,48,72,96,120,144,168");

// ridge neighbour fill: solveLinear / ridgeFit / deFeatRow / buildNeighborFill / buildOnnxInputs fill
{
    const A = [[2, 1, 0], [1, 3, 1], [0, 1, 4]], b = [4, 10, 14]; // A·x with x = 1,2,3
    const x = Core.solveLinear(A, b);
    check("solveLinear 3x3", !!x && Math.abs(x[0] - 1) < 1e-9 && Math.abs(x[1] - 2) < 1e-9 && Math.abs(x[2] - 3) < 1e-9);
    check("solveLinear singular -> null", Core.solveLinear([[1, 1], [1, 1]], [1, 2]) === null);
    check("windPowerProxy", Core.windPowerProxy(25) === 1 && Core.windPowerProxy(3) === 0 && Core.windPowerProxy(0) === 0 && isNaN(Core.windPowerProxy(NaN)));
    const d0 = new Date(h0 + 18 * 3600e3); // hour 18
    const deWx0 = {}; deWx0[Core.utcHourKey(d0)] = [10, 9, 100, 12, 40, 1010];
    const r0 = Core.deFeatRow(d0, deWx0);
    check("deFeatRow shape/dummies", r0.length === 38 && r0[0] === 1 && r0[1 + 18] === 1 && r0[1 + 3] === 0 && r0[32] === Core.windPowerProxy(10));
    // synthetic linear target learned by ridgeFit
    const rows = [], ys = [];
    for (let i = 0; i < 300; i++) {
        const d = new Date(h0 + i * 3600e3);
        const w100 = 5 + (i % 10), temp = 10 + (i % 7);
        const dw = {}; dw[Core.utcHourKey(d)] = [w100, w100 - 1, 100, temp, 50, 1013];
        rows.push(Core.deFeatRow(d, dw));
        ys.push(200 + 3 * temp - 0.5 * Core.windPowerProxy(w100) + (d.getUTCHours() === 18 ? 100 : 0));
    }
    const m = Core.ridgeFit(rows, ys);
    check("ridgeFit recovers linear target", !!m && Math.abs(Core.ridgePredict(m, rows[250]) - ys[250]) < 0.05); // tiny ridge shrinkage
    check("ridgeFit too few rows -> null", Core.ridgeFit(rows.slice(0, 10), ys.slice(0, 10)) === null);
    // buildNeighborFill: published hours kept, unpublished future filled
    const nmap2 = {};
    for (let i = 0; i < 900; i++) { const d = new Date(h0 + i * 3600e3); nmap2[Core.utcHourKey(d)] = [300 + i * 0.1, 350]; } // covers future hours h0+800..899 as published
    const deWxAll = {};
    for (let i = 0; i < 1000; i++) { const d = new Date(h0 + i * 3600e3); deWxAll[Core.utcHourKey(d)] = [8, 7, 100, 12, 40, 1010]; }
    const lastCtx = new Date(h0 + 799 * 3600e3);
    const fut = []; for (let i = 1; i <= 168; i++) fut.push(new Date(h0 + (799 + i) * 3600e3));
    const fill = Core.buildNeighborFill(nmap2, deWxAll, lastCtx.getTime(), fut);
    check("buildNeighborFill keeps published hour", fill.DE[Core.utcHourKey(fut[0])] === undefined && fill.DE[Core.utcHourKey(fut[99])] === undefined); // h0+800..899h published in nmap2
    check("buildNeighborFill fills unpublished future", isFinite(fill.DE[Core.utcHourKey(fut[167])]) && isFinite(fill.SE3[Core.utcHourKey(fut[167])]));
    check("buildNeighborFill respects trainEnd", (function () { // hours after trainEnd must not be trained on: fill still works with only 700 rows
        const nm = {}; for (let i = 0; i < 700; i++) { const d = new Date(h0 + i * 3600e3); nm[Core.utcHourKey(d)] = [300, 350]; }
        const f2 = Core.buildNeighborFill(nm, deWxAll, new Date(h0 + 699 * 3600e3).getTime(), fut);
        return isFinite(f2.DE[Core.utcHourKey(fut[167])]);
    })());
    const inp3 = Core.buildOnnxInputs(hist, wmap, nmap, deWxAll); // nmap covers 900h: future i=768..867 published, 868..935 filled
    check("buildOnnxInputs published nb kept with fill on", inp3.known[3 * 936 + 800] === 300);
    check("buildOnnxInputs ridge fill beyond published", isFinite(inp3.known[3 * 936 + 935]) && isFinite(inp3.known[4 * 936 + 935]));
    check("buildOnnxInputs deWx rows from deWxMap", isFinite(inp3.known[5 * 936 + 800]) && close(inp3.known[5 * 936 + 800], Core.windPowerProxy(8), 1e-9) && inp3.known[6 * 936 + 800] === 7 && inp3.known[10 * 936 + 800] === 1010);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
