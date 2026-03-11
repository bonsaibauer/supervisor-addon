from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any

KNOWN_ENV_KEYS: tuple[str, ...] = (
    "SUPERVISOR_GATEWAY_API_TOKEN",
    "SUPERVISOR_GATEWAY_AUTH_SECRET",
    "SUPERVISOR_GATEWAY_STATE_DIR",
    "SUPERVISOR_GATEWAY_AUTH_USERS_DIR",
    "SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR",
    "SUPERVISOR_GATEWAY_NEWS_STATE_FILE",
    "SUPERVISOR_GATEWAY_NEWS_READ_STATE_FILE",
    "SUPERVISOR_GATEWAY_HOST",
    "SUPERVISOR_GATEWAY_PORT",
    "SUPERVISOR_GATEWAY_PANEL_DIR",
    "SUPERVISOR_GATEWAY_RPC_URL",
    "SUPERVISOR_GATEWAY_RPC_USERNAME",
    "SUPERVISOR_GATEWAY_RPC_PASSWORD",
    "SUPERVISOR_GATEWAY_RPC_NAMESPACE",
    "SUPERVISOR_GATEWAY_REQUIRE_HTTPS",
    "SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS",
    "SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY",
    "SUPERVISOR_GATEWAY_CORS_ORIGINS",
    "SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE",
    "SUPERVISOR_GATEWAY_TLS_AUTO_LOCAL_IPS",
    "SUPERVISOR_GATEWAY_TLS_AUTO_PUBLIC_IP",
    "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_TIMEOUT_SECONDS",
    "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_PROVIDERS",
    "SUPERVISOR_GATEWAY_TLS_EXTRA_SANS",
    "SUPERVISOR_GATEWAY_TLS_CERTFILE",
    "SUPERVISOR_GATEWAY_TLS_KEYFILE",
    "SUPERVISOR_GATEWAY_AUDIT_LOG_PATH",
    "SUPERVISOR_GATEWAY_SUPERVISOR_LOG_FILE",
    "SUPERVISOR_GATEWAY_SUPERVISOR_TAIL_LINES",
    "SUPERVISOR_ADDON_SERVER_ID",
    "SUPERVISOR_ADDON_ACTION_SERVER_START_PROGRAM",
    "SUPERVISOR_ADDON_ACTION_SERVER_STOP_PROGRAM",
    "SUPERVISOR_ADDON_ACTION_SERVER_RESTART_PROGRAM",
    "SUPERVISOR_ADDON_ACTION_BACKUP_CREATE_PROGRAM",
    "SUPERVISOR_ADDON_ACTION_UPDATE_RUN_PROGRAM",
    "SUPERVISOR_ADDON_ACTION_UPDATE_FORCE_PROGRAM",
    "SUPERVISOR_ADDON_FILES_ROOTS",
    "SUPERVISOR_ADDON_FILES_WRITABLE",
    "SUPERVISOR_ADDON_BACKUP_DIR",
    "SUPERVISOR_ADDON_STARTUP_CONFIG",
    "SUPERVISOR_ADDON_STARTUP_FILES",
    "SUPERVISOR_ADDON_ENV_KEYS",
    "SUPERVISOR_ADDON_ENV_EXPOSE_VALUES",
    "SUPERVISOR_ADDON_LOG_STDOUT_PROGRAM",
    "SUPERVISOR_ADDON_LOG_STDERR_PROGRAM",
    "SERVER_NAME",
    "SERVER_SLOT_COUNT",
    "SERVER_QUERYPORT",
    "SERVER_PORT",
    "SERVER_IP",
    "SERVER_SAVE_DIR",
    "SERVER_LOG_DIR",
    "SERVER_VOICE_CHAT_MODE",
    "SERVER_ENABLE_VOICE_CHAT",
    "SERVER_ENABLE_TEXT_CHAT",
    "SERVER_PASSWORD",
    "PUID",
    "PGID",
    "UPDATE_CRON",
    "UPDATE_CHECK_PLAYERS",
    "BACKUP_CRON",
    "BACKUP_DIR",
    "BACKUP_MAX_COUNT",
    "RESTART_CRON",
    "RESTART_CHECK_PLAYERS",
    "GAME_BRANCH",
    "STEAMCMD_ARGS",
    "BOOTSTRAP_HOOK",
    "UPDATE_PRE_HOOK",
    "UPDATE_POST_HOOK",
    "BACKUP_PRE_HOOK",
    "BACKUP_POST_HOOK",
    "RESTART_PRE_HOOK",
    "RESTART_POST_HOOK",
    "STEAM_API_PUBLIC_IP",
    "STEAM_API_KEY",
    "WINEDEBUG",
    "STEAM_COMPAT_DATA_PATH",
    "SERVER_GS_PRESET",
    "SERVER_GS_PLAYER_HEALTH_FACTOR",
    "SERVER_GS_PLAYER_MANA_FACTOR",
    "SERVER_GS_PLAYER_STAMINA_FACTOR",
    "SERVER_GS_PLAYER_BODY_HEAT_FACTOR",
    "SERVER_GS_PLAYER_DIVING_TIME_FACTOR",
    "SERVER_GS_ENABLE_DURABILITY",
    "SERVER_GS_ENABLE_STARVING_DEBUFF",
    "SERVER_GS_FOOD_BUFF_DURATION_FACTOR",
    "SERVER_GS_FROM_HUNGER_TO_STARVING",
    "SERVER_GS_SHROUD_TIME_FACTOR",
    "SERVER_GS_ENABLE_GLIDER_TURBULENCES",
    "SERVER_GS_WEATHER_FREQUENCY",
    "SERVER_GS_FISHING_DIFFICULTY",
    "SERVER_GS_RANDOM_SPAWNER_AMOUNT",
    "SERVER_GS_MINING_DAMAGE_FACTOR",
    "SERVER_GS_PLANT_GROWTH_SPEED_FACTOR",
    "SERVER_GS_RESOURCE_DROP_STACK_AMOUNT_FACTOR",
    "SERVER_GS_FACTORY_PRODUCTION_SPEED_FACTOR",
    "SERVER_GS_PERK_UPGRADE_RECYCLING_FACTOR",
    "SERVER_GS_PERK_COST_FACTOR",
    "SERVER_GS_EXPERIENCE_COMBAT_FACTOR",
    "SERVER_GS_EXPERIENCE_MINING_FACTOR",
    "SERVER_GS_EXPERIENCE_EXPLORATION_QUESTS_FACTOR",
    "SERVER_GS_AGGRO_POOL_AMOUNT",
    "SERVER_GS_ENEMY_DAMAGE_FACTOR",
    "SERVER_GS_ENEMY_HEALTH_FACTOR",
    "SERVER_GS_ENEMY_STAMINA_FACTOR",
    "SERVER_GS_ENEMY_PERCEPTION_RANGE_FACTOR",
    "SERVER_GS_BOSS_DAMAGE_FACTOR",
    "SERVER_GS_BOSS_HEALTH_FACTOR",
    "SERVER_GS_THREAT_BONUS",
    "SERVER_GS_PACIFY_ALL_ENEMIES",
    "SERVER_GS_TAMING_STARTLE_REPERCUSSION",
    "SERVER_GS_DAY_TIME_DURATION",
    "SERVER_GS_NIGHT_TIME_DURATION",
    "SERVER_GS_TOMBSTONE_MODE",
    "SERVER_GS_CURSE_MODIFIER",
)

