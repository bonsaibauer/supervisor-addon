from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from ..clients.supervisor_rpc import SupervisorGatewayRPCClient
from ..config import Settings

POWER_ACTION_MAP = {
    "start": "server.start",
    "stop": "server.stop",
    "restart": "server.restart_safe",
    "restart_safe": "server.restart_safe",
}


class ActionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = SupervisorGatewayRPCClient(settings)

    async def ping(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.client.call_addon, "ping")

    async def reload_actions(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.client.call_addon, "reloadActions")

    async def list_servers(self) -> list[str]:
        return await asyncio.to_thread(self.client.call_addon, "listServers")

    async def get_server(self, server_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.client.call_addon, "getServer", server_id)

    async def list_actions(self, server_id: str) -> list[str]:
        return await asyncio.to_thread(self.client.call_addon, "listActions", server_id)

    async def run_action(self, server_id: str, action_id: str, wait: bool) -> dict[str, Any]:
        return await asyncio.to_thread(self.client.call_addon, "runAction", server_id, action_id, wait)

    async def run_power(self, server_id: str, signal: str, wait: bool) -> tuple[str, dict[str, Any]]:
        action_id = POWER_ACTION_MAP[signal]
        available = await self.list_actions(server_id)
        if action_id not in available:
            raise HTTPException(
                status_code=400,
                detail=f"mapped action '{action_id}' is not configured for server '{server_id}'",
            )

        result = await self.run_action(server_id, action_id, wait)
        return action_id, result

    async def run_backup(self, server_id: str, wait: bool) -> dict[str, Any]:
        available = await self.list_actions(server_id)
        if "backup.create" not in available:
            raise HTTPException(
                status_code=400,
                detail=f"backup action 'backup.create' is not configured for server '{server_id}'",
            )
        return await self.run_action(server_id, "backup.create", wait)

    async def run_update(self, server_id: str, mode: str, wait: bool) -> tuple[str, dict[str, Any]]:
        action_id = "update.force" if mode == "force" else "update.run"
        result = await self.run_action(server_id, action_id, wait)
        return action_id, result

