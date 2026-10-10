"""Healthcare navigation: find the nearest emergency facilities.

Two sources, always labelled so nobody mistakes one for the other:

1. A seed list of public hospitals (data/facilities.csv) loaded into SQLite.
   Every row stays "not yet verified" until a team member phones the facility
   and fills in `verified_on`. Phone numbers are blank until then, on purpose:
   a wrong emergency number is worse than none.
2. Live OpenStreetMap lookups (Nominatim to geocode a place name, Overpass to
   list hospitals nearby). Free, no key, community-edited and unverified.

National emergency numbers are always returned first, so a caller never has to
wait for a search to know what to do. This module never contacts a facility.
"""
from __future__ import annotations

import csv
import difflib
import math
import re
import sqlite3
from pathlib import Path
from typing import Optional

import httpx

from . import config

DATA = Path(__file__).resolve().parent / "data"
NE_VIEWBOX = "88.0,29.5,97.5,21.9"  # lon/lat box around the eight North Eastern states

EMERGENCY_NUMBERS = [
    {"number": "112", "label": "National emergency (police, fire, ambulance)"},
    {"number": "108", "label": "Ambulance (in most states)"},
    {"number": "102", "label": "Pregnancy and child transport (where available)"},
    {"number": "14416", "label": "Tele-MANAS mental health support"},
]
NOT_CONTACTED = ("Aarogya Saathi has not contacted any hospital or ambulance. "
                 "Call the facility or 108/112 yourself.")


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE facility (
            id TEXT PRIMARY KEY, name TEXT, kind TEXT, district TEXT, state TEXT,
            lat REAL, lon REAL, phone TEXT, emergency_24x7 TEXT, capabilities TEXT,
            source TEXT, verified_on TEXT, notes TEXT);
        CREATE TABLE place (name TEXT, state TEXT, lat REAL, lon REAL, pin_prefix TEXT, aliases TEXT, pins TEXT);
    """)
    for table, fname in (("facility", "facilities.csv"), ("place", "places.csv")):
        with open(DATA / fname, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0].keys())
        db.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                       [tuple(r[c] for c in cols) for r in rows])
    return db


_db = _connect()


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- where is the caller? ----------

def _places() -> list[sqlite3.Row]:
    return _db.execute("SELECT * FROM place").fetchall()


def _place_dict(row: sqlite3.Row, how: str) -> dict:
    return {"name": row["name"], "state": row["state"], "lat": row["lat"], "lon": row["lon"],
            "approximate": True, "method": how}


def resolve_local(text: str) -> Optional[dict]:
    """Match a PIN code or a town name (English or native script) against the gazetteer."""
    t = text.strip().lower()
    if not t:
        return None
    pin = re.search(r"\b(\d{6})\b", t)
    if pin:
        code = pin.group(1)
        for row in _places():  # exact PIN (Guwahati localities) beats the 3-digit area
            if code in (row["pins"] or "").split("|"):
                return _place_dict(row, f"PIN code {code}")
        row = _db.execute("SELECT * FROM place WHERE pin_prefix = ?", (code[:3],)).fetchone()
        if row:
            return _place_dict(row, f"PIN code area {code[:3]}xxx")
    names: dict[str, sqlite3.Row] = {}
    for row in _places():
        names[row["name"].lower()] = row
        for alias in filter(None, (row["aliases"] or "").split("|")):
            names[alias.lower()] = row
    # Longest names first, so "North Guwahati" wins over "Guwahati".
    for name, row in sorted(names.items(), key=lambda kv: -len(kv[0])):
        if len(name) >= 3 and name in t:
            return _place_dict(row, "town name")
    words = re.findall(r"\w+", t)
    for w in words:
        hit = difflib.get_close_matches(w, list(names), n=1, cutoff=0.82)
        if hit:
            return _place_dict(names[hit[0]], "town name (closest spelling)")
    return None


def _client() -> httpx.AsyncClient:
    s = config.settings
    return httpx.AsyncClient(timeout=8, headers={"User-Agent": f"AarogyaSaathi/1.0 ({s.osm_contact})"})


async def geocode_osm(text: str) -> Optional[dict]:
    if not config.settings.osm_enabled:
        return None
    try:
        async with _client() as c:
            resp = await c.get("https://nominatim.openstreetmap.org/search", params={
                "q": text, "format": "json", "limit": 1, "countrycodes": "in",
                "viewbox": NE_VIEWBOX, "bounded": 1})
        hits = resp.json() if resp.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return None
    if not hits:
        return None
    h = hits[0]
    return {"name": h.get("display_name", text).split(",")[0], "state": None, "lat": float(h["lat"]),
            "lon": float(h["lon"]), "approximate": True, "method": "OpenStreetMap place search"}


async def resolve(text: str) -> Optional[dict]:
    return resolve_local(text) or await geocode_osm(text)


# ---------- facilities near a point ----------

def _facility_dict(row: sqlite3.Row, lat: float, lon: float) -> dict:
    verified = bool(row["verified_on"])
    return {
        "id": row["id"], "name": row["name"], "kind": row["kind"], "district": row["district"],
        "state": row["state"], "lat": row["lat"], "lon": row["lon"],
        "distance_km": round(km_between(lat, lon, row["lat"], row["lon"]), 1),
        "phone": row["phone"] or None, "emergency_24x7": row["emergency_24x7"],
        "capabilities": row["capabilities"], "source": row["source"],
        "verified": verified, "verified_on": row["verified_on"] or None,
        "verification": f"Verified by phone on {row['verified_on']}" if verified
        else "Not yet verified. Confirm by phone before travelling.",
        "notes": row["notes"],
        "map_url": f"https://www.openstreetmap.org/?mlat={row['lat']}&mlon={row['lon']}#map=15/{row['lat']}/{row['lon']}",
    }


def nearby_seed(lat: float, lon: float, limit: int = 5) -> list[dict]:
    rows = _db.execute("SELECT * FROM facility").fetchall()
    out = sorted((_facility_dict(r, lat, lon) for r in rows), key=lambda f: f["distance_km"])
    return out[:limit]


async def nearby_osm(lat: float, lon: float, radius_m: int = 25000, limit: int = 5) -> list[dict]:
    if not config.settings.osm_enabled:
        return []
    query = (f'[out:json][timeout:8];(node["amenity"="hospital"](around:{radius_m},{lat},{lon});'
             f'way["amenity"="hospital"](around:{radius_m},{lat},{lon}););out center 30;')
    try:
        async with _client() as c:
            resp = await c.post("https://overpass-api.de/api/interpreter", data={"data": query})
        elements = resp.json().get("elements", []) if resp.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        flat, flon = e.get("lat") or e.get("center", {}).get("lat"), e.get("lon") or e.get("center", {}).get("lon")
        if not name or flat is None:
            continue
        out.append({
            "id": f"osm-{e['type']}-{e['id']}", "name": name, "kind": tags.get("healthcare", "hospital"),
            "district": tags.get("addr:district"), "state": tags.get("addr:state"), "lat": flat, "lon": flon,
            "distance_km": round(km_between(lat, lon, flat, flon), 1),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "emergency_24x7": {"yes": "listed", "no": "not listed"}.get(tags.get("emergency", ""), "unknown"),
            "capabilities": None, "source": "OpenStreetMap (community data)", "verified": False, "verified_on": None,
            "verification": "From OpenStreetMap, not verified. Confirm by phone before travelling.",
            "notes": None,
            "map_url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
        })
    out.sort(key=lambda f: f["distance_km"])
    return out[:limit]


async def find(lat: float, lon: float) -> dict:
    seed = nearby_seed(lat, lon)
    osm = await nearby_osm(lat, lon)
    seen = {f["name"].lower() for f in seed}
    osm = [f for f in osm if f["name"].lower() not in seen]
    # For an emergency, point to the closest place expected to run a 24x7 emergency, not a campus clinic.
    capable = [f for f in seed + osm if f["emergency_24x7"] in ("expected", "listed")]
    nearest = min(capable or seed + osm, key=lambda f: f["distance_km"], default=None)
    return {"emergency_numbers": EMERGENCY_NUMBERS, "facilities": seed, "osm_facilities": osm,
            "nearest": nearest, "notice": NOT_CONTACTED,
            "distance_note": "Straight-line distance. Road distance in the hills can be much longer."}
