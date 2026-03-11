from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import Settings


def _auto_generate_enabled() -> bool:
    raw = os.getenv("SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_dns_name(value: str) -> str:
    token = value.strip().rstrip(".")
    if not token:
        raise ValueError("empty DNS SAN value")
    if "/" in token or " " in token or ":" in token:
        raise ValueError(f"invalid DNS SAN value '{value}'")
    return token


def _parse_san_token(token: str) -> tuple[str, str]:
    raw = token.strip()
    if not raw:
        raise ValueError("empty SAN token")

    kind = ""
    value = raw
    if ":" in raw:
        prefix, remainder = raw.split(":", 1)
        prefix_normalized = prefix.strip().lower()
        if prefix_normalized in {"ip", "dns"}:
            kind = prefix_normalized
            value = remainder.strip()

    if kind == "ip":
        try:
            ip = ipaddress.ip_address(value)
        except ValueError as error:
            raise ValueError(f"invalid IP SAN value '{value}'") from error
        return ("ip", str(ip))

    if kind == "dns":
        return ("dns", _normalize_dns_name(value))

    try:
        ip = ipaddress.ip_address(raw)
        return ("ip", str(ip))
    except ValueError:
        return ("dns", _normalize_dns_name(raw))


def _discover_bind_host_sans(settings: Settings) -> list[tuple[str, str]]:
    host = settings.host.strip()
    if not host or host in {"0.0.0.0", "::", "*", "localhost"}:
        return []
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_unspecified:
            return []
        return [("ip", str(ip))]
    except ValueError:
        return [("dns", _normalize_dns_name(host))]


def _discover_local_interface_ips(settings: Settings) -> list[tuple[str, str]]:
    if not settings.tls_auto_local_ips:
        return []

    discovered: list[tuple[str, str]] = []

    host_candidates = {socket.gethostname(), socket.getfqdn()}
    for hostname in host_candidates:
        if not hostname:
            continue
        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError:
            continue
        for info in infos:
            address = info[4][0]
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if ip.is_unspecified or ip.is_loopback:
                continue
            discovered.append(("ip", str(ip)))

    for target in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((target, 80))
                address = sock.getsockname()[0]
            ip = ipaddress.ip_address(address)
            if not ip.is_unspecified and not ip.is_loopback:
                discovered.append(("ip", str(ip)))
                break
        except OSError:
            continue

    return discovered


def _discover_public_ip(settings: Settings) -> list[tuple[str, str]]:
    if not settings.tls_auto_public_ip:
        return []

    timeout = settings.tls_public_ip_timeout_seconds
    for url in settings.tls_public_ip_providers:
        request = Request(url, headers={"User-Agent": "supervisor-gateway/auto-san"})
        try:
            with urlopen(request, timeout=timeout) as response:
                text = response.read(128).decode("utf-8", errors="ignore").strip()
        except (URLError, TimeoutError, OSError):
            continue
        try:
            ip = ipaddress.ip_address(text)
        except ValueError:
            continue
        if ip.is_unspecified or ip.is_loopback:
            continue
        return [("ip", str(ip))]
    return []


def _build_sans(settings: Settings) -> list[str]:
    entries: list[tuple[str, str]] = [("dns", "localhost"), ("ip", "127.0.0.1")]

    entries.extend(_discover_bind_host_sans(settings))
    entries.extend(_discover_local_interface_ips(settings))
    entries.extend(_discover_public_ip(settings))

    extra = os.getenv("SUPERVISOR_GATEWAY_TLS_EXTRA_SANS", "").strip()
    if extra:
        for item in extra.split(","):
            token = item.strip()
            if not token:
                continue
            entries.append(_parse_san_token(token))

    sans: list[str] = []
    seen: set[tuple[str, str]] = set()
    dns_index = 1
    ip_index = 1
    for kind, value in entries:
        key = (kind, value)
        if key in seen:
            continue
        seen.add(key)
        if kind == "dns":
            sans.append(f"DNS.{dns_index} = {value}")
            dns_index += 1
        else:
            sans.append(f"IP.{ip_index} = {value}")
            ip_index += 1

    return sans


def _generate_self_signed(cert_path: Path, key_path: Path, settings: Settings) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    config = "\n".join(
        [
            "[req]",
            "default_bits = 4096",
            "prompt = no",
            "default_md = sha256",
            "x509_extensions = v3_req",
            "distinguished_name = dn",
            "",
            "[dn]",
            "CN = localhost",
            "O = supervisor-addon",
            "",
            "[v3_req]",
            "subjectAltName = @alt_names",
            "keyUsage = digitalSignature, keyEncipherment",
            "extendedKeyUsage = serverAuth",
            "",
            "[alt_names]",
            *_build_sans(settings),
            "",
        ]
    )

    with tempfile.NamedTemporaryFile("w", encoding="ascii", delete=False) as handle:
        handle.write(config)
        config_path = Path(handle.name)

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:4096",
                "-sha256",
                "-days",
                "825",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-config",
                str(config_path),
                "-extensions",
                "v3_req",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            key_path.chmod(0o600)
        except Exception:
            pass
    except FileNotFoundError as error:
        raise RuntimeError(
            "HTTPS is enabled, but OpenSSL is not available for automatic certificate generation."
        ) from error
    except subprocess.CalledProcessError as error:
        output = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"automatic TLS certificate generation failed: {output}") from error
    finally:
        try:
            config_path.unlink(missing_ok=True)
        except Exception:
            pass


