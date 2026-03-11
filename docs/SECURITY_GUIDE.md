# Security Guide

This document explains the security model and current security controls of this repository:

- `supervisor_gateway` (FastAPI API + panel hosting + auth + TLS + update install)
- `supervisor_addon` (Supervisor XML-RPC addon)
- `panel` (React frontend)

It is written for operators who deploy the stack directly on an IP address (no domain) with self-signed TLS certificates.

## 1. Security Goals and Scope

Primary goals:

- Protect server-control operations (start/stop/restart/update/backup).
- Protect file operations (read/write/upload/download) against path traversal and unrestricted access.
- Protect authentication state and secrets.
- Keep API traffic encrypted by default.
- Provide safe-by-default startup behavior.
- Maintain auditability of high-impact actions.

Out of scope:

- Host OS hardening (kernel, firewall, IDS, fail2ban).
- Network perimeter controls outside this container/service.
- Secrets management platform integration (Vault, KMS, etc.).

## 2. High-Level Security Architecture

Security-relevant design choices in this repo:

- Single gateway process exposes API and panel on one port.
- Supervisor RPC is restricted to Unix socket (`unix://...`) and not exposed as inet/http RPC.
- HTTPS is enabled by default (`SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true`).
- If cert/key files are missing and auto-generation is enabled, a self-signed cert/key is generated at startup.
- Authentication supports:
  - session cookie (`sgw_session`, `HttpOnly`, `SameSite=Strict`)
  - bearer token header
  - `X-API-Token` header
- Role and server-scope authorization is enforced per endpoint.
- API/login rate limits are enforced per client IP.
- Security headers are set for responses (CSP, HSTS on HTTPS, frame deny, no-sniff, etc.).
- File endpoints enforce configured roots + writable sub-roots and block root-escape attempts.
- Audit log events are written for security-relevant operations.

## 3. Current Deployment Pattern: Public IP, No Domain, Self-Signed TLS

Your current model (IP-only access, no DNS name, self-signed certificate) is supported.

### What this means in practice

- Browser certificate warnings are expected unless clients trust your cert/CA manually.
- TLS still encrypts transport and protects against passive interception.
- Identity trust is weaker than a CA-issued cert until clients pin/trust it.
- CORS must include the exact panel origins you use (for example `https://<PUBLIC_IP>:8080`).

### Recommended baseline for this model

```env
SUPERVISOR_GATEWAY_HOST=0.0.0.0
SUPERVISOR_GATEWAY_PORT=8080

SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true
SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true
SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=false
SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true

SUPERVISOR_GATEWAY_CORS_ORIGINS=https://127.0.0.1:8080,https://localhost:8080,https://<PUBLIC_IP>:8080
SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS=false

SUPERVISOR_GATEWAY_API_TOKEN=<set-persistent-secret>
SUPERVISOR_GATEWAY_AUTH_SECRET=<set-persistent-secret>

SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=false
```

## 4. Threat Model (Practical)

Main threats this repo addresses:

- Unauthenticated API access.
- Privilege misuse across roles.
- Cross-server scope abuse.
- File path traversal and writes outside approved roots.
- Brute-force login attempts.
- Cleartext transport in non-HTTPS mode.
- Proxy-header spoofing when misconfigured.
- Untrusted update payload tampering (checksum verification).

Residual risks to manage operationally:

- If default passwords (`change-me`) are not changed, compromise is trivial.
- If `SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=true` without strict network isolation, forwarded-header spoofing can bypass transport assumptions.
- If `SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=true`, sensitive env values can be revealed in UI/API views.
- If HTTP mode is used with remote exposure (`REQUIRE_HTTPS=false` and `INSECURE_HTTP_LOCAL_ONLY=false`), traffic can be intercepted.

## 5. Authentication and Session Security

Implemented controls:

