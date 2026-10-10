"""Nearby healthcare facility finder, using documented data only.

Sources, always labelled in results:
1. OpenStreetMap (ODbL), live via the Overpass API, cached in SQLite for 7 days.
   `scripts/import_osm_facilities.py` can also pre-load an area for offline use.
2. `data/verified_facilities.csv`: rows your team has checked by phone, with
   the services and phone number confirmed and the date of the check.

Emergency capability is never guessed from a name or type: it is "yes" only
when the data says so (OSM `emergency=yes`, or a verified row), else "unknown".
Nothing here contacts a facility.
"""
from __future__ import annotations

import asyncio
import csv
import difflib
import json
import math
import re
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Optional

from . import config
from .providers import ProviderError, json_of, send

DATA = Path(__file__).resolve().parent / "data"
CACHE_DAYS = 7
RADII_M = (10_000, 30_000, 80_000)

EMERGENCY_NUMBERS = [
    {"number": "112", "label": "National emergency (police, fire, ambulance)"},
    {"number": "108", "label": "Ambulance (in most states)"},
    {"number": "102", "label": "Pregnancy and child transport (where available)"},
    {"number": "14416", "label": "Tele-MANAS mental health support"},
]
NOT_CONTACTED = "Aarogya Saathi has not contacted any hospital or ambulance. Call them or 112 yourself."

SCHEMA = """
CREATE TABLE IF NOT EXISTS facility (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT, address TEXT, lat REAL NOT NULL, lon REAL NOT NULL,
    phone TEXT, emergency TEXT, services TEXT, source TEXT NOT NULL, verified_on TEXT, fetched_on TEXT);
CREATE TABLE IF NOT EXISTS osm_cache (key TEXT PRIMARY KEY, fetched REAL, payload TEXT);
CREATE TABLE IF NOT EXISTS geocode_cache (query TEXT PRIMARY KEY, fetched REAL, payload TEXT);
"""


def _connect() -> sqlite3.Connection:
    path = config.settings.db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    _load_verified(db)
    return db


def _load_verified(db: sqlite3.Connection) -> None:
    path = DATA / "verified_facilities.csv"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(row for row in f if not row.startswith("#")):
            if not (r.get("name") and r.get("lat") and r.get("lon") and r.get("verified_on")):
                continue  # a row without a verification date is not verified data
            db.execute("INSERT OR REPLACE INTO facility VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                f"verified-{r['name'].lower()}", r["name"], r.get("kind") or "hospital", r.get("address"),
                float(r["lat"]), float(r["lon"]), r.get("phone") or None, r.get("emergency") or "unknown",
                r.get("services") or None, "Verified by the Aarogya Saathi team", r["verified_on"], None))
    db.commit()


_db: Optional[sqlite3.Connection] = None


def db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = _connect()
    return _db


def reset() -> None:
    """For tests and config reloads."""
    global _db
    if _db is not None:
        _db.close()
    _db = None


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


# ---------- where is the user? ----------

_nominatim_lock = asyncio.Lock()
_last_nominatim = 0.0


def _ua() -> dict:
    return {"User-Agent": f"AarogyaSaathi/1.0 ({config.settings.osm_contact})"}


