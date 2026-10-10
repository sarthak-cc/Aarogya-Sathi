"""Text-to-speech.

* Sarvam Bulbul: Hindi, Bengali, English (and other languages outside the NE).
* MMS-TTS: Meta's open-source per-language voices run locally on CPU. Optional;
  covers Assamese and Nepali, which Bulbul does not. Licence CC-BY-NC 4.0.
* Parler: self-hosted AI4Bharat Indic Parler-TTS on a GPU (tts_server/).
"""
from __future__ import annotations

import asyncio
import base64
import io
from functools import lru_cache

from .. import config, languages
from . import ProviderError, json_of, send

MMS_MODELS = {"as-IN": "facebook/mms-tts-asm", "ne-IN": "facebook/mms-tts-npi", "hi-IN": "facebook/mms-tts-hin",
              "bn-IN": "facebook/mms-tts-ben", "en-IN": "facebook/mms-tts-eng"}


def available(lang_code: str) -> list[str]:
    s = config.settings
    lang = languages.get(lang_code)
    if not lang:
        return []
    out = []
    if "sarvam" in lang.tts and s.has_sarvam:
        out.append("sarvam")
    if lang_code in s.mms_langs and lang_code in MMS_MODELS:
        out.append("mms")
    if "parler" in lang.tts and s.has_parler:
        out.append("parler")
    return out


async def synthesize(text: str, lang_code: str, pace: float = 0.95) -> tuple[bytes, str, str]:
    """Return (audio bytes, mime type, provider)."""
    providers = available(lang_code)
    if not text:
        raise ProviderError("Voice", "bad_response", "nothing to speak")
    if not providers:
        raise ProviderError("Voice", "unsupported" if languages.get(lang_code) else "bad_response", lang_code)
    last: ProviderError | None = None
    for p in providers:  # first configured provider wins; fall through on failure
        try:
            if p == "sarvam":
                return await _sarvam(text, lang_code, pace), "audio/wav", "sarvam bulbul"
            if p == "mms":
                return await asyncio.to_thread(_mms, text, lang_code), "audio/wav", "mms-tts (local)"
            if p == "parler":
                return await _parler(text, lang_code), "audio/wav", "parler (self-hosted)"
        except ProviderError as exc:
            last = exc
    raise last  # type: ignore[misc]


async def _sarvam(text: str, lang_code: str, pace: float) -> bytes:
    s = config.settings
    resp = await send("Sarvam voice", "POST", f"{s.sarvam_base_url}/text-to-speech",
                      headers={"api-subscription-key": s.sarvam_api_key},
                      json={"text": text[:2500], "target_language_code": lang_code, "model": s.sarvam_tts_model,
                            "speaker": s.sarvam_tts_speaker, "pace": pace})
    audios = json_of(resp, "Sarvam voice").get("audios") or []
    if not audios:
        raise ProviderError("Sarvam voice", "bad_response", "no audio")
    try:
        return base64.b64decode(audios[0])
    except ValueError as exc:
        raise ProviderError("Sarvam voice", "bad_response", "bad base64") from exc


async def _parler(text: str, lang_code: str) -> bytes:
    s = config.settings
    resp = await send("Parler voice", "POST", f"{s.parler_tts_url.rstrip('/')}/tts", timeout=60,
                      json={"text": text, "language": lang_code})
    return resp.content


@lru_cache(maxsize=4)
def _mms_model(name: str):
    try:
        from transformers import AutoTokenizer, VitsModel  # optional heavy dependency
    except ImportError as exc:
        raise ProviderError("Local voice (MMS)", "not_configured", "pip install -r requirements-tts.txt") from exc
    return AutoTokenizer.from_pretrained(name), VitsModel.from_pretrained(name)


def _mms(text: str, lang_code: str) -> bytes:
    import numpy as np
    import soundfile as sf
    import torch

    tokenizer, model = _mms_model(MMS_MODELS[lang_code])
    if getattr(tokenizer, "is_uroman", False):  # some checkpoints expect romanised input
        try:
            import uroman as ur
            text = ur.Uroman().romanize_string(text)
        except ImportError as exc:
            raise ProviderError("Local voice (MMS)", "not_configured", "pip install uroman") from exc
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        wave = model(**inputs).waveform[0].cpu().numpy()
    buf = io.BytesIO()
    sf.write(buf, np.asarray(wave, dtype="float32"), model.config.sampling_rate, format="WAV")
    return buf.getvalue()
