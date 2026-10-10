"""Nearby facility finder: documented data only, honest labels (MOCKED OpenStreetMap)."""
import json

import httpx

from app import facilities
from tests.conftest import configure

OVERPASS = {"elements": [
    {"type": "node", "id": 1, "lat": 26.150, "lon": 91.670,
     "tags": {"amenity": "clinic", "name": "Campus Clinic"}},
    {"type": "way", "id": 2, "center": {"lat": 26.155, "lon": 91.765},
     "tags": {"amenity": "hospital", "name": "Big Public Hospital", "emergency": "yes", "phone": "+91 361 000 0000",
              "addr:city": "Guwahati"}},
    {"type": "node", "id": 3, "lat": 26.128, "lon": 91.677,
     "tags": {"amenity": "hospital", "name": "Private Hospital"}},
    {"type": "node", "id": 4, "lat": 26.13, "lon": 91.68, "tags": {"amenity": "hospital"}},  # no name: skipped
]}


def osm(monkeypatch, http):
    configure(monkeypatch, OSM_ENABLED="true")
    facilities.reset()
    http.on("/api/interpreter", httpx.Response(200, json=OVERPASS))
    http.on("/search", httpx.Response(200, json=[{"lat": "26.143", "lon": "91.660", "display_name": "Jalukbari, Guwahati, Assam"}]))


def test_device_location_emergency_ranking_and_labels(client, monkeypatch, http):
    osm(monkeypatch, http)
    r = client.post("/api/facilities/search", json={"lat": 26.143, "lon": 91.660, "emergency": True}).json()
    names = [f["name"] for f in r["facilities"]]
    assert names[0] == "Big Public Hospital"  # listed emergency department first
    assert names.index("Private Hospital") < names.index("Campus Clinic")  # hospitals before clinics
    big = r["facilities"][0]
    assert big["emergency_label"] == "Emergency department listed" and "not verified" in big["phone_label"]
    priv = next(f for f in r["facilities"] if f["name"] == "Private Hospital")
    assert priv["emergency"] == "unknown" and priv["phone"] is None  # never inferred
    assert "OpenStreetMap" in r["attribution"] and "not contacted" in r["notice"]
    assert big["directions_url"].startswith("https://www.google.com/maps/dir/")
    assert "Overpass" not in json.dumps(r)


def test_place_text_uses_nominatim_then_caches(client, monkeypatch, http):
    osm(monkeypatch, http)
    for _ in range(2):
        r = client.post("/api/facilities/search", json={"text": "Jalukbari"}).json()
        assert r["place"]["method"] == "OpenStreetMap place search"
    assert sum(p.endswith("/search") for p in http.paths()) == 1
    assert sum(p.endswith("/api/interpreter") for p in http.paths()) == 1  # Overpass cached too


def test_osm_outage_is_reported(client, monkeypatch, http):
    configure(monkeypatch, OSM_ENABLED="true")
    facilities.reset()
    http.on("/api/interpreter", httpx.Response(504))
    r = client.post("/api/facilities/search", json={"lat": 26.14, "lon": 91.66}).json()
    assert r["error"]["kind"] == "unavailable" and r["facilities"] == [] and r["limitation"]


def test_no_data_source_is_explained(client):
    r = client.post("/api/facilities/search", json={"lat": 26.14, "lon": 91.66}).json()
    assert r["facilities"] == [] and "No facility data source" in r["limitation"]


def test_offline_place_resolution_when_osm_off(client):
    r = client.post("/api/facilities/search", json={"text": "781014"}).json()
    assert r["place"]["name"] == "Jalukbari" and "approximate" in r["place"]["method"]
    assert client.post("/api/facilities/search", json={"text": "qqqq zzzz"}).json()["limitation"]
    assert client.post("/api/facilities/search", json={}).status_code == 422


def test_verified_rows_only_with_a_date(tmp_path, monkeypatch):
    csv = tmp_path / "verified_facilities.csv"
    csv.write_text("# comment\nname,kind,address,lat,lon,phone,emergency,services,verified_on\n"
                   "Checked Hospital,hospital,Somewhere,26.15,91.66,0361-1,yes,Emergency,2026-10-11\n"
                   "Unchecked Hospital,hospital,,26.15,91.66,,,,\n", encoding="utf-8")
    monkeypatch.setattr(facilities, "DATA", tmp_path)
    facilities.reset()
    rows = facilities.stored_near(26.15, 91.66, 5)
    assert [r["name"] for r in rows] == ["Checked Hospital"]
    shown = facilities._present(rows[0], 26.15, 91.66)
    assert shown["verified"] and "verified by the team" in shown["phone_label"]
