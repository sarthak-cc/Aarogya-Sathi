"""Language capability registry.

`provider_support` records what the upstream providers *claim* to support
(checked against their public docs in Oct 2026). `configured_capabilities()`
combines that with which API keys are actually set, so the UI and IVR never
promise a voice conversation that cannot happen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import config


@dataclass(frozen=True)
class Language:
    code: str  # BCP-47 code used across the app
    name: str
    native_name: str
    states: tuple[str, ...]
    keypad: Optional[str]  # digit on the IVR language menu; None = sub-menu only
    stt: tuple[str, ...] = ()  # providers able to transcribe
    translate: tuple[str, ...] = ()  # providers able to translate to/from English
    tts: tuple[str, ...] = ()  # providers able to speak it
    browser_voice: Optional[str] = None  # Web Speech lang tag likely to exist
    notes: str = ""
    tested_end_to_end: bool = False  # flip only after a native speaker verifies a full call


REGISTRY: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language(
            "as-IN", "Assamese", "অসমীয়া", ("Assam",), "1",
            stt=("sarvam",), translate=("sarvam",), tts=("parler",),
            notes="Sarvam Saaras v4 STT + Sarvam Translate; voice via self-hosted Indic Parler-TTS.",
        ),
        Language(
            "brx-IN", "Bodo", "बड़ो", ("Assam",), "2",
            stt=("sarvam",), translate=("sarvam",), tts=("parler",),
            notes="Devanagari script. Same stack as Assamese.",
        ),
        Language(
            "mni-IN", "Manipuri (Meitei)", "মৈতৈলোন্", ("Manipur",), "3",
            stt=("sarvam",), translate=("sarvam",), tts=("parler",),
            notes="Output script (Bengali vs Meitei Mayek) must be checked with native users.",
        ),
        Language(
            "ne-IN", "Nepali", "नेपाली", ("Sikkim", "Assam", "Meghalaya"), "4",
            stt=("sarvam", "groq"), translate=("sarvam",), tts=("parler",),
            browser_voice="ne-NP",
        ),
        Language(
            "bn-IN", "Bengali", "বাংলা", ("Tripura", "Assam (Barak Valley)"), "5",
            stt=("sarvam", "groq"), translate=("sarvam",), tts=("sarvam",),
            browser_voice="bn-IN",
        ),
        Language(
            "hi-IN", "Hindi", "हिन्दी", ("All NER states",), "6",
            stt=("sarvam", "groq"), translate=("sarvam",), tts=("sarvam",),
            browser_voice="hi-IN",
        ),
        Language(
            "en-IN", "English", "English", ("All NER states",), "7",
            stt=("sarvam", "groq"), translate=("identity",), tts=("sarvam",),
            browser_voice="en-IN",
        ),
        # Languages the NER needs but no public speech model covers reliably yet.
        Language("kha-IN", "Khasi", "Ka Ktien Khasi", ("Meghalaya",), None,
                 notes="No reliable public STT/TTS found. Requests are logged to prioritise data collection."),
        Language("grt-IN", "Garo", "A·chik", ("Meghalaya",), None,
                 notes="No reliable public STT/TTS found."),
        Language("lus-IN", "Mizo", "Mizo ṭawng", ("Mizoram",), None,
                 notes="No reliable public STT/TTS found."),
        Language("trp-IN", "Kokborok", "Kók Borok", ("Tripura",), None,
                 notes="No reliable public STT/TTS found."),
        Language("nag-IN", "Nagamese", "Nagamese", ("Nagaland",), None,
                 notes="Creole without public speech models; Hindi/English often understood."),
    ]
}

# Keypad 8 on the language menu = "my language is not listed"
OTHER_LANGUAGES_DIGIT = "8"


def get(code: str) -> Optional[Language]:
    return REGISTRY.get(code)


def by_keypad(digit: str) -> Optional[Language]:
    for lang in REGISTRY.values():
        if lang.keypad == digit:
            return lang
    return None


def configured_capabilities(lang: Language) -> dict:
    s = config.settings
    stt_live = ("sarvam" in lang.stt and s.has_sarvam) or ("groq" in lang.stt and s.has_groq_stt)
    translate_live = "identity" in lang.translate or ("sarvam" in lang.translate and s.has_sarvam)
    tts_live = ("sarvam" in lang.tts and s.has_sarvam) or ("parler" in lang.tts and s.has_parler)

    if not lang.stt:
        level = "unsupported"
    elif stt_live and translate_live and tts_live and s.has_llm:
        level = "full_voice"
    elif lang.stt and lang.translate and lang.tts:
        level = "voice_ready_needs_keys"
    else:
        level = "partial"

    return {
        "code": lang.code,
        "name": lang.name,
        "native_name": lang.native_name,
        "states": list(lang.states),
        "keypad": lang.keypad,
        "provider_support": {
            "stt": list(lang.stt),
            "translate": list(lang.translate),
            "tts": list(lang.tts),
        },
        "configured": {
            "stt": stt_live,
            "translate": translate_live,
            "tts": tts_live,
            "llm": s.has_llm,
        },
        "level": level,
        "browser_voice": lang.browser_voice,
        "tested_end_to_end": lang.tested_end_to_end,
        "notes": lang.notes,
    }


def all_capabilities() -> list[dict]:
    return [configured_capabilities(lang) for lang in REGISTRY.values()]
