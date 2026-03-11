from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..permissions import PERM_LOGS_READ
from ..security import get_settings, require_api_rate_limit, require_permission
from ..services import log_stream_service
from ..services.rpc_errors import raise_http_from_rpc


def create_logs_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_api_rate_limit)])

    @router.get("/servers/{server_id}/logs/{channel}")
    async def read_log(
        server_id: str,
        channel: str,
        offset: int = Query(default=0),
        length: int = Query(default=4096),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_LOGS_READ, server_scoped=True)),
    ):
        try:
            return await log_stream_service.read_log(current, server_id, channel, offset, length)
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/logs/{channel}/tail")
    async def tail_log(
        server_id: str,
        channel: str,
        offset: int = Query(default=0),
        length: int = Query(default=4096),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_LOGS_READ, server_scoped=True)),
    ):
        try:
            return await log_stream_service.tail_log(current, server_id, channel, offset, length)
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/logs/{channel}/stream")
    async def stream_log(
        request: Request,
        server_id: str,
        channel: str,
        offset: int = Query(default=0),
        chunk_bytes: int | None = Query(default=None),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_LOGS_READ, server_scoped=True)),
    ):
        return StreamingResponse(
            log_stream_service.stream_events(
                request=request,
                settings=current,
                server_id=server_id,
                channel=channel,
                offset=offset,
                chunk_bytes=chunk_bytes,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router