- Password hashing uses PBKDF2-HMAC-SHA256 with per-password salt and high iteration count.
- Bootstrap users are generated with `must_change_password=true`.
- `admin` is always ensured; optional `guest`/`viewer` are synced from ENV flags.
- User authorization data is stored per-user JSON in `SUPERVISOR_GATEWAY_AUTH_USERS_DIR`.
- Bootstrap templates are read from JSON files in `SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR`.
- Session tokens are HMAC-signed and include expiration (`exp`).
- Session cookie settings:
  - `HttpOnly=true`
  - `Secure` follows `SUPERVISOR_GATEWAY_REQUIRE_HTTPS`
  - `SameSite=Strict`
  - bounded `max_age`
- `must_change_password` blocks session users from using protected endpoints until password rotation is completed.

Operator guidance:

- Always set persistent values for both:
  - `SUPERVISOR_GATEWAY_AUTH_SECRET`
  - `SUPERVISOR_GATEWAY_API_TOKEN`
- Change `change-me` immediately for all enabled accounts.
- Keep `AUTH_PASSWORD_MIN_LENGTH >= 8` (higher is better for internet exposure).

## 6. Authorization Model

Roles:

- Default roles are `admin`, `guest`, and `viewer`.
- Additional custom roles are supported through per-user JSON (`role` + `permissions`).

Enforcement model:

- Permission checks are attached per API endpoint.
- Server-scoped endpoints require the target `server_id` to be in the identity allowlist (or `*`).
- Non-global users are blocked from global activity reads without `server_id`.

## 7. Transport Security (HTTPS, TLS, Proxy)

### HTTPS enforcement

- If `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true`, non-HTTPS requests are rejected (API) or redirected (HTML routes).
- HSTS is added on HTTPS responses.

### Self-signed auto-generation

When enabled (`SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true`) and files are missing:

- Cert/key are generated automatically.
- SAN list includes:
  - `localhost`
  - `127.0.0.1`
  - optional bind host
  - optional discovered local interface IPs
  - optional discovered public IP
  - optional explicit entries from `SUPERVISOR_GATEWAY_TLS_EXTRA_SANS`

Renewal support:

- API supports certificate renewal endpoint for auto-generated cert mode.
- News/alerts report missing, expired, or soon-expiring certificates.

### Proxy mode

`SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=true` means:

- HTTPS detection can rely on `X-Forwarded-Proto`.
- Client IP can rely on `X-Forwarded-For`.

Use this only when direct access to gateway is blocked and only a trusted reverse proxy can reach it.

## 8. HTTP Fallback Safety Guard

If `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=false`:

- With `SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true`, only loopback clients are accepted.
- Startup fails if host is not loopback while local-only guard is enabled.

This is intentionally fail-safe to prevent accidental insecure remote exposure.

## 9. Security Headers

When `SUPERVISOR_GATEWAY_SECURITY_HEADERS=true` (default), gateway sets:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- CSP with strict defaults (`default-src 'self'`, `frame-ancestors 'none'`, etc.)
- `Strict-Transport-Security` on HTTPS requests

Also:

- `/auth/*` responses include `Cache-Control: no-store`.

## 10. CORS Security

CORS behavior is controlled by:

- `SUPERVISOR_GATEWAY_CORS_ORIGINS`
- `SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS`

Rules:

- `*` with credentials is rejected by config validation.
- For IP-only public usage, explicitly include your HTTPS IP origin.
- Keep origins minimal; avoid wildcard in exposed deployments.

## 11. Rate Limiting and Abuse Resistance

In-memory sliding-window limits per client IP:

- API: `SUPERVISOR_GATEWAY_API_RATE_LIMIT_PER_MINUTE` (default 240)
- Login: `SUPERVISOR_GATEWAY_LOGIN_RATE_LIMIT_PER_MINUTE` (default 10)

Additional limiter behavior:

- stale key pruning
- bounded key map to reduce memory blowup under key-flood conditions

## 12. File Access Security

File endpoints are permission-gated and enforce:

- allowed absolute roots (`SUPERVISOR_ADDON_FILES_ROOTS`)
- writable subset (`SUPERVISOR_ADDON_FILES_WRITABLE`)
- canonical path resolution with escape checks
- block writes/deletes outside writable roots
- refuse deleting configured root itself
- upload, read, write size limits
- filename/path normalization for uploads

