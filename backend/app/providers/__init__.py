"""External AI providers behind small, swappable async functions.

Every failure becomes a ProviderError with a `kind` the UI can explain honestly:
  not_configured | auth | rate_limited | timeout | unavailable | bad_response | unsupported
"""
from __future__ import annotations

from typing import Optional

import httpx

from .. import config

MESSAGES = {
    "not_configured": "{provider} is not configured on the server.",
    "auth": "{provider} rejected the API key. Check the key in the server settings.",
    "rate_limited": "{provider} free-tier limit reached. Please wait a little and try again.",
    "timeout": "{provider} took too long to respond. Please try again.",
    "unavailable": "{provider} is not reachable right now. Please try again shortly.",
    "bad_response": "{provider} sent an unexpected reply.",
    "unsupported": "{provider} does not support this language.",
    "model_unavailable": "{provider} could not find the configured model. Check the model name on the server.",
}


class ProviderError(Exception):
    def __init__(self, provider: str, kind: str, detail: str = "", retry_after: Optional[float] = None):
        self.provider, self.kind, self.detail, self.retry_after = provider, kind, detail, retry_after
        super().__init__(f"{provider}: {kind}{' (' + detail + ')' if detail else ''}")

    def public(self) -> dict:
        return {"provider": self.provider, "kind": self.kind,
                "message": MESSAGES.get(self.kind, "{provider} failed.").format(provider=self.provider),
                "retry_after": self.retry_after}


def client(timeout: Optional[float] = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout or config.settings.http_timeout)


def raise_for(resp: httpx.Response, provider: str) -> None:
    """Map HTTP failures to error kinds. Never echo bodies: they can contain health details."""
    code = resp.status_code
    if code < 400:
        return
    if code in (401, 403):
        raise ProviderError(provider, "auth", f"HTTP {code}")
    if code == 429:
        retry = resp.headers.get("retry-after")
        try:
            retry_after = float(retry) if retry else None
        except ValueError:
            retry_after = None
        raise ProviderError(provider, "rate_limited", "HTTP 429", retry_after)
    if code >= 500:
        raise ProviderError(provider, "unavailable", f"HTTP {code}")
    raise ProviderError(provider, "bad_response", f"HTTP {code}")


async def send(provider: str, method: str, url: str, timeout: Optional[float] = None, **kwargs) -> httpx.Response:
    """One HTTP call with uniform error mapping."""
    try:
        async with client(timeout) as c:
            resp = await c.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise ProviderError(provider, "timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(provider, "unavailable", type(exc).__name__) from exc
    raise_for(resp, provider)
    return resp


def json_of(resp: httpx.Response, provider: str):
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(provider, "bad_response", "not JSON") from exc
