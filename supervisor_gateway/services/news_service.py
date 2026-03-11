from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

from ..config import Settings
from ..tls import get_tls_certificate_expiry_days
from .update_service import get_update_status

_SUPPORT_PROMPT_INTERVAL_SECONDS = 90 * 24 * 60 * 60
_SUPPORT_PROMPT_URL = "https://buymeacoffee.com/bonsaibauer"


@dataclass(frozen=True)
class NewsAction:
    id: str
    label: str
    kind: str
    target: str | None = None
    label_values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "target": self.target,
            "label_values": self.label_values,
        }


@dataclass(frozen=True)
class NewsItem:
    id: str
    level: str
    title: str
    message: str
    category: str
    title_values: dict[str, Any] = field(default_factory=dict)
    message_values: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    actions: list[NewsAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "title_values": self.title_values,
            "message_values": self.message_values,
            "created_at": self.created_at,
            "actions": [action.to_dict() for action in self.actions],
        }


def _action_open_env() -> NewsAction:
    return NewsAction(id="open.env", label="news.action.open_env", kind="navigate", target="/env")


def _action_open_config() -> NewsAction:
    return NewsAction(id="open.config", label="news.action.open_config", kind="navigate", target="/config")


def _action_check_again() -> NewsAction:
    return NewsAction(id="update.check", label="news.action.check_again", kind="refresh_news")


def _action_release_notes(target: str | None) -> NewsAction:
    return NewsAction(id="update.release_notes", label="news.action.release_notes", kind="external", target=target)


def _action_releases(target: str | None) -> NewsAction:
    return NewsAction(id="update.release_notes", label="news.action.releases", kind="external", target=target)


def _action_install_update() -> NewsAction:
    return NewsAction(id="update.install", label="news.action.install_update", kind="install_update")


def _action_renew_certificate() -> NewsAction:
    return NewsAction(id="tls.renew", label="news.action.renew_certificate", kind="renew_tls_cert")


def _action_support_project() -> NewsAction:
    return NewsAction(
        id="support.buy_me_a_coffee",
        label="news.action.buy_me_a_coffee",
        kind="external",
        target=_SUPPORT_PROMPT_URL,
    )


def _required_action_label_key(required_action: str | None) -> str:
    mapping = {
        "browser_reload": "news.update.required_action.browser_reload",
        "gateway_restart": "news.update.required_action.gateway_restart",
        "container_recreate": "news.update.required_action.container_recreate",
    }
    return mapping.get((required_action or "").strip(), "news.update.required_action.container_recreate")


