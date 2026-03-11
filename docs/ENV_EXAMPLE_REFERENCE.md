# Environment Reference (`.env.example`)

This document is the English reference for all values shown in `.env.example`, including valid formats, ranges, and security behavior.

## Parsing Rules

| Type | Accepted values |
| --- | --- |
| Boolean | `true/false`, `1/0`, `yes/no`, `on/off` (case-insensitive) |
| Integer | Base-10 integer string |
| Float | Numeric string (`5`, `5.0`, `0.5`) |
| CSV list | Comma-separated, empty items ignored |

## Wrapper Integration

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_ADDON` | `true` | Boolean | Wrapper toggle used by `enshrouded-server` bootstrap to enable/disable addon install/start. Not consumed by `supervisor-addon` Python code directly. |

## Security Behavior Matrix

| Configuration | Behavior |
| --- | --- |
| `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true` | Non-HTTPS requests are rejected. |
| HTTPS enabled + no cert/key + `SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true` | Self-signed cert/key are generated on startup. |
| `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=false` + `SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true` | HTTP access is restricted to localhost clients. |
| HTTP mode + localhost-only guard enabled + host is not loopback | Startup fails fast. |

## Gateway Auth Variables

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_API_TOKEN` | empty | Non-empty string or empty | Empty means runtime auto-generates a random token. |
| `SUPERVISOR_GATEWAY_AUTH_SECRET` | empty | Non-empty string or empty | Empty means runtime auto-generates random secret. |
| `Generated defaults` | n/a | n/a | `admin` is always ensured. New bootstrap users use `change-me` and forced password change. |
| `SUPERVISOR_GATEWAY_STATE_DIR` | `/opt/enshrouded/supervisor-addon` (commented) | Directory path | Base path for persistent gateway state (auth/news), recommended on mounted volume. |
| `SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR` | `/opt/enshrouded/supervisor-addon/auth-templates` (commented) | Directory path | Bootstrap templates (`*.json`) used to auto-create/remove managed users on startup. |
| `SUPERVISOR_GATEWAY_AUTH_USERS_DIR` | `/opt/enshrouded/supervisor-addon/auth-users` (commented) | Directory path | Source of truth: one JSON per user with role/permissions/scope. |
| `SUPERVISOR_GATEWAY_NEWS_STATE_FILE` | `/opt/enshrouded/supervisor-addon/news-state.json` (commented) | File path | Stores periodic news metadata (for example support reminder timestamp). |
| `SUPERVISOR_GATEWAY_NEWS_READ_STATE_FILE` | `/opt/enshrouded/supervisor-addon/news-read-state.json` (commented) | File path | Stores read/unread state per user and server for News tab/Chirper. |
| `AUTH_TEMPLATE_GUEST_ENABLED` | `false` | Boolean | Bootstrap sync: `true` creates `guest` file if missing, `false` removes it. |
| `AUTH_TEMPLATE_VIEWER_ENABLED` | `false` | Boolean | Bootstrap sync: `true` creates `viewer` file if missing, `false` removes it. |
| `AUTH_TEMPLATE_<NAME>_ENABLED` | unset | Boolean | Enables/disables custom template `<name>.json` in `AUTH_TEMPLATES_DIR` (schema: uppercase `A-Z0-9_` in env name). |
| `AUTH_PASSWORD_MIN_LENGTH` | `8` | Integer `>= 8` | Enforced on password change endpoint. |
| `SUPERVISOR_GATEWAY_AUTH_TOKEN_TTL_SECONDS` | `28800` (implicit) | Integer `>= 60` | Session token TTL in seconds. |

## Network, TLS, and CORS

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_HOST` | `0.0.0.0` | Host/IP string | In HTTP mode with localhost guard, host must be loopback. |
| `SUPERVISOR_GATEWAY_PORT` | `8080` | Integer `>= 1` | Gateway listen port. |
| `SUPERVISOR_GATEWAY_REQUIRE_HTTPS` | `true` | Boolean | Main transport security switch. |
| `SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY` | `true` | Boolean | Localhost-only guard for HTTP mode. |
| `SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS` | `false` | Boolean | Enable only behind trusted reverse proxy. |
| `SUPERVISOR_GATEWAY_CORS_ORIGINS` | `https://127.0.0.1:8080,https://localhost:8080` | CSV of origins | If `*` is included, credentials must stay disabled. |
| `SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS` | `false` (implicit) | Boolean | Must be `false` when CORS list contains `*`. |
| `SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE` | `true` | Boolean | Auto-generates self-signed cert/key if missing. |
| `SUPERVISOR_GATEWAY_TLS_AUTO_LOCAL_IPS` | `true` (implicit/commented) | Boolean | Adds discovered non-loopback local interface IPs to auto-generated cert SANs. |
| `SUPERVISOR_GATEWAY_TLS_AUTO_PUBLIC_IP` | `true` (implicit/commented) | Boolean | Tries to discover and include the public IP in auto-generated cert SANs. |
| `SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_TIMEOUT_SECONDS` | `2.0` (implicit/commented) | Float `>= 0.1` | Timeout per public-IP provider request. |
| `SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_PROVIDERS` | `https://api.ipify.org,https://ifconfig.me/ip` (implicit/commented) | CSV of URLs | Provider list used for public-IP discovery; each should return plain text IP. |
| `SUPERVISOR_GATEWAY_TLS_CERTFILE` | `/opt/enshrouded/supervisor-addon/tls/gateway.crt` (commented) | File path | Cert and key must be set together if either is set. |
| `SUPERVISOR_GATEWAY_TLS_KEYFILE` | `/opt/enshrouded/supervisor-addon/tls/gateway.key` (commented) | File path | Cert and key must be set together if either is set. |
| `SUPERVISOR_GATEWAY_TLS_EXTRA_SANS` | empty (commented) | CSV of `DNS:name` and/or `IP:x.x.x.x` | Used by auto-generated self-signed cert SAN list. |

