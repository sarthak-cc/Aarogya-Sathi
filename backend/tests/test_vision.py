"""Camera prototype: POST /api/vision/analyze with a MOCKED Groq vision API (no network, no real key).
A real-provider check is in scripts/verify_vision_live.py."""
import io
import json

import httpx
import pytest
from PIL import Image

from tests.conftest import configure


def jpeg(size=(64, 48), color=(200, 120, 110), exif_gps=False) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {2: (26.0, 8.0, 0.0)}  # GPSInfo: latitude
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


GOOD = {"observation": "The photo shows a small red patch on the skin of a hand.",
        "possible_explanations": ["This can happen with an insect bite.", "This can happen with mild skin irritation."],
        "follow_up_questions": ["How long has it been there?"],
        "recommended_next_steps": ["Keep it clean and dry.", "Take 2 tablets of cetirizine twice a day.", "Do not scratch it."],
        "urgency": "see_health_worker", "image_quality": "ok"}


def reply(obj):
    content = obj if isinstance(obj, str) else json.dumps(obj)
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


@pytest.fixture
def groq(monkeypatch, http):
    configure(monkeypatch, GROQ_API_KEY="test-groq", SARVAM_API_KEY="test-sarvam")
    from tests.conftest import fake_translate, fake_tts, fake_clone
    http.on("/translate", fake_translate).on("/text-to-speech", fake_tts).on("/voices/clone", fake_clone)
    http.on("/chat/completions", reply(GOOD))
    return http


def post(client, data=None, ctype="image/jpeg", lang="en-IN", note=""):
    return client.post("/api/vision/analyze", files={"image": ("photo.jpg", jpeg() if data is None else data, ctype)},
                       data={"language": lang, "note": note})


def test_valid_photo_english_schema_and_request(client, groq):
    r = post(client)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["error"] is None
    v = body["vision"]
    assert set(v) == {"observation", "possible_explanations", "follow_up_questions", "recommended_next_steps",
                      "urgency", "image_quality", "disclaimer"}
    assert v["observation"].startswith("The photo shows") and "not a diagnosis" in v["disclaimer"]
    assert body["answer"]["source"] == "vision" and body["answer"]["model"] == "qwen/qwen3.8-27b"
    assert body["voice"]["audio_url"].startswith("/api/audio/")
    sent = groq.bodies("/chat/completions")[0]
    assert sent["model"] == "qwen/qwen3.8-27b" and sent["reasoning_effort"] == "none"
    parts = sent["messages"][1]["content"]
    assert parts[1]["type"] == "image_url" and parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    auth = next(c for c in groq.calls if c.url.path.endswith("/chat/completions")).headers["authorization"]
    assert auth == "Bearer test-groq"


def test_dose_in_model_output_is_removed(client, groq):
    v = post(client).json()["vision"]
    assert not any("2 tablets" in s for s in v["recommended_next_steps"])
    assert any("pharmacist" in s for s in v["recommended_next_steps"])


def test_hindi_is_translated_and_spoken_in_hindi(client, groq):
    body = post(client, lang="hi-IN").json()
    assert body["answer"]["lang"] == "hi-IN"
    assert body["vision"]["observation"].startswith("hi-IN[")
    assert "निदान" in body["vision"]["disclaimer"]
    assert groq.bodies("/text-to-speech")[0]["target_language_code"] == "hi-IN"


def test_assamese_uses_cloned_voice_when_configured(client, groq, monkeypatch):
    configure(monkeypatch, SARVAM_VOICE_ID="voice-123")
    body = post(client, lang="as-IN").json()
    assert body["answer"]["lang"] == "as-IN" and body["voice"]["provider"] == "sarvam voice clone"
    assert "ৰোগ নিৰ্ণয়" in body["vision"]["disclaimer"]


def test_translation_failure_keeps_english_and_says_so(client, groq):
    groq.on("/translate", httpx.Response(503))
    body = post(client, lang="hi-IN").json()
    assert body["ok"] and body["answer"]["lang"] == "en-IN" and "translation failed" in body["answer"]["language_note"]


def test_metadata_is_stripped_and_large_images_resized(client, groq):
    big = jpeg(size=(4000, 3000), exif_gps=True)
    post(client, data=big)
    url = groq.bodies("/chat/completions")[0]["messages"][1]["content"][1]["image_url"]["url"]
    import base64
    sent = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert max(sent.size) <= 1280 and not sent.getexif()


