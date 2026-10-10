"""Real phone calls via Twilio Programmable Voice (keypad/feature phones).

Flow: incoming call -> language menu (DTMF) -> <Record> question -> STT ->
read-back + DTMF confirm -> answer audio -> post-answer DTMF menu -> optional
handoff slip -> hang up. All AI work happens server-side; the caller only
needs an ordinary phone line.

Note: an Indian inbound number needs KYC/regulatory approval from the
provider. Until then, test with a provider-approved trial number.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from . import config, handoff, languages, pipeline, prompts, sessions
from .sessions import State

router = APIRouter(prefix="/telephony/twilio", tags=["telephony"])

SAY_LANG = {"en-IN": "en-IN", "hi-IN": "hi-IN"}  # languages Twilio <Say> can voice directly


# ---------- security ----------

def compute_signature(auth_token: str, url: str, params: dict) -> str:
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


async def _verified_form(request: Request) -> dict:
    form = {k: str(v) for k, v in (await request.form()).items()}
    s = config.settings
    if not s.twilio_auth_token:
        raise HTTPException(503, "Telephony awaiting configuration")
    if s.twilio_validate_signature:
        url = s.public_base_url.rstrip("/") + request.url.path
        if request.url.query:
            url += "?" + request.url.query
        expected = compute_signature(s.twilio_auth_token, url, form)
        if not hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(403, "Invalid Twilio signature")
    return form


# ---------- TwiML helpers ----------

def _twiml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
                    media_type="application/xml")


async def _voice(session: sessions.Session, prompt: dict) -> str:
    """<Play> generated audio when we have a voice, else <Say> where Twilio can."""
    spoken = await pipeline.speak(session, prompt["text"], prompt["lang"])
    if spoken["audio_url"]:
        return f"<Play>{escape(config.settings.public_base_url.rstrip('/') + spoken['audio_url'])}</Play>"
    say_lang = SAY_LANG.get(prompt["lang"], "en-IN")
    text = prompt["text"] if prompt["lang"] in SAY_LANG else prompts.EN.get("partial_language")
    return f'<Say language="{say_lang}">{escape(text)}</Say>'


def _gather(action: str, inner: str, num_digits: int = 1, timeout: int = 6) -> str:
    return f'<Gather input="dtmf" numDigits="{num_digits}" timeout="{timeout}" action="{action}">{inner}</Gather>'


def _record(action: str) -> str:
    return (f'<Record action="{action}" maxLength="20" timeout="3" playBeep="true" '
            f'trim="trim-silence" finishOnKey="#"/>')


def _session(form: dict) -> sessions.Session:
    return sessions.get_or_create(form.get("CallSid", "unknown"), "twilio")


def _duplicate(request: Request, session: sessions.Session) -> bool:
    token = request.headers.get("I-Twilio-Idempotency-Token")
    if not token:
        return False
    if token in session.seen_events:
        return True
    session.seen_events.add(token)
    return False


async def _language_menu() -> str:
    menu = {"text": prompts.EN["welcome"] + " " + prompts.language_menu(), "lang": "en-IN"}
    return f'<Say language="en-IN">{escape(menu["text"])}</Say>'


async def _ask(session: sessions.Session) -> str:
    return await _voice(session, await prompts.get("ask_question", session.language)) + _record("/telephony/twilio/recording")


async def _after_answer(session: sessions.Session, turn: dict) -> str:
    body = ""
    if turn["voice"]["audio_url"]:
        body += f"<Play>{escape(config.settings.public_base_url.rstrip('/') + turn['voice']['audio_url'])}</Play>"
    else:
        body += await _voice(session, {"text": turn["answer"]["text"], "lang": turn["answer"]["lang"]})
    body += _gather("/telephony/twilio/menu", await _voice(session, turn["menu"]))
    return body


# ---------- webhooks ----------

@router.post("/voice")
async def incoming(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    if session.state == State.INCOMING_CALL:
        session.transition(State.LANGUAGE_SELECTION)
    return _twiml(_gather("/telephony/twilio/language", await _language_menu()) +
                  '<Say language="en-IN">We did not receive a choice. Goodbye.</Say><Hangup/>')


@router.post("/language")
async def choose_language(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    digit = form.get("Digits", "")
    if digit == languages.OTHER_LANGUAGES_DIGIT:
        sessions.unsupported_language_requests["other_ner"] = sessions.unsupported_language_requests.get("other_ner", 0) + 1
        return _twiml(f'<Say language="en-IN">{escape(prompts.EN["unsupported_language"])}</Say>' +
                      _gather("/telephony/twilio/language", await _language_menu()))
    lang = languages.by_keypad(digit)
    if not lang:
        return _twiml(_gather("/telephony/twilio/language", await _language_menu()))
    session.language = lang.code
    if session.state != State.LANGUAGE_SELECTION:
        session.transition(State.LANGUAGE_SELECTION)
    session.transition(State.READY_TO_LISTEN)
    confirm_prompt = await prompts.get("language_confirmed", lang.code) if lang.code in ("en-IN", "hi-IN", "as-IN") \
        else {"text": f"{lang.name}.", "lang": "en-IN"}
    return _twiml(await _voice(session, confirm_prompt) + await _ask(session))


@router.post("/recording")
async def recording(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    if _duplicate(request, session):
        return _twiml("<Pause length=\"1\"/>")
    url = form.get("RecordingUrl")
    if not url:
        return _twiml(await _ask(session))
    s = config.settings
    async with httpx.AsyncClient(timeout=s.http_timeout) as c:
        resp = await c.get(url + ".wav", auth=(s.twilio_account_sid, s.twilio_auth_token))
    if resp.status_code >= 400:
        return _twiml(await _voice(session, await prompts.get("not_heard", session.language)) + await _ask(session))
    heard = await pipeline.hear(session, resp.content, "call.wav", "audio/wav")
    if not heard["ok"]:
        if session.retries >= 3:
            return _twiml(await _voice(session, await prompts.get("goodbye", session.language)) + "<Hangup/>")
        return _twiml(await _voice(session, heard["prompt"]) + _record("/telephony/twilio/recording"))
    return _twiml(_gather("/telephony/twilio/confirm", await _voice(session, heard["prompt"])))


@router.post("/confirm")
async def confirm(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    result = await pipeline.confirm(session, form.get("Digits") == "1")
    if not result.get("ok"):
        return _twiml(await _ask(session))
    if not result["confirmed"]:
        return _twiml(await _voice(session, result["prompt"]) + _record("/telephony/twilio/recording"))
    return _twiml(await _after_answer(session, result["turn"]))


@router.post("/menu")
async def menu(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    digit = form.get("Digits", "")
    if digit == "1":
        session.transition(State.READY_TO_LISTEN)
        return _twiml(await _ask(session))
    if digit == "2" and session.last_answer:
        return _twiml(await _after_answer(session, session.last_answer))
    if digit == "5":
        result = await pipeline.simpler(session)
        if result.get("ok"):
            return _twiml(await _after_answer(session, result["turn"]))
    if digit == "3":
        session.transition(State.LANGUAGE_SELECTION)
        return _twiml(_gather("/telephony/twilio/language", await _language_menu()))
    if digit == "9":
        session.transition(State.CONSENT)
        return _twiml(_gather("/telephony/twilio/consent", await _voice(session, await prompts.get("consent_slip", session.language))))
    last = session.last_answer
    return _twiml(_gather("/telephony/twilio/menu", await _voice(session, last["menu"] if last else await prompts.get("after_answer", session.language))))


@router.post("/consent")
async def consent(request: Request):
    form = await _verified_form(request)
    session = _session(form)
    body = ""
    if form.get("Digits") == "1" and session.turns:
        session.consent_slip = True
        slip = handoff.build(session)
        session.slip = slip
        spaced = " ".join(slip["code"])
        body += f'<Say language="en-IN">Your slip code is {spaced}. I repeat, {spaced}. Show this code to your ASHA worker.</Say>'
    body += await _voice(session, await prompts.get("goodbye", session.language))
    sessions.end(session)
    return _twiml(body + "<Hangup/>")


@router.post("/status")
async def status(request: Request):
    form = await _verified_form(request)
    if form.get("CallStatus") in ("completed", "failed", "busy", "no-answer", "canceled"):
        session = sessions.get(form.get("CallSid", ""))
        if session:
            sessions.end(session)
    return Response(status_code=204)
