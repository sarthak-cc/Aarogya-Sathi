"""Twilio webhook security and IVR flow (no real calls)."""
import pytest

from app import config, sessions
from app.telephony import compute_signature

BASE = "https://example.ngrok.app"


@pytest.fixture
def twilio(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE)
    config.reload_settings()


def signed_post(client, path, data):
    sig = compute_signature("secret-token", BASE + path, data)
    return client.post(path, data=data, headers={"X-Twilio-Signature": sig})


def test_awaiting_configuration_without_token(client):
    assert client.post("/telephony/twilio/voice", data={"CallSid": "CA1"}).status_code == 503


def test_rejects_bad_signature(client, twilio):
    r = client.post("/telephony/twilio/voice", data={"CallSid": "CA1"}, headers={"X-Twilio-Signature": "forged"})
    assert r.status_code == 403


def test_incoming_call_language_menu(client, twilio):
    r = signed_post(client, "/telephony/twilio/voice", {"CallSid": "CA1", "From": "+910000000000"})
    assert r.status_code == 200
    assert "<Gather" in r.text and "press 1" in r.text.lower()
    r = signed_post(client, "/telephony/twilio/language", {"CallSid": "CA1", "Digits": "6"})
    assert "<Record" in r.text
    assert sessions.get("CA1").language == "hi-IN"


def test_other_language_digit_is_honest(client, twilio):
    signed_post(client, "/telephony/twilio/voice", {"CallSid": "CA2"})
    r = signed_post(client, "/telephony/twilio/language", {"CallSid": "CA2", "Digits": "8"})
    assert "cannot yet talk in your language" in r.text


def test_duplicate_webhook_processed_once(client, twilio):
    signed_post(client, "/telephony/twilio/voice", {"CallSid": "CA3"})
    data = {"CallSid": "CA3", "RecordingUrl": "https://api.twilio.com/rec/RE1"}
    sig = compute_signature("secret-token", BASE + "/telephony/twilio/recording", data)
    headers = {"X-Twilio-Signature": sig, "I-Twilio-Idempotency-Token": "evt-1"}
    s = sessions.get("CA3")
    s.seen_events.add("evt-1")  # pretend the first delivery was already handled
    r = client.post("/telephony/twilio/recording", data=data, headers=headers)
    assert "<Pause" in r.text


def test_status_callback_clears_session(client, twilio):
    signed_post(client, "/telephony/twilio/voice", {"CallSid": "CA4"})
    sessions.get("CA4").turns.append({"transcript": "x"})
    signed_post(client, "/telephony/twilio/status", {"CallSid": "CA4", "CallStatus": "completed"})
    assert sessions.get("CA4").turns == []
