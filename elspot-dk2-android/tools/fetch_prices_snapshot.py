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
DAYS = 36
AREAS = ["DK1", "DK2"]


def main():
    start = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M")
    params = urllib.parse.urlencode({
        "filter": json.dumps({"PriceArea": AREAS}),
        "start": start, "sort": "TimeUTC asc", "limit": (DAYS + 1) * 96 * len(AREAS) + 400,
    })
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL + "?" + params, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode())
            by_area = {a: [] for a in AREAS}
            for rec in data.get("records", []):
                area = rec.get("PriceArea")
                if area in by_area:
                    by_area[area].append(rec)
            for area in AREAS:
                records = by_area[area]
                if len(records) < 24 * 7:
                    raise RuntimeError(f"only {len(records)} records for {area}")
                payload = json.dumps({
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "price_area": area,
                    "records": records,
                })
                for out_dir in OUT_DIRS:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out = out_dir / f"prices-{area.lower()}.json"
                    out.write_text(payload)
                    print(f"snapshot {area}: {len(records)} records -> {out} ({out.stat().st_size // 1024} KB)")
            return
        except Exception as e:
            last_err = e
            if "429" in str(e):
                time.sleep(20)
    print(f"snapshot refresh failed, keeping old files: {last_err}")


if __name__ == "__main__":
    main()
