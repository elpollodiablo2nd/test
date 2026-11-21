"""Refresh the bundled price snapshot (www/assets/prices-dk2.json) from Energinet.

The app falls back to this snapshot when live fetches fail (rate limits / offline).
Best effort: keeps the previous snapshot on failure. Run via tools/sync-www.sh.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "www" / "assets" / "prices-dk2.json"
URL = "https://api.energidataservice.dk/dataset/DayAheadPrices"
DAYS = 36


def main():
    start = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M")
    params = urllib.parse.urlencode({
        "filter": json.dumps({"PriceArea": ["DK2"]}),
        "start": start, "sort": "TimeUTC asc", "limit": (DAYS + 1) * 96 + 200,
    })
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL + "?" + params, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            records = data.get("records", [])
            if len(records) < 24 * 7:
                raise RuntimeError(f"only {len(records)} records")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps({
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "price_area": "DK2",
                "records": records,
            }))
            print(f"snapshot refreshed: {len(records)} records -> {OUT} ({OUT.stat().st_size // 1024} KB)")
            return
        except Exception as e:
            last_err = e
            if "429" in str(e):
                time.sleep(20)
    print(f"snapshot refresh failed, keeping old file: {last_err}")


if __name__ == "__main__":
    main()
