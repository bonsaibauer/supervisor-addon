from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import threading
import time
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from ..config import Settings

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass(frozen=True)
class UpdateStatus:
    current_version: str
    latest_version: str | None
    latest_tag: str | None
    update_available: bool
    release_url: str
    update_kind: str
    required_action: str
    primary_button: str
    reason: str | None
    recommended_steps: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "latest_tag": self.latest_tag,
            "update_available": self.update_available,
            "release_url": self.release_url,
            "update_kind": self.update_kind,
            "required_action": self.required_action,
            "primary_button": self.primary_button,
            "reason": self.reason,
            "recommended_steps": self.recommended_steps,
            "error": self.error,
        }


def _normalize_semver(raw: str | None) -> tuple[int, int, int] | None:
    if not raw:
        return None
    match = _SEMVER_RE.match(raw.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _read_installed_version(settings: Settings) -> str:
    version_file = settings.release_version_file
    if version_file:
        try:
            payload = json.loads(Path(version_file).read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                for key in ("version", "tag"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip().lstrip("v")
        except Exception:
            pass

    return "unknown"


def _fetch_latest_release(owner: str, repo: str, timeout_seconds: float) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "supervisor-gateway-update-check",
        },
    )
    with urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("github release response was not an object")
    return payload


def _fetch_release_version_json(latest_payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any] | None:
    assets = latest_payload.get("assets")
    if not isinstance(assets, list):
        return None
    version_asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict)
            and str(item.get("name", "")).strip() == "version.json"
            and isinstance(item.get("browser_download_url"), str)
        ),
        None,
    )
    if not version_asset:
        return None
    url = str(version_asset.get("browser_download_url", "")).strip()
    if not url:
        return None

    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "supervisor-gateway-update-check",
        },
    )
    with urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if isinstance(payload, dict):
        return payload
    return None


def fetch_latest_release(settings: Settings) -> dict[str, Any]:
    return _fetch_latest_release(settings.github_owner, settings.github_repo, settings.github_timeout_seconds)


def _cache_key(settings: Settings) -> str:
    return f"{settings.github_owner}/{settings.github_repo}"


def _get_cached(settings: Settings) -> dict[str, Any] | None:
    key = _cache_key(settings)
    now = time.time()
    with _CACHE_LOCK:
        data = _CACHE.get(key)
        if not data:
            return None
        expires_at, payload = data
        if expires_at < now:
            _CACHE.pop(key, None)
            return None
        return payload


def _set_cached(settings: Settings, payload: dict[str, Any]) -> None:
    key = _cache_key(settings)
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + settings.github_cache_seconds, payload)


def get_update_status(settings: Settings, *, force_refresh: bool = False) -> UpdateStatus:
    current_version = _read_installed_version(settings)
    release_url = f"https://github.com/{settings.github_owner}/{settings.github_repo}/releases/latest"
    version_error = None
    if current_version == "unknown":
        version_error = (
            f"installed version unavailable: expected version file at '{settings.release_version_file}'"
        )

    latest_payload = None if force_refresh else _get_cached(settings)
    if latest_payload is None:
        try:
            latest_payload = _fetch_latest_release(
                settings.github_owner,
                settings.github_repo,
                settings.github_timeout_seconds,
            )
            try:
                version_manifest = _fetch_release_version_json(latest_payload, settings.github_timeout_seconds)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
                version_manifest = None
            if isinstance(version_manifest, dict):
                latest_payload = dict(latest_payload)
                latest_payload["__version_manifest"] = version_manifest
            _set_cached(settings, latest_payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
            return UpdateStatus(
                current_version=current_version,
                latest_version=None,
                latest_tag=None,
                update_available=False,
                release_url=release_url,
                update_kind="unknown",
                required_action="none",
                primary_button="No action needed",
                reason=None,
                recommended_steps=[],
                error=str(error),
            )

    latest_tag_raw = latest_payload.get("tag_name")
    latest_tag = str(latest_tag_raw).strip() if isinstance(latest_tag_raw, str) else None
    latest_version = latest_tag.lstrip("v") if latest_tag else None

    current_semver = _normalize_semver(current_version)
    latest_semver = _normalize_semver(latest_tag)
    update_available = bool(current_semver and latest_semver and latest_semver > current_semver)

    version_manifest = latest_payload.get("__version_manifest")
    manifest = version_manifest if isinstance(version_manifest, dict) else None
    if manifest is None:
        try:
            manifest = _fetch_release_version_json(latest_payload, settings.github_timeout_seconds)
            if isinstance(manifest, dict):
                latest_payload = dict(latest_payload)
                latest_payload["__version_manifest"] = manifest
                _set_cached(settings, latest_payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
            manifest = None

    update_kind = "no_action"
    required_action = "none"
    primary_button = "No action needed"
    reason = None
    recommended_steps: list[str] = []

    if update_available:
        if isinstance(manifest, dict):
            update_kind = str(manifest.get("update_kind", "unknown")).strip() or "unknown"
            required_action = str(manifest.get("required_action", "gateway_restart")).strip() or "gateway_restart"
            primary_button = str(manifest.get("primary_button", "Restart Gateway")).strip() or "Restart Gateway"
            reason_raw = manifest.get("reason")
            reason = str(reason_raw).strip() if isinstance(reason_raw, str) and reason_raw.strip() else None
            steps_raw = manifest.get("recommended_steps")
            if isinstance(steps_raw, list):
                recommended_steps = [str(step).strip() for step in steps_raw if str(step).strip()]
        if not recommended_steps:
            update_kind = update_kind if update_kind != "no_action" else "unknown"
            required_action = required_action if required_action != "none" else "gateway_restart"
            primary_button = primary_button if primary_button != "No action needed" else "Restart Gateway"
            if not reason:
                reason = "Apply update and restart supervisor-gateway."
            recommended_steps = [
                "Install update from panel/API.",
                "Restart supervisor-gateway.",
                "Reload browser if panel assets were changed.",
            ]

    return UpdateStatus(
        current_version=current_version.lstrip("v"),
        latest_version=latest_version,
        latest_tag=latest_tag,
        update_available=update_available,
        release_url=release_url,
        update_kind=update_kind,
        required_action=required_action,
        primary_button=primary_button,
        reason=reason,
        recommended_steps=recommended_steps,
        error=version_error,
    )
