from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..permissions import PERM_ACTIVITY_READ
from ..security import get_settings, require_api_rate_limit, require_permission
from ..services.activity_service import read_activity


def create_activity_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_api_rate_limit)])

    @router.get("/activity")
    async def activity(
        limit: int = Query(default=100, ge=1, le=1000),
        server_id: str | None = Query(default=None),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_ACTIVITY_READ)),
    ):
        events = read_activity(current, identity, limit=limit, server_id=server_id)
        return {"ok": True, "items": events}

    @router.get("/servers/{server_id}/activity")
    async def server_activity(
        server_id: str,
        limit: int = Query(default=100, ge=1, le=1000),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_ACTIVITY_READ, server_scoped=True)),
    ):
        events = read_activity(current, identity, limit=limit, server_id=server_id)
        return {"ok": True, "server_id": server_id, "items": events}

    return router

