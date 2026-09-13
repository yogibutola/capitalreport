from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """One recorded user action, as surfaced in the platform activity feed.

    ``actor`` is the account email taken from the request's JWT, or ``"anonymous"``
    when the request carried no valid token (e.g. sign-in, public registration).
    """
    ts: datetime = Field(..., description="When the request completed (UTC)")
    actor: str = Field(..., description="Account email, or 'anonymous'")
    actor_role: Optional[str] = Field(None, description="'player' | 'admin' | 'superadmin'")
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Request path")
    route: Optional[str] = Field(None, description="Matched route template, e.g. /api/v1/league/{league_id}")
    status_code: int = Field(..., description="HTTP status of the response")
    duration_ms: int = Field(..., description="Server-side handling time in milliseconds")
    action: str = Field(..., description="Human-readable label, e.g. 'Created a league'")
    client_ip: Optional[str] = Field(None, description="Client IP, if known")
    error: Optional[str] = Field(None, description="Error detail when status_code >= 400")


class AuditEntryResponse(AuditEntry):
    """Audit entry as returned by the platform console API."""
    id: Optional[str] = Field(None, description="Mongo document id")


class PlatformMetrics(BaseModel):
    """Aggregate counters shown on the platform console header."""
    total_clubs: int = 0
    total_players: int = 0
    total_leagues: int = 0
    total_tournaments: int = 0
    actions_24h: int = 0
    active_actors_24h: int = 0
    signins_7d: int = 0
    errors_24h: int = 0
