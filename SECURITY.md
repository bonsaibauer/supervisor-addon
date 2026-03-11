# Security Policy

This repository supports two primary deployment models.  
The first two sections are the main operational security baselines.  
All additional policy details follow below.

## 1. Standard Delivery Configuration (Public IP, No Domain)

This is the default deployment style for direct IP access, typically with self-signed TLS.

### Active security controls

- HTTPS enforcement via `SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true`
- Auto-generated self-signed certificate if missing via `SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true`
- Session security (signed tokens, expiry, secure/HttpOnly cookie behavior)
- API authentication via session and token headers (`Authorization`, `X-API-Token`)
- Role/permission checks and server-scope authorization on protected endpoints
- Security headers/CSP enabled by default (`SUPERVISOR_GATEWAY_SECURITY_HEADERS=true`)
- Rate limiting by client IP (API + login)
- File path restrictions with writable allowlist and traversal protection
- Update checksum verification support (`SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM=true` by runtime default)
- Audit logging support (`SUPERVISOR_GATEWAY_AUDIT_LOG_PATH`)

### Active shipped config (`.env.example`)

The following values are currently set in `.env.example`:

```env
SUPERVISOR_GATEWAY_HOST=0.0.0.0
SUPERVISOR_GATEWAY_PORT=8080
SUPERVISOR_GATEWAY_CORS_ORIGINS=https://127.0.0.1:8080,https://localhost:8080

SUPERVISOR_GATEWAY_REQUIRE_HTTPS=true
SUPERVISOR_GATEWAY_INSECURE_HTTP_LOCAL_ONLY=true
SUPERVISOR_GATEWAY_TRUST_PROXY_HEADERS=false
SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true

AUTH_TEMPLATE_GUEST_ENABLED=true
AUTH_TEMPLATE_VIEWER_ENABLED=true
AUTH_PASSWORD_MIN_LENGTH=8

SUPERVISOR_GATEWAY_UPDATE_INSTALL_ENABLED=true
SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=true
```

### Required operator actions for secure IP-only operation

1. Set persistent secrets:
   - `SUPERVISOR_GATEWAY_API_TOKEN`
   - `SUPERVISOR_GATEWAY_AUTH_SECRET`
2. Change bootstrap passwords immediately (default bootstrap password is `change-me`).
3. Add your actual public origin to CORS:
   - Example: `SUPERVISOR_GATEWAY_CORS_ORIGINS=https://<PUBLIC_IP>:8080`
4. For production hardening, set `SUPERVISOR_ADDON_ENV_EXPOSE_VALUES=false`.
5. If guest/viewer accounts are not needed, set:
   - `AUTH_TEMPLATE_GUEST_ENABLED=false`
   - `AUTH_TEMPLATE_VIEWER_ENABLED=false`
6. Restrict network access to trusted admin IPs where possible.

## 2. Domain Deployment (DNS + Reverse Proxy)

This is the recommended internet-facing production model.

### Required architecture

- Public HTTPS terminates at reverse proxy (`443`)
- Gateway runs on private/local upstream (`127.0.0.1:8080` or internal network)
- Only proxy can reach gateway upstream port
- Direct public access to gateway port must be blocked

### Required gateway env configuration

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

### Reverse proxy requirements

- Forward `X-Forwarded-Proto=https`
- Forward `X-Forwarded-For` and `Host`
- Enable managed TLS certificate renewal (for example Let's Encrypt)
- Preserve long-lived connections for SSE/log streaming

### Migration checklist (IP -> domain)

1. Create DNS (`A`/`AAAA`) for your panel host.
2. Deploy reverse proxy with TLS.
3. Block public inbound access to gateway port.
4. Apply env settings above and restart services.
5. Verify login/session flow and HTTPS/HSTS behavior.

## 3. GitHub Workflow Security (SARIF, Trivy, Release Integrity)

Security-relevant automation is implemented in:

- `.github/workflows/release-enshrouded.yml`

### What the workflow currently does

- Uses explicit permissions including `security-events: write` for code scanning upload.
- Runs Trivy filesystem scan in table format for `CRITICAL,HIGH` (non-blocking).
- Generates full SARIF scan for `CRITICAL,HIGH,MEDIUM` (non-blocking).
- Trims SARIF result locations (`max 1000`) to keep upload manageable.
- Uploads SARIF to GitHub Code Scanning (`github/codeql-action/upload-sarif@v4`, category `trivy-fs`).
- Publishes a security summary in GitHub Actions job summary.
- Uploads scan artifacts (`trivy.sarif`, `trivy.limited.sarif`) per run.
- Creates release archive checksum (`sha256`) and publishes `.sha256` alongside release asset.

### Security behavior note

Trivy findings are currently **informational in CI** (`--exit-code 0`), so vulnerabilities do not block release automatically.  
Operational enforcement is still available at install time via checksum validation (`SUPERVISOR_GATEWAY_UPDATE_REQUIRE_CHECKSUM=true`).

## Supported Versions

| Version line | Security updates |
| --- | --- |
| Latest release tag | Supported |
| Older release tags | Best effort, no guarantee |

## Reporting a Vulnerability

Please do not open public issues for sensitive vulnerabilities.

Preferred reporting path:

1. Use GitHub Security Advisories / private vulnerability reporting when available.
2. If private reporting is not available, contact repository maintainers directly.
3. Include:
   - affected version/tag
   - reproduction steps
   - impact assessment
   - suggested remediation if available

### Coordinated disclosure process

- Initial triage target: within 72 hours
- Status update target: within 7 days
- Fix and release timeline depends on severity and required testing

## Additional Security Documentation

- [docs/SECURITY_GUIDE.md](docs/SECURITY_GUIDE.md)
- [docs/ENV_EXAMPLE_REFERENCE.md](docs/ENV_EXAMPLE_REFERENCE.md)