SERVER_ROLE_SUFFIXES: tuple[str, ...] = (
    "NAME",
    "PASSWORD",
    "CAN_KICK_BAN",
    "CAN_ACCESS_INVENTORIES",
    "CAN_EDIT_WORLD",
    "CAN_EDIT_BASE",
    "CAN_EXTEND_BASE",
    "RESERVED_SLOTS",
)

_SERVER_ROLE_INDEX_RE = re.compile(r"^SERVER_ROLE_(\d+)_")

DEPRECATED_ENV_KEYS: frozenset[str] = frozenset(
    {
        "SERVER_PASSWORD",
        "SERVER_PORT",
    }
)

AUTO_GENERATED_ENV_KEYS: frozenset[str] = frozenset(
    {
        "SUPERVISOR_GATEWAY_API_TOKEN",
        "SUPERVISOR_GATEWAY_AUTH_SECRET",
    }
)

DEFAULT_ENV_VALUES: dict[str, str] = {
    "AUTH_PASSWORD_MIN_LENGTH": "8",
    "AUTH_TEMPLATE_GUEST_ENABLED": "false",
    "AUTH_TEMPLATE_VIEWER_ENABLED": "false",
    "SUPERVISOR_GATEWAY_HOST": "0.0.0.0",
    "SUPERVISOR_GATEWAY_PORT": "8080",
    "SUPERVISOR_GATEWAY_PANEL_DIR": "/opt/supervisor-addon/panel",
    "SUPERVISOR_GATEWAY_RPC_USERNAME": "dummy",
    "SUPERVISOR_GATEWAY_RPC_PASSWORD": "dummy",
    "SUPERVISOR_GATEWAY_RPC_NAMESPACE": "addon",
    "SUPERVISOR_GATEWAY_REQUIRE_HTTPS": "true",
    "SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS": "false",
    "SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY": "true",
    "SUPERVISOR_GATEWAY_CORS_ORIGINS": "https://127.0.0.1:8080,https://localhost:8080",
    "SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS": "false",
    "SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE": "true",
    "SUPERVISOR_GATEWAY_TLS_CERTFILE": "/opt/enshrouded/supervisor-addon/tls/gateway.crt",
    "SUPERVISOR_GATEWAY_TLS_KEYFILE": "/opt/enshrouded/supervisor-addon/tls/gateway.key",
    "SUPERVISOR_GATEWAY_TLS_AUTO_LOCAL_IPS": "true",
    "SUPERVISOR_GATEWAY_TLS_AUTO_PUBLIC_IP": "true",
    "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_TIMEOUT_SECONDS": "2.0",
    "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_PROVIDERS": "https://api.ipify.org,https://ifconfig.me/ip",
    "SUPERVISOR_GATEWAY_AUTH_TOKEN_TTL_SECONDS": "28800",
    "SUPERVISOR_GATEWAY_STATE_DIR": "/opt/enshrouded/supervisor-addon",
    "SUPERVISOR_GATEWAY_AUTH_USERS_DIR": "/opt/enshrouded/supervisor-addon/auth-users",
    "SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR": "/opt/enshrouded/supervisor-addon/auth-templates",
    "SUPERVISOR_GATEWAY_NEWS_STATE_FILE": "/opt/enshrouded/supervisor-addon/news-state.json",
    "SUPERVISOR_GATEWAY_NEWS_READ_STATE_FILE": "/opt/enshrouded/supervisor-addon/news-read-state.json",
    "SUPERVISOR_GATEWAY_AUDIT_LOG_PATH": "/var/log/supervisor/supervisor-gateway-audit.log",
    "SUPERVISOR_GATEWAY_STREAM_POLL_SECONDS": "1.0",
    "SUPERVISOR_GATEWAY_STREAM_CHUNK_BYTES": "4096",
    "SUPERVISOR_GATEWAY_SUPERVISOR_LOG_FILE": "/var/log/supervisor/container-stream.log",
    "SUPERVISOR_GATEWAY_SUPERVISOR_TAIL_LINES": "200",
    "SUPERVISOR_GATEWAY_FILES_MAX_READ_BYTES": "2097152",
    "SUPERVISOR_GATEWAY_FILES_MAX_WRITE_BYTES": "2097152",
    "SUPERVISOR_GATEWAY_FILES_MAX_UPLOAD_BYTES": "209715200",
    "SUPERVISOR_GATEWAY_API_RATE_LIMIT_PER_MINUTE": "240",
    "SUPERVISOR_GATEWAY_LOGIN_RATE_LIMIT_PER_MINUTE": "10",
    "SUPERVISOR_GATEWAY_SECURITY_HEADERS": "true",
    "SUPERVISOR_GATEWAY_DEBUG": "false",
    "SUPERVISOR_GATEWAY_RELEASE_VERSION_FILE": "/opt/supervisor-addon/config/version.json",
    "SUPERVISOR_GATEWAY_GITHUB_OWNER": "bonsaibauer",
    "SUPERVISOR_GATEWAY_GITHUB_REPO": "supervisor-addon",
    "SUPERVISOR_GATEWAY_GITHUB_TIMEOUT_SECONDS": "5.0",
    "SUPERVISOR_GATEWAY_GITHUB_CACHE_SECONDS": "1800",
    "SUPERVISOR_GATEWAY_UPDATE_INSTALL_ENABLED": "true",
    "SUPERVISOR_GATEWAY_UPDATE_ASSET_NAME": "enshrouded-release.tar.gz",
    "SUPERVISOR_GATEWAY_UPDATE_ROOT_DIR": "/opt/supervisor-addon",
    "SUPERVISOR_GATEWAY_UPDATE_BACKUP_DIR": "/opt/supervisor-addon-backups",
    "SUPERVISOR_GATEWAY_UPDATE_TMP_DIR": "/tmp/supervisor-addon-updater",
    "SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM": "true",
    "SUPERVISOR_GATEWAY_UPDATE_SUPERVISORCTL_BIN": "supervisorctl",
    "SUPERVISOR_GATEWAY_UPDATE_RESTART_PROGRAMS": "supervisor-gateway",
    "SUPERVISOR_ADDON_SERVER_ID": "enshrouded",
    "SUPERVISOR_ADDON_ACTION_SERVER_START_PROGRAM": "enshrouded-server",
    "SUPERVISOR_ADDON_ACTION_SERVER_STOP_PROGRAM": "enshrouded-server",
    "SUPERVISOR_ADDON_ACTION_SERVER_RESTART_PROGRAM": "enshrouded-restart",
    "SUPERVISOR_ADDON_ACTION_BACKUP_CREATE_PROGRAM": "enshrouded-backup",
    "SUPERVISOR_ADDON_ACTION_UPDATE_RUN_PROGRAM": "enshrouded-updater",
    "SUPERVISOR_ADDON_ACTION_UPDATE_FORCE_PROGRAM": "enshrouded-force-update",
    "SUPERVISOR_ADDON_FILES_ROOTS": "/opt/enshrouded",
    "SUPERVISOR_ADDON_FILES_WRITABLE": "server,backups",
    "SUPERVISOR_ADDON_BACKUP_DIR": "server/backups",
    "SUPERVISOR_ADDON_STARTUP_CONFIG": "server/enshrouded_server.json",
    "SUPERVISOR_ADDON_STARTUP_FILES": "server/enshrouded_server.json",
    "SUPERVISOR_ADDON_LOG_STDOUT_PROGRAM": "enshrouded-server",
    "SUPERVISOR_ADDON_LOG_STDERR_PROGRAM": "enshrouded-server",
    "SUPERVISOR_ADDON_ENV_EXPOSE_VALUES": "false",
    "PUID": "4711",
    "PGID": "4711",
    "GAME_BRANCH": "public",
    "STEAMCMD_ARGS": "$GAME_BRANCH validate",
    "UPDATE_CHECK_PLAYERS": "false",
    "BACKUP_DIR": "backups",
    "BACKUP_MAX_COUNT": "0",
    "WINEDEBUG": "-all",
    "VITE_GATEWAY_URL": "https://127.0.0.1:8080",
    "VITE_GATEWAY_TOKEN_MODE": "bearer",
    "VITE_DEFAULT_SERVER_ID": "enshrouded",
}