## RPC and Gateway Runtime

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_RPC_URL` | `unix:///dev/shm/supervisor.sock` | Must use `unix://` scheme | Required. Non-unix RPC URLs are rejected. |
| `SUPERVISOR_GATEWAY_RPC_USERNAME` | `dummy` | String | Required in typical `unix_http_server` auth setups. |
| `SUPERVISOR_GATEWAY_RPC_PASSWORD` | `dummy` | String | Required in typical `unix_http_server` auth setups. |
| `SUPERVISOR_GATEWAY_RPC_NAMESPACE` | `addon` | String | Namespace used for addon RPC methods. |
| `SUPERVISOR_GATEWAY_PANEL_DIR` | `/opt/supervisor-addon/panel` | Directory path | Static panel files location. |
| `SUPERVISOR_GATEWAY_AUDIT_LOG_PATH` | `/var/log/supervisor/supervisor-gateway-audit.log` (commented) | File path | Audit event log destination. |
| `SUPERVISOR_GATEWAY_SECURITY_HEADERS` | `true` (implicit) | Boolean | Enables response security headers (incl. CSP). |
| `SUPERVISOR_GATEWAY_DEBUG` | `false` (implicit) | Boolean | Debug mode toggle. |

## Stream, File, and Rate Limits

| Variable | Default | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_STREAM_POLL_SECONDS` | `1.0` | Float `>= 0.1` | Poll interval for stream endpoints. |
| `SUPERVISOR_GATEWAY_STREAM_CHUNK_BYTES` | `4096` | Integer `>= 128` | Stream chunk size. |
| `SUPERVISOR_GATEWAY_SUPERVISOR_LOG_FILE` | `/var/log/supervisor/container-stream.log` (commented) | File path | Source file for Supervisor tab stream (`tail -F`). |
| `SUPERVISOR_GATEWAY_SUPERVISOR_TAIL_LINES` | `200` (commented) | Integer `>= 1` | Initial tail line count for Supervisor tab stream. |
| `SUPERVISOR_GATEWAY_FILES_MAX_READ_BYTES` | `2097152` | Integer `>= 1024` | Max readable file size. |
| `SUPERVISOR_GATEWAY_FILES_MAX_WRITE_BYTES` | `2097152` | Integer `>= 1024` | Max write payload size. |
| `SUPERVISOR_GATEWAY_FILES_MAX_UPLOAD_BYTES` | `209715200` | Integer `>= 1024` | Max upload size. |
| `SUPERVISOR_GATEWAY_API_RATE_LIMIT_PER_MINUTE` | `240` | Integer `>= 1` | Per-IP API request cap. |
| `SUPERVISOR_GATEWAY_LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Integer `>= 1` | Per-IP login attempt cap. |

## Runtime Metrics (`/proc`)

CPU and memory metrics used by the panel are read from `/proc`:

- `/proc/stat` (CPU aggregate + per-core deltas between polls)
- `/proc/meminfo` (`MemTotal` and `MemAvailable`)

No Docker socket and no `docker stats` call is required for these metrics.

