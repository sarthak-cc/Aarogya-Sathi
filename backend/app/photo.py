"""Camera prototype: photo → Groq vision → safety checks → user's language → voice.

    optional note ─► SAFETY RULES (triage.py) ─┬─► emergency script now, photo not sent (no delay)
                                                └─► vision model (EN) ─► dose filter ─► urgency (can only add caution)
                                                      ─► translate fields ─► spoken summary ─► existing TTS

The deterministic rules always run first and are never overridden by the image
model; the model's urgency label can only raise the level of caution.
The image is processed in memory and discarded; it is never logged or stored.
"""
from __future__ import annotations

import asyncio
import re
import time
from contextlib import contextmanager
from typing import Optional

from . import medicine, pipeline, prompts, triage
from .providers import ProviderError, translate, vision

PRIVACY = "The photo was sent once to Groq for analysis and was not stored by Aarogya Saathi."


@contextmanager
def _timed(ms: dict, name: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms[name] = round((time.perf_counter() - t0) * 1000)


async def _to_lang(texts: list[str], lang: str) -> tuple[list[str], Optional[str]]:
    """Translate a list of English strings; on failure keep English and say so."""
    if lang == "en-IN" or not texts:
        return texts, None
    try:
        return list(await asyncio.gather(*(translate.from_english(t, lang) for t in texts))), None
    except ProviderError as exc:
        return texts, f"Shown in English because translation failed: {exc.public()['message']}"


def _empty(lang: str) -> dict:
    return {"ok": False, "language": lang, "vision": None, "english": None, "answer": None,
            "triage": {"level": "none", "blocking": False, "source": None, "matches": []},
            "offer_facilities": False, "voice": None, "error": None, "timings_ms": {}, "privacy": PRIVACY}


async def analyze(data: bytes, content_type: str, lang: str, note: str = "") -> dict:
    """Returns a response dict; `error` is set (and `ok` False) whenever the analysis did not happen."""
    out = _empty(lang)
    ms = out["timings_ms"]
    note = (note or "").strip()[:300]

    # 1. Deterministic safety rules on anything the person typed or said with the photo.
    note_en = note
    if note and lang != "en-IN":
        try:
            note_en = await translate.to_english(note, lang)
        except ProviderError:
            note_en = note  # native-language rules still run below
    if note:
        tri = triage.assess(note, note_en)
        out["triage"] = {**tri.to_dict(), "source": "rules" if tri.matches else None}
        if tri.is_blocking:  # emergency guidance must not wait for an image model
            msg = await prompts.emergency_message(tri.level.value, [m["rule"] for m in tri.matches], lang)
            out.update(ok=True, offer_facilities=tri.level == triage.Level.EMERGENCY,
                       answer={"text": msg["text"], "lang": msg["lang"], "source": f"{tri.level.value}_script",
                               "model": None, "language_note": None})
            out["voice"] = await pipeline.speak(None, msg["text"], msg["lang"])
            out["privacy"] = "The photo was not sent: emergency guidance was given first."
            return out

    # 2. Validate and shrink the image (also strips EXIF/GPS metadata).
    try:
        with _timed(ms, "image_prep"):
            image = await asyncio.to_thread(vision.prepare, data, content_type)
    except vision.InvalidImage as exc:
        out["error"] = {"provider": "Photo", "kind": "invalid_image", "message": str(exc), "retry_after": None}
        out["privacy"] = "The photo was not sent."
        return out

    # 3. The vision model.
    try:
        with _timed(ms, "vision"):
            result = await vision.analyze(image, note_en)
    except ProviderError as exc:
        out["error"] = exc.public()
        return out

    # 4. Output safety: no doses anywhere; urgency from the model can only add caution.
    def clean(t: str) -> str:
        s = medicine.strip_doses(t)[0] if t else ""
        return re.sub(r"^\s*\(mock(?:\s+[a-z]{2}(?:-[A-Z]{2})?)?\)\s*:?\s*", "", s, flags=re.I).strip()

    english = {
        "observation": clean(result.observation),
        "possible_explanations": [clean(t) for t in result.possible_explanations],
        "follow_up_questions": [clean(t) for t in result.follow_up_questions],
        "recommended_next_steps": [clean(t) for t in result.recommended_next_steps],
        "urgency": result.urgency, "image_quality": result.image_quality,
        "disclaimer": prompts.EN["photo_disclaimer"],
    }
    rules_level = out["triage"]["level"]
    if result.urgency == "emergency":
        out["triage"] = {"level": "emergency", "blocking": True, "source": "vision_ai",
                         "matches": [{"rule": "vision_ai", "label": "Photo check found possible danger signs", "level": "emergency"}]}
        out["offer_facilities"] = True
    elif result.urgency == "urgent" and rules_level == "none":
        out["triage"] = {"level": "urgent", "blocking": False, "source": "vision_ai",
                         "matches": [{"rule": "vision_ai", "label": "Photo check suggests seeing a health worker within a day", "level": "urgent"}]}

    # 5. Into the selected language (never silently switched).
    with _timed(ms, "translate_out"):
        lists = [english["observation"], *english["possible_explanations"], *english["follow_up_questions"],
                 *english["recommended_next_steps"]]
        translated, note_lang = await _to_lang(lists, lang)
        disclaimer = await prompts.get("photo_disclaimer", lang)
    translated = [clean(t) for t in translated]
    shown_lang = lang if note_lang is None else "en-IN"
    n1, n2 = len(english["possible_explanations"]), len(english["follow_up_questions"])
    localized = {
        "observation": translated[0],
        "possible_explanations": translated[1:1 + n1],
        "follow_up_questions": translated[1 + n1:1 + n1 + n2],
        "recommended_next_steps": translated[1 + n1 + n2:],
        "urgency": result.urgency, "image_quality": result.image_quality,
        "disclaimer": disclaimer["text"] if disclaimer["lang"] == shown_lang else english["disclaimer"],
    }

    # 6. Concise user-facing answer (~25-45 words).
    # Structure: What I see (1 sentence) + What to do (1-2 actions) + Warning (if relevant) + Question (<=1, if useful).
    # Strictly omits debug logs, model names, possible explanations, and disclaimer from spoken text.
    parts: list[str] = []
    if out["triage"]["level"] == "emergency":
        em = await prompts.emergency_message("emergency", [], lang)
        if em["lang"] == shown_lang:
            parts.append(clean(em["text"]))

    obs = clean(localized["observation"])
    if obs:
        parts.append(obs)

    steps = [clean(s) for s in localized["recommended_next_steps"][:2] if s]
    parts.extend(steps)

    questions = [clean(q) for q in localized["follow_up_questions"][:1] if q]
    parts.extend(questions)

    spoken = " ".join(p for p in parts if p).strip()

    out.update(ok=True, vision=localized, english=english,
               answer={"text": spoken, "lang": shown_lang, "source": "vision", "model": result.model,
                       "language_note": note_lang})
    with _timed(ms, "voice"):
        out["voice"] = await pipeline.speak(None, spoken, shown_lang)
    return out

