"""Routine answers come from the LLM (MOCKED HTTP). No scripted fallback exists."""
import json

import httpx

from app.providers import llm
from tests.conftest import configure, llm_reply


def start(client, lang="en-IN"):
    r = client.post("/api/conversations", json={"language": lang})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_arbitrary_question_is_sent_to_the_llm(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nCracked heels can happen with dry skin. Soak your feet and use a thick cream."))
    cid = start(client)
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "Why do my heels crack in winter?"}).json()
    assert t["error"] is None
    assert t["answer"]["source"] == "llm" and t["answer"]["model"] == "openai/gpt-oss-120b"
    assert "Soak your feet" in t["answer"]["text"]
    req = live.bodies("/chat/completions")[0]
    assert req["model"] == "openai/gpt-oss-120b" and req["reasoning_effort"] == "low"
    assert req["messages"][-1] == {"role": "user", "content": "Why do my heels crack in winter?"}
    assert "llm" in t["timings_ms"]


def test_follow_up_questions_carry_history(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nDrink clean water and rest."))
    cid = start(client)
    client.post(f"/api/conversations/{cid}/ask", json={"text": "My child has diarrhoea."})
    client.post(f"/api/conversations/{cid}/ask", json={"text": "And how much water?"})
    msgs = live.bodies("/chat/completions")[1]["messages"]
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == "My child has diarrhoea."


def test_hindi_pivots_through_translation_both_ways(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nRest and drink water."))
    cid = start(client, "hi-IN")
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "मुझे सिरदर्द है"}).json()
    assert t["english"] == "EN[मुझे सिरदर्द है]"
    assert live.bodies("/chat/completions")[0]["messages"][-1]["content"] == "EN[मुझे सिरदर्द है]"
    assert t["answer"]["text"] == "hi-IN[Rest and drink water.]" and t["answer"]["lang"] == "hi-IN"
    assert t["voice"]["audio_url"].startswith("/api/audio/")


def test_translation_failure_is_labelled_not_hidden(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nRest."))
    live.on("/translate", lambda r: httpx.Response(200, json={"translated_text": "EN[q]"})
            if json.loads(r.content)["target_language_code"] == "en-IN" else httpx.Response(503))
    cid = start(client, "hi-IN")
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "सवाल"}).json()
    assert t["answer"]["lang"] == "en-IN" and "translation failed" in t["answer"]["language_note"]


def test_missing_llm_key_is_reported_honestly(client, monkeypatch, http):
    configure(monkeypatch, SARVAM_API_KEY="x")
    r = client.post("/api/conversations", json={"language": "en-IN"})
    assert r.status_code == 409 and "AI key" in r.json()["detail"]


def test_provider_errors_are_explained(client, live):
    cid = start(client)
    for status, kind in [(401, "auth"), (429, "rate_limited"), (503, "unavailable")]:
        live.on("/chat/completions", httpx.Response(status, headers={"retry-after": "30"}))
        t = client.post(f"/api/conversations/{cid}/ask", json={"text": "What is anaemia?"}).json()
        assert t["answer"] is None and t["error"]["kind"] == kind, (status, t["error"])
        assert t["error"]["message"]


def test_malformed_llm_reply(client, live):
    cid = start(client)
    live.on("/chat/completions", httpx.Response(200, json={"choices": []}))
    assert client.post(f"/api/conversations/{cid}/ask", json={"text": "What is anaemia?"}).json()["error"]["kind"] == "bad_response"
    live.on("/chat/completions", httpx.Response(200, content=b"<html>"))
    assert client.post(f"/api/conversations/{cid}/ask", json={"text": "What is anaemia?"}).json()["error"]["kind"] == "bad_response"
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\n"))
    assert client.post(f"/api/conversations/{cid}/ask", json={"text": "What is anaemia?"}).json()["error"]["kind"] == "bad_response"


def test_reasoning_param_dropped_for_models_that_reject_it(client, live):
    replies = iter([httpx.Response(400), llm_reply("TRIAGE: ROUTINE\nOk answer.")])
    live.on("/chat/completions", lambda r: next(replies))
    cid = start(client)
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "What is anaemia?"}).json()
    assert t["answer"]["text"] == "Ok answer."
    first, second = live.bodies("/chat/completions")
    assert "reasoning_effort" in first and "reasoning_effort" not in second


def test_simpler_reasks_with_simple_level(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nShort answer."))
    cid = start(client)
    client.post(f"/api/conversations/{cid}/ask", json={"text": "What is diabetes?"})
    t = client.post(f"/api/conversations/{cid}/simpler").json()
    assert t["level"] == "simple"
    assert "10-year-old" in live.bodies("/chat/completions")[-1]["messages"][0]["content"]


def test_parse_triage_tag():
    assert llm.parse("TRIAGE: URGENT\nSee a doctor today.") == ("urgent", "See a doctor today.")
    assert llm.parse("**TRIAGE: emergency**\nGo now.") == ("emergency", "Go now.")
    assert llm.parse("No tag here.") == ("routine", "No tag here.")


def test_system_prompt_safety_rules():
    system = llm.build_messages("q", [], "standard")[0]["content"]
    for rule in ["Never prescribe", "never state a dose", "Never claim you contacted", "never say the person definitely".lower()]:
        assert rule.lower() in system.lower()


def test_dose_in_ai_answer_is_removed(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nParacetamol is used for fever. Take 500 mg twice a day. Rest well."))
    cid = start(client)
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "What dose of paracetamol should I take?"}).json()
    assert t["medicine"] == {"request": True, "dose_removed": True}
    assert "500 mg" not in t["answer"]["text"] and "pharmacist" in t["answer"]["text"]
    assert "medicine_safety" in [c["id"] for c in t["answer"]["cards"]]
