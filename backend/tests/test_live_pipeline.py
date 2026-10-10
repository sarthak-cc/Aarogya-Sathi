"""Live-mode pipeline with providers mocked at the HTTP layer (no network)."""
import base64
import json

import httpx
import pytest

from app import config, knowledge
from app.providers import llm


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-sarvam")
    monkeypatch.setenv("LLM_API_KEY", "test-llm")
    monkeypatch.setenv("PARLER_TTS_URL", "https://parler.example")
    config.reload_settings()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/translate"):
            body = json.loads(request.content)
            if body["target_language_code"] == "en-IN":
                return httpx.Response(200, json={"translated_text": "My child has had a cough for two days."})
            return httpx.Response(200, json={"translated_text": "অসমীয়া উত্তৰ"})
        if request.url.path.endswith("/chat/completions"):
            sys_prompt = json.loads(request.content)["messages"][0]["content"]
            assert "CARD child_cough" in sys_prompt  # answer is grounded on the retrieved card
            return httpx.Response(200, json={"choices": [{"message": {"content": "**Keep** the child warm.\n- Keep feeding."}}]})
        if request.url.path.endswith("/tts"):
            return httpx.Response(200, content=b"RIFFfakewav", headers={"content-type": "audio/wav"})
        if request.url.path.endswith("/speech-to-text"):
            return httpx.Response(200, json={"transcript": "মোৰ কেঁচুৱাটোৰ কাহ", "language_code": "as-IN"})
        if request.url.path.endswith("/text-to-speech"):
            return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF").decode()]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr("app.providers.client", lambda: real(transport=transport))
    monkeypatch.setattr("app.providers.stt.client", lambda: real(transport=transport))
    monkeypatch.setattr("app.providers.translate.client", lambda: real(transport=transport))
    monkeypatch.setattr("app.providers.llm.client", lambda: real(transport=transport))
    monkeypatch.setattr("app.providers.tts.client", lambda: real(transport=transport))
    from app.providers import translate
    translate._cache.clear()
    return calls


def test_full_live_turn(client, call, live):
    t = client.post(f"/api/calls/{call}/message", json={"text": "মোৰ কেঁচুৱাটোৰ দুদিনৰ পৰা কাহ হৈছে"}).json()["turn"]
    assert t["english_source"] == "sarvam"
    assert t["answer"]["source"] == "llm"
    assert t["answer"]["english"] == "Keep the child warm. Keep feeding."  # markdown stripped for speech
    assert t["answer"]["text"] == "অসমীয়া উত্তৰ" and t["answer"]["lang"] == "as-IN"
    assert t["voice"]["voice"] == "parler" and t["voice"]["audio_url"].startswith("/api/audio/")
    assert {"translate_in", "triage", "retrieve", "llm", "translate_out", "tts"} <= set(t["timings_ms"])
    assert client.get(t["voice"]["audio_url"]).content == b"RIFFfakewav"


def test_speech_upload_goes_through_readback(client, call, live):
    r = client.post(f"/api/calls/{call}/transcribe", files={"audio": ("q.webm", b"audio", "audio/webm")}).json()
    assert r["ok"] and r["transcript"] == "মোৰ কেঁচুৱাটোৰ কাহ"
    assert "মই শুনিলোঁ" in r["prompt"]["text"]
    turn = client.post(f"/api/calls/{call}/confirm", json={"correct": True}).json()["turn"]
    assert turn["stt_provider"] == "sarvam" and "stt" in turn["timings_ms"]


def test_llm_failure_falls_back_to_vetted_card(client, call, live, monkeypatch):
    async def boom(*a, **k):
        from app.providers import ProviderError
        raise ProviderError("timeout")
    monkeypatch.setattr("app.providers.llm.answer", boom)
    t = client.post(f"/api/calls/{call}/message", json={"text": "কাহ"}).json()["turn"]
    assert t["answer"]["source"] == "card_fallback"


def test_system_prompt_rules():
    cards = knowledge.retrieve("my child has a cough")
    msgs = llm.build_messages("my child has a cough", cards, level="simple", urgent=True)
    sys = msgs[0]["content"]
    for rule in ["Never diagnose", "doses", "Never claim you contacted", "ONLY the facts", "URGENT"]:
        assert rule in sys
    assert "10-year-old" in sys
