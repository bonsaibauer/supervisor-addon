from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import Settings
from .update_service import fetch_latest_release

_LOCK = threading.Lock()


@dataclass(frozen=True)
class InstallResult:
    ok: bool
    tag: str | None
    version: str | None
    checksum: str | None
    backup_path: str | None
    release_url: str | None
    restart_scheduled: bool
    steps: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tag": self.tag,
            "version": self.version,
            "checksum": self.checksum,
            "backup_path": self.backup_path,
            "release_url": self.release_url,
            "restart_scheduled": self.restart_scheduled,
            "steps": self.steps,
            "error": self.error,
        }


def _request(url: str, timeout_seconds: float) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "supervisor-gateway-installer",
        },
    )


def _download(url: str, destination: Path, timeout_seconds: float) -> str:
    hasher = hashlib.sha256()
    with urlopen(_request(url, timeout_seconds), timeout=timeout_seconds) as response:  # noqa: S310
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                hasher.update(chunk)
    return hasher.hexdigest()


def _try_download_checksum(url: str, timeout_seconds: float) -> str | None:
    try:
        with urlopen(_request(url, timeout_seconds), timeout=timeout_seconds) as response:  # noqa: S310
            text = response.read().decode("utf-8", errors="replace").strip()
    except (HTTPError, URLError, TimeoutError):
        return None
    if not text:
        return None
    token = text.split()[0].strip().lower()
    if len(token) == 64 and all(ch in "0123456789abcdef" for ch in token):
        return token
    return None


