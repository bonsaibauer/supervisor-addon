from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from supervisor.http import NOT_DONE_YET
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.xmlrpc import Faults, RPCError

from .action_registry import ActionRegistry

API_VERSION = "1.0"


class SupervisorAddonRPCInterface:
    def __init__(self, supervisord, **config: Any):
        self.supervisord = supervisord
        self.config = config
        self._supervisor = SupervisorNamespaceRPCInterface(supervisord)
        if config.get("actions_config"):
            raise ValueError(
                "actions_config is no longer supported. Configure actions via SUPERVISOR_ADDON_* environment variables."
            )
        self._registry = ActionRegistry()
        self._audit_log_path = config.get("audit_log")

    def getAPIVersion(self) -> str:
        return API_VERSION

    def ping(self) -> dict[str, Any]:
        return {"ok": True, "api_version": API_VERSION}

    def reloadActions(self) -> dict[str, Any]:
        self._registry.reload()
        return {
            "ok": True,
            "servers": self._registry.list_servers(),
            "count": len(self._registry.list_servers()),
        }

    def listServers(self) -> list[str]:
        return self._registry.list_servers()

    def listActions(self, server_id: str) -> list[str]:
        self._server_or_fault(server_id)
        return self._registry.list_actions(server_id)

    def getServer(self, server_id: str) -> dict[str, Any]:
        # Keep env catalog and startup JSON derived values current without
        # requiring explicit reloadActions or process restart.
        self._registry.reload()
        server = self._server_or_fault(server_id)
        runtime_program = server.runtime_program()

        process_info: dict[str, Any] | None = None
        if runtime_program:
            try:
                process_info = self._supervisor.getProcessInfo(runtime_program)
            except RPCError as error:
                # If the mapping points to a non-existing program, keep returning
                # config data and simply omit process runtime details.
                if error.code != Faults.BAD_NAME:
                    raise

        response = {
            "server_id": server.server_id,
            "actions": {
                action_id: {
                    "type": action.action_type,
                    "program": action.program,
                }
                for action_id, action in server.actions.items()
            },
            "logs": dict(server.logs),
            "files": dict(server.files),
            "runtime_program": runtime_program,
            "process_info": process_info,
        }
        return self._xmlrpc_safe(response)

    def getAllProcessInfo(self) -> list[dict[str, Any]]:
        return self._supervisor.getAllProcessInfo()

    def runAction(self, server_id: str, action_id: str, wait: bool = False):
        server = self._server_or_fault(server_id)
        action = self._action_or_fault(server_id, action_id)

        result_or_callback = self._execute_action(action.action_type, action.program, wait=wait)
        meta = {
            "server_id": server.server_id,
            "action_id": action.action_id,
            "type": action.action_type,
            "program": action.program,
            "wait": bool(wait),
        }

        if callable(result_or_callback):
            def deferred():
                value = result_or_callback()
                if value is NOT_DONE_YET:
                    return NOT_DONE_YET

                response = {
                    "ok": True,
                    **meta,
                    "result": value,
                }
                self._audit("action.run", response)
                return response

            deferred.delay = getattr(result_or_callback, "delay", 0.05)
            deferred.rpcinterface = self
            return deferred

        response = {
            "ok": True,
            **meta,
            "result": result_or_callback,
        }
        self._audit("action.run", response)
        return response

    def readServerStdoutLog(self, server_id: str, offset: int, length: int) -> str:
        program = self._log_program(server_id, "stdout")
        return self._supervisor.readProcessStdoutLog(program, offset, length)

    def tailServerStdoutLog(self, server_id: str, offset: int, length: int) -> list[Any]:
        program = self._log_program(server_id, "stdout")
        return self._supervisor.tailProcessStdoutLog(program, offset, length)

    def readServerStderrLog(self, server_id: str, offset: int, length: int) -> str:
        program = self._log_program(server_id, "stderr")
        return self._supervisor.readProcessStderrLog(program, offset, length)

    def tailServerStderrLog(self, server_id: str, offset: int, length: int) -> list[Any]:
        program = self._log_program(server_id, "stderr")
        return self._supervisor.tailProcessStderrLog(program, offset, length)

    def _execute_action(self, action_type: str, program: str, wait: bool):
        if action_type == "supervisor.start":
            return self._supervisor.startProcess(program, wait=wait)
        if action_type == "supervisor.stop":
            return self._supervisor.stopProcess(program, wait=wait)
        if action_type == "supervisor.restart":
            # For restart, we keep it simple and robust for game-server wrappers:
            # try stopping first, then start. If already stopped, start anyway.
            try:
                self._supervisor.stopProcess(program, wait=False)
            except RPCError as error:
                if error.code != Faults.NOT_RUNNING:
                    raise
            return self._supervisor.startProcess(program, wait=wait)

        raise RPCError(Faults.BAD_ARGUMENTS, f"unsupported action type '{action_type}'")

    def _server_or_fault(self, server_id: str):
        server = self._registry.get_server(server_id)
        if not server:
            raise RPCError(Faults.BAD_NAME, f"server '{server_id}' not found")
        return server

    def _action_or_fault(self, server_id: str, action_id: str):
        action = self._registry.get_action(server_id, action_id)
        if not action:
            raise RPCError(Faults.BAD_NAME, f"action '{server_id}.{action_id}' not found")
        return action

    def _log_program(self, server_id: str, channel: str) -> str:
        server = self._server_or_fault(server_id)
        key = f"{channel}_program"
        program = server.logs.get(key) or server.runtime_program()
        if not program:
            raise RPCError(
                Faults.BAD_NAME, f"no {channel} log program configured for server '{server_id}'"
            )
        return program

    def _audit(self, event: str, payload: dict[str, Any]) -> None:
        if not self._audit_log_path:
            return
        line = {
            "ts": int(time.time()),
            "event": event,
            "payload": payload,
        }
        try:
            audit_file = Path(self._audit_log_path)
            audit_file.parent.mkdir(parents=True, exist_ok=True)
            with audit_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, separators=(",", ":")) + "\n")
        except Exception:
            # Never fail the control operation because of audit logging.
            return

    def _xmlrpc_safe(self, value: Any) -> Any:
        """Convert unsupported XML-RPC `None` values into empty strings recursively."""
        if value is None:
            return ""
        if isinstance(value, dict):
            return {str(key): self._xmlrpc_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._xmlrpc_safe(item) for item in value]
        if isinstance(value, tuple):
            return [self._xmlrpc_safe(item) for item in value]
        return value


def make_supervisor_rpcinterface(supervisord, **config):
    return SupervisorAddonRPCInterface(supervisord, **config)