@pytest.mark.parametrize("data,ctype,reason", [
    (b"", "image/jpeg", "empty"),
    (b"not an image at all", "image/jpeg", "could not be read"),
    (b"GIF89a....", "image/gif", "JPEG, PNG or WebP"),
    (b"%PDF-1.4", "application/pdf", "JPEG, PNG or WebP"),
])
def test_invalid_uploads_never_reach_the_model(client, groq, data, ctype, reason):
    body = post(client, data=data, ctype=ctype).json()
    assert not body["ok"] and body["error"]["kind"] == "invalid_image" and reason in body["error"]["message"]
    assert not groq.bodies("/chat/completions")


def test_oversized_upload_rejected(client, groq, monkeypatch):
    configure(monkeypatch, VISION_MAX_UPLOAD_MB="0.01")
    assert post(client, data=jpeg(size=(400, 400)) + b"\0" * 20000).status_code == 413


def test_missing_key_is_honest(client, monkeypatch, http):
    configure(monkeypatch, SARVAM_API_KEY="x")
    body = post(client).json()
    assert not body["ok"] and body["error"]["kind"] == "not_configured" and body["vision"] is None


@pytest.mark.parametrize("resp,kind", [
    (httpx.Response(429, headers={"retry-after": "20"}), "rate_limited"),
    (httpx.Response(401), "auth"),
    (httpx.Response(503), "unavailable"),
    (httpx.Response(404), "model_unavailable"),
])
def test_provider_errors(client, groq, resp, kind):
    groq.on("/chat/completions", resp)
    body = post(client).json()
    assert not body["ok"] and body["error"]["kind"] == kind and body["vision"] is None


def test_timeout(client, groq):
    def boom(_):
        raise httpx.ReadTimeout("slow")
    groq.on("/chat/completions", boom)
    assert post(client).json()["error"]["kind"] == "timeout"


@pytest.mark.parametrize("content", ["Sorry, I cannot help.", '{"observation": ""}', "{not json}", ""])
def test_malformed_model_reply_is_an_error_not_a_guess(client, groq, content):
    groq.on("/chat/completions", reply(content))
    body = post(client).json()
    assert not body["ok"] and body["error"]["kind"] == "bad_response"


def test_think_tags_and_unknown_urgency(client, groq):
    groq.on("/chat/completions", reply("<think>hmm</think>" + json.dumps({**GOOD, "urgency": "maybe"})))
    assert post(client).json()["vision"]["urgency"] == "see_health_worker"


def test_reasoning_param_rejected_retries_same_model(client, groq):
    replies = iter([httpx.Response(400), reply(GOOD)])
    groq.on("/chat/completions", lambda r: next(replies))
    assert post(client).json()["ok"]
    a, b = groq.bodies("/chat/completions")
    assert a["model"] == b["model"] == "qwen/qwen3.8-27b" and "reasoning_effort" not in b


def test_model_emergency_raises_caution(client, groq):
    groq.on("/chat/completions", reply({**GOOD, "urgency": "emergency"}))
    body = post(client).json()
    assert body["triage"]["level"] == "emergency" and body["triage"]["source"] == "vision_ai"
    assert body["offer_facilities"] and "112" in body["answer"]["text"]


def test_emergency_words_in_note_skip_the_photo_entirely(client, groq):
    body = post(client, note="snake bite on his leg in the paddy field").json()
    assert body["triage"]["source"] == "rules" and body["answer"]["source"] == "emergency_script"
    assert "112" in body["answer"]["text"] and not groq.bodies("/chat/completions")


def test_model_cannot_lower_rule_based_urgency(client, groq):
    groq.on("/chat/completions", reply({**GOOD, "urgency": "routine"}))
    body = post(client, note="I have high fever and this rash").json()
    assert body["triage"]["level"] == "urgent" and body["triage"]["source"] == "rules"


def test_unknown_language(client, groq):
    assert post(client, lang="xx-YY").status_code == 422


def test_existing_endpoints_unchanged(client):
    assert client.get("/api/health").json()["providers"]["vision"]["configured"] is False
    assert client.get("/api/languages").status_code == 200
