"""Conversations, kept in memory only.

A conversation holds the chosen language, a short English history for
follow-up questions, and generated audio keys. Nothing is written to disk and
everything expires after SESSION_TTL_SECONDS of inactivity or on delete.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

from . import audio_store, config


@dataclass
class Conversation:
    id: str
    language: str
    history: list[dict] = field(default_factory=list)  # English turns for LLM context
    last_question: Optional[str] = None  # caller's words, for "simpler words"
    audio_keys: list[str] = field(default_factory=list)
    updated: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated = time.time()

    def remember(self, question_en: str, answer_en: str) -> None:
        self.history = (self.history + [{"role": "user", "content": question_en},
                                        {"role": "assistant", "content": answer_en}])[-12:]


_store: dict[str, Conversation] = {}


def create(language: str) -> Conversation:
    _purge()
    c = Conversation(id=secrets.token_urlsafe(9), language=language)
    _store[c.id] = c
    return c


def get(conv_id: str) -> Optional[Conversation]:
    _purge()
    c = _store.get(conv_id)
    if c:
        c.touch()
    return c


def delete(conv_id: str) -> bool:
    c = _store.pop(conv_id, None)
    if c:
        audio_store.drop_many(c.audio_keys)
    return c is not None


def clear() -> None:
    for cid in list(_store):
        delete(cid)


def _purge() -> None:
    cutoff = time.time() - config.settings.session_ttl_seconds
    for cid in [k for k, v in _store.items() if v.updated < cutoff]:
        delete(cid)