def ensure_runtime_tls(settings: Settings) -> None:
    if not settings.require_https:
        return
    if settings.trust_proxy_headers:
        return
    if not settings.tls_certfile or not settings.tls_keyfile:
        raise RuntimeError("HTTPS requires both TLS certificate and key paths.")

    cert_path = Path(settings.tls_certfile)
    key_path = Path(settings.tls_keyfile)
    if cert_path.is_file() and key_path.is_file():
        return

    if not _auto_generate_enabled():
        raise RuntimeError(
            "TLS certificate/key file missing and automatic generation is disabled. "
            "Set SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true or provide cert/key files."
        )

    _generate_self_signed(cert_path, key_path, settings)


def get_tls_certificate_expiry_days(settings: Settings) -> int | None:
    if not settings.tls_certfile:
        return None
    cert_path = Path(settings.tls_certfile)
    if not cert_path.is_file():
        return None

    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    line = (result.stdout or "").strip()
    if not line.startswith("notAfter="):
        return None
    value = line.split("=", 1)[1].strip()
    try:
        not_after = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    seconds_left = (not_after - datetime.now(timezone.utc)).total_seconds()
    return int(seconds_left // 86400)


def renew_tls_certificate(settings: Settings) -> dict[str, str | int]:
    if not settings.require_https:
        raise RuntimeError("TLS renewal requires HTTPS mode.")
    if settings.trust_proxy_headers:
        raise RuntimeError("TLS renewal is disabled when trusting proxy TLS headers.")
    if not settings.tls_certfile or not settings.tls_keyfile:
        raise RuntimeError("TLS renewal requires both certificate and key paths.")
    if not _auto_generate_enabled():
        raise RuntimeError(
            "Automatic TLS generation is disabled. Set SUPERVISOR_GATEWAY_TLS_AUTO_GENERATE=true to renew."
        )

    cert_path = Path(settings.tls_certfile)
    key_path = Path(settings.tls_keyfile)
    try:
        cert_path.unlink(missing_ok=True)
        key_path.unlink(missing_ok=True)
    except Exception as error:
        raise RuntimeError(f"failed to remove existing TLS files: {error}") from error

    _generate_self_signed(cert_path, key_path, settings)
    days = get_tls_certificate_expiry_days(settings)
    return {
        "certfile": str(cert_path),
        "keyfile": str(key_path),
        "expires_in_days": -1 if days is None else days,
    }
