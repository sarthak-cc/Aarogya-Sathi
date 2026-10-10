"""Language capability registry.

`stt` / `translate` / `tts` record what providers document as supported
(checked October 2026). `capability()` combines that with what is configured
on this server and with the results of `scripts/verify_live.py`, so the
language picker only offers what can really work, and says what is verified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config

VERIFICATION_FILE = Path(__file__).resolve().parent / "data" / "verification.json"


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native_name: str
    script: str
    states: tuple[str, ...]
    stt: tuple[str, ...] = ()
    translate: tuple[str, ...] = ()
    tts: tuple[str, ...] = ()
    example: str = ""
    notes: str = ""


REGISTRY: dict[str, Language] = {lang.code: lang for lang in [
    Language("hi-IN", "Hindi", "हिन्दी", "Devanagari", ("All NE states",), ("sarvam", "groq"), ("sarvam",), ("sarvam",),
             "मुझे दो दिन से बुखार है, क्या करूँ?"),
    Language("as-IN", "Assamese", "অসমীয়া", "Assamese (Bengali-Assamese)", ("Assam",), ("sarvam",), ("sarvam",), ("sarvam-clone", "mms", "parler"),
             "মোৰ দুদিন ধৰি জ্বৰ হৈছে, কি কৰিম?",
             "Sarvam standard Bulbul has no Assamese voice. Spoken answers use a cloned voice (SARVAM_VOICE_ID), or optional MMS/Parler."),
    Language("en-IN", "English", "English", "Latin", ("All NE states",), ("sarvam", "groq"), ("identity",), ("sarvam",),
             "I have had a fever for two days. What should I do?"),
    Language("bn-IN", "Bengali", "বাংলা", "Bengali", ("Tripura", "Barak Valley"), ("sarvam", "groq"), ("sarvam",), ("sarvam",),
             "আমার দুদিন ধরে জ্বর, কী করব?"),
    Language("ne-IN", "Nepali", "नेपाली", "Devanagari", ("Sikkim", "Assam", "Meghalaya"), ("sarvam", "groq"), ("sarvam",),
             ("mms", "parler"), "मलाई दुई दिनदेखि ज्वरो छ, के गर्ने?",
             "Sarvam has no Nepali voice. Spoken answers need the optional local MMS voice or a Parler server."),
    Language("brx-IN", "Bodo", "बड़ो", "Devanagari", ("Assam",), ("sarvam",), ("sarvam",), ("parler",), "",
             "Spoken answers need a self-hosted Parler server. Translation quality not yet reviewed by native speakers."),
    Language("mni-IN", "Manipuri (Meitei)", "মৈতৈলোন্", "Bengali script (Meitei Mayek not verified)", ("Manipur",),
             ("sarvam",), ("sarvam",), ("parler",), "",
             "Output script (Bengali script vs Meitei Mayek) is not verified. Spoken answers need a Parler server."),
    # Needed in the North East, but no reliable public speech or translation service exists yet.
    Language("kha-IN", "Khasi", "Ka Ktien Khasi", "Latin", ("Meghalaya",),
             notes="No reliable speech recognition, translation or voice service found."),
    Language("grt-IN", "Garo", "A·chik", "Latin", ("Meghalaya",),
             notes="No reliable speech recognition, translation or voice service found."),
    Language("lus-IN", "Mizo", "Mizo ṭawng", "Latin", ("Mizoram",),
             notes="No reliable speech recognition, translation or voice service found."),
    Language("trp-IN", "Kokborok", "Kók Borok", "Latin / Bengali", ("Tripura",),
             notes="No reliable speech recognition, translation or voice service found."),
    Language("nag-IN", "Nagamese", "Nagamese", "Latin", ("Nagaland",),
             notes="No public speech or translation models. Many speakers also use Hindi or Assamese."),
]}


def get(code: str) -> Optional[Language]:
    return REGISTRY.get(code)


def verification() -> dict:
    try:
        return json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def capability(lang: Language) -> dict:
    from .providers import tts  # local import avoids a cycle

    s = config.settings
    stt_live = ("sarvam" in lang.stt and s.has_sarvam) or ("groq" in lang.stt and s.has_groq_stt)
    translate_live = "identity" in lang.translate or ("sarvam" in lang.translate and s.has_sarvam)
    voices = tts.available(lang.code)
    can_answer = s.has_llm and translate_live

    if not lang.stt and not lang.translate:
        status, summary = "unavailable", "Not available yet"
    elif not can_answer:
        status = "not_configured"
        summary = "Needs the AI key" if not s.has_llm else "Needs the Sarvam key"
    elif stt_live and voices:
        status, summary = "voice", "Speak and listen"
    elif stt_live:
        status, summary = "voice_in_text_out", "Speak; answer shown as text"
    else:
        status, summary = "text", "Type; answer shown as text"

    checked = verification().get(lang.code, {})
    return {
        "code": lang.code, "name": lang.name, "native_name": lang.native_name, "script": lang.script,
        "states": list(lang.states), "example": lang.example, "notes": lang.notes,
        "status": status, "summary": summary, "selectable": status not in ("unavailable", "not_configured"),
        "speech_input": stt_live, "speech_output": voices, "translation": translate_live,
        "verified": {"passed": bool(checked.get("passed")), "date": checked.get("date"),
                     "checks": checked.get("checks", {})},
    }


def all_capabilities() -> list[dict]:
    return [capability(lang) for lang in REGISTRY.values()]
