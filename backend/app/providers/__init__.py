"""External AI providers behind small, swappable async functions."""
from __future__ import annotations

import httpx

from .. import config


class ProviderUnavailable(Exception):
    """No configured provider can serve this request (e.g. missing API key)."""


class ProviderError(Exception):
    """A configured provider failed (timeout, 4xx/5xx, bad payload)."""


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=config.settings.http_timeout)


def raise_for(resp: httpx.Response, provider: str) -> None:
    if resp.status_code >= 400:
        # Never echo request bodies (they can contain health details) into errors/logs.
        raise ProviderError(f"{provider} returned HTTP {resp.status_code}")
