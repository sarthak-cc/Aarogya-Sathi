"""Text-to-speech: Sarvam Bulbul (Hindi/Bengali/English) and self-hosted
AI4Bharat Indic Parler-TTS (Assamese/Bodo/Manipuri/Nepali)."""
from __future__ import annotations

import base64

import httpx

from .. import config, languages
from . import ProviderError, ProviderUnavailable, client, raise_for


async def synthesize(text: str, lang_code: str, pace: float = 0.9) -> tuple[bytes, str]:
    """Return (wav_bytes, provider). Raises ProviderUnavailable if no voice exists."""
    s = config.settings
    lang = languages.get(lang_code)
    if lang is None or not text:
        raise ProviderUnavailable("nothing to speak")

    if "sarvam" in lang.tts and s.has_sarvam:
        payload = {"text": text[:2500], "language_code": lang_code, "model": s.sarvam_tts_model,
                   "speaker": s.sarvam_tts_speaker, "pace": pace, "speech_sample_rate": 16000}
        try:
            async with client() as c:
                resp = await c.post(f"{s.sarvam_base_url}/text-to-speech",
                                    headers={"api-subscription-key": s.sarvam_api_key}, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"sarvam tts network error: {type(exc).__name__}") from exc
        raise_for(resp, "sarvam-tts")
        audios = resp.json().get("audios") or []
        if not audios:
            raise ProviderError("sarvam tts returned no audio")
        return base64.b64decode(audios[0]), "sarvam"

    if "parler" in lang.tts and s.has_parler:
        try:
            async with client() as c:
                resp = await c.post(f"{s.parler_tts_url.rstrip('/')}/tts",
                                    json={"text": text, "language": lang_code}, timeout=60)
        except httpx.HTTPError as exc:
            raise ProviderError(f"parler tts network error: {type(exc).__name__}") from exc
        raise_for(resp, "parler-tts")
        return resp.content, "parler"

    raise ProviderUnavailable(f"no voice configured for {lang.name}")
