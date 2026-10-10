"""Central configuration, read from environment variables (or a local .env file).

Nothing here is ever sent to the browser except the yes/no status from
`provider_status()`. Missing keys are reported honestly; no stage is faked.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str, default: bool) -> bool:
    return _env(name, "true" if default else "false").lower() not in ("false", "0", "no", "off")


@dataclass
class Settings:
    # LLM: any OpenAI-compatible chat API. Default Groq (free tier, rate limited).
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY") or _env("GROQ_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "https://api.groq.com/openai/v1"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "openai/gpt-oss-120b"))
    # gpt-oss models accept low|medium|high. Leave blank for models without reasoning controls.
    llm_reasoning_effort: str = field(default_factory=lambda: _env("LLM_REASONING_EFFORT", "low"))
    llm_max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "1200")))
    llm_timeout: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT", "30")))

    # Sarvam AI: speech-to-text (22 Indian languages), translation, Bulbul voice (11 languages).
    sarvam_api_key: str = field(default_factory=lambda: _env("SARVAM_API_KEY"))
    sarvam_base_url: str = field(default_factory=lambda: _env("SARVAM_BASE_URL", "https://api.sarvam.ai"))
    sarvam_stt_model: str = field(default_factory=lambda: _env("SARVAM_STT_MODEL", "saaras:v3"))
    sarvam_stt_mode: str = field(default_factory=lambda: _env("SARVAM_STT_MODE", "transcribe"))
    sarvam_translate_model: str = field(default_factory=lambda: _env("SARVAM_TRANSLATE_MODEL", "sarvam-translate:v1"))
    sarvam_tts_model: str = field(default_factory=lambda: _env("SARVAM_TTS_MODEL", "bulbul:v3"))
    sarvam_tts_speaker: str = field(default_factory=lambda: _env("SARVAM_TTS_SPEAKER", "priya"))

    # Groq Whisper as a second speech-to-text option (en/hi/bn/ne). Uses the Groq key.
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY") or _env("LLM_API_KEY"))
    groq_stt_model: str = field(default_factory=lambda: _env("GROQ_STT_MODEL", "whisper-large-v3-turbo"))
    groq_stt_url: str = field(default_factory=lambda: _env("GROQ_STT_URL", "https://api.groq.com/openai/v1/audio/transcriptions"))

    # Optional voices for languages Bulbul does not cover.
    # MMS: Meta's open-source MMS-TTS run locally on CPU (pip install -r requirements-tts.txt).
    mms_tts_langs: str = field(default_factory=lambda: _env("MMS_TTS_LANGS"))  # e.g. "as-IN,ne-IN"
    parler_tts_url: str = field(default_factory=lambda: _env("PARLER_TTS_URL"))  # self-hosted GPU server

    # OpenStreetMap (free, documented, ODbL). Nominatim asks for a contact in the User-Agent.
    osm_enabled: bool = field(default_factory=lambda: _flag("OSM_ENABLED", True))
    osm_contact: str = field(default_factory=lambda: _env("OSM_CONTACT", "aarogya-saathi"))
    overpass_url: str = field(default_factory=lambda: _env("OVERPASS_URL", "https://overpass-api.de/api/interpreter"))
    nominatim_url: str = field(default_factory=lambda: _env("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"))
    db_path: str = field(default_factory=lambda: _env(
        "DB_PATH", str(Path(__file__).resolve().parents[1] / "data" / "aarogya.db")))

    http_timeout: float = field(default_factory=lambda: float(_env("HTTP_TIMEOUT", "20")))
    session_ttl_seconds: int = field(default_factory=lambda: int(_env("SESSION_TTL_SECONDS", "3600")))

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_sarvam(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def has_groq_stt(self) -> bool:
        # The LLM key only doubles as a Whisper key when the LLM itself is Groq.
        return bool(_env("GROQ_API_KEY")) or (bool(self.llm_api_key) and "groq.com" in self.llm_base_url)

    @property
    def mms_langs(self) -> set[str]:
        return {c.strip() for c in self.mms_tts_langs.split(",") if c.strip()}

    @property
    def has_parler(self) -> bool:
        return bool(self.parler_tts_url)

    def provider_status(self) -> dict:
        """What is configured. 'configured' means a key is set, not that the service has been verified."""
        return {
            "llm": {"configured": self.has_llm, "model": self.llm_model if self.has_llm else None,
                    "needs": None if self.has_llm else "Set LLM_API_KEY (a free Groq key from console.groq.com)."},
            "speech_to_text": {"configured": self.has_sarvam or self.has_groq_stt,
                               "providers": [p for p, ok in (("sarvam", self.has_sarvam), ("groq-whisper", self.has_groq_stt)) if ok],
                               "needs": None if self.has_sarvam else "Set SARVAM_API_KEY for Indian-language speech recognition."},
            "translation": {"configured": self.has_sarvam,
                            "needs": None if self.has_sarvam else "Set SARVAM_API_KEY. Without it only English works."},
            "text_to_speech": {"configured": self.has_sarvam or bool(self.mms_langs) or self.has_parler,
                               "providers": [p for p, ok in (("sarvam-bulbul", self.has_sarvam), ("mms", bool(self.mms_langs)),
                                                             ("parler", self.has_parler)) if ok]},
            "maps": {"configured": self.osm_enabled, "source": "OpenStreetMap" if self.osm_enabled else None},
        }


settings = Settings()


def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