def _validate_staged_version(staged_root: Path, expected_tag: str) -> tuple[str, str]:
    version_path = staged_root / "config" / "version.json"
    if not version_path.is_file():
        raise RuntimeError(f"missing version file in release: {version_path}")

    payload = json.loads(version_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("invalid version.json payload")

    version = str(payload.get("version", "")).strip()
    tag = str(payload.get("tag", "")).strip()
    if not version or not tag:
        raise RuntimeError("version.json must include 'version' and 'tag'")
    if tag != expected_tag:
        raise RuntimeError(f"version.json tag mismatch: expected '{expected_tag}', got '{tag}'")
    return version, tag


def _run_checked(command: list[str]) -> str:
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        output = process.stderr.strip() or process.stdout.strip() or f"command failed: {' '.join(command)}"
        raise RuntimeError(output)
    return (process.stdout or "").strip()


def _safe_extract_tar(archive: tarfile.TarFile, target_dir: Path) -> None:
    target_dir_resolved = target_dir.resolve()
    for member in archive.getmembers():
        member_target = (target_dir_resolved / member.name).resolve()
        try:
            member_target.relative_to(target_dir_resolved)
        except ValueError:
            raise RuntimeError(f"unsafe archive path detected: {member.name}")
        # Disallow links/devices to avoid path-hijacking through symlink chains.
        if member.issym() or member.islnk() or member.isdev():
            raise RuntimeError(f"unsupported archive member type: {member.name}")
    archive.extractall(target_dir_resolved)


def _schedule_delayed_restart(supervisorctl_bin: str, program: str) -> None:
    subprocess.Popen(
        [supervisorctl_bin, "restart", program],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for entry in path.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _replace_directory_contents(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"source directory does not exist: {source}")
    target.mkdir(parents=True, exist_ok=True)
    _clear_directory(target)
    shutil.copytree(source, target, dirs_exist_ok=True)


def install_update(settings: Settings, requested_tag: str | None, restart: bool) -> InstallResult:
    if not settings.update_install_enabled:
        return InstallResult(
            ok=False,
            tag=None,
            version=None,
            checksum=None,
            backup_path=None,
            release_url=None,
            restart_scheduled=False,
            steps=["install disabled"],
            error="update install is disabled by configuration",
        )

    if not _LOCK.acquire(blocking=False):
        return InstallResult(
            ok=False,
            tag=None,
            version=None,
            checksum=None,
            backup_path=None,
            release_url=None,
            restart_scheduled=False,
            steps=["lock busy"],
            error="another update installation is already running",
        )

    steps: list[str] = []
    backup_archive_path: str | None = None
    release_url: str | None = None
    checksum: str | None = None
    tag: str | None = None
    version: str | None = None
    restart_scheduled = False

    current_root = Path(settings.update_root_dir).resolve()
    state_paths = (
        Path(settings.state_dir).resolve(),
        Path(settings.auth_users_dir).resolve(),
        Path(settings.auth_templates_dir).resolve(),
        Path(settings.news_state_file).resolve(),
        Path(settings.news_read_state_file).resolve(),
    )
    for path in state_paths:
        try:
            path.relative_to(current_root)
            return InstallResult(
                ok=False,
                tag=None,
                version=None,
                checksum=None,
                backup_path=None,
                release_url=None,
                restart_scheduled=False,
                steps=["validate persistent state paths"],
                error=(
                    f"persistent state path '{path}' is inside update root '{current_root}'. "
                    "Move SUPERVISOR_GATEWAY_STATE_DIR (and related files) outside update root."
                ),
            )
        except ValueError:
            pass
    backup_dir = Path(settings.update_backup_dir).resolve()
    tmp_dir = Path(settings.update_tmp_dir).resolve()
    current_parent = current_root.parent
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    swap_backup_path = current_parent / f".supervisor-addon.backup.{ts}"
    swap_new_path = current_parent / f".supervisor-addon.new.{ts}"
    work_dir = tmp_dir / f"run-{ts}"
    archive_path = work_dir / settings.update_asset_name
    extract_dir = work_dir / "extract"
    swapped = False
    moved_backup = False

    try:
        steps.append("fetch latest release metadata")
        latest = fetch_latest_release(settings)
        tag_raw = latest.get("tag_name")
        if not isinstance(tag_raw, str) or not tag_raw.strip():
            raise RuntimeError("latest release does not include tag_name")
        tag = tag_raw.strip()
        if requested_tag and requested_tag.strip() and requested_tag.strip() != tag:
            raise RuntimeError(f"requested tag '{requested_tag}' does not match latest tag '{tag}'")

        html_url = latest.get("html_url")
        if isinstance(html_url, str) and html_url.strip():
            release_url = html_url.strip()

        assets = latest.get("assets")
        if not isinstance(assets, list):
            raise RuntimeError("latest release assets are missing")

        asset = next((item for item in assets if isinstance(item, dict) and item.get("name") == settings.update_asset_name), None)
        if not asset:
            raise RuntimeError(f"release asset '{settings.update_asset_name}' not found")
        asset_url = asset.get("browser_download_url")
        if not isinstance(asset_url, str) or not asset_url.strip():
            raise RuntimeError("release asset download URL missing")

        checksum_asset_name = f"{settings.update_asset_name}.sha256"
        checksum_asset = next((item for item in assets if isinstance(item, dict) and item.get("name") == checksum_asset_name), None)
        checksum_url = None
        if checksum_asset and isinstance(checksum_asset.get("browser_download_url"), str):
            checksum_url = str(checksum_asset["browser_download_url"])

        steps.append("prepare workspace")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        steps.append("download release asset")
        checksum = _download(asset_url, archive_path, settings.github_timeout_seconds)

        steps.append("verify checksum")
        expected_checksum = _try_download_checksum(checksum_url, settings.github_timeout_seconds) if checksum_url else None
        if settings.update_require_checksum and not expected_checksum:
            raise RuntimeError(f"missing checksum asset '{checksum_asset_name}'")
        if expected_checksum and checksum != expected_checksum:
            raise RuntimeError("checksum mismatch for downloaded release asset")

        steps.append("extract release")
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract_tar(archive, extract_dir)

        steps.append("validate release version metadata")
        version, _ = _validate_staged_version(extract_dir, tag)
        for required_path in ("python", "panel", "config"):
            if not (extract_dir / required_path).exists():
                raise RuntimeError(f"release payload missing '{required_path}' directory")

        steps.append("install wheel from staged payload")
        wheel_candidates = sorted((extract_dir / "python").glob("supervisor_stack-*.whl"))
        if not wheel_candidates:
            raise RuntimeError("no supervisor_stack wheel found in staged payload")
        wheel_path = wheel_candidates[-1]
        _run_checked(
            [
                "python3",
                "-m",
                "pip",
                "install",
                "--break-system-packages",
                "--no-cache-dir",
                str(wheel_path),
            ]
        )

        steps.append("prepare atomic replacement")
        if swap_new_path.exists():
            shutil.rmtree(swap_new_path)
        shutil.copytree(extract_dir, swap_new_path)

        if not current_root.exists():
            raise RuntimeError(f"current install root does not exist: {current_root}")

        steps.append("swap current install with staged payload")
        if swap_backup_path.exists():
            shutil.rmtree(swap_backup_path)
        shutil.copytree(current_root, swap_backup_path)
        _replace_directory_contents(swap_new_path, current_root)
        swapped = True

        steps.append("store persistent backup")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_target = backup_dir / f"{tag.lstrip('v')}-{ts}"
        if backup_target.exists():
            shutil.rmtree(backup_target)
        shutil.move(str(swap_backup_path), str(backup_target))
        moved_backup = True
        backup_archive_path = str(backup_target)

        if restart:
            steps.append("run supervisor reread/update")
            _run_checked([settings.update_supervisorctl_bin, "reread"])
            _run_checked([settings.update_supervisorctl_bin, "update"])

            steps.append("restart configured programs")
            for program in settings.update_restart_programs:
                name = program.strip()
                if not name:
                    continue
                if name == "supervisor-gateway":
                    _schedule_delayed_restart(settings.update_supervisorctl_bin, name)
                    restart_scheduled = True
                else:
                    _run_checked([settings.update_supervisorctl_bin, "restart", name])

        return InstallResult(
            ok=True,
            tag=tag,
            version=version,
            checksum=checksum,
            backup_path=backup_archive_path,
            release_url=release_url,
            restart_scheduled=restart_scheduled,
            steps=steps,
            error=None,
        )
    except Exception as error:  # noqa: BLE001
        if swapped:
            try:
                restore_source: Path | None = None
                if moved_backup and backup_archive_path:
                    restore_source = Path(backup_archive_path)
                elif swap_backup_path.exists():
                    restore_source = swap_backup_path
                if restore_source is not None:
                    _replace_directory_contents(restore_source, current_root)
            except Exception:
                pass

        return InstallResult(
            ok=False,
            tag=tag,
            version=version,
            checksum=checksum,
            backup_path=backup_archive_path,
            release_url=release_url,
            restart_scheduled=restart_scheduled,
            steps=steps,
            error=str(error),
        )
    finally:
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
            if swap_new_path.exists():
                shutil.rmtree(swap_new_path)
        except Exception:
            pass
        _LOCK.release()
