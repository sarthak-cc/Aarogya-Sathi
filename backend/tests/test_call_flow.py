"""End-to-end call flow in demo mode (no API keys)."""
from app import sessions


def test_health_and_languages(client):
    assert client.get("/api/health").json()["status"] == "ok"
    langs = client.get("/api/languages").json()["languages"]
    codes = {l["code"]: l for l in langs}
    assert codes["as-IN"]["keypad"] == "1"
    assert codes["kha-IN"]["level"] == "unsupported"
    assert codes["as-IN"]["level"] == "voice_ready_needs_keys"  # no keys -> never claims full voice


def test_language_required_before_question(client):
    cid = client.post("/api/calls/start").json()["call"]["id"]
    r = client.post(f"/api/calls/{cid}/message", json={"text": "fever"})
    assert r.status_code == 409


def test_language_selection_and_persistence(client, call):
    r = client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে। মই কি কৰিম?"}).json()
    t = r["turn"]
    assert t["answer"]["lang"] == "as-IN"
    assert t["answer"]["source"] == "demo"
    r2 = client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কেঁচুৱাটোৰ দুদিনৰ পৰা কাহ হৈছে।"}).json()
    assert r2["turn"]["answer"]["lang"] == "as-IN"
    assert sessions.get(call).language == "as-IN"


def test_unsupported_language_is_honest(client):
    cid = client.post("/api/calls/start").json()["call"]["id"]
    r = client.post(f"/api/calls/{cid}/language", json={"digit": "8"}).json()
    assert r["supported"] is False
    assert "cannot yet" in r["prompt"]["text"]
    assert "as-IN" in r["alternatives"]
    assert client.get("/api/stats/unsupported-languages").json()["requests"]["other_ner"] >= 1


def test_emergency_skips_ai(client, call):
    t = client.post(f"/api/calls/{call}/message", json={"text": "পথাৰত মোৰ ভাইটিক সাপে কামোৰিলে।"}).json()["turn"]
    assert t["triage"]["level"] == "emergency"
    assert t["answer"]["source"] == "emergency"
    assert "112" in t["answer"]["text"]
    assert "llm" not in t["timings_ms"]
    assert sessions.get(call).state.value == "EMERGENCY"


def test_unknown_question_does_not_invent(client):
    cid = client.post("/api/calls/start").json()["call"]["id"]
    client.post(f"/api/calls/{cid}/language", json={"digit": "7"})
    t = client.post(f"/api/calls/{cid}/message", json={"text": "Can you tell me about my knee replacement surgery"}).json()["turn"]
    assert "do not have reliable information" in t["answer"]["text"]


def test_readback_confirm_and_reject(client, call):
    r = client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে।", "skip_readback": False}).json()
    assert "মই শুনিলোঁ" in r["prompt"]["text"]
    assert sessions.get(call).state.value == "CONFIRMING"
    no = client.post(f"/api/calls/{call}/confirm", json={"correct": False}).json()
    assert no["confirmed"] is False and sessions.get(call).state.value == "READY_TO_LISTEN"
    client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে।", "skip_readback": False})
    yes = client.post(f"/api/calls/{call}/confirm", json={"correct": True}).json()
    assert yes["turn"]["answer"]["text"]


def test_simpler_is_shorter(client, call):
    full = client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে। মই কি কৰিম?"}).json()["turn"]
    simple = client.post(f"/api/calls/{call}/simpler").json()["turn"]
    assert len(simple["answer"]["text"]) < len(full["answer"]["text"])
    assert simple["level"] == "simple"


def test_audio_upload_without_stt_explains_fallback(client, call):
    r = client.post(f"/api/calls/{call}/transcribe", files={"audio": ("q.webm", b"fake-audio", "audio/webm")}).json()
    assert r["ok"] is False and r["reason"] == "stt_unavailable"


def test_end_without_consent_clears_everything(client, call):
    client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে।"})
    r = client.post(f"/api/calls/{call}/end", json={"consent_slip": False}).json()
    assert r["slip"] is None and r["data_cleared"]
    s = sessions.get(call)
    assert s.turns == [] and s.history == []
    assert client.post(f"/api/calls/{call}/message", json={"text": "hi"}).status_code == 404


def test_consent_slip_created_and_deletable(client, call):
    client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কালিৰ পৰা জ্বৰ হৈছে। মই কি কৰিম?"})
    client.post(f"/api/calls/{call}/message", json={"text": "পথাৰত মোৰ ভাইটিক সাপে কামোৰিলে।"})
    slip = client.post(f"/api/calls/{call}/end", json={"consent_slip": True}).json()["slip"]
    assert slip["urgency"] == "emergency"
    assert "Snakebite" in slip["red_flags"]
    assert slip["concerns"][0]["duration"] == "since yesterday"
    assert "diagnos" in slip["disclaimer"].lower()
    assert client.get(f"/api/slips/{slip['code']}").status_code == 200
    client.delete(f"/api/slips/{slip['code']}")
    assert client.get(f"/api/slips/{slip['code']}").status_code == 404


def test_validation(client, call):
    assert client.post(f"/api/calls/{call}/message", json={"text": ""}).status_code == 422
    assert client.post(f"/api/calls/{call}/language", json={"digit": "x"}).status_code == 422
    assert client.post("/api/calls/NOPE/message", json={"text": "hi"}).status_code == 404