async def geocode_osm(text: str) -> Optional[dict]:
    """Nominatim search (usage policy: max 1 request per second, cached)."""
    global _last_nominatim
    q = text.strip().lower()
    row = db().execute("SELECT payload FROM geocode_cache WHERE query = ?", (q,)).fetchone()
    if row:
        return json.loads(row["payload"])
    params = {"format": "json", "limit": 1, "countrycodes": "in", "addressdetails": 0}
    pin = re.fullmatch(r"\s*(\d{6})\s*", text)
    params.update({"postalcode": pin.group(1)} if pin else {"q": text})
    async with _nominatim_lock:
        wait = 1.0 - (time.time() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim = time.time()
        resp = await send("OpenStreetMap place search", "GET", config.settings.nominatim_url, timeout=10, params=params, headers=_ua())
    hits = json_of(resp, "OpenStreetMap place search")
    if not hits:
        return None
    h = hits[0]
    first, _, rest = (h.get("display_name") or text).partition(",")
    place = {"name": first.strip(), "detail": rest.strip() or None,
             "lat": float(h["lat"]), "lon": float(h["lon"]), "approximate": True,
             "method": "OpenStreetMap place search"}
    db().execute("INSERT OR REPLACE INTO geocode_cache VALUES (?,?,?)", (q, time.time(), json.dumps(place)))
    db().commit()
    return place


def resolve_offline(text: str) -> Optional[dict]:
    """Built-in list of NE towns, Guwahati localities and PIN areas (approximate centres)."""
    t = text.strip().lower()
    if not t:
        return None
    with open(DATA / "places.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pin = re.search(r"\b(\d{6})\b", t)
    if pin:
        code = pin.group(1)
        for r in rows:
            if code in (r["pins"] or "").split("|"):
                return _place(r, f"PIN code {code}")
        for r in rows:
            if r["pin_prefix"] == code[:3]:
                return _place(r, f"PIN area {code[:3]}xxx")
    names: dict[str, dict] = {}
    for r in rows:
        names[r["name"].lower()] = r
        for alias in filter(None, (r["aliases"] or "").split("|")):
            names[alias.lower()] = r
    for name, r in sorted(names.items(), key=lambda kv: -len(kv[0])):  # "North Guwahati" before "Guwahati"
        if len(name) >= 3 and name in t:
            return _place(r, "town name")
    for w in re.findall(r"\w+", t):
        hit = difflib.get_close_matches(w, list(names), n=1, cutoff=0.82)
        if hit:
            return _place(names[hit[0]], "closest town name")
    return None


def _place(r: dict, how: str) -> dict:
    return {"name": r["name"], "detail": r["state"], "lat": float(r["lat"]), "lon": float(r["lon"]),
            "approximate": True, "method": f"{how} (built-in approximate town list)"}


async def resolve(text: str) -> tuple[Optional[dict], Optional[dict]]:
    """Return (place, error). Uses OpenStreetMap when enabled, else the built-in list."""
    error = None
    if config.settings.osm_enabled:
        try:
            place = await geocode_osm(text)
            if place:
                return place, None
        except ProviderError as exc:
            error = exc.public()
    return resolve_offline(text), error


# ---------- facilities near a point ----------

def _osm_query(lat: float, lon: float, radius: int) -> str:
    around = f"(around:{radius},{lat},{lon})"
    parts = "".join(f'{t}["{k}"="{v}"]{around};' for t in ("node", "way", "relation")
                    for k, v in (("amenity", "hospital"), ("amenity", "clinic"), ("healthcare", "hospital"),
                                 ("healthcare", "clinic"), ("healthcare", "centre")))
    return f"[out:json][timeout:15];({parts});out center tags 60;"


def _from_osm(e: dict) -> Optional[dict]:
    tags = e.get("tags") or {}
    name = tags.get("name:en") or tags.get("name")
    lat = e.get("lat", (e.get("center") or {}).get("lat"))
    lon = e.get("lon", (e.get("center") or {}).get("lon"))
    if not name or lat is None or lon is None:
        return None
    is_hospital = tags.get("amenity") == "hospital" or tags.get("healthcare") == "hospital"
    kind = "hospital" if is_hospital else ("health_centre" if tags.get("healthcare") == "centre" else "clinic")
    addr = ", ".join(v for k in ("addr:housename", "addr:street", "addr:suburb", "addr:city", "addr:district",
                                 "addr:postcode") if (v := tags.get(k)))
    return {"id": f"osm-{e['type']}-{e['id']}", "name": name, "kind": kind, "address": addr or None,
            "lat": float(lat), "lon": float(lon), "phone": tags.get("phone") or tags.get("contact:phone"),
            "emergency": {"yes": "yes", "no": "no"}.get(tags.get("emergency", ""), "unknown"),
            "services": tags.get("healthcare:speciality"), "source": "OpenStreetMap",
            "verified_on": None, "fetched_on": date.today().isoformat()}


async def fetch_osm(lat: float, lon: float, radius: int) -> list[dict]:
    key = f"{lat:.2f},{lon:.2f},{radius}"
    row = db().execute("SELECT fetched, payload FROM osm_cache WHERE key = ?", (key,)).fetchone()
    if row and time.time() - row["fetched"] < CACHE_DAYS * 86400:
        return json.loads(row["payload"])
    resp = await send("OpenStreetMap hospital search", "POST", config.settings.overpass_url, timeout=25,
                      data={"data": _osm_query(lat, lon, radius)}, headers=_ua())
    body = json_of(resp, "OpenStreetMap hospital search")
    found = [f for e in body.get("elements", []) if (f := _from_osm(e))]
    db().execute("INSERT OR REPLACE INTO osm_cache VALUES (?,?,?)", (key, time.time(), json.dumps(found)))
    db().commit()
    return found


def stored_near(lat: float, lon: float, radius_km: float) -> list[dict]:
    """Verified rows plus anything pre-imported from OpenStreetMap."""
    d = radius_km / 111.0
    rows = db().execute("SELECT * FROM facility WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                        (lat - d, lat + d, lon - d * 1.3, lon + d * 1.3)).fetchall()
    return [dict(r) for r in rows]


def _present(f: dict, lat: float, lon: float) -> dict:
    verified = bool(f.get("verified_on"))
    phone_source = "verified by the team" if verified else "from OpenStreetMap, not verified"
    return {
        **f,
        "distance_km": round(km_between(lat, lon, f["lat"], f["lon"]), 1),
        "verified": verified,
        "emergency_label": {"yes": "Emergency department listed", "no": "No emergency department listed"}
        .get(f.get("emergency"), "Emergency service unknown"),
        "phone_label": f"Phone {phone_source}" if f.get("phone") else "No phone number in the data",
        "data_label": f"Verified by phone on {f['verified_on']}" if verified
        else f"{f['source']} (community data, last fetched {f.get('fetched_on') or 'unknown'}). Not verified.",
        "directions_url": f"https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={f['lat']},{f['lon']}",
        "map_url": f"https://www.openstreetmap.org/?mlat={f['lat']}&mlon={f['lon']}#map=16/{f['lat']}/{f['lon']}",
    }


async def find(lat: float, lon: float, emergency: bool = False, limit: int = 8) -> dict:
    s = config.settings
    found: dict[str, dict] = {}
    error = None
    radius_used = None
    for radius in RADII_M:
        radius_used = radius
        for f in stored_near(lat, lon, radius / 1000):
            found.setdefault(f["id"], f)
        if s.osm_enabled:
            try:
                for f in await fetch_osm(lat, lon, radius):
                    found.setdefault(f["id"], f)
            except ProviderError as exc:
                error = exc.public()
                break
        hospitals = [f for f in found.values() if f["kind"] == "hospital"]
        if len(hospitals) >= 3 or (not emergency and len(found) >= 3):
            break
    items = [_present(f, lat, lon) for f in found.values()]
    # Emergency: hospitals first (a listed emergency department first of all), then distance.
    rank = (lambda f: (f["kind"] != "hospital", f["emergency"] != "yes", f["distance_km"])) if emergency \
        else (lambda f: f["distance_km"])
    items.sort(key=rank)
    limitation = None
    if not s.osm_enabled and not items:
        limitation = ("No facility data source is configured. Turn on OpenStreetMap (OSM_ENABLED=true) or add "
                      "checked facilities to data/verified_facilities.csv.")
    elif not items:
        limitation = f"No facilities found within {radius_used // 1000} km in the available data."
    return {"facilities": items[:limit], "emergency_numbers": EMERGENCY_NUMBERS, "notice": NOT_CONTACTED,
            "error": error, "limitation": limitation,
            "distance_note": "Straight-line distance. Road distance in the hills can be much longer.",
            "attribution": "Facility data © OpenStreetMap contributors, ODbL." if s.osm_enabled else None}
