"""Emergency location step and verified-facility search (seed list only; OSM is off in tests)."""
import pytest

from app import facilities, sessions


@pytest.mark.parametrize("text,place", [
    ("I am at Assam Engineering College", "Assam Engineering College"),
    ("jalukbari", "Jalukbari"),
    ("781014", "Jalukbari"),
    ("near the bridge in North Guwahati", "North Guwahati"),
    ("গুৱাহাটী", "Guwahati"),
    ("মালিগাঁও", "Maligaon"),
    ("pin 786001", "Dibrugarh"),
    ("shilong", "Shillong"),
])
def test_resolves_places_pins_and_native_names(text, place):
    assert facilities.resolve_local(text)["name"] == place


def test_unknown_place_is_not_guessed():
    assert facilities.resolve_local("somewhere far away xyz") is None


def test_seed_facilities_are_honest_about_verification():
    for f in facilities.nearby_seed(26.143, 91.660, limit=50):
        if not f["verified"]:
            assert f["phone"] is None  # no unverified emergency phone numbers
            assert "Not yet verified" in f["verification"]


async def _find(lat, lon):
    return await facilities.find(lat, lon)


def test_emergency_turn_asks_for_location_then_lists_facilities(client, call):
    t = client.post(f"/api/calls/{call}/message", json={"text": "My father has severe chest pain"}).json()["turn"]
    assert t["triage"]["level"] == "emergency"
    assert "112" in t["answer"]["text"]  # guidance comes first, before any search
    assert t["location_prompt"]["text"]
    assert "4" in t["menu"]["text"]

    r = client.post(f"/api/calls/{call}/location", json={"text": "Assam Engineering College, Jalukbari"}).json()
    assert r["ok"] and r["place"]["name"] == "Assam Engineering College"
    assert [n["number"] for n in r["emergency_numbers"]][:2] == ["112", "108"]
    assert r["facilities"][0]["distance_km"] < 3
    assert r["nearest"]["emergency_24x7"] == "expected"  # a campus clinic is not sent as the emergency stop
    assert "not contacted" in r["notice"]
    assert r["prompt"]["text"]


def test_device_location_and_session_wipe(client, call):
    r = client.post(f"/api/calls/{call}/location", json={"lat": 26.1445, "lon": 91.7362, "accuracy_m": 30}).json()
    assert r["ok"] and r["place"]["method"] == "device location"
    assert sessions.get(call).location is not None
    client.post(f"/api/calls/{call}/end", json={"consent_slip": False})
    assert sessions.get(call).location is None


def test_location_not_found_still_gives_emergency_numbers(client, call):
    r = client.post(f"/api/calls/{call}/location", json={"text": "qqqq zzzz"}).json()
    assert not r["ok"] and r["emergency_numbers"][0]["number"] == "112"


def test_public_facility_search_by_pin(client):
    r = client.get("/api/facilities", params={"q": "781014"}).json()
    assert r["place"]["name"] == "Jalukbari" and len(r["facilities"]) == 5
    assert client.get("/api/facilities").status_code == 422


def test_channels_are_honest(client):
    ch = {c["id"]: c["status"] for c in client.get("/api/channels").json()["channels"]}
    assert ch == {"web_voice": "live", "phone_line": "planned", "hospital_alert": "not built"}
