import pytest
from fastapi.testclient import TestClient

from app import config, main, sessions


@pytest.fixture(autouse=True)
def demo_settings(monkeypatch):
    """Every test starts in demo mode (no keys) unless it opts into live mocks."""
    for var in ["SARVAM_API_KEY", "LLM_API_KEY", "GROQ_API_KEY", "PARLER_TTS_URL"]:
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("OSM_ENABLED", "false")  # tests never touch the network
    config.reload_settings()
    sessions._sessions.clear()
    main._hits.clear()
    yield
    config.reload_settings()


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def call(client):
    """A started call with Assamese selected."""
    cid = client.post("/api/calls/start").json()["call"]["id"]
    client.post(f"/api/calls/{cid}/language", json={"digit": "1"})
    return cid
