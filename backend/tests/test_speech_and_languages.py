"""Speech in/out paths and honest language capabilities (MOCKED HTTP)."""
import httpx

from tests.conftest import configure, llm_reply

WAV = b"RIFF" + b"\x00" * 64


def test_speech_question_transcribed_answered_and_spoken(client, live):
    live.on("/speech-to-text", httpx.Response(200, json={"transcript": "मुझे खाँसी है", "language_code": "hi-IN"}))
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nDrink warm water."))
    cid = client.post("/api/conversations", json={"language": "hi-IN"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/speech", files={"audio": ("q.wav", WAV, "audio/wav")}).json()
    assert r["heard"]["text"] == "मुझे खाँसी है" and r["heard"]["provider"].startswith("sarvam")
    assert r["turn"]["question"]["text"] == "मुझे खाँसी है"
    assert "speech_to_text" in r["turn"]["timings_ms"]
    stt = next(c for c in live.calls if c.url.path.endswith("/speech-to-text"))
    assert b'name="model"' in stt.content and b"saaras:v3" in stt.content and b"transcribe" in stt.content
    tts = live.bodies("/text-to-speech")[0]
    assert tts["target_language_code"] == "hi-IN" and tts["model"] == "bulbul:v3"


def test_no_speech_found(client, live):
    live.on("/speech-to-text", httpx.Response(200, json={"transcript": ""}))
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/speech", files={"audio": ("q.wav", WAV, "audio/wav")}).json()
    assert r["turn"] is None and r["error"]["kind"] == "bad_response" and r["hint"]["text"]


def test_speech_without_stt_key_is_explained(client, monkeypatch, http):
    configure(monkeypatch, LLM_API_KEY="x", LLM_BASE_URL="https://example.org/v1")  # LLM only, not Groq
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/speech", files={"audio": ("q.wav", WAV, "audio/wav")}).json()
    assert r["error"]["kind"] == "not_configured"


def test_audio_validation(client, live):
    cid = client.post("/api/conversations", json={"language": "en-IN"}).json()["id"]
    assert client.post(f"/api/conversations/{cid}/speech", files={"audio": ("q.wav", b"", "audio/wav")}).status_code == 422
    big = b"0" * (4 * 1024 * 1024 + 1)
    assert client.post(f"/api/conversations/{cid}/speech", files={"audio": ("q.wav", big, "audio/wav")}).status_code == 413
    assert client.post("/api/conversations/nope/ask", json={"text": "hi"}).status_code == 404
    assert client.post(f"/api/conversations/{cid}/ask", json={"text": ""}).status_code == 422


def test_assamese_answer_is_text_with_honest_voice_note(client, live):
    live.on("/chat/completions", llm_reply("TRIAGE: ROUTINE\nRest."))
    cid = client.post("/api/conversations", json={"language": "as-IN"}).json()["id"]
    t = client.post(f"/api/conversations/{cid}/ask", json={"text": "মোৰ মূৰ বিষাইছে"}).json()
    assert t["answer"]["lang"] == "as-IN"
    assert t["voice"]["audio_url"] is None and "No voice for Assamese" in t["voice"]["note"]
    assert not live.bodies("/text-to-speech")  # never sent to a TTS that has no Assamese voice


def test_language_matrix_without_keys_offers_nothing(client):
    langs = {l["code"]: l for l in client.get("/api/languages").json()["languages"]}
    assert not any(l["selectable"] for l in langs.values())
    assert langs["kha-IN"]["status"] == "unavailable" and langs["hi-IN"]["status"] == "not_configured"
    assert client.post("/api/conversations", json={"language": "kha-IN"}).status_code == 409


def test_language_matrix_with_keys(client, live):
    langs = {l["code"]: l for l in client.get("/api/languages").json()["languages"]}
    assert langs["hi-IN"]["status"] == "voice" and langs["hi-IN"]["speech_output"] == ["sarvam"]
    assert langs["as-IN"]["status"] == "voice_in_text_out"
    assert langs["mni-IN"]["status"] == "voice_in_text_out" and "Meitei" in langs["mni-IN"]["notes"]
    for code in ("kha-IN", "grt-IN", "lus-IN", "trp-IN", "nag-IN"):
        assert langs[code]["selectable"] is False
    assert langs["hi-IN"]["verified"]["passed"] in (True, False)  # comes from scripts/verify_live.py only


def test_health_reports_configuration_without_secrets(client, live):
    body = client.get("/api/health").text
    assert "test-groq" not in body and "test-sarvam" not in body
    p = client.get("/api/health").json()["providers"]
    assert p["llm"]["configured"] and p["llm"]["model"] == "openai/gpt-oss-120b"
