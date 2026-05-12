"""
API Key Authentication
=======================
Static API key guard for mutating / dangerous dashboard endpoints.

Configuration:
    Set env var DASHBOARD_API_KEY to a strong random secret.
    If the var is unset or empty the guard is bypassed (dev mode).

Usage:
    from api.auth import require_api_key
    from fastapi import Depends

    @app.post("/api/something-dangerous")
    async def handler(_: None = Depends(require_api_key)):
        ...
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_BYPASS_WARNED = False


async def require_api_key(api_key: str = Security(_API_KEY_HEADER)) -> None:
    """
    FastAPI dependency that validates the X-API-Key request header.

    - If DASHBOARD_API_KEY env var is unset/empty: allow all requests (dev mode).
    - If DASHBOARD_API_KEY is set: reject requests with missing/wrong key (HTTP 401).
    """
    global _BYPASS_WARNED
    expected = os.environ.get("DASHBOARD_API_KEY", "").strip()

    if not expected:
        if not _BYPASS_WARNED:
            logger.warning(
                "DASHBOARD_API_KEY is not set — all write endpoints are unprotected. "
                "Set this env var before exposing the dashboard to a network."
            )
            _BYPASS_WARNED = True
        return  # dev mode — no key required

    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