def _default_value_for(name: str) -> str | None:
    return DEFAULT_ENV_VALUES.get(name)


def _is_deprecated_env_key(name: str) -> bool:
    return name in DEPRECATED_ENV_KEYS


def _format_effective_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _normalize_json_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _lookup_json_value_in_dict(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]

    key_lower = key.strip().lower()
    for raw_key, value in payload.items():
        if isinstance(raw_key, str) and raw_key.strip().lower() == key_lower:
            return value

    key_normalized = _normalize_json_key(key)
    if not key_normalized:
        return None
    for raw_key, value in payload.items():
        if isinstance(raw_key, str) and _normalize_json_key(raw_key) == key_normalized:
            return value
    return None


def _lookup_json_value(payload: dict[str, Any], key: str) -> Any:
    direct = _lookup_json_value_in_dict(payload, key)
    if direct is not None:
        return direct

    for wrapper_key in ("server", "settings", "config", "configuration"):
        nested = _lookup_json_value_in_dict(payload, wrapper_key)
        if isinstance(nested, dict):
            nested_value = _lookup_json_value_in_dict(nested, key)
            if nested_value is not None:
                return nested_value
    return None


def _json_value_for_server_gs(name: str, startup_json: dict[str, Any]) -> str | None:
    suffix = name.removeprefix("SERVER_GS_")
    if not suffix:
        return None

    if suffix == "PRESET":
        value = _lookup_json_value(startup_json, "gameSettingsPreset")
        if value is None:
            return None
        return _format_effective_value(value)

    settings = _lookup_json_value(startup_json, "gameSettings")
    if not isinstance(settings, dict):
        return None

    parts = [part for part in suffix.lower().split("_") if part]
    if not parts:
        return None
    key = parts[0] + "".join(part.capitalize() for part in parts[1:])
    direct = _lookup_json_value(settings, key)
    if direct is not None:
        return _format_effective_value(direct)
    return None


