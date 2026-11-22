"""Gateway bearer-token authentication and admin scope.

Auth is enabled when ``GEOMIND_API_TOKEN`` is set, unless
``GEOMIND_AUTH=off`` (explicit local-dev opt-out). With no token configured the
gateway stays open for loopback development; task 1.2 binds it to 127.0.0.1 by
default so the open mode is never exposed on a LAN.

An optional ``GEOMIND_ADMIN_TOKEN`` grants the admin scope used by settings,
provider, environment and model-management routes. When it is not set the API
token also carries admin scope, so a single-token deployment keeps working.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException

log = logging.getLogger("geofront.auth")

API_TOKEN_ENV = "GEOMIND_API_TOKEN"
ADMIN_TOKEN_ENV = "GEOMIND_ADMIN_TOKEN"
AUTH_MODE_ENV = "GEOMIND_AUTH"

BearerHeader = Annotated[str | None, Header(alias="Authorization")]


def auth_enabled() -> bool:
    """Return True when requests must carry a bearer token."""
    if os.environ.get(AUTH_MODE_ENV, "").strip().lower() == "off":
        return False
    return bool(os.environ.get(API_TOKEN_ENV, "").strip())


def admin_token_configured() -> bool:
    return bool(os.environ.get(ADMIN_TOKEN_ENV, "").strip())


def _presented_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _matches(presented: str | None, expected: str) -> bool:
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented, expected)


def require_token(authorization: BearerHeader = None) -> None:
    """Require a valid bearer token on every ``/api/v1`` route when enabled."""
    if not auth_enabled():
        return
    presented = _presented_token(authorization)
    expected = os.environ[API_TOKEN_ENV].strip()
    # An admin token is also a valid bearer token; otherwise the admin scope
    # could never reach a route that has both dependencies attached.
    admin = os.environ.get(ADMIN_TOKEN_ENV, "").strip()
    if not _matches(presented, expected) and not (admin and _matches(presented, admin)):
        raise HTTPException(
            status_code=401,
            detail="unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(authorization: BearerHeader = None) -> None:
    """Require the admin-scoped token on privileged routes when enabled."""
    if not auth_enabled():
        return
    admin = os.environ.get(ADMIN_TOKEN_ENV, "").strip()
    expected = admin or os.environ[API_TOKEN_ENV].strip()
    if not _matches(_presented_token(authorization), expected):
        raise HTTPException(status_code=403, detail="forbidden")


# Attached to every API router at registration time in ``main.create_app``.
API_DEPS = [Depends(require_token)]
# Attached to privileged routers / endpoints in addition to API_DEPS.
ADMIN_DEPS = [Depends(require_admin)]