## Update/Release Variables

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_RELEASE_VERSION_FILE` | `/opt/supervisor-addon/config/version.json` (commented) | File path | Current installed version metadata. |
| `SUPERVISOR_GATEWAY_GITHUB_OWNER` | `bonsaibauer` (commented) | String | Release source owner. |
| `SUPERVISOR_GATEWAY_GITHUB_REPO` | `supervisor-addon` (commented) | String | Release source repo. |
| `SUPERVISOR_GATEWAY_GITHUB_TIMEOUT_SECONDS` | `5` (commented) | Float `>= 0.5` | GitHub API timeout. |
| `SUPERVISOR_GATEWAY_GITHUB_CACHE_SECONDS` | `1800` (commented) | Integer `>= 30` | Cache TTL for latest release checks. |
| `SUPERVISOR_GATEWAY_UPDATE_INSTALL_ENABLED` | `true` | Boolean | Enables install endpoint behavior. |
| `SUPERVISOR_GATEWAY_UPDATE_ASSET_NAME` | `enshrouded-release.tar.gz` (commented) | String | Expected release asset filename. |
| `SUPERVISOR_GATEWAY_UPDATE_ROOT_DIR` | `/opt/supervisor-addon` (commented) | Directory path | Live install root. |
| `SUPERVISOR_GATEWAY_UPDATE_BACKUP_DIR` | `/opt/supervisor-addon-backups` (commented) | Directory path | Backup target for previous install. |
| `SUPERVISOR_GATEWAY_UPDATE_TMP_DIR` | `/tmp/supervisor-addon-updater` (commented) | Directory path | Temporary work directory. |
| `SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM` | `true` (commented) | Boolean | Requires `.sha256` asset to match. |
| `SUPERVISOR_GATEWAY_UPDATE_SUPERVISORCTL_BIN` | `supervisorctl` (commented) | Executable name/path | Used for reread/update/restart commands. |
| `SUPERVISOR_GATEWAY_UPDATE_RESTART_PROGRAMS` | `supervisor-gateway` (commented) | CSV list | Programs restarted after install. |

## Panel Build Overrides (`VITE_*`)

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `VITE_GATEWAY_URL` | `https://127.0.0.1:8080` (commented) | Absolute URL | Optional API base override for panel build. |
| `VITE_GATEWAY_TOKEN_MODE` | `bearer` (commented) | `bearer` or `x-api-token` | Header mode for non-cookie token fallback. |
| `VITE_DEFAULT_SERVER_ID` | `enshrouded` (commented) | String | Default selected server in UI. |

## Addon Action Mapping and Paths

| Variable | Default in `.env.example` | Allowed values / constraints | Notes |
| --- | --- | --- | --- |
| `SUPERVISOR_ADDON_SERVER_ID` | `enshrouded` (commented) | String | Logical server identifier in addon RPC. |
| `SUPERVISOR_ADDON_ACTION_SERVER_START_PROGRAM` | `enshrouded-server` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_ACTION_SERVER_STOP_PROGRAM` | `enshrouded-server` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_ACTION_SERVER_RESTART_PROGRAM` | `enshrouded-restart` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_ACTION_BACKUP_CREATE_PROGRAM` | `enshrouded-backup` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_ACTION_UPDATE_RUN_PROGRAM` | `enshrouded-updater` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_ACTION_UPDATE_FORCE_PROGRAM` | `enshrouded-force-update` (commented) | Supervisor program name | Action map target. |
| `SUPERVISOR_ADDON_FILES_ROOTS` | `/opt/enshrouded` (commented) | CSV paths | File roots; values are normalized to absolute paths. |
| `SUPERVISOR_ADDON_FILES_WRITABLE` | `server,backups` (commented) | CSV paths | Writable subset; relative entries resolve under first `FILES_ROOTS` item. |
| `SUPERVISOR_ADDON_BACKUP_DIR` | `server/backups` (commented) | Path | Backup location; relative values resolve under first `FILES_ROOTS` item. |
| `SUPERVISOR_ADDON_STARTUP_CONFIG` | `server/enshrouded_server.json` (commented) | Path | Primary startup config path; relative values resolve under first `FILES_ROOTS` item. |
| `SUPERVISOR_ADDON_STARTUP_FILES` | `server/enshrouded_server.json` (commented) | CSV paths | Startup file list; relative values resolve under first `FILES_ROOTS` item. |
| `SUPERVISOR_ADDON_ENV_KEYS` | empty (implicit/commented by use) | CSV env names | Additional env keys included in env catalog. |
| `SUPERVISOR_ADDON_ENV_EXPOSE_VALUES` | `false` (commented) | Boolean | If `false`, env catalog values are masked as `***`. |
| `SUPERVISOR_ADDON_LOG_STDOUT_PROGRAM` | `enshrouded-server` (implicit) | Supervisor program name | Source for stdout log methods. |
| `SUPERVISOR_ADDON_LOG_STDERR_PROGRAM` | `enshrouded-server` (implicit) | Supervisor program name | Source for stderr log methods. |

## Recommended Baselines

### Public access without domain (self-signed TLS)

```env
SUPERVISOR_GATEWAY_HOST=0.0.0.0
SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true
SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true
SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=false
SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true
SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=false
```

### Local/tunnel-only HTTP fallback

```env
SUPERVISOR_GATEWAY_HOST=127.0.0.1
SUPERVISOR_GATEWAY_REQUIRE_HTTPS=false
SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true
```