This protects against classic traversal and arbitrary-path write/delete attacks.

## 13. Update Pipeline Security

Update install flow includes:

- fetch release metadata from configured GitHub repo
- download release tarball
- compute SHA-256 checksum
- optionally require `.sha256` asset and enforce match
- safe tar extraction (blocks path traversal, links, device entries)
- staged validation of required payload structure
- backup + replace + rollback on failure
- optional controlled restart via supervisorctl

Critical guardrail:

- Installation aborts if persistent state paths are inside update root, preventing state loss on replace.

## 14. Audit and Activity Trail

Gateway writes JSON-lines audit events for:

- login
- password change
- server control actions
- file operations
- TLS renew
- update install actions
- action reload

Config:

- `SUPERVISOR_GATEWAY_AUDIT_LOG_PATH`

Behavior:

- logging failure does not break successful API operations (availability-first).

## 15. Frontend Security Behavior

Panel-side behavior relevant to security:

- Uses `fetch(..., credentials: 'same-origin')`.
- Supports token headers (`Authorization` or `X-API-Token`) for non-cookie flows.
- Keeps token in volatile runtime memory (`volatileToken`), not persisted localStorage by default in current code path.
- UI permission checks are present, but server-side permission checks remain the source of truth.

## 16. Persistent State and Secret Handling

Security-relevant state files:

- `SUPERVISOR_GATEWAY_AUTH_USERS_DIR` (one JSON per user)
- `SUPERVISOR_GATEWAY_AUTH_TEMPLATES_DIR` (bootstrap templates)
- `SUPERVISOR_GATEWAY_NEWS_STATE_FILE`
- `SUPERVISOR_GATEWAY_NEWS_READ_STATE_FILE`

Best practice:

- Keep state directory on persistent storage outside update root.
- Restrict file permissions at OS/container level.
- Back up state securely (especially auth user and template directories).

## 17. Security-Relevant Environment Variables (Detailed)

This section focuses on variables with direct security impact.

### 17.1 Core Auth Secrets and Password Policy

| Variable | Purpose | Default behavior | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_API_TOKEN` | Static API token authentication | Random token generated at runtime if unset | Set explicitly and persist it |
| `SUPERVISOR_GATEWAY_AUTH_SECRET` | HMAC secret for session tokens | Random secret generated at runtime if unset | Set explicitly and persist it |
| `SUPERVISOR_GATEWAY_AUTH_TOKEN_TTL_SECONDS` | Session token lifetime | `28800` | Lower for stricter session risk (for example `3600`-`14400`) |
| `AUTH_PASSWORD_MIN_LENGTH` | Minimum new password length | `8` | Use `12+` for internet-facing panel |
| `AUTH_TEMPLATE_GUEST_ENABLED` | Enables `guest` bootstrap account | `false` | Keep `false` unless required |
| `AUTH_TEMPLATE_VIEWER_ENABLED` | Enables `viewer` bootstrap account | `false` | Enable only when needed |
| `AUTH_TEMPLATE_<NAME>_ENABLED` | Enables custom bootstrap template `<name>.json` | unset | Use explicit per-template flags only |

### 17.2 HTTPS, TLS, and Proxy Trust

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_REQUIRE_HTTPS` | Enforce HTTPS transport | `true` | Keep `true` |
| `SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE` | Auto-generate self-signed cert if missing | `true` | Keep `true` for IP-only self-signed mode |
| `SUPERVISOR_GATEWAY_TLS_CERTFILE` | TLS certificate path | `/opt/enshrouded/supervisor-addon/tls/gateway.crt` | Persist path in mounted volume |
| `SUPERVISOR_GATEWAY_TLS_KEYFILE` | TLS private key path | `/opt/enshrouded/supervisor-addon/tls/gateway.key` | Restrict file permissions |
| `SUPERVISOR_GATEWAY_TLS_AUTO_LOCAL_IPS` | Add local interface IP SANs | `true` | Keep `true` for LAN/IP access |
| `SUPERVISOR_GATEWAY_TLS_AUTO_PUBLIC_IP` | Add public IP SAN | `true` | Keep `true` for direct public-IP access |
| `SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_TIMEOUT_SECONDS` | Provider timeout | `2.0` | Keep low (1-3s) |
| `SUPERVISOR_GATEWAY_TLS_PUBLIC_IP_PROVIDERS` | Public IP discovery endpoints | `ipify`, `ifconfig.me` | Use trusted providers only |
| `SUPERVISOR_GATEWAY_TLS_EXTRA_SANS` | Extra SAN entries (`DNS:`/`IP:`) | empty | Add explicit IP/DNS used by clients |
| `SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS` | Trust forwarded proto/IP headers | `false` | Keep `false` unless behind strict trusted proxy |
| `SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY` | Localhost-only guard in HTTP mode | `true` | Keep `true` |

