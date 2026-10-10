"""Aarogya Saathi API. Run:  uvicorn app.main:app --reload  (from backend/)"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audio_store, config, demo, handoff, knowledge, languages, facilities, pipeline, prompts, sessions
from .sessions import InvalidTransition, State

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aarogya")  # logs carry session ids and states only, never health text

app = FastAPI(
    title="Aarogya Saathi API",
    version="1.0.0",
    description="Voice-first multilingual health-information companion for North East India. "
                "General information only; not a diagnosis; never replaces a health professional.",
)

MAX_AUDIO_BYTES = 5 * 1024 * 1024
RATE_LIMIT = 90  # requests per minute per client IP
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        now, q = time.time(), _hits[ip]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(now)
    return await call_next(request)


@app.exception_handler(InvalidTransition)
async def _invalid_transition(_: Request, exc: InvalidTransition):
    return JSONResponse({"detail": f"Action not allowed right now ({exc})."}, status_code=409)


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.error("unhandled error: %s", type(exc).__name__)  # no message: it may contain user text
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


# ---------- models ----------

class StartCall(BaseModel):
    channel: Literal["simulator"] = "simulator"


class SetLanguage(BaseModel):
    code: Optional[str] = Field(None, examples=["as-IN"])
    digit: Optional[str] = Field(None, pattern=r"^[0-9]$")


class Message(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    skip_readback: bool = True


class Confirm(BaseModel):
    correct: bool


class Speak(BaseModel):
    text: str = Field(..., min_length=1, max_length=2500)
    lang: str


class EndCall(BaseModel):
    consent_slip: bool = False


class Location(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    accuracy_m: Optional[float] = Field(None, ge=0)
    text: Optional[str] = Field(None, max_length=200, examples=["Jalukbari, near Assam Engineering College"])


class Literacy(BaseModel):
    level: Literal["standard", "simple"]


def _session(call_id: str) -> sessions.Session:
    s = sessions.get(call_id)
    if not s or s.state == State.CALL_ENDED:
        raise HTTPException(404, "Call not found or already ended")
    return s


def _require_language(s: sessions.Session) -> None:
    if not s.language:
        raise HTTPException(409, "Choose a language first")


# ---------- info ----------

@app.get("/api/health", tags=["info"])
async def health():
    return {"status": "ok", "providers": config.settings.mode_summary()}


@app.get("/api/languages", tags=["info"])
async def get_languages():
    return {"languages": languages.all_capabilities(), "menu": prompts.language_menu(),
            "other_languages_digit": languages.OTHER_LANGUAGES_DIGIT}


@app.get("/api/channels", tags=["info"])
async def channels():
    """Be explicit about what is live and what is planned."""
    return {"channels": [
        {"id": "web_voice", "name": "Web voice (browser microphone over HTTPS)", "status": "live",
         "detail": "Works on any phone or laptop browser. No app and no phone number needed."},
        {"id": "phone_line", "name": "Keypad phone line (IVR)", "status": "planned",
         "detail": "Needs a paid telephony provider (for example Twilio or Exotel) and an Indian number with KYC. "
                   "The call flow is channel-agnostic, so a phone adapter plugs into the same pipeline."},
        {"id": "hospital_alert", "name": "Notify a hospital or ambulance", "status": "not built",
         "detail": "Needs an authorised integration with confirmation. Today the caller gets contact details only."},
    ]}


@app.get("/api/facilities", tags=["navigation"])
async def find_facilities(lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-180, le=180),
                          q: Optional[str] = Query(None, max_length=200)):
    """Nearest facilities by coordinates, or by a place name / PIN code."""
    place = None
    if lat is None or lon is None:
        if not q:
            raise HTTPException(422, "Give lat and lon, or a place name or PIN code in q")
        place = await facilities.resolve(q)
        if not place:
            raise HTTPException(404, "Place not found. Try a nearby town or a PIN code.")
        lat, lon = place["lat"], place["lon"]
    return {"place": place, **await facilities.find(lat, lon)}


@app.get("/api/scenarios", tags=["info"])
async def scenarios():
    return {"scenarios": [{"id": s["id"], "title": s["title"], "questions": s["q"]} for s in demo.SCENARIOS]}


@app.get("/api/knowledge", tags=["info"])
async def knowledge_cards():
    return {"cards": [{"id": c.id, "title": c.title, "facts": c.facts, "seek_care": c.seek_care, "source": c.source}
                      for c in knowledge.CARDS]}


@app.get("/api/stats/unsupported-languages", tags=["info"])
async def unsupported_stats():
    return {"requests": sessions.unsupported_language_requests}


# ---------- call flow ----------

@app.post("/api/calls/start", tags=["call"])
async def start_call(_: StartCall = StartCall()):
    s = sessions.create("simulator")
    s.transition(State.LANGUAGE_SELECTION)
    log.info("call started %s", s.id)
    return {"call": s.public(), "welcome": prompts.EN["welcome"], "menu": prompts.language_menu(),
            "disclaimer": prompts.EN["disclaimer"], "demo_mode": not config.settings.has_llm}


@app.post("/api/calls/{call_id}/language", tags=["call"])
async def set_language(call_id: str, body: SetLanguage):
    s = _session(call_id)
    if body.digit == languages.OTHER_LANGUAGES_DIGIT or (body.code and languages.get(body.code) and not languages.get(body.code).keypad):
        key = body.code or "other_ner"
        sessions.unsupported_language_requests[key] = sessions.unsupported_language_requests.get(key, 0) + 1
        return {"supported": False, "prompt": {"text": prompts.EN["unsupported_language"], "lang": "en-IN"},
                "alternatives": [l["code"] for l in languages.all_capabilities() if l["keypad"]]}
    lang = languages.by_keypad(body.digit) if body.digit else languages.get(body.code or "")
    if not lang or not lang.keypad:
        raise HTTPException(422, "Unknown language")
    s.language = lang.code
    if s.state != State.LANGUAGE_SELECTION:
        s.transition(State.LANGUAGE_SELECTION)
    s.transition(State.READY_TO_LISTEN)
    confirmed = await prompts.get("language_confirmed", lang.code) if lang.code in prompts.HAND or lang.code == "en-IN" \
        else {"text": f"{lang.native_name} ({lang.name})", "lang": lang.code, "source": "name"}
    ask = await prompts.get("ask_question", lang.code)
    disclaimer = await prompts.get("disclaimer", lang.code)
    voices = [await pipeline.speak(s, p["text"], p["lang"]) for p in (confirmed, ask)]
    return {"supported": True, "call": s.public(), "capabilities": languages.configured_capabilities(lang),
            "prompts": {"confirmed": confirmed, "ask": ask, "disclaimer": disclaimer}, "voices": voices}


@app.post("/api/calls/{call_id}/transcribe", tags=["call"])
async def transcribe(call_id: str, audio: UploadFile = File(...),
                     purpose: Literal["question", "location"] = Form("question")):
    s = _session(call_id)
    _require_language(s)
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too long. Please keep questions under 30 seconds.")
    if purpose == "location":
        return await pipeline.transcribe_only(s, data, audio.filename or "place.webm", audio.content_type or "audio/webm")
    if s.state in (State.ANSWERED, State.EMERGENCY):
        s.transition(State.READY_TO_LISTEN)
    result = await pipeline.hear(s, data, audio.filename or "speech.webm", audio.content_type or "audio/webm")
    if result.get("ok"):
        result["voice"] = await pipeline.speak(s, result["prompt"]["text"], result["prompt"]["lang"])
    return result


@app.post("/api/calls/{call_id}/confirm", tags=["call"])
async def confirm(call_id: str, body: Confirm):
    s = _session(call_id)
    result = await pipeline.confirm(s, body.correct)
    if result.get("ok") and not result.get("confirmed"):
        result["voice"] = await pipeline.speak(s, result["prompt"]["text"], result["prompt"]["lang"])
    return result


@app.post("/api/calls/{call_id}/message", tags=["call"])
async def message(call_id: str, body: Message):
    """Typed question (browser fallback). Typed text needs no read-back."""
    s = _session(call_id)
    _require_language(s)
    if s.state in (State.ANSWERED, State.EMERGENCY, State.CONFIRMING):
        s.pending = None
        s.transition(State.READY_TO_LISTEN)
    if not body.skip_readback:
        s.pending = {"transcript": body.text.strip(), "stt_provider": "typed", "timings": {}}
        s.transition(State.CONFIRMING)
        prompt = await prompts.get("readback", s.language, text=body.text.strip())
        return {"ok": True, "transcript": body.text.strip(), "prompt": prompt}
    return {"ok": True, "turn": await pipeline.answer(s, body.text.strip(), stt_provider="typed")}


@app.post("/api/calls/{call_id}/location", tags=["navigation"])
async def set_location(call_id: str, body: Location):
    """Browser GPS, or what the caller said (village, town, PIN code, landmark). Kept only for this call."""
    s = _session(call_id)
    lang = s.language or "en-IN"
    if body.lat is not None and body.lon is not None:
        place = {"name": "Your phone's location", "state": None, "lat": body.lat, "lon": body.lon,
                 "approximate": (body.accuracy_m or 0) > 500, "method": "device location",
                 "accuracy_m": body.accuracy_m}
    elif body.text and body.text.strip():
        place = await facilities.resolve(body.text)
        if not place and lang != "en-IN":
            english = await pipeline.to_english_or_none(body.text, lang)
            place = await facilities.resolve(english) if english else None
    else:
        raise HTTPException(422, "Share a location or say a place name")
    if not place:
        prompt = await prompts.get("location_not_found", lang)
        return {"ok": False, "prompt": prompt, "voice": await pipeline.speak(s, prompt["text"], prompt["lang"]),
                "emergency_numbers": facilities.EMERGENCY_NUMBERS}
    s.location = place
    result = await facilities.find(place["lat"], place["lon"])
    nearest = result["nearest"]
    prompt = await prompts.get("facility_found", lang, name=nearest["name"], km=f"{nearest['distance_km']:g}") \
        if nearest else await prompts.get("location_not_found", lang)
    return {"ok": True, "place": place, **result, "prompt": prompt,
            "voice": await pipeline.speak(s, prompt["text"], prompt["lang"])}


@app.post("/api/calls/{call_id}/simpler", tags=["call"])
async def simpler(call_id: str):
    s = _session(call_id)
    result = await pipeline.simpler(s)
    if not result.get("ok"):
        raise HTTPException(409, "Ask a question first")
    return result


@app.post("/api/calls/{call_id}/literacy", tags=["call"])
async def literacy(call_id: str, body: Literacy):
    s = _session(call_id)
    s.literacy = body.level
    return {"call": s.public()}


@app.post("/api/calls/{call_id}/repeat", tags=["call"])
async def repeat(call_id: str):
    s = _session(call_id)
    last = s.last_answer
    if not last:
        raise HTTPException(409, "Nothing to repeat yet")
    return {"turn": last}


@app.post("/api/calls/{call_id}/speak", tags=["call"])
async def speak(call_id: str, body: Speak):
    s = _session(call_id)
    if not languages.get(body.lang):
        raise HTTPException(422, "Unknown language")
    return await pipeline.speak(s, body.text, body.lang)


@app.post("/api/calls/{call_id}/end", tags=["call"])
async def end_call(call_id: str, body: EndCall = EndCall()):
    s = _session(call_id)
    slip = None
    if body.consent_slip and s.turns:
        s.consent_slip = True
        slip = handoff.build(s)
        s.slip = slip
    goodbye = await prompts.get("goodbye", s.language or "en-IN")
    cleared = sessions.end(s)
    log.info("call ended %s slip=%s", s.id, bool(slip))
    return {"goodbye": goodbye, "slip": slip, **cleared}


@app.delete("/api/calls/{call_id}", tags=["call"])
async def delete_call(call_id: str):
    return {"deleted": sessions.delete(call_id)}


# ---------- slips & audio ----------

@app.get("/api/slips/{code}", tags=["handoff"])
async def get_slip(code: str):
    slip = handoff.lookup(code)
    if not slip:
        raise HTTPException(404, "Slip not found or expired (slips last 24 hours)")
    return slip


@app.delete("/api/slips/{code}", tags=["handoff"])
async def delete_slip(code: str):
    return {"deleted": handoff.delete(code)}


@app.get("/api/audio/{key}", tags=["audio"])
async def get_audio(key: str):
    item = audio_store.get(key)
    if not item:
        raise HTTPException(404, "Audio expired")
    return Response(content=item[0], media_type=item[1], headers={"Cache-Control": "no-store"})


# ---------- frontend ----------

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(FRONTEND / "index.html")
