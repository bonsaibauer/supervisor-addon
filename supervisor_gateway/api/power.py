from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..permissions import PERM_SERVER_CONTROL
from ..security import get_settings, require_api_rate_limit, require_permission
from ..services.action_service import ActionService
from ..services.activity_service import write_audit_event
from ..services.rpc_errors import raise_http_from_rpc
from .schemas import PowerRequest, RunActionRequest, UpdateRequest


def create_power_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_api_rate_limit)])

    @router.post("/servers/{server_id}/power")
    async def power_action(
        server_id: str,
        body: PowerRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_CONTROL, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            action_id, result = await service.run_power(server_id, body.signal, body.wait)
            write_audit_event(
                current,
                "server.action",
                {
                    "server_id": server_id,
                    "signal": body.signal,
                    "action_id": action_id,
                    "wait": body.wait,
                    "result": result,
                    "actor": identity.username,
                },
            )
            return {"ok": True, "signal": body.signal, "action_id": action_id, "result": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/backups")
    async def create_backup(
        server_id: str,
        body: RunActionRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_CONTROL, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            result = await service.run_backup(server_id, body.wait)
            write_audit_event(
                current,
                "server.action",
                {
                    "server_id": server_id,
                    "action_id": "backup.create",
                    "wait": body.wait,
                    "result": result,
                    "actor": identity.username,
                },
            )
            return {"ok": True, "action_id": "backup.create", "result": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/updates")
    async def run_update(
        server_id: str,
        body: UpdateRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_CONTROL, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            action_id, result = await service.run_update(server_id, body.mode, body.wait)
            write_audit_event(
                current,
                "server.action",
                {
                    "server_id": server_id,
                    "mode": body.mode,
                    "action_id": action_id,
                    "wait": body.wait,
                    "result": result,
                    "actor": identity.username,
                },
            )
            return {"ok": True, "action_id": action_id, "result": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    return router
