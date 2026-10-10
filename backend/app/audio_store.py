"""Short-lived in-memory audio store so generated speech can be served to the
browser. Nothing is written to disk; clips expire."""
from __future__ import annotations

import secrets
import time

TTL_SECONDS = 600
_store: dict[str, tuple[float, bytes, str]] = {}


def put(data: bytes, mime: str = "audio/wav") -> str:
    _purge()
    key = secrets.token_urlsafe(12)
    _store[key] = (time.time(), data, mime)
    return key


def get(key: str) -> tuple[bytes, str] | None:
    _purge()
    item = _store.get(key)
    return (item[1], item[2]) if item else None


def drop_many(keys: list[str]) -> None:
    for k in keys:
        _store.pop(k, None)


def _purge() -> None:
    cutoff = time.time() - TTL_SECONDS
    for k in [k for k, v in _store.items() if v[0] < cutoff]:
        _store.pop(k, None)