def _env_catalog_map(server: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = server.get("files")
    if not isinstance(files, dict):
        return {}
    raw_catalog = files.get("env_catalog")
    if not isinstance(raw_catalog, list):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for entry in raw_catalog:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not isinstance(key, str):
            continue
        result[key] = entry
    return result


def _env_is_set(catalog: dict[str, dict[str, Any]], key: str) -> bool:
    entry = catalog.get(key)
    if not entry:
        return False
    return bool(entry.get("is_set"))


def _tls_auto_generate_enabled() -> bool:
    raw = os.getenv("SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_origin(origin: str) -> str | None:
    parsed = urlparse((origin or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _load_news_state(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _store_news_state(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    except Exception:
        return


def _load_news_read_state(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _auth_user_must_change_password(auth_users_dir: str, username: str) -> bool:
    try:
        users_dir = Path(auth_users_dir)
        if not users_dir.is_dir():
            return False
        for path in sorted(users_dir.glob("*.json")):
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            name = str(payload.get("username", "")).strip()
            if name != username:
                continue
            return bool(payload.get("must_change_password", False))
    except Exception:
        return False
    return False


def _store_news_read_state(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    except Exception:
        return


def _user_server_read_ids(state: dict[str, Any], username: str, server_id: str) -> set[str]:
    users = state.get("users")
    if not isinstance(users, dict):
        return set()
    user_entry = users.get(username)
    if not isinstance(user_entry, dict):
        return set()
    server_entry = user_entry.get(server_id)
    if not isinstance(server_entry, list):
        return set()
    return {str(item).strip() for item in server_entry if isinstance(item, str) and str(item).strip()}


def _set_user_server_read_id(state: dict[str, Any], username: str, server_id: str, news_id: str, read: bool) -> None:
    users = state.get("users")
    if not isinstance(users, dict):
        users = {}
        state["users"] = users
    user_entry = users.get(username)
    if not isinstance(user_entry, dict):
        user_entry = {}
        users[username] = user_entry
    server_entry = user_entry.get(server_id)
    if not isinstance(server_entry, list):
        server_entry = []
        user_entry[server_id] = server_entry

    normalized = str(news_id).strip()
    existing = {str(item).strip() for item in server_entry if isinstance(item, str) and str(item).strip()}
    if read:
        existing.add(normalized)
    else:
        existing.discard(normalized)
    user_entry[server_id] = sorted(existing)


def _clear_news_id_for_all_users_on_server(state: dict[str, Any], server_id: str, news_id: str) -> bool:
    users = state.get("users")
    if not isinstance(users, dict):
        return False

    changed = False
    target_id = str(news_id).strip()
    if not target_id:
        return False

    for user_entry in users.values():
        if not isinstance(user_entry, dict):
            continue
        server_entry = user_entry.get(server_id)
        if not isinstance(server_entry, list):
            continue
        existing = [str(item).strip() for item in server_entry if isinstance(item, str) and str(item).strip()]
        filtered = [item for item in existing if item != target_id]
        if filtered != existing:
            user_entry[server_id] = sorted(set(filtered))
            changed = True

    return changed


def collect_news(
    settings: Settings,
    *,
    server_id: str,
    server: dict[str, Any],
    force_refresh_updates: bool = False,
    current_origin: str | None = None,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    catalog = _env_catalog_map(server)
    now = int(time.time())
    news_state_path = Path(settings.news_state_file)

    update_status = get_update_status(settings, force_refresh=force_refresh_updates)
    if update_status.error:
        items.append(
            NewsItem(
                id="update.check_failed",
                level="warning",
                title="news.item.update_check_failed.title",
                message="news.item.update_check_failed.message",
                message_values={"error": update_status.error},
                category="update",
                actions=[_action_check_again()],
            )
        )
    elif update_status.update_available:
        required_action = _required_action_label_key(update_status.required_action)
        steps_text = "\n".join(f"- {step}" for step in update_status.recommended_steps[:3]) if update_status.recommended_steps else ""
        detail_parts: list[str] = []
        if update_status.reason:
            detail_parts.append(update_status.reason)
        if steps_text:
            detail_parts.append(steps_text)
        details_block = ""
        if detail_parts:
            details_block = "\n" + "\n".join(detail_parts)

        actions = [_action_release_notes(update_status.release_url)]
        if update_status.required_action != "container_recreate":
            actions.append(_action_install_update())

        items.append(
            NewsItem(
                id="update.available",
                level="update",
                title="news.item.update_available.title",
                title_values={"latest_version": update_status.latest_version or "-"},
                message="news.item.update_available.message",
                message_values={
                    "current_version": update_status.current_version,
                    "required_action": required_action,
                    "details_block": details_block,
                },
                category="update",
                actions=actions,
            )
        )
    else:
        items.append(
            NewsItem(
                id="update.ok",
                level="update",
                title="news.item.update_ok.title",
                message="news.item.update_ok.message",
                message_values={"current_version": update_status.current_version},
                category="update",
                actions=[_action_releases(update_status.release_url)],
            )
        )

    for cron_key in ("BACKUP_CRON", "UPDATE_CRON", "RESTART_CRON"):
        if _env_is_set(catalog, cron_key):
            continue
        items.append(
            NewsItem(
                id=f"cron.{cron_key.lower()}",
                level="warning",
                title="news.item.cron_missing.title",
                title_values={"cron_key": cron_key},
                message="news.item.cron_missing.message",
                message_values={
                    "cron_key": cron_key,
                    "server_id": server_id,
                },
                category="automation",
                actions=[_action_open_env()],
            )
        )

    files = server.get("files")
    startup_config_path: str | None = None
    if isinstance(files, dict):
        startup_raw = files.get("startup_config")
        if isinstance(startup_raw, str) and startup_raw.strip():
            startup_config_path = startup_raw.strip()
    if startup_config_path and not Path(startup_config_path).is_file():
        items.append(
            NewsItem(
                id="startup.config.missing",
                level="error",
                title="news.item.startup_config_missing.title",
                message="news.item.startup_config_missing.message",
                message_values={"startup_config_path": startup_config_path},
                category="config",
                actions=[_action_open_config()],
            )
        )

    if "SUPERVISOR_GATEWAY_AUTH_SECRET" not in os.environ:
        items.append(
            NewsItem(
                id="security.auth_secret.ephemeral",
                level="warning",
                title="news.item.auth_secret_ephemeral.title",
                message="news.item.auth_secret_ephemeral.message",
                category="security",
                actions=[_action_open_env()],
            )
        )

    if "SUPERVISOR_GATEWAY_API_TOKEN" not in os.environ:
        items.append(
            NewsItem(
                id="security.api_token.ephemeral",
                level="warning",
                title="news.item.api_token_ephemeral.title",
                message="news.item.api_token_ephemeral.message",
                category="security",
                actions=[_action_open_env()],
            )
        )

    if _env_is_set(catalog, "AUTH_TEMPLATE_GUEST_ENABLED") and str(os.getenv("AUTH_TEMPLATE_GUEST_ENABLED", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        if _auth_user_must_change_password(settings.auth_users_dir, "guest"):
            items.append(
                NewsItem(
                    id="auth.guest.default_password_active",
                    level="warning",
                    title="news.item.auth_guest_default_password_active.title",
                    message="news.item.auth_guest_default_password_active.message",
                    category="security",
                    actions=[_action_open_env()],
                )
            )

    if _env_is_set(catalog, "AUTH_TEMPLATE_VIEWER_ENABLED") and str(os.getenv("AUTH_TEMPLATE_VIEWER_ENABLED", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        if _auth_user_must_change_password(settings.auth_users_dir, "viewer"):
            items.append(
                NewsItem(
                    id="auth.viewer.default_password_active",
                    level="warning",
                    title="news.item.auth_viewer_default_password_active.title",
                    message="news.item.auth_viewer_default_password_active.message",
                    category="security",
                    actions=[_action_open_env()],
                )
            )

    if not settings.require_https:
        if settings.insecure_http_local_only:
            items.append(
                NewsItem(
                    id="http.local_only",
                    level="info",
                    title="news.item.http_local_only.title",
                    message="news.item.http_local_only.message",
                    category="transport",
                    actions=[_action_open_env()],
                )
            )
        else:
            items.append(
                NewsItem(
                    id="http.remote_exposed",
                    level="error",
                    title="news.item.http_remote_exposed.title",
                    message="news.item.http_remote_exposed.message",
                    category="transport",
                    actions=[_action_open_env()],
                )
            )
    else:
        certfile = (settings.tls_certfile or "").strip()
        keyfile = (settings.tls_keyfile or "").strip()
        if certfile and keyfile and (not Path(certfile).is_file() or not Path(keyfile).is_file()):
            items.append(
                NewsItem(
                    id="https.cert_or_key_missing",
                    level="error",
                    title="news.item.https_cert_or_key_missing.title",
                    message="news.item.https_cert_or_key_missing.message",
                    category="transport",
                    actions=[_action_open_env()],
                )
            )
        elif _tls_auto_generate_enabled():
            items.append(
                NewsItem(
                    id="https.self_signed_expected",
                    level="warning",
                    title="news.item.https_self_signed_expected.title",
                    message="news.item.https_self_signed_expected.message",
                    category="transport",
                    actions=[_action_open_env()],
                )
            )

        expiry_days = get_tls_certificate_expiry_days(settings)
        if expiry_days is not None and expiry_days < 0:
            renew_actions = [_action_open_env()]
            if _tls_auto_generate_enabled():
                renew_actions.insert(0, _action_renew_certificate())
            items.append(
                NewsItem(
                    id="tls.cert_expired",
                    level="error",
                    title="news.item.tls_cert_expired.title",
                    message="news.item.tls_cert_expired.message",
                    message_values={"days": abs(expiry_days)},
                    category="transport",
                    actions=renew_actions,
                )
            )
        elif expiry_days is not None and expiry_days <= 30:
            renew_actions = [_action_open_env()]
            if _tls_auto_generate_enabled():
                renew_actions.insert(0, _action_renew_certificate())
            items.append(
                NewsItem(
                    id="tls.cert_expires_soon",
                    level="warning",
                    title="news.item.tls_cert_expires_soon.title",
                    message=(
                        "news.item.tls_cert_expires_soon_today.message"
                        if expiry_days == 0
                        else "news.item.tls_cert_expires_soon_days.message"
                    ),
                    message_values={"days": expiry_days},
                    category="transport",
                    actions=renew_actions,
                )
            )

    if "*" in settings.cors_origins:
        items.append(
            NewsItem(
                id="cors.wildcard_origin",
                level="warning",
                title="news.item.cors_wildcard_origin.title",
                message="news.item.cors_wildcard_origin.message",
                category="transport",
                actions=[_action_open_env()],
            )
        )
    elif settings.trust_proxy_headers:
        request_origin = _normalize_origin(current_origin or "")
        allowed_origins = {_normalize_origin(origin) for origin in settings.cors_origins}
        allowed_origins.discard(None)
        if request_origin and request_origin not in allowed_origins:
            items.append(
                NewsItem(
                    id="cors.domain_missing",
                    level="warning",
                    title="news.item.cors_domain_missing.title",
                    message="news.item.cors_domain_missing.message",
                    message_values={"request_origin": request_origin},
                    category="transport",
                    actions=[_action_open_env()],
                )
            )

    if settings.require_https and settings.trust_proxy_headers:
        items.append(
            NewsItem(
                id="https.proxy_headers_enabled",
                level="warning",
                title="news.item.https_proxy_headers_enabled.title",
                message="news.item.https_proxy_headers_enabled.message",
                category="transport",
                actions=[_action_open_env()],
            )
        )

    items.append(
        NewsItem(
            id="env.startup_only",
            level="info",
            title="news.item.env_startup_only.title",
            message="news.item.env_startup_only.message",
            category="configuration",
            actions=[_action_open_env()],
        )
    )

    items.append(
        NewsItem(
            id="roles.info",
            level="info",
            title="news.item.roles_info.title",
            message="news.item.roles_info.message",
            category="guidance",
        )
    )

    items.append(
        NewsItem(
            id="support.reminder",
            level="info",
            title="news.item.support_reminder.title",
            message="news.item.support_reminder.message",
            category="support",
            actions=[_action_support_project()],
        )
    )

    state = _load_news_state(news_state_path)
    last_reopen_raw = state.get("last_support_reopen_ts")
    last_reopen_ts = int(last_reopen_raw) if isinstance(last_reopen_raw, (int, float)) else 0
    if now - last_reopen_ts >= _SUPPORT_PROMPT_INTERVAL_SECONDS:
        read_state_path = Path(settings.news_read_state_file)
        read_state = _load_news_read_state(read_state_path)
        if _clear_news_id_for_all_users_on_server(read_state, server_id, "support.reminder"):
            _store_news_read_state(read_state_path, read_state)
        state["last_support_reopen_ts"] = now
        _store_news_state(news_state_path, state)

    level_order = {"error": 0, "warning": 1, "info": 2, "update": 3}
    items.sort(key=lambda item: (level_order.get(item.level, 3), -item.created_at, item.id))
    return items


def list_news_for_user(
    settings: Settings,
    *,
    server_id: str,
    server: dict[str, Any],
    username: str,
    force_refresh_updates: bool = False,
    include_read: bool = True,
    current_origin: str | None = None,
) -> list[dict[str, Any]]:
    items = collect_news(
        settings,
        server_id=server_id,
        server=server,
        force_refresh_updates=force_refresh_updates,
        current_origin=current_origin,
    )
    read_state = _load_news_read_state(Path(settings.news_read_state_file))
    read_ids = _user_server_read_ids(read_state, username, server_id)

    payload: list[dict[str, Any]] = []
    for item in items:
        is_read = item.id in read_ids
        if not include_read and is_read:
            continue
        row = item.to_dict()
        row["is_read"] = is_read
        payload.append(row)
    return payload


def set_news_read_state(settings: Settings, *, username: str, server_id: str, news_id: str, read: bool) -> None:
    normalized = str(news_id).strip()
    if not normalized:
        return
    read_state_path = Path(settings.news_read_state_file)
    state = _load_news_read_state(read_state_path)
    _set_user_server_read_id(state, username, server_id, normalized, read)
    _store_news_read_state(read_state_path, state)

