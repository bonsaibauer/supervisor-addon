from __future__ import annotations

from .config import (
    ActionConfig,
    ActionDefinition,
    ServerDefinition,
    load_action_config_from_env,
)


class ActionRegistry:
    def __init__(self):
        self.config: ActionConfig = ActionConfig(version=1, servers={})
        self.reload()

    def reload(self) -> None:
        self.config = load_action_config_from_env()

    def list_servers(self) -> list[str]:
        return sorted(self.config.servers.keys())

    def get_server(self, server_id: str) -> ServerDefinition | None:
        return self.config.servers.get(server_id)

    def list_actions(self, server_id: str) -> list[str]:
        server = self.get_server(server_id)
        if not server:
            return []
        return sorted(server.actions.keys())

    def get_action(self, server_id: str, action_id: str) -> ActionDefinition | None:
        server = self.get_server(server_id)
        if not server:
            return None
        return server.actions.get(action_id)
