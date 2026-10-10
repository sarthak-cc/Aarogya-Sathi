"""Aarogya Saathi API. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audio_store, config, facilities, languages, photo, pipeline, prompts, sessions
from .providers import ProviderError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aarogya")  # logs carry ids and error kinds only, never health text

app = FastAPI(
    title="Aarogya Saathi API",
    version="2.0.0",
    description="Voice-first multilingual health-information companion for North East India. "
                "General information only; not a diagnosis; never replaces a health professional.",
)

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # about 2 minutes of 16 kHz mono WAV
RATE_LIMIT = 60  # requests per minute per client, protects the free-tier provider quotas
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now, q = time.time(), _hits[ip]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(now)
    return await call_next(request)


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.error("unhandled error: %s", type(exc).__name__)  # no message: it may contain user text
    return JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)


# ---------- models ----------

class NewConversation(BaseModel):
    language: str = Field(..., examples=["hi-IN"])


class Ask(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    simple: bool = False


class Speak(BaseModel):
    text: str = Field(..., min_length=1, max_length=2500)
    lang: str


class Location(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    accuracy_m: Optional[float] = Field(None, ge=0)
    text: Optional[str] = Field(None, max_length=200, examples=["Jalukbari, Guwahati"])
    emergency: bool = False


def _conversation(conv_id: str) -> sessions.Conversation:
    c = sessions.get(conv_id)
    if not c:
        raise HTTPException(404, "Conversation not found or expired. Please start again.")
    return c


def _usable_language(code: str) -> dict:
    lang = languages.get(code)
    if not lang:
        raise HTTPException(422, "Unknown language")
    cap = languages.capability(lang)
    if not cap["selectable"]:
        raise HTTPException(409, f"{lang.name} is not available on this server: {cap['summary']}. {lang.notes}".strip())
    return cap


# ---------- info ----------

@app.get("/api/health", tags=["info"])
async def health():
    return {"status": "ok", "providers": config.settings.provider_status()}


@app.get("/api/languages", tags=["info"])
async def get_languages():
    return {"languages": languages.all_capabilities()}


# ---------- conversation ----------

@app.post("/api/conversations", tags=["conversation"])
async def new_conversation(body: NewConversation):
    cap = _usable_language(body.language)
    c = sessions.create(body.language)
    return {"id": c.id, "language": cap}


@app.post("/api/conversations/{conv_id}/ask", tags=["conversation"])
async def ask(conv_id: str, body: Ask):
    """Typed question."""
    c = _conversation(conv_id)
    return await pipeline.ask(c, body.text.strip(), level="simple" if body.simple else "standard")


@app.post("/api/conversations/{conv_id}/speech", tags=["conversation"])
async def speech(conv_id: str, audio: UploadFile = File(...), simple: bool = Form(False)):
    """Spoken question: speech-to-text, then the same pipeline as a typed question."""
    c = _conversation(conv_id)
    data = await audio.read()
    if not data:
        raise HTTPException(422, "No audio received")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too long. Please keep questions under a minute.")
    t0 = time.perf_counter()
    try:
        heard = await pipeline.hear(data, audio.filename or "speech.wav", audio.content_type or "audio/wav", c.language)
    except ProviderError as exc:
        hint = await prompts.get("not_heard", c.language)
        return {"heard": None, "turn": None, "error": exc.public(), "hint": hint}
    heard["ms"] = round((time.perf_counter() - t0) * 1000)
    turn = await pipeline.ask(c, heard["text"], level="simple" if simple else "standard", heard=heard)
    turn["timings_ms"] = {"speech_to_text": heard["ms"], **turn["timings_ms"]}
    return {"heard": heard, "turn": turn, "error": None}


@app.post("/api/conversations/{conv_id}/simpler", tags=["conversation"])
async def simpler(conv_id: str):
    c = _conversation(conv_id)
    if not c.last_question:
        raise HTTPException(409, "Ask a question first")
    return await pipeline.ask(c, c.last_question, level="simple")


@app.delete("/api/conversations/{conv_id}", tags=["conversation"])
async def end(conv_id: str):
    return {"deleted": sessions.delete(conv_id)}


@app.get("/api/emergency", tags=["safety"])
async def emergency(lang: str = "en-IN"):
    """Instant emergency guidance for the Emergency button. Never calls the AI."""
    if not languages.get(lang):
        raise HTTPException(422, "Unknown language")
    msg = await prompts.get("emergency", lang)
    ask_loc = await prompts.get("ask_location", lang)
    return {"message": msg, "location_prompt": ask_loc, "emergency_numbers": facilities.EMERGENCY_NUMBERS,
            "voice": await pipeline.speak(None, msg["text"], msg["lang"])}


@app.post("/api/speak", tags=["voice"])
async def speak(body: Speak):
    """Speak any text again (replay after audio expired)."""
    if not languages.get(body.lang):
        raise HTTPException(422, "Unknown language")
    return await pipeline.speak(None, body.text, body.lang)


@app.get("/api/audio/{key}", tags=["voice"])
async def get_audio(key: str):
    item = audio_store.get(key)
    if not item:
        raise HTTPException(404, "Audio expired")
    return Response(content=item[0], media_type=item[1], headers={"Cache-Control": "no-store"})


# ---------- camera prototype ----------

@app.post("/api/vision/analyze", tags=["vision"])
async def vision_analyze(image: UploadFile = File(...), language: str = Form("en-IN"),
                         note: str = Form("", max_length=300)):
    """Analyze one confirmed photo. Processed in memory, never stored or logged."""
    if not languages.get(language):
        raise HTTPException(422, "Unknown language")
    limit = int(config.settings.vision_max_upload_mb * 1024 * 1024)
    data = await image.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Photo too large. Please use one under {config.settings.vision_max_upload_mb:g} MB.")
    result = await photo.analyze(data, image.content_type or "", language, note)
    log.info("vision analyze ok=%s error=%s", result["ok"], (result["error"] or {}).get("kind"))
    return result


# ---------- nearby facilities ----------

@app.post("/api/facilities/search", tags=["facilities"])
async def search_facilities(body: Location):
    """Nearest facilities by device location, or by a typed village / town / PIN code / landmark."""
    place, geo_error = None, None
    if body.lat is not None and body.lon is not None:
        place = {"name": "Your location", "detail": None, "lat": body.lat, "lon": body.lon,
                 "approximate": (body.accuracy_m or 0) > 1000, "method": "device location",
                 "accuracy_m": body.accuracy_m}
    elif body.text and body.text.strip():
        place, geo_error = await facilities.resolve(body.text)
        if not place:
            return {"place": None, "facilities": [], "emergency_numbers": facilities.EMERGENCY_NUMBERS,
                    "error": geo_error, "notice": facilities.NOT_CONTACTED,
                    "limitation": "Could not find that place. Try a nearby town, district or 6-digit PIN code."}
    else:
        raise HTTPException(422, "Share your location or type a place name")
    result = await facilities.find(place["lat"], place["lon"], emergency=body.emergency)
    return {"place": place, **result, "error": result["error"] or geo_error}


# ---------- frontend ----------

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(FRONTEND / "index.html")