### 17.3 CORS and Browser Boundary

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_CORS_ORIGINS` | Allowed browser origins | `https://127.0.0.1:8080,https://localhost:8080` | Add exact public IP origin; avoid `*` |
| `SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS` | Credentialed CORS | `false` | Keep `false` unless you require cross-origin cookies |
| `SUPERVISOR_GATEWAY_SECURITY_HEADERS` | Enables security headers/CSP | `true` | Keep `true` |

### 17.4 Rate Limiting and Exposure Surface

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_API_RATE_LIMIT_PER_MINUTE` | API request cap per IP | `240` | Tune lower for internet exposure if needed |
| `SUPERVISOR_GATEWAY_LOGIN_RATE_LIMIT_PER_MINUTE` | Login attempt cap per IP | `10` | Keep strict (5-10) |
| `SUPERVISOR_GATEWAY_HOST` | Bind interface | `0.0.0.0` | Use `0.0.0.0` only when remote access is needed |
| `SUPERVISOR_GATEWAY_PORT` | Listening port | `8080` | Use firewall/security-group restrictions |

### 17.5 File Operation Constraints

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_FILES_MAX_READ_BYTES` | Max single read size | `2097152` | Keep low enough to prevent abuse |
| `SUPERVISOR_GATEWAY_FILES_MAX_WRITE_BYTES` | Max single write size | `2097152` | Keep low enough to prevent abuse |
| `SUPERVISOR_GATEWAY_FILES_MAX_UPLOAD_BYTES` | Max upload size | `209715200` | Set based on real backup/config needs |
| `SUPERVISOR_ADDON_FILES_ROOTS` | Allowed file roots | `/opt/enshrouded` | Keep minimal |
| `SUPERVISOR_ADDON_FILES_WRITABLE` | Writable subset roots | `/opt/enshrouded/server,/opt/enshrouded/backups` | Keep narrow |

### 17.6 Sensitive Data Exposure Controls

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_ADDON_ENV_EXPOSE_VALUES` | Show real env values in env catalog | `false` | Keep `false` in production |
| `SUPERVISOR_GATEWAY_AUDIT_LOG_PATH` | Audit file path | `/var/log/supervisor/supervisor-gateway-audit.log` | Protect file permissions and rotate logs |

### 17.7 Update and Supply-Chain Safeguards

| Variable | Purpose | Default | Security recommendation |
| --- | --- | --- | --- |
| `SUPERVISOR_GATEWAY_UPDATE_INSTALL_ENABLED` | Enable update install API | `true` | Disable if central update control is required |
| `SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM` | Require `.sha256` checksum asset | `true` | Keep `true` |
| `SUPERVISOR_GATEWAY_GITHUB_OWNER` | Release source owner | `bonsaibauer` | Pin to trusted owner |
| `SUPERVISOR_GATEWAY_GITHUB_REPO` | Release source repo | `supervisor-addon` | Pin to trusted repo |
| `SUPERVISOR_GATEWAY_UPDATE_ROOT_DIR` | Replace target | `/opt/supervisor-addon` | Keep state dirs outside this path |
| `SUPERVISOR_GATEWAY_STATE_DIR` | Persistent auth/news state root | `/opt/enshrouded/supervisor-addon` | Keep outside update root |

## 18. Hardening Checklist for Production (IP-Only + Self-Signed)

1. Set persistent secrets:
   - `SUPERVISOR_GATEWAY_API_TOKEN`
   - `SUPERVISOR_GATEWAY_AUTH_SECRET`
2. Keep HTTPS required and local HTTP guard enabled.
3. Keep proxy header trust disabled unless strictly required.
4. Add exact public IP origin to `SUPERVISOR_GATEWAY_CORS_ORIGINS`.
5. Keep `SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=false`.
6. Change all default bootstrap passwords immediately.
7. Keep state files on persistent volume outside update root.
8. Restrict network access with firewall/security groups to known admin IPs when possible.
9. Monitor audit logs for failed logins and high-risk actions.
10. Keep checksum verification enabled for updates.

## 19. Quick Validation Commands

Run these from inside the container/host where gateway is reachable:

```bash
# health over TLS (self-signed -> -k)
curl -kfsS https://127.0.0.1:8080/health

