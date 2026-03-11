from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import time
from typing import Any

from fastapi import HTTPException

from ..auth import AuthenticatedIdentity
from ..permissions import is_server_allowed
from ..config import Settings


def read_audit_events(
    audit_log_path: str | None,
    limit: int = 100,
    server_id: str | None = None,
) -> list[dict[str, Any]]:
    if not audit_log_path:
        return []

    path = Path(audit_log_path)
    if not path.exists():
        return []

    safe_limit = max(1, min(limit, 1000))
    window = deque(maxlen=max(safe_limit * 8, 100))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line:
                window.append(line)

    result: list[dict[str, Any]] = []
    for line in reversed(window):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if server_id:
            payload = event.get("payload", {})
            if payload.get("server_id") != server_id:
                continue

        result.append(event)
        if len(result) >= safe_limit:
            break

    return result


def write_audit_event(
    settings: Settings,
    event: str,
    payload: dict[str, Any],
) -> None:
    if not settings.audit_log_path:
        return

    line = {
        "ts": int(time.time()),
        "event": event,
        "payload": payload,
    }
    try:
        path = Path(settings.audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")
    except Exception:
        # Never fail a successful API operation because activity logging failed.
        return


def is_global_scope(identity: AuthenticatedIdentity) -> bool:
    return "*" in identity.allowed_servers


def read_activity(
    settings: Settings,
    identity: AuthenticatedIdentity,
    *,
    limit: int,
    server_id: str | None,
):
    if server_id and not is_server_allowed(identity.allowed_servers, server_id):
        raise HTTPException(
            status_code=403,
            detail=f"server '{server_id}' is not in allowed scope",
        )

    if not server_id and not is_global_scope(identity):
        raise HTTPException(
            status_code=403,
            detail="non-admin users must provide server_id when reading global activity",
        )

    return read_audit_events(settings.audit_log_path, limit=limit, server_id=server_id)
