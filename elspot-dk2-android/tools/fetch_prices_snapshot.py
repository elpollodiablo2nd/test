"""Refresh the bundled price snapshots (prices-dk1.json / prices-dk2.json) from Energinet.

The app falls back to these snapshots when live fetches fail (rate limits / offline).
One DayAheadPrices request fetches both price areas; records are split by PriceArea.
Files are written to www/assets/ (bundled into the APK) and elspot-dk2/assets/
(served on Pages as the web app's fallback). Best effort: keeps previous files on failure.
Run via tools/sync-www.sh.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIRS = [ROOT / "www" / "assets", ROOT.parent / "elspot-dk2" / "assets"]
URL = "https://api.energidataservice.dk/dataset/DayAheadPrices"
NORDPOOL_URL = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
DAYS = 36
AREAS = ["DK1", "DK2"]
NEIGHBOR_AREAS = ["DE", "SE3"]  # neighbour-zone day-ahead prices (model covariates)


def _get_json(url, tries=3):
    """GET and parse JSON; returns None on 204 (not published yet); retries on 429/5xx."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status == 204:
                    return None
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(10 * (i + 1))
                continue
            raise


def fetch_nordpool(days):
    """Fallback source: Nord Pool data-portal day-ahead API (no CORS needed server-side).

    Returns {area: [records]} with records shaped like Energinet's
    (TimeUTC, DayAheadPriceDKK, PriceArea), DKK/MWh, 15-min or hourly entries.
    Delivery dates are CET calendar days; today+tomorrow included (204 = not yet published).
    """
    from zoneinfo import ZoneInfo
    now_cet = datetime.now(ZoneInfo("Europe/Copenhagen"))
    by_area = {a: [] for a in AREAS + NEIGHBOR_AREAS}
    alias = {"DE": "DE-LU"}
    for off in range(-days, 2):
        d = (now_cet + timedelta(days=off)).strftime("%Y-%m-%d")
        u = NORDPOOL_URL + "?" + urllib.parse.urlencode({
            "date": d, "market": "DayAhead", "deliveryArea": ",".join(AREAS + ["DE-LU", "SE3"]), "currency": "DKK"})
        try:
            data = _get_json(u)
        except Exception:
            data = None
        if not data:
            continue
        for e in data.get("multiAreaEntries", []):
            start = e.get("deliveryStart")
            for area, v in (e.get("entryPerArea") or {}).items():
                key = area if area in by_area else next((a for a, al in alias.items() if al == area), None)
                if key and start and v is not None:
                    by_area[key].append({"TimeUTC": start, "DayAheadPriceDKK": v, "PriceArea": key})
        time.sleep(0.3)
    return by_area


def main():
    start = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M")
    params = urllib.parse.urlencode({
        "filter": json.dumps({"PriceArea": AREAS + NEIGHBOR_AREAS}),
        "start": start, "sort": "TimeUTC asc", "limit": (DAYS + 1) * 96 * (len(AREAS) + len(NEIGHBOR_AREAS)) + 400,
    })
    last_err = None
    by_area = None
    source = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL + "?" + params, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode())
            by_area = {a: [] for a in AREAS + NEIGHBOR_AREAS}
            for rec in data.get("records", []):
                area = rec.get("PriceArea")
                if area in by_area:
                    by_area[area].append(rec)
            source = "Energinet DayAheadPrices"
            break
        except Exception as e:
            last_err = e
            if "429" in str(e):
                time.sleep(20)
    if by_area is None or any(len(by_area[a]) < 24 * 7 for a in AREAS + NEIGHBOR_AREAS):
        # Energinet unreachable/rate-limited from here -> independent fallback via Nord Pool
        print(f"Energinet failed ({last_err}); trying Nord Pool data-portal API...")
        by_area = fetch_nordpool(DAYS)
        source = "Nord Pool day-ahead (dataportal-api)"
    if any(len(by_area[a]) < 24 * 7 for a in AREAS + NEIGHBOR_AREAS):
        print(f"snapshot refresh failed, keeping old files: {last_err or 'too few records'}")
        return
    for area in AREAS:
        records = sorted(by_area[area], key=lambda r: r["TimeUTC"])
        payload = json.dumps({
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "price_area": area,
            "source": source,
            "records": records,
        })
        for out_dir in OUT_DIRS:
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"prices-{area.lower()}.json"
            out.write_text(payload)
            print(f"snapshot {area}: {len(records)} records ({source}) -> {out} ({out.stat().st_size // 1024} KB)")
    nb_records = sorted([r for a in NEIGHBOR_AREAS for r in by_area[a]], key=lambda r: r["TimeUTC"])
    nb_payload = json.dumps({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "price_area": ",".join(NEIGHBOR_AREAS),
        "source": source,
        "records": nb_records,
    })
    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "prices-neighbors.json"
        out.write_text(nb_payload)
        print(f"snapshot neighbors {NEIGHBOR_AREAS}: {len(nb_records)} records ({source}) -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
