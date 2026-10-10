"""Speech-to-text: Sarvam Saaras (22 Indian languages) with Groq Whisper as a second option."""
from __future__ import annotations

from .. import config, languages
from . import ProviderError, json_of, send

WHISPER_LANG = {"hi-IN": "hi", "bn-IN": "bn", "ne-IN": "ne", "en-IN": "en"}


async def transcribe(audio: bytes, filename: str, content_type: str, lang_code: str) -> dict:
    s = config.settings
    lang = languages.get(lang_code)
    if lang is None:
        raise ProviderError("Speech recognition", "unsupported", lang_code)
    if not audio:
        raise ProviderError("Speech recognition", "bad_response", "empty audio")
    file = {"file": (filename, audio, content_type or "audio/wav")}

    if "sarvam" in lang.stt and s.has_sarvam:
        data = {"model": s.sarvam_stt_model, "language_code": lang_code}
        if s.sarvam_stt_mode:
            data["mode"] = s.sarvam_stt_mode
        resp = await send("Sarvam speech recognition", "POST", f"{s.sarvam_base_url}/speech-to-text",
                          headers={"api-subscription-key": s.sarvam_api_key}, data=data, files=file)
        body = json_of(resp, "Sarvam speech recognition")
        return {"text": (body.get("transcript") or "").strip(), "provider": f"sarvam {s.sarvam_stt_model}",
                "detected_language": body.get("language_code")}

    if "groq" in lang.stt and s.has_groq_stt:
        resp = await send("Groq Whisper", "POST", s.groq_stt_url,
                          headers={"Authorization": f"Bearer {s.groq_api_key}"},
                          data={"model": s.groq_stt_model, "language": WHISPER_LANG[lang_code],
                                "response_format": "json", "temperature": "0"}, files=file)
        body = json_of(resp, "Groq Whisper")
        return {"text": (body.get("text") or "").strip(), "provider": f"groq {s.groq_stt_model}",
                "detected_language": lang_code}

    if lang.stt:
        raise ProviderError("Speech recognition", "not_configured", "SARVAM_API_KEY is not set")
    raise ProviderError("Speech recognition", "unsupported", lang.name)
