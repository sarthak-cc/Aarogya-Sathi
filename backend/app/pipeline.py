"""The conversation pipeline.

    speech ─► STT ─► translate→EN ─► SAFETY RULES ─┬─► emergency script (no LLM) ─► offer nearby hospitals
                                                   └─► LLM (EN) ─► AI triage tag ─► dose filter ─► translate back ─► TTS

There is no scripted fallback for routine questions: if the AI or translation
service is missing or fails, the turn says so. Each stage is timed.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Optional

from . import audio_store, knowledge, languages, medicine, prompts, triage
from .providers import ProviderError, llm, stt, translate, tts
from .sessions import Conversation


class _Timer:
    def __init__(self):
        self.ms: dict[str, int] = {}

    @contextmanager
    def run(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.ms[name] = self.ms.get(name, 0) + round((time.perf_counter() - t0) * 1000)


async def speak(conv: Optional[Conversation], text: str, lang_code: str, simple: bool = False) -> dict:
    """Synthesize speech; never fails the turn, always says why there is no audio."""
    try:
        audio, mime, provider = await tts.synthesize(text, lang_code, pace=0.85 if simple else 0.95)
    except ProviderError as exc:
        lang = languages.get(lang_code)
        note = (f"No voice for {lang.name} is set up on this server, so the answer is shown as text."
                if exc.kind == "unsupported" and lang else exc.public()["message"])
        return {"audio_url": None, "provider": None, "note": note, "error": exc.public()}
    key = audio_store.put(audio, mime)
    if conv:
        conv.audio_keys.append(key)
    return {"audio_url": f"/api/audio/{key}", "provider": provider, "note": None, "error": None}


async def hear(audio: bytes, filename: str, content_type: str, lang_code: str) -> dict:
    """Speech to text. Raises ProviderError with an honest reason."""
    result = await stt.transcribe(audio, filename, content_type, lang_code)
    if len(result["text"].strip()) < 2:
        raise ProviderError("Speech recognition", "bad_response", "no speech found")
    return result


async def emergency_turn(conv: Conversation, level: str, rule_ids: list[str], timer: _Timer) -> dict:
    with timer.run("script"):
        msg = await prompts.emergency_message(level, rule_ids, conv.language)
        ask_loc = await prompts.get("ask_location", conv.language)
    note = "Shown in English: no translation is configured for this language." if msg["source"] == "english_fallback" else None
    return {"text": msg["text"], "lang": msg["lang"], "source": f"{level}_script", "english": None,
            "language_note": note, "location_prompt": ask_loc}


async def ask(conv: Conversation, text: str, level: str = "standard", heard: Optional[dict] = None) -> dict:
    """Answer one question. Returns a turn; `error` is set when a required service failed."""
    timer = _Timer()
    lang = conv.language
    conv.last_question = text
    turn: dict = {"question": {"text": text, "lang": lang, "stt": heard}, "english": None, "level": level,
                  "triage": None, "answer": None, "medicine": {"request": False, "dose_removed": False},
                  "voice": None, "offer_facilities": False, "error": None, "notes": []}

    # 1. English pivot (needed for the LLM, and gives the safety rules a second copy)
    english: Optional[str] = None
    translate_error: Optional[ProviderError] = None
    try:
        with timer.run("translate_in"):
            english = await translate.to_english(text, lang)
    except ProviderError as exc:
        translate_error = exc
    turn["english"] = english

    # 2. Independent safety rules, before any AI
    with timer.run("safety_rules"):
        tri = triage.assess(text, english or "")
    turn["triage"] = {**tri.to_dict(), "source": "rules" if tri.matches else None}
    if english is None and lang != "en-IN":
        turn["notes"].append("Safety rules ran on your own words only, because translation was not available.")

    if tri.is_blocking:
        turn["answer"] = await emergency_turn(conv, tri.level.value, [m["rule"] for m in tri.matches], timer)
        turn["offer_facilities"] = tri.level == triage.Level.EMERGENCY
        return await _finish(conv, turn, timer)

    if translate_error:
        turn["error"] = translate_error.public()
        return _done(turn, timer)

    # 3. Real LLM answer for routine questions
    med_request = medicine.is_prescription_request(text, english or "")
    turn["medicine"]["request"] = med_request
    cards = knowledge.retrieve(english or "")
    if med_request:
        cards = [knowledge.by_id("medicine_safety")] + [c for c in cards if c.id != "medicine_safety"][:1]
    try:
        with timer.run("llm"):
            result = await llm.answer(english or text, cards, level=level, history=conv.history,
                                      medicine_request=med_request)
    except ProviderError as exc:
        turn["error"] = exc.public()
        return _done(turn, timer)

    # 4. Second safety net: the AI's own triage tag can only raise the level, never lower it
    if result.triage == "emergency":
        turn["triage"] = {"level": "emergency", "blocking": True, "source": "ai",
                          "matches": [{"rule": "ai_triage", "label": "AI safety check found danger signs", "level": "emergency"}]}
        turn["answer"] = await emergency_turn(conv, "emergency", [], timer)
        turn["offer_facilities"] = True
        return await _finish(conv, turn, timer)
    if result.triage == "urgent" and tri.level == triage.Level.NONE:
        turn["triage"] = {"level": "urgent", "blocking": False, "source": "ai",
                          "matches": [{"rule": "ai_triage", "label": "AI suggests seeing a health worker soon", "level": "urgent"}]}

    # 5. Output validation: no doses, ever
    answer_en, removed = medicine.strip_doses(result.text)
    turn["medicine"]["dose_removed"] = removed

    # 6. Back to the user's language
    answer = {"text": answer_en, "lang": lang, "source": "llm", "model": result.model, "english": answer_en,
              "language_note": None, "cards": [{"id": c.id, "title": c.title, "source": c.source} for c in cards]}
    if lang != "en-IN":
        try:
            with timer.run("translate_out"):
                answer["text"] = await translate.from_english(answer_en, lang)
        except ProviderError as exc:
            answer["lang"] = "en-IN"
            answer["language_note"] = f"Shown in English because translation failed: {exc.public()['message']}"
    turn["answer"] = answer
    conv.remember(english or text, answer_en)
    return await _finish(conv, turn, timer)


async def _finish(conv: Conversation, turn: dict, timer: _Timer) -> dict:
    with timer.run("voice"):
        turn["voice"] = await speak(conv, turn["answer"]["text"], turn["answer"]["lang"], simple=turn["level"] == "simple")
    return _done(turn, timer)


def _done(turn: dict, timer: _Timer) -> dict:
    turn["timings_ms"] = timer.ms
    return turn
