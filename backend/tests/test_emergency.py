"""Independent safety layer: emergencies never wait for, or depend on, the LLM (MOCKED HTTP)."""
import pytest

from tests.conftest import llm_reply


@pytest.mark.parametrize("lang,text,rule", [
    ("en-IN", "My father has severe chest pain and is sweating", "chest_pain"),
    ("hi-IN", "मेरे पिता के सीने में दर्द है", "chest_pain"),
    ("as-IN", "দেউতাৰ বুকুত বিষ হৈছে", "chest_pain"),
    ("bn-IN", "বাবার বুকে ব্যথা হচ্ছে", "chest_pain"),
    ("en-IN", "She suddenly cannot speak and her face is drooping", "stroke"),
    ("hi-IN", "मेरी माँ बेहोश हो गई हैं", "unconscious"),
    ("en-IN", "There is heavy bleeding from his leg", "bleeding"),
    ("as-IN", "মোৰ ভাইক সাপে কামোৰিলে", "snakebite"),
])
def test_rules_trigger_emergency_without_the_llm(client, live, lang, text, rule):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nShould never be used."))
    cid = client.post("/api/conversations", json={"language": lang}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": text}).json()
    assert t["triage"]["level"] == "emergency" and t["triage"]["source"] == "rules"
    assert rule in [m["rule"] for m in t["triage"]["matches"]]
    assert t["answer"]["source"] == "emergency_script" and "112" in t["answer"]["text"]
    assert t["offer_facilities"] is True and t["answer"]["location_prompt"]["text"]
    assert not any(p.endswith("/chat/completions") for p in live.paths())


def test_emergency_still_works_when_ai_and_translation_are_down(client, live):
    import httpx
    live.on("/chat/completions", httpx.Response(503)).on("/translate", httpx.Response(503))
    cid = client.post("/api/conversations", json={"language": "hi-IN"}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "उसे सांस नहीं आ रही"}).json()
    assert t["triage"]["level"] == "emergency" and t["error"] is None
    assert t["answer"]["lang"] == "hi-IN" and "112" in t["answer"]["text"]


def test_ai_backup_triage_upgrades_missed_emergency(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: EMERGENCY\nThis needs help now."))
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "My grandfather's lips look grey and he is very cold"}).json()
    assert t["triage"]["source"] == "ai" and t["answer"]["source"] == "emergency_script"


def test_crisis_gives_helpline_not_ai(client, live):
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "I want to end my life"}).json()
    assert t["triage"]["level"] == "crisis" and "14416" in t["answer"]["text"]


def test_routine_question_is_not_an_emergency(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nWash hands with soap."))
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "How can I stop my family getting typhoid?"}).json()
    assert t["triage"]["level"] == "none" and t["answer"]["source"] == "llm"


def test_emergency_button_is_instant_and_needs_no_keys(client):
    r = client.get("/api/emergency", params={"lang": "as-IN"}).json()
    assert "112" in r["message"]["text"] and r["message"]["lang"] == "as-IN"
    assert r["emergency_numbers"][0]["number"] == "112"
    assert r["voice"]["audio_url"] is None and r["voice"]["note"]  # no voice configured, says so
