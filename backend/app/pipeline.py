"""The conversation pipeline shared by the browser simulator and real phone calls.

    audio ─► STT ─► read-back confirm ─► translate→EN ─► TRIAGE ─┬─► emergency script (no LLM)
                                                                └─► retrieve cards ─► LLM (EN) ─► translate→native ─► TTS

Each stage is timed so the UI can show a latency waterfall per turn.
"""
from __future__ import annotations

import time
from typing import Optional

from . import audio_store, demo, knowledge, languages, prompts, triage
from .providers import ProviderError, ProviderUnavailable, llm, stt, translate, tts
from .sessions import Session, State


class _Timer:
    def __init__(self):
        self.ms: dict[str, int] = {}

    def run(self, name: str):
        timer = self

        class _Ctx:
            def __enter__(self_inner):
                self_inner.t0 = time.perf_counter()

            def __exit__(self_inner, *exc):
                timer.ms[name] = timer.ms.get(name, 0) + round((time.perf_counter() - self_inner.t0) * 1000)
                return False

        return _Ctx()


_PRERENDERED: dict[tuple[str, str], str] | None = None


def _prerendered(text: str, lang_code: str) -> Optional[str]:
    """Fixed prompts rendered ahead of time by scripts/prerender_prompts.py play with zero TTS latency."""
    global _PRERENDERED
    if _PRERENDERED is None:
        import json
        from pathlib import Path

        _PRERENDERED = {}
        index = Path(__file__).resolve().parents[2] / "frontend" / "prompts" / "index.json"
        if index.exists():
            for lang, items in json.loads(index.read_text()).items():
                for item in items.values():
                    _PRERENDERED[(lang, item["text"])] = item["url"]
    return _PRERENDERED.get((lang_code, text))


async def speak(session: Session, text: str, lang_code: str) -> dict:
    """Synthesize speech if any voice exists; never fails the turn."""
    cached = _prerendered(text, lang_code)
    if cached:
        return {"audio_url": cached, "voice": "prerendered", "voice_note": None}
    try:
        audio, provider = await tts.synthesize(text, lang_code, pace=0.8 if session.literacy == "simple" else 0.9)
    except ProviderUnavailable:
        return {"audio_url": None, "voice": "none", "voice_note": "No server voice for this language; browser voice or text shown."}
    except ProviderError as exc:
        return {"audio_url": None, "voice": "error", "voice_note": str(exc)}
    key = audio_store.put(audio, "audio/wav")
    session.audio_keys.append(key)
    return {"audio_url": f"/api/audio/{key}", "voice": provider, "voice_note": None}


async def hear(session: Session, audio: bytes, filename: str, content_type: str) -> dict:
    """Transcribe an utterance and ask the caller to confirm it (read-back)."""
    timer = _Timer()
    lang = session.language or "en-IN"
    try:
        with timer.run("stt"):
            result = await stt.transcribe(audio, filename, content_type, lang)
    except ProviderUnavailable:
        return {"ok": False, "reason": "stt_unavailable", "prompt": await prompts.get("not_heard", lang),
                "hint": "Speech recognition is not configured for this language. Type the question instead."}
    except ProviderError as exc:
        session.retries += 1
        return {"ok": False, "reason": "stt_error", "detail": str(exc), "prompt": await prompts.get("not_heard", lang)}

    transcript = result["text"]
    if len(transcript.strip()) < 2:
        session.retries += 1
        return {"ok": False, "reason": "empty_transcript", "prompt": await prompts.get("not_heard", lang)}

    session.retries = 0
    session.pending = {"transcript": transcript, "stt_provider": result["provider"], "timings": timer.ms}
    session.transition(State.CONFIRMING)
    return {"ok": True, "transcript": transcript, "stt_provider": result["provider"],
            "prompt": await prompts.get("readback", lang, text=transcript), "timings_ms": timer.ms}


async def confirm(session: Session, correct: bool) -> dict:
    lang = session.language or "en-IN"
    if not session.pending:
        return {"ok": False, "reason": "nothing_to_confirm"}
    if not correct:
        session.pending = None
        session.transition(State.READY_TO_LISTEN)
        return {"ok": True, "confirmed": False, "prompt": await prompts.get("ask_question", lang)}
    pending, session.pending = session.pending, None
    turn = await answer(session, pending["transcript"], prior_timings=pending.get("timings"),
                        stt_provider=pending.get("stt_provider"))
    return {"ok": True, "confirmed": True, "turn": turn}


