from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

from hashtag_robotics.config import Settings

SESSION_COOKIE = "hashtag_session"
SESSION_HEADER = "x-hashtag-token"

# Reachable before a session exists: one reports liveness, the other mints it.
PUBLIC_API_PATHS = {"/api/health", "/api/session"}


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def host_of(value: str | None) -> str:
    """The bare hostname from a Host or Origin header, without port or brackets."""
    if not value:
        return ""
    candidate = value if "//" in value else f"//{value}"
    hostname = urlsplit(candidate).hostname
    return (hostname or "").strip("[]").lower()


class LocalAccessGuard:
    """Keeps a browser page on another origin out of the local control plane.

    Three independent gates, because each covers a case the others miss:
    a Host allowlist stops DNS rebinding, an Origin allowlist stops ordinary
    cross-site requests, and a per-run token stops anything on this machine
    that never loaded the dashboard.
    """

    def __init__(self, settings: Settings, token: str) -> None:
        self.settings = settings
        self.token = token

    def allowed_host(self, value: str | None) -> bool:
        host = host_of(value)
        if not host:
            return True
        allowed = {item.lower() for item in self.settings.allowed_hosts}
        if self.settings.frontend_dev_url:
            allowed.add(host_of(self.settings.frontend_dev_url))
        return host in allowed

    def allowed_origin(self, origin: str | None) -> bool:
        if not origin or origin == "null":
            return not origin
        return self.allowed_host(origin)

    def authorised(self, header: str | None, cookie: str | None) -> bool:
        presented = header or cookie or ""
        return secrets.compare_digest(presented, self.token)

    def reject(self, detail: str, status_code: int) -> JSONResponse:
        return JSONResponse({"detail": detail}, status_code=status_code)

    def check(self, request: Request) -> JSONResponse | None:
        if not self.allowed_host(request.headers.get("host")):
            return self.reject(
                f"Host '{request.headers.get('host')}' is not an allowed local host.",
                403,
            )
        if not self.allowed_origin(request.headers.get("origin")):
            return self.reject(
                f"Origin '{request.headers.get('origin')}' may not call this control plane.",
                403,
            )

        path = request.url.path
        needs_session = path.startswith("/api/") and path not in PUBLIC_API_PATHS
        if needs_session and not self.authorised(
            request.headers.get(SESSION_HEADER),
            request.cookies.get(SESSION_COOKIE),
        ):
            return self.reject("A dashboard session token is required.", 401)
        return None
