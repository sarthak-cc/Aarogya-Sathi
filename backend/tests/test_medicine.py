"""Medicine safety: explain, never prescribe or dose."""
import json

import httpx
import pytest

from app import config, medicine


@pytest.mark.parametrize("text", [
    "Which medicine should I take for fever?", "What is the dose of paracetamol for my child?",
    "How many tablets should I take?", "Can you prescribe something for my cough?", "कौन सी दवा लूँ?",
])
def test_detects_prescription_requests(text):
    assert medicine.is_prescription_request(text)


def test_general_medicine_question_is_not_a_prescription_request():
    assert not medicine.is_prescription_request("Is it safe to share antibiotics with my brother?")


@pytest.mark.parametrize("text,dose", [
    ("Take 500 mg now.", True), ("Give 2 tablets twice a day.", True), ("Use 5 ml of syrup.", True),
    ("Take it every 6 hours.", True), ("Ask your pharmacist how to take it.", False), ("Call 112 or 108.", False),
])
def test_dose_filter(text, dose):
    assert medicine.contains_dose(text) is dose


def test_offline_answer_refuses_to_prescribe(client):
    cid = client.post("/api/calls/start").json()["call"]["id"]
    client.post(f"/api/calls/{cid}/language", json={"digit": "7"})
    t = client.post(f"/api/calls/{cid}/message", json={"text": "Which medicine should I take for fever?"}).json()["turn"]
    assert t["medicine"]["request"] is True
    assert t["cards"][0]["id"] == "medicine_safety"
    assert "cannot tell you which medicine" in t["answer"]["text"]
    assert not medicine.contains_dose(t["answer"]["text"])


def test_llm_answer_with_a_dose_is_blocked(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-llm")
    config.reload_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            assert "Never prescribe" in json.loads(request.content)["messages"][0]["content"]
            return httpx.Response(200, json={"choices": [{"message": {"content": "Take 500 mg paracetamol twice a day."}}]})
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr("app.providers.llm.client", lambda: real(transport=httpx.MockTransport(handler)))
    cid = client.post("/api/calls/start").json()["call"]["id"]
    client.post(f"/api/calls/{cid}/language", json={"digit": "7"})
    t = client.post(f"/api/calls/{cid}/message", json={"text": "What dose of paracetamol should I take?"}).json()["turn"]
    assert t["medicine"]["dose_blocked"] is True
    assert t["answer"]["source"] == "card_fallback"
    assert "500 mg" not in t["answer"]["text"]
