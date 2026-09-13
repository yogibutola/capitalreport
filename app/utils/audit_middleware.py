import logging
import os
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool

from app.utils.security import verify_token

logger = logging.getLogger(__name__)

# Requests we never audit: pre-flight, the docs, health-ish reads, and the AI
# quote poll. Sign-in is recorded explicitly by PBPlayerService (with the real
# actor email), so the middleware skips it to avoid double-counting.
_SKIP_PREFIXES = (
    "/api/v1/pickleball/quote",
)
_SKIP_EXACT = {
    "/", "/openapi.json", "/docs", "/redoc", "/favicon.ico",
    "/api/v1/signin", "/api/v1/demo-signin",
}
# Under this prefix only writes matter - a superadmin browsing the feed is noise.
_READONLY_SKIP_PREFIX = "/api/v1/platform-console"

# (METHOD, route template) -> human label for the activity feed.
_ACTION_MAP: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/signin"): "Signed in",
    ("POST", "/api/v1/demo-signin"): "Started a demo",
    ("POST", "/api/v1/signup"): "Registered as a player",
    ("POST", "/api/v1/signup/club"): "Registered a club",
    ("POST", "/api/v1/forgot-password"): "Requested a password reset",
    ("POST", "/api/v1/reset-password"): "Reset their password",
    ("POST", "/api/v1/change-password"): "Changed their password",
    ("PUT", "/api/v1/profile"): "Updated their profile",
    ("POST", "/api/v1/league"): "Created a league",
    ("DELETE", "/api/v1/league/{league_id}"): "Deleted a league",
    ("POST", "/api/v1/league/round"): "Advanced a league round",
    ("POST", "/api/v1/league/register"): "Joined a league",
    ("POST", "/api/v1/league/withdraw"): "Withdrew from a league",
    ("POST", "/api/v1/league/match/score"): "Submitted a match score",
    ("DELETE", "/api/v1/league/{league_id}/player"): "Left a league",
    ("POST", "/api/v1/tournament"): "Created a tournament",
    ("DELETE", "/api/v1/tournament/{tournament_id}"): "Deleted a tournament",
    ("POST", "/api/v1/tournament/register"): "Registered for a tournament",
    ("POST", "/api/v1/tournament/register/public"): "Registered for a tournament",
    ("POST", "/api/v1/tournament/{tournament_id}/draw"): "Generated a tournament draw",
    ("POST", "/api/v1/tournament/{tournament_id}/match/score"): "Submitted a tournament score",
    ("POST", "/api/v1/platform-console/clubs"): "Added a club",
    ("DELETE", "/api/v1/platform-console/clubs/{email}"): "Removed a club",
    ("POST", "/api/v1/platform-console/players"): "Added a player",
    ("DELETE", "/api/v1/platform-console/players/{email}"): "Removed a player",
}


def _extract_actor(request: Request) -> tuple[str, str | None]:
    """Best-effort (email, role) from the Bearer token; ('anonymous', None) otherwise."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return "anonymous", None
    try:
        payload = verify_token(header.split(" ", 1)[1].strip())
        return (payload.get("sub") or "anonymous").lower(), payload.get("role")
    except Exception:
        return "anonymous", None


def action_label(method: str, route: str | None, path: str) -> str:
    """Human label for a request; falls back to 'METHOD /path'."""
    if route and (method, route) in _ACTION_MAP:
        return _ACTION_MAP[(method, route)]
    if (method, path) in _ACTION_MAP:
        return _ACTION_MAP[(method, path)]
    return f"{method} {path}"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Records every mutating (and most read) ``/api/v1`` request into ``audit_log``.

    Disabled - a transparent pass-through - when ``AUDIT_LOG_ENABLED`` is not
    ``"true"`` or when the audit store cannot be constructed (no ``MONGO_URI``).
    An audit write failure is logged once and never affects the response.
    """

    def __init__(self, app):
        super().__init__(app)
        self._store = None
        self._disabled = os.getenv("AUDIT_LOG_ENABLED", "true").lower() != "true"
        if self._disabled:
            logger.info("Audit logging disabled via AUDIT_LOG_ENABLED")

    def _get_store(self):
        if self._store is None:
            from app.store.mongo.pb_audit_store import PBAuditStore
            self._store = PBAuditStore()
        return self._store

    def _should_audit(self, request: Request) -> bool:
        if self._disabled or request.method == "OPTIONS":
            return False
        path = request.url.path
        if path in _SKIP_EXACT or not path.startswith("/api/v1/"):
            return False
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return False
        if path.startswith(_READONLY_SKIP_PREFIX) and request.method in ("GET", "HEAD"):
            return False
        return True

    async def dispatch(self, request: Request, call_next):
        if not self._should_audit(request):
            return await call_next(request)

        actor, role = _extract_actor(request)
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)

        route = getattr(request.scope.get("route"), "path", None)
        entry = {
            "ts": datetime.now(timezone.utc),
            "actor": actor,
            "actor_role": role,
            "method": request.method,
            "path": request.url.path,
            "route": route,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "action": action_label(request.method, route, request.url.path),
            "client_ip": request.client.host if request.client else None,
            "error": None if response.status_code < 400 else f"HTTP {response.status_code}",
        }

        try:
            await run_in_threadpool(self._get_store().record, entry)
        except Exception:
            logger.warning("Audit log write failed; disabling audit logging", exc_info=True)
            self._disabled = True

        return response
