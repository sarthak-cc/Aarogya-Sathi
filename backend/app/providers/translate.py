"""Translation to and from English with Sarvam Translate (covers the 22 scheduled languages).

English is the pivot: the LLM reasons in English and the safety rules also see
an English copy. Errors are raised, never hidden behind a fake translation.
"""
from __future__ import annotations

from .. import config, languages
from . import ProviderError, json_of, send

PROVIDER = "Sarvam translation"
_cache: dict[tuple[str, str, str], str] = {}


async def _sarvam(text: str, src: str, tgt: str) -> str:
    s = config.settings
    key = (text, src, tgt)
    if key in _cache:
        return _cache[key]
    resp = await send(PROVIDER, "POST", f"{s.sarvam_base_url}/translate",
                      headers={"api-subscription-key": s.sarvam_api_key},
                      json={"input": text[:2000], "source_language_code": src, "target_language_code": tgt,
                            "model": s.sarvam_translate_model})
    out = (json_of(resp, PROVIDER).get("translated_text") or "").strip()
    if not out:
        raise ProviderError(PROVIDER, "bad_response", "empty translation")
    if len(_cache) > 2000:
        _cache.clear()
    _cache[key] = out
    return out


def _check(lang_code: str) -> None:
    lang = languages.get(lang_code)
    if not lang or "sarvam" not in lang.translate:
        raise ProviderError(PROVIDER, "unsupported", lang_code)
    if not config.settings.has_sarvam:
        raise ProviderError(PROVIDER, "not_configured", "SARVAM_API_KEY is not set")


async def to_english(text: str, src: str) -> str:
    if src == "en-IN" or not text:
        return text
    _check(src)
    return await _sarvam(text, src, "en-IN")


async def from_english(text: str, tgt: str) -> str:
    if tgt == "en-IN" or not text:
        return text
    _check(tgt)
    return await _sarvam(text, "en-IN", tgt)
