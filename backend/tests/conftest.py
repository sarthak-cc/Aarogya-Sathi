"""Shared fixtures. All provider tests here use MOCKED HTTP (no network, no real keys).
Real-provider checks live in scripts/verify_live.py and need real keys."""
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, facilities, main, sessions
from app.providers import translate

KEYS = ["SARVAM_API_KEY", "LLM_API_KEY", "GROQ_API_KEY", "PARLER_TTS_URL", "MMS_TTS_LANGS", "SARVAM_VOICE_ID"]


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch, tmp_path):
    for var in KEYS:
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("OSM_ENABLED", "false")
    monkeypatch.setenv("DB_PATH", ":memory:")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    test_data = tmp_path / "data"
    test_data.mkdir()
    (test_data / "verified_facilities.csv").write_text(
        "# empty\nname,kind,address,lat,lon,phone,emergency,services,verified_on\n", encoding="utf-8"
    )
    (test_data / "places.csv").write_text(
        (facilities.DATA / "places.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(facilities, "DATA", test_data)
    config.reload_settings()
    facilities.reset()
    sessions.clear()
    translate._cache.clear()
    main._hits.clear()
    yield
    facilities.reset()
    config.reload_settings()


@pytest.fixture
def client():
    return TestClient(main.app)


def configure(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    config.reload_settings()


class MockHTTP:
    """Routes outgoing provider requests to handlers by URL path suffix and records them."""

    def __init__(self):
        self.routes: dict[str, object] = {}
        self.calls: list[httpx.Request] = []

    def on(self, suffix, handler):
        self.routes[suffix] = handler
        return self

    def paths(self):
        return [r.url.path for r in self.calls]

    def bodies(self, suffix):
        return [json.loads(r.content) for r in self.calls if r.url.path.endswith(suffix)]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        for suffix, handler in self.routes.items():
            if request.url.path.endswith(suffix):
                return handler(request) if callable(handler) else handler
        return httpx.Response(404)


@pytest.fixture
def http(monkeypatch):
    mock = MockHTTP()
    real = httpx.AsyncClient
    monkeypatch.setattr("app.providers.client", lambda timeout=None: real(transport=httpx.MockTransport(mock)))
    return mock


def llm_reply(text):
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": text}}]})


def fake_translate(request):
    body = json.loads(request.content)
    if body["target_language_code"] == "en-IN":
        return httpx.Response(200, json={"translated_text": f"EN[{body['input']}]"})
    return httpx.Response(200, json={"translated_text": f"{body['target_language_code']}[{body['input']}]"})


def fake_tts(_request):
    return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFFfake").decode()]})


def fake_clone(_request):
    return httpx.Response(200, json={"audio": base64.b64encode(b"RIFFfakeclone").decode(), "audio_duration": 2.5})


@pytest.fixture
def live(monkeypatch, http):
    """Groq + Sarvam 'configured' with mocked responses."""
    configure(monkeypatch, LLM_API_KEY="test-groq", SARVAM_API_KEY="test-sarvam")
    http.on("/translate", fake_translate).on("/text-to-speech", fake_tts).on("/voices/clone", fake_clone)
    return http
