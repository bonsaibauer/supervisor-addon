from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from urllib.parse import urlparse

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..permissions import PERM_ADMIN, PERM_NEWS_READ, PERM_SERVER_CONTROL, PERM_SERVER_READ
from ..security import get_settings, require_api_rate_limit, require_permission
from ..services.action_service import ActionService
from ..services.activity_service import write_audit_event
from ..services.rpc_errors import raise_http_from_rpc
from ..services.runtime_stats_service import read_runtime_stats
from ..services.update_install_service import install_update
from ..services.news_service import list_news_for_user, set_news_read_state
from ..services.update_service import get_update_status
from ..tls import renew_tls_certificate
from .schemas import InstallUpdateRequest, NewsReadRequest, RunActionRequest


def create_servers_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_api_rate_limit)])

    def _origin_from_request(request: Request) -> str | None:
        origin = (request.headers.get("origin") or "").strip()
        if origin:
            return origin
        referer = (request.headers.get("referer") or "").strip()
        if not referer:
            return None
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    @router.get("/meta")
    async def meta(
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_ADMIN)),
    ):
        exposed = {
            "rpc_url": current.rpc_url,
            "rpc_username": current.rpc_username,
            "rpc_password": "***" if current.rpc_password else None,
            "rpc_namespace": current.rpc_namespace,
            "api_token": "***" if current.api_token else None,
            "auth_secret": "***" if current.auth_secret else None,
            "auth_token_ttl_seconds": current.auth_token_ttl_seconds,
            "cors_origins": current.cors_origins,
            "cors_allow_credentials": current.cors_allow_credentials,
            "api_rate_limit_per_minute": current.api_rate_limit_per_minute,
            "login_rate_limit_per_minute": current.login_rate_limit_per_minute,
            "require_https": current.require_https,
            "insecure_http_local_only": current.insecure_http_local_only,
            "host": current.host,
            "port": current.port,
            "tls_certfile": current.tls_certfile,
            "tls_keyfile": current.tls_keyfile,
        }
        return {"ok": True, "settings": exposed}

    @router.post("/reload-actions")
    async def reload_actions(
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_ADMIN)),
    ):
        service = ActionService(current)
        try:
            result = await service.reload_actions()
            write_audit_event(
                current,
                "gateway.reload_actions",
                {
                    "actor": identity.username,
                    "result": result,
                },
            )
            return {"ok": True, "result": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers")
    async def list_servers(
        include_details: bool = Query(default=True),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_ADMIN)),
    ):
        service = ActionService(current)
        try:
            server_ids = await service.list_servers()

            if not include_details:
                return {"ok": True, "items": [{"server_id": sid} for sid in server_ids]}

            items: list[dict[str, Any]] = []
            for server_id in server_ids:
                try:
                    item = await service.get_server(server_id)
                    items.append(item)
                except Exception as error:  # noqa: BLE001
                    items.append({"server_id": server_id, "error": str(error)})

            return {"ok": True, "items": items}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}")
    async def get_server(
        server_id: str,
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_READ, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            result = await service.get_server(server_id)
            return {"ok": True, "item": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/actions")
    async def list_server_actions(
        server_id: str,
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_READ, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            actions = await service.list_actions(server_id)
            return {"ok": True, "server_id": server_id, "actions": actions}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/stats")
    async def server_stats(
        server_id: str,
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_READ, server_scoped=True)),
    ):
        return {"ok": True, "item": read_runtime_stats(server_id)}

    @router.get("/servers/{server_id}/news")
    async def server_news(
        server_id: str,
        request: Request,
        refresh: bool = Query(default=False),
        include_read: bool = Query(default=True),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_NEWS_READ, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            server = await service.get_server(server_id)
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)
        items = list_news_for_user(
            current,
            server_id=server_id,
            server=server,
            username=identity.username,
            force_refresh_updates=refresh,
            include_read=include_read,
            current_origin=_origin_from_request(request),
        )
        return {"ok": True, "server_id": server_id, "items": items}

    @router.post("/servers/{server_id}/news/{news_id}/read")
    async def set_server_news_read(
        server_id: str,
        news_id: str,
        body: NewsReadRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_NEWS_READ, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            await service.get_server(server_id)
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)
        set_news_read_state(
            current,
            username=identity.username,
            server_id=server_id,
            news_id=news_id,
            read=body.read,
        )
        return {"ok": True, "server_id": server_id, "news_id": news_id, "read": body.read}

    @router.get("/update/status")
    async def update_status(
        refresh: bool = Query(default=False),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_ADMIN)),
    ):
        status = get_update_status(current, force_refresh=refresh)
        return {"ok": True, **status.to_dict()}

    @router.post("/update/install")
    async def update_install(
        body: InstallUpdateRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_ADMIN)),
    ):
        result = install_update(current, requested_tag=body.tag, restart=body.restart)
        write_audit_event(
            current,
            "gateway.update_install",
            {
                "actor": identity.username,
                "requested_tag": body.tag,
                "restart": body.restart,
                "result": result.to_dict(),
            },
        )
        return result.to_dict()

    @router.post("/servers/{server_id}/tls/renew")
    async def tls_renew(
        server_id: str,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_CONTROL, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            await service.get_server(server_id)
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

        result = renew_tls_certificate(current)
        write_audit_event(
            current,
            "gateway.tls_renew",
            {
                "actor": identity.username,
                "server_id": server_id,
                "result": result,
            },
        )
        return {"ok": True, "server_id": server_id, **result}

    @router.post("/servers/{server_id}/actions/{action_id}")
    async def run_action(
        server_id: str,
        action_id: str,
        body: RunActionRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_SERVER_CONTROL, server_scoped=True)),
    ):
        service = ActionService(current)
        try:
            result = await service.run_action(server_id, action_id, body.wait)
            write_audit_event(
                current,
                "server.action",
                {
                    "server_id": server_id,
                    "action_id": action_id,
                    "wait": body.wait,
                    "result": result,
                    "actor": identity.username,
                },
            )
            return {"ok": True, "result": result}
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    return router
