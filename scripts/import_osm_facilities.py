"""Pre-load OpenStreetMap health facilities for an area into the local SQLite database,
so the finder works offline or on a slow link. Real, documented data (ODbL); nothing invented.

    cd backend && python ../scripts/import_osm_facilities.py              # Guwahati
    cd backend && python ../scripts/import_osm_facilities.py 26.14 91.66 40000
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import facilities  # noqa: E402


async def main(lat: float, lon: float, radius: int) -> None:
    rows = await facilities.fetch_osm(lat, lon, radius)
    db = facilities.db()
    for f in rows:
        db.execute("INSERT OR REPLACE INTO facility VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f["id"], f["name"], f["kind"], f["address"], f["lat"], f["lon"], f["phone"], f["emergency"],
                    f["services"], f["source"], None, f["fetched_on"]))
    db.commit()
    kinds = {k: sum(1 for f in rows if f["kind"] == k) for k in ("hospital", "health_centre", "clinic")}
    print(f"Stored {len(rows)} facilities from OpenStreetMap {kinds}; "
          f"{sum(1 for f in rows if f['emergency'] == 'yes')} list an emergency department.")


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(float(a[0]) if a else 26.1445, float(a[1]) if len(a) > 1 else 91.7362,
                     int(a[2]) if len(a) > 2 else 30000))