_SERVER_ROLE_ENV_RE = re.compile(r"^SERVER_ROLE_(\d+)_(.+)$")

_SERVER_ROLE_FIELD_MAP: dict[str, str] = {
    "NAME": "name",
    "PASSWORD": "password",
    "CAN_KICK_BAN": "canKickBan",
    "CAN_ACCESS_INVENTORIES": "canAccessInventories",
    "CAN_EDIT_WORLD": "canEditWorld",
    "CAN_EDIT_BASE": "canEditBase",
    "CAN_EXTEND_BASE": "canExtendBase",
    "RESERVED_SLOTS": "reservedSlots",
}


_SERVER_CORE_FIELD_MAP: dict[str, str] = {
    "NAME": "name",
    "SLOT_COUNT": "slotCount",
    "QUERYPORT": "queryPort",
    "PORT": "port",
    "IP": "ip",
    "LOG_DIR": "logDirectory",
    "SAVE_DIR": "saveDirectory",
    "VOICE_CHAT_MODE": "voiceChatMode",
    "ENABLE_VOICE_CHAT": "enableVoiceChat",
    "ENABLE_TEXT_CHAT": "enableTextChat",
    "PASSWORD": "password",
}


def _json_value_for_server_role(name: str, startup_json: dict[str, Any]) -> str | None:
    match = _SERVER_ROLE_ENV_RE.match(name)
    if not match:
        return None

    index = int(match.group(1))
    suffix = match.group(2)

    roles_value = _lookup_json_value(startup_json, "userGroups")
    if not isinstance(roles_value, list):
        return None
    if index < 0 or index >= len(roles_value):
        return None

    role_entry = roles_value[index]
    if not isinstance(role_entry, dict):
        return None

    field_name = _SERVER_ROLE_FIELD_MAP.get(suffix)
    if not field_name:
        return None
    role_value = _lookup_json_value(role_entry, field_name)
    if role_value is None:
        return None
    return _format_effective_value(role_value)


