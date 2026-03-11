from __future__ import annotations

from collections.abc import Iterable

PERM_ADMIN = "admin"
PERM_LOGS_READ = "logs.read"
PERM_ACTIVITY_READ = "activity.read"
PERM_SERVER_READ = "server.read"
PERM_SERVER_CONTROL = "server.control"
PERM_FILES_READ = "files.read"
PERM_FILES_WRITE = "files.write"
PERM_NEWS_READ = "news.read"

ALL_PERMISSIONS = {
    PERM_ADMIN,
    PERM_LOGS_READ,
    PERM_ACTIVITY_READ,
    PERM_SERVER_READ,
    PERM_SERVER_CONTROL,
    PERM_FILES_READ,
    PERM_FILES_WRITE,
    PERM_NEWS_READ,
}


def normalize_permissions(values: Iterable[str]) -> list[str]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return sorted(normalized)


def has_permission(permissions: Iterable[str], permission: str) -> bool:
    normalized = {str(value).strip() for value in permissions if str(value).strip()}
    return permission in normalized or PERM_ADMIN in normalized


def is_server_allowed(allowed_servers: list[str], server_id: str) -> bool:
    if "*" in allowed_servers:
        return True
    return server_id in allowed_servers
