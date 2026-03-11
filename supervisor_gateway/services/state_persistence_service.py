from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from typing import Any

from ..config import Settings

_STATE_SCHEMA_MANIFEST = "state-schema.json"
_SCHEMA_VERSION = 1
_STATE_TARGET_VERSIONS: dict[str, int] = {
    "auth_users_dir": 2,
    "news_state": 1,
    "news_read_state": 1,
}


def _backup_file(path: Path) -> None:
    if not path.is_file():
        return
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = path.with_name(f"{path.name}.bak.{timestamp}")
    backup.write_bytes(path.read_bytes())


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as handle:
        json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
        handle.flush()
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": _SCHEMA_VERSION, "files": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid state schema manifest format: {path}")
    files = payload.get("files")
    if not isinstance(files, dict):
        files = {}
    return {"version": _SCHEMA_VERSION, "files": files}


def _write_manifest(path: Path, files: dict[str, int]) -> None:
    payload = {
        "version": _SCHEMA_VERSION,
        "updated_at": int(time.time()),
        "files": files,
    }
    _atomic_write_json(path, payload)


def _migrate_news_state_v0_to_v1(path: Path, payload: Any) -> tuple[Any, bool]:
    if isinstance(payload, dict):
        return payload, False
    raise RuntimeError(f"invalid news state payload in {path}: expected object")


def _migrate_news_read_state_v0_to_v1(path: Path, payload: Any) -> tuple[Any, bool]:
    if isinstance(payload, dict):
        return payload, False
    raise RuntimeError(f"invalid news read state payload in {path}: expected object")


def _migrate_file_to_target(
    *,
    state_name: str,
    path: Path,
    current_version: int,
    target_version: int,
) -> int:
    if current_version > target_version:
        raise RuntimeError(
            f"state '{state_name}' version {current_version} is newer than supported {target_version}"
        )
    if current_version == target_version:
        return current_version
    if not path.is_file():
        return target_version

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid JSON in persistent state '{path}'") from error

    changed = False
    version = current_version
    while version < target_version:
        if state_name == "news_state" and version == 0:
            payload, step_changed = _migrate_news_state_v0_to_v1(path, payload)
        elif state_name == "news_read_state" and version == 0:
            payload, step_changed = _migrate_news_read_state_v0_to_v1(path, payload)
        else:
            raise RuntimeError(f"missing migration path for state '{state_name}' from v{version}")
        changed = changed or step_changed
        version += 1

    if changed:
        _backup_file(path)
        _atomic_write_json(path, payload)

    return version


def _validate_auth_users_dir_v2(path: Path) -> None:
    if not path.is_dir():
        return
    for file_path in sorted(path.glob("*.json")):
        if not file_path.is_file():
            continue
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid auth user payload in {file_path}: expected object")
        preferences = payload.get("preferences")
        if not isinstance(preferences, dict):
            raise RuntimeError(
                f"invalid auth user payload in {file_path}: preferences object is required"
            )
        language = str(preferences.get("language", "")).strip()
        timezone = str(preferences.get("timezone", "")).strip()
        if not language:
            raise RuntimeError(
                f"invalid auth user payload in {file_path}: preferences.language is required"
            )
        if not timezone:
            raise RuntimeError(
                f"invalid auth user payload in {file_path}: preferences.timezone is required"
            )


def _migrate_auth_users_dir_to_target(path: Path, current_version: int, target_version: int) -> int:
    if current_version > target_version:
        raise RuntimeError(
            f"state 'auth_users_dir' version {current_version} is newer than supported {target_version}"
        )
    path.mkdir(parents=True, exist_ok=True)
    has_user_files = any(path.glob("*.json"))
    if current_version == 0 and not has_user_files:
        _validate_auth_users_dir_v2(path)
        return target_version
    if current_version != target_version:
        raise RuntimeError(
            f"state 'auth_users_dir' legacy version {current_version} is not supported; expected {target_version}"
        )
    _validate_auth_users_dir_v2(path)
    return target_version


def ensure_persistent_state_files(settings: Settings) -> None:
    state_dir = Path(settings.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    auth_users_dir = Path(settings.auth_users_dir)
    auth_users_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.auth_templates_dir).mkdir(parents=True, exist_ok=True)

    targets = [
        Path(settings.news_state_file),
        Path(settings.news_read_state_file),
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)

    manifest_path = state_dir / _STATE_SCHEMA_MANIFEST
    manifest = _read_manifest(manifest_path)
    file_versions_raw = manifest.get("files")
    file_versions = file_versions_raw if isinstance(file_versions_raw, dict) else {}

    state_paths = {
        "auth_users_dir": auth_users_dir,
        "news_state": Path(settings.news_state_file),
        "news_read_state": Path(settings.news_read_state_file),
    }

    updated_versions: dict[str, int] = {}
    for state_name, target_version in _STATE_TARGET_VERSIONS.items():
        current_version_raw = file_versions.get(state_name, 0)
        try:
            current_version = int(current_version_raw)
        except (TypeError, ValueError):
            current_version = 0

        path = state_paths[state_name]
        if state_name == "auth_users_dir":
            next_version = _migrate_auth_users_dir_to_target(path, current_version, target_version)
        else:
            next_version = _migrate_file_to_target(
                state_name=state_name,
                path=path,
                current_version=current_version,
                target_version=target_version,
            )
        updated_versions[state_name] = next_version

    _write_manifest(manifest_path, updated_versions)
