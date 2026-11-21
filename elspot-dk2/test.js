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

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
