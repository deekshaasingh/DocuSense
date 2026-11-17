"""
API-key auth guardrail (see docs/guardrails.md).

Deliberately simple: a static allowlist checked against the `X-API-Key`
header, not a full user/session system. That's the right scope for a
project at this stage -- it stops an open upload endpoint from being a
free-for-all, without inventing a login system nothing else here needs yet.

AUTH_ENABLED exists so tests, CI, and local single-user `docker compose up`
can turn it off explicitly and loudly (set the env var) rather than the
code silently skipping auth whenever no key happens to be configured.
"""
from fastapi import Header, HTTPException

from config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.AUTH_ENABLED:
        return
    if not settings.API_KEYS:
        # Auth is turned on but nobody configured a key -- fail closed with
        # a message that says why, instead of a confusing 401 with no keys
        # that could ever satisfy it.
        raise HTTPException(500, "AUTH_ENABLED=true but no API_KEYS configured")
    if x_api_key is None or x_api_key not in settings.API_KEYS:
        raise HTTPException(401, "missing or invalid X-API-Key header")