def _json_value_for_server_core(name: str, startup_json: dict[str, Any]) -> str | None:
    if not name.startswith("SERVER_"):
        return None
    suffix = name.removeprefix("SERVER_")
    if not suffix or suffix.startswith("ROLE_") or suffix.startswith("GS_"):
        return None

    field_name = _SERVER_CORE_FIELD_MAP.get(suffix)
    if not field_name:
        return None

    direct = _lookup_json_value(startup_json, field_name)
    if direct is not None:
        return _format_effective_value(direct)
    if suffix == "PORT":
        game_port = _lookup_json_value(startup_json, "gamePort")
        if game_port is not None:
            return _format_effective_value(game_port)
    return None


def _is_json_managed_key(name: str) -> bool:
    if name.startswith("SERVER_GS_"):
        return True
    if name.startswith("SERVER_ROLE_"):
        return True
    if name.startswith("SERVER_"):
        return True
    return False


def _json_effective_value(name: str, startup_json: dict[str, Any] | None) -> str | None:
    if not startup_json:
        return None
    if name.startswith("SERVER_GS_"):
        return _json_value_for_server_gs(name, startup_json)
    if name.startswith("SERVER_ROLE_"):
        return _json_value_for_server_role(name, startup_json)
    if name.startswith("SERVER_"):
        return _json_value_for_server_core(name, startup_json)
    return None


