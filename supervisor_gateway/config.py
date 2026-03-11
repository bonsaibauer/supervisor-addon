from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse


def _env_present(name: str) -> str:
    if name not in os.environ:
        raise ValueError(f"missing required environment variable '{name}'")
    return str(os.environ[name])


def _env_required_str(name: str) -> str:
    text = _env_present(name).strip()
    if not text:
        raise ValueError(f"environment variable '{name}' must not be empty")
    return text


def _env_optional_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"environment variable '{name}' must be a boolean (true/false/1/0/yes/no/on/off)"
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return _parse_bool(name, str(value))


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    value = os.getenv(name)
    if value is None:
        value_int = default
    else:
        try:
            value_int = int(str(value).strip())
        except (TypeError, ValueError) as error:
            raise ValueError(f"environment variable '{name}' must be an integer") from error
    if minimum is not None and value_int < minimum:
        raise ValueError(f"environment variable '{name}' must be >= {minimum}")
    return value_int


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    value = os.getenv(name)
    if value is None:
        value_float = default
    else:
        try:
            value_float = float(str(value).strip())
        except (TypeError, ValueError) as error:
            raise ValueError(f"environment variable '{name}' must be a float") from error
    if minimum is not None and value_float < minimum:
        raise ValueError(f"environment variable '{name}' must be >= {minimum}")
    return value_float