async def answer(session: Session, transcript: str, simple: Optional[bool] = None,
                 prior_timings: Optional[dict] = None, stt_provider: Optional[str] = None) -> dict:
    """Run triage + grounded answer for a confirmed (or typed) question."""
    timer = _Timer()
    timer.ms.update(prior_timings or {})
    lang = session.language or "en-IN"
    level = "simple" if (simple if simple is not None else session.literacy == "simple") else "standard"

    # 1. Pivot to English (live translator, else offline demo phrasebook)
    english, english_source = None, None
    try:
        with timer.run("translate_in"):
            english = await translate.to_english(transcript, lang)
        english_source = "identity" if lang == "en-IN" else ("sarvam" if english is not None else None)
    except ProviderError:
        english = None
    if english is None:
        english = demo.english_for(transcript, lang)
        english_source = "demo_phrasebook" if english else None

    # 2. Deterministic safety triage on BOTH native and English text
    with timer.run("triage"):
        tri = triage.assess(transcript, english or "")

    turn: dict = {"transcript": transcript, "english": english, "english_source": english_source,
                  "stt_provider": stt_provider, "triage": tri.to_dict(), "cards": [], "level": level}

    if tri.is_blocking:
        key = "crisis" if tri.level == triage.Level.CRISIS else "emergency"
        msg = await prompts.get(key, lang)
        text = msg["text"]
        if key == "emergency":
            rule_ids = [m["rule"] for m in tri.matches]
            tip = _emergency_tip(rule_ids, lang)
            if tip is None:
                tip_en = next((prompts.EMERGENCY_TIPS_EN[r] for r in rule_ids if r in prompts.EMERGENCY_TIPS_EN), None)
                if tip_en:
                    tip = await _translate_or_english(tip_en, lang)
            if tip:
                text = f"{text} {tip}"
        turn["answer"] = {"text": text, "lang": msg["lang"], "source": key, "english": None}
        session.transition(State.EMERGENCY)
    else:
        # 3. Retrieve vetted cards and generate a grounded answer
        with timer.run("retrieve"):
            cards = knowledge.retrieve(english or "")
        turn["cards"] = [{"id": c.id, "title": c.title, "source": c.source} for c in cards]
        urgent = tri.level == triage.Level.URGENT
        native_answer, answer_en, source = None, None, None

        if english and llm_ready():
            try:
                with timer.run("llm"):
                    answer_en = await llm.answer(english, cards, level=level, urgent=urgent, history=session.history)
                source = "llm"
            except (ProviderError, ProviderUnavailable):
                answer_en, source = None, None
        if answer_en is None:
            scenario = demo.match(transcript, lang)
            if scenario and scenario["a"]:
                native_answer = demo.answer_for(scenario["id"], lang, simple=(level == "simple"))
                answer_en = demo.answer_for(scenario["id"], "en-IN", simple=(level == "simple"))
                source = "demo"
            else:
                answer_en = knowledge.card_answer(cards, simpler=(level == "simple"))
                if urgent:
                    answer_en += " Please see a health worker or doctor within a day."
                source = "card_fallback"

        answer_lang = lang
        if native_answer is None:
            with timer.run("translate_out"):
                native_answer = await _translate_or_none(answer_en, lang)
            if native_answer is None:
                native_answer, answer_lang = answer_en, "en-IN"
                source = f"{source}+english_fallback" if lang != "en-IN" else source
        turn["answer"] = {"text": native_answer, "lang": answer_lang, "source": source, "english": answer_en}
        session.history += [{"role": "user", "content": english or transcript},
                            {"role": "assistant", "content": answer_en}]
        session.transition(State.ANSWERED)

    with timer.run("tts"):
        turn["voice"] = await speak(session, turn["answer"]["text"], turn["answer"]["lang"])
    turn["menu"] = await prompts.get("after_answer", lang)
    turn["timings_ms"] = timer.ms
    turn["index"] = len(session.turns)
    session.turns.append(turn)
    return turn


async def simpler(session: Session) -> dict:
    """Literacy dial: re-explain the last question in simpler words."""
    last = session.last_answer
    if not last:
        return {"ok": False, "reason": "no_previous_answer"}
    session.literacy = "simple"
    if session.state != State.READY_TO_LISTEN:
        session.transition(State.READY_TO_LISTEN)
    turn = await answer(session, last["transcript"], simple=True)
    turn["rephrase_of"] = last["index"]
    return {"ok": True, "turn": turn}


def llm_ready() -> bool:
    from . import config

    return config.settings.has_llm


def _emergency_tip(rule_ids: list[str], lang: str) -> Optional[str]:
    hand = demo.EMERGENCY_TIPS_HAND.get(lang, {})
    for r in rule_ids:
        if r in hand:
            return hand[r]
    if lang == "en-IN":
        return next((prompts.EMERGENCY_TIPS_EN[r] for r in rule_ids if r in prompts.EMERGENCY_TIPS_EN), None)
    return None


async def _translate_or_none(text: str, lang: str) -> Optional[str]:
    try:
        return await translate.from_english(text, lang)
    except ProviderError:
        return None


async def _translate_or_english(text: str, lang: str) -> str:
    return (await _translate_or_none(text, lang)) or text


def language_status(code: str) -> dict:
    lang = languages.get(code)
    return languages.configured_capabilities(lang) if lang else {}
