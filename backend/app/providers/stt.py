"""Speech-to-text: Sarvam Saaras (NER languages) with Groq Whisper fallback."""
from __future__ import annotations

import json

import httpx

from .. import config, languages
from . import ProviderError, ProviderUnavailable, client, raise_for

# Bias recognition towards health vocabulary (Saaras v4 `keyterms`, max 50).
MEDICAL_KEYTERMS = [
    "fever", "malaria", "dengue", "diarrhoea", "ORS", "cough", "pregnancy", "ASHA", "PHC", "snake bite",
    "blood pressure", "sugar", "TB", "vomiting", "headache", "chest pain", "jaundice", "typhoid",
    "scrub typhus", "Japanese encephalitis", "112", "paracetamol", "vaccine", "zinc",
]

WHISPER_LANG = {"hi-IN": "hi", "bn-IN": "bn", "ne-IN": "ne", "en-IN": "en"}


async def transcribe(audio: bytes, filename: str, content_type: str, lang_code: str) -> dict:
    s = config.settings
    lang = languages.get(lang_code)
    if lang is None:
        raise ProviderUnavailable(f"unknown language {lang_code}")
    if not audio:
        raise ProviderError("empty audio")

    if "sarvam" in lang.stt and s.has_sarvam:
        data = {"model": s.sarvam_stt_model, "language_code": lang_code}
        if s.sarvam_stt_model.endswith("v4"):
            data["keyterms"] = json.dumps(MEDICAL_KEYTERMS)
        try:
            async with client() as c:
                resp = await c.post(
                    f"{s.sarvam_base_url}/speech-to-text",
                    headers={"api-subscription-key": s.sarvam_api_key},
                    data=data,
                    files={"file": (filename, audio, content_type or "application/octet-stream")},
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"sarvam stt network error: {type(exc).__name__}") from exc
        raise_for(resp, "sarvam-stt")
        body = resp.json()
        return {"text": (body.get("transcript") or "").strip(), "provider": "sarvam",
                "detected_language": body.get("language_code")}

    if "groq" in lang.stt and s.has_groq_stt:
        try:
            async with client() as c:
                resp = await c.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {s.groq_api_key}"},
                    data={"model": s.groq_stt_model, "language": WHISPER_LANG[lang_code],
                          "response_format": "json", "temperature": "0"},
                    files={"file": (filename, audio, content_type or "application/octet-stream")},
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"groq stt network error: {type(exc).__name__}") from exc
        raise_for(resp, "groq-stt")
        return {"text": (resp.json().get("text") or "").strip(), "provider": "groq-whisper",
                "detected_language": lang_code}

    raise ProviderUnavailable(f"no speech recognition configured for {lang.name}")