def _strip_json_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                result.append(char)
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        result.append(char)
        index += 1

    return "".join(result)


def _remove_json_trailing_commas(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead].isspace():
                lookahead += 1
            if lookahead < length and text[lookahead] in {"}", "]"}:
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)


def _try_parse_startup_json(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        relaxed = _remove_json_trailing_commas(_strip_json_comments(raw_text))
        try:
            payload = json.loads(relaxed)
        except json.JSONDecodeError as error:
            return None, f"invalid JSON (line {error.lineno}, col {error.colno}): {error.msg}"

    if isinstance(payload, dict):
        return payload, None
    return None, "invalid JSON: top-level value must be an object"


def _load_startup_json(startup_config: str, primary_root: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    path_raw = startup_config.strip()
    if not path_raw:
        return None, "startup config path is empty"

    candidate_paths: list[Path] = [Path(path_raw)]
    normalized = path_raw.replace("\\", "/")
    # Backward-compatibility: treat "/server/..." as root-relative startup path.
    # Older setups often use this style for files under the first FILES_ROOTS entry.
    if primary_root and (normalized == "/server" or normalized.startswith("/server/")):
        fallback = (Path(primary_root) / normalized.lstrip("/")).resolve(strict=False)
        if str(fallback) not in {str(path) for path in candidate_paths}:
            candidate_paths.append(fallback)

    parse_error: str | None = None
    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except OSError as error:
            parse_error = f"failed reading '{path}': {error}"
            continue
        payload, error = _try_parse_startup_json(raw_text)
        if payload is not None:
            return payload, None
        parse_error = f"{path}: {error or 'invalid JSON'}"
    return None, parse_error


def _collect_server_role_indexes() -> set[int]:
    indexes: set[int] = {0}

    for env_key in os.environ.keys():
        match = _SERVER_ROLE_INDEX_RE.match(env_key)
        if match:
            indexes.add(int(match.group(1)))

    return indexes


def _mask_env_value(key: str, value: str) -> str:
    sensitive_tokens = ("TOKEN", "SECRET", "PASSWORD", "HASH")
    key_upper = key.upper()
    if any(token in key_upper for token in sensitive_tokens):
        return "***"
    return value if len(value) <= 220 else f"{value[:220]}..."


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _collect_env_catalog(extra_keys: list[str], startup_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    expose_values = _env_bool("SUPERVISOR_ADDON_ENV_EXPOSE_VALUES", False)
    keys: list[str] = list(KNOWN_ENV_KEYS)
    keys.extend(extra_keys)
    keys.extend(key for key in os.environ.keys() if key.startswith("AUTH_TEMPLATE_"))
    keys.extend(key for key in os.environ.keys() if key.startswith("SERVER_ROLE_"))
    keys.extend(key for key in os.environ.keys() if key.startswith("SERVER_GS_"))
    for index in sorted(_collect_server_role_indexes()):
        keys.extend(f"SERVER_ROLE_{index}_{suffix}" for suffix in SERVER_ROLE_SUFFIXES)

    seen: set[str] = set()
    catalog: list[dict[str, Any]] = []
    for key in keys:
        name = str(key).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        raw = os.getenv(name)
        text = str(raw).strip() if raw is not None else ""
        is_set = bool(text)
        deprecated = _is_deprecated_env_key(name)
        is_automatic = (not is_set) and (name in AUTO_GENERATED_ENV_KEYS)
        if deprecated:
            status = "deprecated"
        elif is_automatic:
            status = "automatic"
        elif is_set:
            status = "set"
        else:
            status = "unset"
        if _is_json_managed_key(name):
            effective_default = _json_effective_value(name, startup_json)
        else:
            effective_default = _default_value_for(name)
        catalog.append(
            {
                "key": name,
                "is_set": is_set,
                "deprecated": deprecated,
                "status": status,
                "value": "***"
                if is_automatic
                else ((_mask_env_value(name, text) if expose_values else "***") if is_set else None),
                "default_value": None if is_set else effective_default,
            }
        )
    return sorted(catalog, key=lambda item: str(item["key"]))


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    action_type: str
    program: str


@dataclass
class ServerDefinition:
    server_id: str
    actions: dict[str, ActionDefinition] = field(default_factory=dict)
    logs: dict[str, str] = field(default_factory=dict)
    files: dict[str, Any] = field(default_factory=dict)

    def runtime_program(self) -> str | None:
        stdout_program = self.logs.get("stdout_program")
        if stdout_program:
            return stdout_program
        if "server.start" in self.actions:
            return self.actions["server.start"].program
        for action in self.actions.values():
            return action.program
        return None


@dataclass
class ActionConfig:
    version: int
    servers: dict[str, ServerDefinition]


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    text = _normalize_env_text(value)
    return text or default


def _csv_or_default(name: str, default_values: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default_values
    values = [_normalize_env_text(part) for part in str(value).split(",")]
    values = [part for part in values if part]
    return values or default_values


def _normalize_env_text(value: Any) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _resolve_absolute_root_path(value: str) -> str:
    text = _normalize_env_text(value).replace("\\", "/")
    if not text:
        return ""
    path = Path(text)
    if not path.is_absolute():
        path = Path("/") / path
    return str(path.resolve(strict=False))


def _resolve_path_against_root(value: str, primary_root: str) -> str:
    text = _normalize_env_text(value).replace("\\", "/")
    if not text:
        return primary_root
    path = Path(text)
    if path.is_absolute():
        return str(path.resolve(strict=False))
    relative = text.lstrip("/")
    root_name = Path(primary_root).name.strip().lower()
    # Backward-compatibility: avoid duplicating ".../server/server/..." when
    # FILES_ROOTS already points to the server directory.
    if root_name == "server" and (relative.lower() == "server" or relative.lower().startswith("server/")):
        relative = relative[6:].lstrip("/")
    if not relative:
        return str(Path(primary_root).resolve(strict=False))
    return str((Path(primary_root) / relative).resolve(strict=False))


def _resolve_paths_against_root(values: list[str], primary_root: str) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for value in values:
        path = _resolve_path_against_root(value, primary_root)
        if not path or path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def load_action_config_from_env() -> ActionConfig:
    server_id = _env_or_default("SUPERVISOR_ADDON_SERVER_ID", "enshrouded")

    start_program = _env_or_default("SUPERVISOR_ADDON_ACTION_SERVER_START_PROGRAM", "enshrouded-server")
    stop_program = _env_or_default("SUPERVISOR_ADDON_ACTION_SERVER_STOP_PROGRAM", "enshrouded-server")
    restart_program = _env_or_default("SUPERVISOR_ADDON_ACTION_SERVER_RESTART_PROGRAM", "enshrouded-restart")
    backup_program = _env_or_default("SUPERVISOR_ADDON_ACTION_BACKUP_CREATE_PROGRAM", "enshrouded-backup")
    update_run_program = _env_or_default("SUPERVISOR_ADDON_ACTION_UPDATE_RUN_PROGRAM", "enshrouded-updater")
    update_force_program = _env_or_default(
        "SUPERVISOR_ADDON_ACTION_UPDATE_FORCE_PROGRAM", "enshrouded-force-update"
    )

    actions: dict[str, ActionDefinition] = {
        "server.start": ActionDefinition(
            action_id="server.start",
            action_type="supervisor.start",
            program=start_program,
        ),
        "server.stop": ActionDefinition(
            action_id="server.stop",
            action_type="supervisor.stop",
            program=stop_program,
        ),
        "server.restart_safe": ActionDefinition(
            action_id="server.restart_safe",
            action_type="supervisor.start",
            program=restart_program,
        ),
        "backup.create": ActionDefinition(
            action_id="backup.create",
            action_type="supervisor.start",
            program=backup_program,
        ),
        "update.run": ActionDefinition(
            action_id="update.run",
            action_type="supervisor.start",
            program=update_run_program,
        ),
        "update.force": ActionDefinition(
            action_id="update.force",
            action_type="supervisor.start",
            program=update_force_program,
        ),
    }

    roots_raw = _csv_or_default("SUPERVISOR_ADDON_FILES_ROOTS", ["/opt/enshrouded"])
    roots: list[str] = []
    seen_roots: set[str] = set()
    for root_raw in roots_raw:
        resolved_root = _resolve_absolute_root_path(root_raw)
        if not resolved_root or resolved_root in seen_roots:
            continue
        seen_roots.add(resolved_root)
        roots.append(resolved_root)
    if not roots:
        roots = [str(Path("/opt/enshrouded").resolve(strict=False))]

    primary_root = roots[0]
    writable_raw = _csv_or_default("SUPERVISOR_ADDON_FILES_WRITABLE", ["server", "backups"])
    writable = _resolve_paths_against_root(writable_raw, primary_root)
    if not writable:
        writable = _resolve_paths_against_root(["server", "backups"], primary_root)

    backup_dir = _resolve_path_against_root(
        _env_or_default("SUPERVISOR_ADDON_BACKUP_DIR", "server/backups"),
        primary_root,
    )
    startup_config = _resolve_path_against_root(
        _env_or_default("SUPERVISOR_ADDON_STARTUP_CONFIG", "server/enshrouded_server.json"),
        primary_root,
    )
    startup_files = _resolve_paths_against_root(
        _csv_or_default("SUPERVISOR_ADDON_STARTUP_FILES", ["server/enshrouded_server.json"]),
        primary_root,
    )

    env_keys = _csv_or_default("SUPERVISOR_ADDON_ENV_KEYS", [])
    startup_json, startup_json_error = _load_startup_json(startup_config, primary_root)
    env_catalog = _collect_env_catalog(env_keys, startup_json)

    stdout_program = _env_or_default("SUPERVISOR_ADDON_LOG_STDOUT_PROGRAM", "enshrouded-server")
    stderr_program = _env_or_default("SUPERVISOR_ADDON_LOG_STDERR_PROGRAM", "enshrouded-server")

    files: dict[str, Any] = {
        "roots": roots,
        "writable": writable,
        "backup_dir": backup_dir,
        "startup_config": startup_config,
        "startup_files": startup_files,
        "startup_json_loaded": startup_json is not None,
        "startup_json_error": startup_json_error,
        "env_keys": env_keys,
        "env_catalog": env_catalog,
    }

    server = ServerDefinition(
        server_id=server_id,
        actions=actions,
        logs={
            "stdout_program": stdout_program,
            "stderr_program": stderr_program,
        },
        files=files,
    )
    return ActionConfig(version=1, servers={server_id: server})
