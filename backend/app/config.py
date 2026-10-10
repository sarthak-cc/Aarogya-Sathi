"""Central configuration. Every external service is optional: when a key is
missing, the matching stage falls back to demo behaviour and says so."""
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


@dataclass
class Settings:
    # Sarvam AI (STT for Assamese/Bodo/Manipuri/Nepali, translation, Hindi/Bengali TTS)
    sarvam_api_key: str = field(default_factory=lambda: _env("SARVAM_API_KEY"))
    sarvam_base_url: str = field(default_factory=lambda: _env("SARVAM_BASE_URL", "https://api.sarvam.ai"))
    sarvam_stt_model: str = field(default_factory=lambda: _env("SARVAM_STT_MODEL", "saaras:v4"))
    sarvam_translate_model: str = field(default_factory=lambda: _env("SARVAM_TRANSLATE_MODEL", "sarvam-translate:v1"))
    sarvam_tts_model: str = field(default_factory=lambda: _env("SARVAM_TTS_MODEL", "bulbul:v3"))
    sarvam_tts_speaker: str = field(default_factory=lambda: _env("SARVAM_TTS_SPEAKER", "priya"))

    # Any OpenAI-compatible chat API: Groq (default), OpenRouter, Ollama, vLLM...
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "https://api.groq.com/openai/v1"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "llama-3.3-70b-versatile"))

    # Groq Whisper fallback STT (English/Hindi/Bengali/Nepali)
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY") or _env("LLM_API_KEY"))
    groq_stt_model: str = field(default_factory=lambda: _env("GROQ_STT_MODEL", "whisper-large-v3-turbo"))

    # Self-hosted AI4Bharat Indic Parler-TTS (see tts_server/), e.g. an ngrok URL
    parler_tts_url: str = field(default_factory=lambda: _env("PARLER_TTS_URL"))

    # Twilio (optional real-phone mode)
    twilio_auth_token: str = field(default_factory=lambda: _env("TWILIO_AUTH_TOKEN"))
    twilio_account_sid: str = field(default_factory=lambda: _env("TWILIO_ACCOUNT_SID"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL"))
    twilio_validate_signature: bool = field(
        default_factory=lambda: _env("TWILIO_VALIDATE_SIGNATURE", "true").lower() != "false"
    )

    http_timeout: float = field(default_factory=lambda: float(_env("HTTP_TIMEOUT", "20")))
    session_ttl_seconds: int = field(default_factory=lambda: int(_env("SESSION_TTL_SECONDS", "1800")))

    @property
    def has_sarvam(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_groq_stt(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_parler(self) -> bool:
        return bool(self.parler_tts_url)

    @property
    def has_twilio(self) -> bool:
        return bool(self.twilio_auth_token and self.public_base_url)

    def mode_summary(self) -> dict:
        return {
            "stt": "sarvam" if self.has_sarvam else ("groq-whisper" if self.has_groq_stt else "demo (type or browser speech)"),
            "translation": "sarvam" if self.has_sarvam else "demo phrasebook",
            "llm": f"live ({self.llm_model})" if self.has_llm else "demo answers (labelled)",
            "tts_indic": "parler" if self.has_parler else "not configured",
            "tts_hi_bn": "sarvam" if self.has_sarvam else "browser voice if available",
            "telephony": "twilio" if self.has_twilio else "awaiting configuration (simulator only)",
        }


settings = Settings()


def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