def _env_csv(name: str, default_values: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default_values
    values = [part.strip() for part in str(value).split(",") if part.strip()]
    return values or default_values


@dataclass(frozen=True)
class Settings:
    rpc_url: str
    rpc_username: str | None
    rpc_password: str | None
    rpc_namespace: str

    api_token: str | None
    auth_secret: str | None
    state_dir: str
    auth_users_dir: str
    auth_templates_dir: str
    auth_template_guest_enabled: bool
    auth_template_viewer_enabled: bool
    news_state_file: str
    news_read_state_file: str
    auth_token_ttl_seconds: int
    auth_min_password_length: int

    audit_log_path: str | None

    stream_poll_seconds: float
    stream_chunk_bytes: int
    supervisor_log_file: str
    supervisor_tail_lines: int

    files_max_read_bytes: int
    files_max_write_bytes: int
    files_max_upload_bytes: int

    cors_origins: list[str]
    cors_allow_credentials: bool

    api_rate_limit_per_minute: int
    login_rate_limit_per_minute: int

    require_https: bool
    insecure_http_local_only: bool
    trust_proxy_headers: bool
    enable_security_headers: bool

    debug: bool
    host: str
    port: int

    tls_certfile: str | None
    tls_keyfile: str | None
    tls_auto_local_ips: bool
    tls_auto_public_ip: bool
    tls_public_ip_timeout_seconds: float
    tls_public_ip_providers: list[str]
    panel_dir: str | None
    release_version_file: str | None
    github_owner: str
    github_repo: str
    github_timeout_seconds: float
    github_cache_seconds: int
    update_install_enabled: bool
    update_asset_name: str
    update_root_dir: str
    update_backup_dir: str
    update_tmp_dir: str
    update_require_checksum: bool
    update_supervisorctl_bin: str
    update_restart_programs: list[str]

    @classmethod
    def from_env(cls) -> "Settings":
        auth_secret = _env_optional_str("SUPERVISOR_GATEWAY_AUTH_SECRET")
        api_token = _env_optional_str("SUPERVISOR_GATEWAY_API_TOKEN")
        auth_template_guest_enabled = _env_bool("AUTH_TEMPLATE_GUEST_ENABLED", False)
        auth_template_viewer_enabled = _env_bool("AUTH_TEMPLATE_VIEWER_ENABLED", False)
        auth_password_min_length = _env_int("AUTH_PASSWORD_MIN_LENGTH", 8, minimum=8)

        if not api_token:
            api_token = secrets.token_hex(32)
        if not auth_secret:
            auth_secret = secrets.token_hex(32)

        state_dir = _env_or_default("SUPERVISOR_GATEWAY_STATE_DIR", "/opt/enshrouded/supervisor-addon")
        auth_users_dir = _env_or_default(
            "SUPERVISOR_GATEWAY_AUTH_USERS_DIR",
            str(Path(state_dir) / "auth-users"),
        )
        auth_templates_dir = _env_or_default(
            "SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR",
            str(Path(state_dir) / "auth-templates"),
        )
        news_state_file = _env_or_default(
            "SUPERVISOR_GATEWAY_NEWS_STATE_FILE",
            str(Path(state_dir) / "news-state.json"),
        )
        news_read_state_file = _env_or_default(
            "SUPERVISOR_GATEWAY_NEWS_READ_STATE_FILE",
            str(Path(state_dir) / "news-read-state.json"),
        )

        cors_origins = _env_csv(
            "SUPERVISOR_GATEWAY_CORS_ORIGINS",
            ["https://127.0.0.1:8080", "https://localhost:8080"],
        )
        cors_allow_credentials = _env_bool("SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS", False)
        if "*" in cors_origins and cors_allow_credentials:
            raise ValueError(
                "SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS must be false when CORS origins contain '*'."
            )

        rpc_url = _env_required_str("SUPERVISOR_GATEWAY_RPC_URL")
        parsed_rpc = urlparse(rpc_url)
        if parsed_rpc.scheme != "unix":
            raise ValueError(
                "SUPERVISOR_GATEWAY_RPC_URL must use unix:// (inet/http RPC is disabled in unix_http_server mode)."
            )

        require_https = _env_bool("SUPERVISOR_GATEWAY_REQUIRE_HTTPS", True)
        trust_proxy_headers = _env_bool("SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS", False)
        if require_https and not trust_proxy_headers:
            tls_certfile = _env_or_default(
                "SUPERVISOR_GATEWAY_TLS_CERTFILE", "/opt/enshrouded/supervisor-addon/tls/gateway.crt"
            )
            tls_keyfile = _env_or_default(
                "SUPERVISOR_GATEWAY_TLS_KEYFILE", "/opt/enshrouded/supervisor-addon/tls/gateway.key"
            )
        else:
            tls_certfile = _env_optional_str("SUPERVISOR_GATEWAY_TLS_CERTFILE")
            tls_keyfile = _env_optional_str("SUPERVISOR_GATEWAY_TLS_KEYFILE")

        if bool(tls_certfile) != bool(tls_keyfile):
            raise ValueError(
                "SUPERVISOR_GATEWAY_TLS_CERTFILE and SUPERVISOR_GATEWAY_TLS_KEYFILE must be set together."
            )
        host = _env_or_default("SUPERVISOR_GATEWAY_HOST", "0.0.0.0")
        insecure_http_local_only = _env_bool("SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY", True)
        if not require_https and insecure_http_local_only and host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError(
                "HTTP mode is restricted to localhost. "
                "Set SUPERVISOR_GATEWAY_HOST=127.0.0.1 or enable HTTPS. "
                "To allow insecure remote HTTP explicitly, set SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=false."
            )

        return cls(
            rpc_url=rpc_url,
            rpc_username=_env_or_default("SUPERVISOR_GATEWAY_RPC_USERNAME", "dummy"),
            rpc_password=_env_or_default("SUPERVISOR_GATEWAY_RPC_PASSWORD", "dummy"),
            rpc_namespace=_env_or_default("SUPERVISOR_GATEWAY_RPC_NAMESPACE", "addon"),
            api_token=api_token,
            auth_secret=auth_secret,
            state_dir=state_dir,
            auth_users_dir=auth_users_dir,
            auth_templates_dir=auth_templates_dir,
            auth_template_guest_enabled=auth_template_guest_enabled,
            auth_template_viewer_enabled=auth_template_viewer_enabled,
            news_state_file=news_state_file,
            news_read_state_file=news_read_state_file,
            auth_token_ttl_seconds=_env_int("SUPERVISOR_GATEWAY_AUTH_TOKEN_TTL_SECONDS", 28800, minimum=60),
            auth_min_password_length=auth_password_min_length,
            audit_log_path=_env_or_default(
                "SUPERVISOR_GATEWAY_AUDIT_LOG_PATH", "/var/log/supervisor/supervisor-gateway-audit.log"
            ),
            stream_poll_seconds=_env_float("SUPERVISOR_GATEWAY_STREAM_POLL_SECONDS", 1.0, minimum=0.1),
            stream_chunk_bytes=_env_int("SUPERVISOR_GATEWAY_STREAM_CHUNK_BYTES", 4096, minimum=128),
            supervisor_log_file=_env_or_default(
                "SUPERVISOR_GATEWAY_SUPERVISOR_LOG_FILE", "/var/log/supervisor/container-stream.log"
            ),
            supervisor_tail_lines=_env_int("SUPERVISOR_GATEWAY_SUPERVISOR_TAIL_LINES", 200, minimum=1),
            files_max_read_bytes=_env_int("SUPERVISOR_GATEWAY_FILES_MAX_READ_BYTES", 2097152, minimum=1024),
            files_max_write_bytes=_env_int("SUPERVISOR_GATEWAY_FILES_MAX_WRITE_BYTES", 2097152, minimum=1024),
            files_max_upload_bytes=_env_int(
                "SUPERVISOR_GATEWAY_FILES_MAX_UPLOAD_BYTES", 209715200, minimum=1024
            ),
            cors_origins=cors_origins,
            cors_allow_credentials=cors_allow_credentials,
            api_rate_limit_per_minute=_env_int("SUPERVISOR_GATEWAY_API_RATE_LIMIT_PER_MINUTE", 240, minimum=1),
            login_rate_limit_per_minute=_env_int("SUPERVISOR_GATEWAY_LOGIN_RATE_LIMIT_PER_MINUTE", 10, minimum=1),
            require_https=require_https,
            insecure_http_local_only=insecure_http_local_only,
            trust_proxy_headers=trust_proxy_headers,
            enable_security_headers=_env_bool("SUPERVISOR_GATEWAY_SECURITY_HEADERS", True),
            debug=_env_bool("SUPERVISOR_GATEWAY_DEBUG", False),
            host=host,
            port=_env_int("SUPERVISOR_GATEWAY_PORT", 8080, minimum=1),
            tls_certfile=tls_certfile,
            tls_keyfile=tls_keyfile,
            tls_auto_local_ips=_env_bool("SUPERVISOR_GATEWAY_TLS_AUTO_LOCAL_IPS", True),
            tls_auto_public_ip=_env_bool("SUPERVISOR_GATEWAY_TLS_AUTO_PUBLIC_IP", True),
            tls_public_ip_timeout_seconds=_env_float(
                "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_TIMEOUT_SECONDS",
                2.0,
                minimum=0.1,
            ),
            tls_public_ip_providers=_env_csv(
                "SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_PROVIDERS",
                ["https://api.ipify.org", "https://ifconfig.me/ip"],
            ),
            panel_dir=_env_or_default("SUPERVISOR_GATEWAY_PANEL_DIR", "/opt/supervisor-addon/panel"),
            release_version_file=_env_or_default(
                "SUPERVISOR_GATEWAY_RELEASE_VERSION_FILE", "/opt/supervisor-addon/config/version.json"
            ),
            github_owner=_env_or_default("SUPERVISOR_GATEWAY_GITHUB_OWNER", "bonsaibauer"),
            github_repo=_env_or_default("SUPERVISOR_GATEWAY_GITHUB_REPO", "supervisor-addon"),
            github_timeout_seconds=_env_float("SUPERVISOR_GATEWAY_GITHUB_TIMEOUT_SECONDS", 5.0, minimum=0.5),
            github_cache_seconds=_env_int("SUPERVISOR_GATEWAY_GITHUB_CACHE_SECONDS", 1800, minimum=30),
            update_install_enabled=_env_bool("SUPERVISOR_GATEWAY_UPDATE_INSTALL_ENABLED", True),
            update_asset_name=_env_or_default("SUPERVISOR_GATEWAY_UPDATE_ASSET_NAME", "enshrouded-release.tar.gz"),
            update_root_dir=_env_or_default("SUPERVISOR_GATEWAY_UPDATE_ROOT_DIR", "/opt/supervisor-addon"),
            update_backup_dir=_env_or_default(
                "SUPERVISOR_GATEWAY_UPDATE_BACKUP_DIR", "/opt/supervisor-addon-backups"
            ),
            update_tmp_dir=_env_or_default("SUPERVISOR_GATEWAY_UPDATE_TMP_DIR", "/tmp/supervisor-addon-updater"),
            update_require_checksum=_env_bool("SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM", True),
            update_supervisorctl_bin=_env_or_default("SUPERVISOR_GATEWAY_UPDATE_SUPERVISORCTL_BIN", "supervisorctl"),
            update_restart_programs=_env_csv("SUPERVISOR_GATEWAY_UPDATE_RESTART_PROGRAMS", ["supervisor-gateway"]),
        )
