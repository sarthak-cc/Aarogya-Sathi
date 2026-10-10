"""Translation to and from English via Sarvam Translate.

English is the pivot language: the LLM reasons in English (where open models
are strongest) and the triage rules see an English version of every message.
Returns None when no translator is configured; callers must handle that.
"""
from __future__ import annotations

import httpx

from .. import config, languages
from . import ProviderError, client, raise_for

_cache: dict[tuple[str, str, str], str] = {}


async def _sarvam(text: str, src: str, tgt: str) -> str:
    s = config.settings
    key = (text, src, tgt)
    if key in _cache:
        return _cache[key]
    payload = {"input": text[:2000], "source_language_code": src, "target_language_code": tgt,
               "model": s.sarvam_translate_model}
    try:
        async with client() as c:
            resp = await c.post(f"{s.sarvam_base_url}/translate",
                                headers={"api-subscription-key": s.sarvam_api_key}, json=payload)
    except httpx.HTTPError as exc:
        raise ProviderError(f"sarvam translate network error: {type(exc).__name__}") from exc
    raise_for(resp, "sarvam-translate")
    out = (resp.json().get("translated_text") or "").strip()
    if len(_cache) > 2000:
        _cache.clear()
    _cache[key] = out
    return out


def _available(lang_code: str) -> bool:
    lang = languages.get(lang_code)
    return bool(lang and "sarvam" in lang.translate and config.settings.has_sarvam)


async def to_english(text: str, src: str) -> str | None:
    if src == "en-IN" or not text:
        return text
    if not _available(src):
        return None
    return await _sarvam(text, src, "en-IN")


async def from_english(text: str, tgt: str) -> str | None:
    if tgt == "en-IN" or not text:
        return text
    if not _available(tgt):
        return None
    return await _sarvam(text, "en-IN", tgt)