# verify HTTPS-only rejection path if accidentally using HTTP
curl -sS http://127.0.0.1:8080/health

# inspect certificate SANs and expiry
openssl x509 -in /opt/enshrouded/supervisor-addon/tls/gateway.crt -noout -text | grep -E "Subject:|DNS:|IP Address:|Not After"
```

## 20. Related Documentation

- Environment details and full variable catalog: `docs/ENV_EXAMPLE_REFERENCE.md`
- Startup and integration details: `README.md`

## 21. Steps for Domain + Reverse Proxy Deployment

This is the recommended setup for internet-facing production.

### 21.1 Target Architecture

- Public traffic terminates TLS at reverse proxy (`443`).
- Reverse proxy forwards requests to gateway on private/local network (`http://127.0.0.1:8080`).
- Gateway trusts forwarded headers from proxy only.
- Direct public access to gateway port is blocked by firewall/security group.

### 21.2 Step-by-Step Migration

1. Create DNS records
   - Add an `A` (and/or `AAAA`) record for your domain (for example `panel.example.com`) to your server IP.
2. Open only required public ports
   - Allow inbound `80/tcp` and `443/tcp` for ACME and HTTPS.
   - Block public access to gateway port `8080` (allow local/proxy path only).
3. Install and configure reverse proxy
   - Use Nginx, Caddy, or Traefik.
   - Enable automatic certificate issuance/renewal (for example Let's Encrypt).
4. Set gateway env for proxy mode
   - `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true`
   - `SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=true`
   - `SUPERVISOR_GATEWAY_CORS_ORIGINS=https://panel.example.com`
   - Keep `SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true`
5. Recreate/restart container/service
   - Env changes are startup-only.
6. Verify headers and auth flow
   - Confirm HTTPS, HSTS, and successful login/session behavior.
7. Enforce network boundary
   - Ensure only reverse proxy can reach gateway upstream endpoint.

### 21.3 Example: Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name panel.example.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name panel.example.com;

    ssl_certificate /etc/letsencrypt/live/panel.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/panel.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE/log streaming stability
        proxy_buffering off;
        proxy_read_timeout 3600;
    }
}
```

### 21.4 Example Env for Domain + Proxy

```env
SUPERVISOR_GATEWAY_HOST=0.0.0.0
SUPERVISOR_GATEWAY_PORT=8080

SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true
SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=true
SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true

SUPERVISOR_GATEWAY_CORS_ORIGINS=https://panel.example.com
SUPERVISOR_GATEWAY_CORS_ALLOW_CREDENTIALS=false

SUPERVISOR_GATEWAY_API_TOKEN=<persistent-secret>
SUPERVISOR_GATEWAY_AUTH_SECRET=<persistent-secret>
SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=false
```

### 21.5 Important Notes

- When `SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=true`, do not expose gateway directly to the internet.
- In proxy mode, TLS cert files on gateway are optional, because TLS terminates at proxy.
- Keep origin list strict; do not use wildcard CORS for production.
- Rotate secrets if gateway was previously exposed directly without proxy protection.

