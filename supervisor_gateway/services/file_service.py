from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import Settings
from .action_service import ActionService


@dataclass(frozen=True)
class ListedFile:
    name: str
    path: str
    is_file: bool
    is_dir: bool
    size: int
    modified_at: int
    mode: str


class ServerFileService:
    def __init__(
        self,
        server_id: str,
        files_config: dict[str, Any] | None,
        *,
        max_read_bytes: int,
        max_write_bytes: int,
        max_upload_bytes: int,
        blocked_paths: list[Path] | None = None,
    ):
        self.server_id = server_id
        self.files_config = files_config or {}
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes
        self.max_upload_bytes = max_upload_bytes
        self.blocked_paths = blocked_paths or []

        roots = self._parse_roots(self.files_config.get("roots"))
        if not roots:
            raise HTTPException(
                status_code=400,
                detail="api.files.error.no_roots_configured",
            )
        self.roots = roots

        writable = self._parse_roots(self.files_config.get("writable"))
        self.writable = writable or roots

    @staticmethod
    def _parse_roots(value: Any) -> list[Path]:
        if not value:
            return []
        if not isinstance(value, list):
            raise HTTPException(status_code=400, detail="api.files.error.roots_not_list")

        roots: list[Path] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                continue
            root = Path(item).resolve(strict=False)
            if not root.is_absolute():
                continue
            roots.append(root)
        return roots

    @staticmethod
    def _is_within(base: Path, target: Path) -> bool:
        try:
            target.relative_to(base)
            return True
        except ValueError:
            return False

    def _is_blocked(self, target: Path) -> bool:
        return any(self._is_within(blocked, target) for blocked in self.blocked_paths)

    def _pick_root(self, root_hint: str | None) -> Path:
        if not root_hint:
            return self.roots[0]

        for root in self.roots:
            if str(root) == root_hint:
                return root
        raise HTTPException(
            status_code=400,
            detail="api.files.error.unknown_root",
        )

    def _resolve_virtual_path(
        self, virtual_path: str, *, root_hint: str | None, require_writable: bool = False
    ) -> tuple[Path, Path]:
        root = self._pick_root(root_hint)
        normalized = (virtual_path or "").strip().replace("\\", "/")
        relative = normalized.lstrip("/")
        if relative == "":
            candidate = root
        else:
            candidate = (root / relative).resolve(strict=False)

        if not self._is_within(root, candidate):
            raise HTTPException(status_code=400, detail="api.files.error.path_escapes_root")

        if require_writable and not any(self._is_within(w, candidate) for w in self.writable):
            raise HTTPException(status_code=403, detail="api.files.error.path_outside_writable_roots")
        if self._is_blocked(candidate):
            raise HTTPException(status_code=403, detail="api.files.error.path_blocked")

        return candidate, root

    @staticmethod
    def _virtualize(path: Path, root: Path) -> str:
        relative = path.relative_to(root).as_posix()
        return "/" if relative in {"", "."} else f"/{relative}"

    def list_directory(self, path: str = "/", root_hint: str | None = None) -> dict[str, Any]:
        directory, root = self._resolve_virtual_path(path, root_hint=root_hint)
        if not directory.exists():
            raise HTTPException(status_code=404, detail="api.files.error.directory_not_found")
        if not directory.is_dir():
            raise HTTPException(status_code=400, detail="api.files.error.path_not_directory")

        items: list[ListedFile] = []
        for entry in sorted(
            directory.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        ):
            if self._is_blocked(entry):
                continue
            stat = entry.stat()
            items.append(
                ListedFile(
                    name=entry.name,
                    path=self._virtualize(entry, root),
                    is_file=entry.is_file(),
                    is_dir=entry.is_dir(),
                    size=0 if entry.is_dir() else int(stat.st_size),
                    modified_at=int(stat.st_mtime),
                    mode=oct(stat.st_mode & 0o777),
                )
            )

        return {
            "root": str(root),
            "path": self._virtualize(directory, root),
            "items": [item.__dict__ for item in items],
        }

    def read_file(self, path: str, root_hint: str | None = None) -> dict[str, Any]:
        file_path, root = self._resolve_virtual_path(path, root_hint=root_hint)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="api.files.error.file_not_found")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="api.files.error.path_not_file")

        size = file_path.stat().st_size
        if size > self.max_read_bytes:
            raise HTTPException(
                status_code=413,
                detail="api.files.error.file_too_large_read",
            )

        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "root": str(root),
            "path": self._virtualize(file_path, root),
            "size": size,
            "content": content,
        }

    def write_file(self, path: str, content: str, root_hint: str | None = None) -> dict[str, Any]:
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_write_bytes:
            raise HTTPException(
                status_code=413,
                detail="api.files.error.content_too_large",
            )

        file_path, root = self._resolve_virtual_path(
            path, root_hint=root_hint, require_writable=True
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(encoded)

        return {
            "root": str(root),
            "path": self._virtualize(file_path, root),
            "size": len(encoded),
            "written": True,
        }

    def create_folder(self, path: str, root_hint: str | None = None) -> dict[str, Any]:
        folder, root = self._resolve_virtual_path(path, root_hint=root_hint, require_writable=True)
        folder.mkdir(parents=True, exist_ok=True)
        return {"root": str(root), "path": self._virtualize(folder, root), "created": True}

    def rename_items(self, items: list[dict[str, str]], root_hint: str | None = None) -> dict[str, Any]:
        if not items:
            raise HTTPException(status_code=400, detail="api.files.error.rename_items_missing")

        moved: list[dict[str, str]] = []
        for item in items:
            source_str = item.get("source", "")
            target_str = item.get("target", "")
            if not source_str or not target_str:
                raise HTTPException(status_code=400, detail="api.files.error.rename_item_invalid")

            source_path, source_root = self._resolve_virtual_path(
                source_str, root_hint=root_hint, require_writable=True
            )
            target_path, target_root = self._resolve_virtual_path(
                target_str, root_hint=root_hint, require_writable=True
            )
            if source_root != target_root:
                raise HTTPException(status_code=400, detail="api.files.error.cross_root_rename_not_supported")
            if not source_path.exists():
                raise HTTPException(status_code=404, detail="api.files.error.rename_source_not_found")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.rename(target_path)
            moved.append(
                {
                    "from": self._virtualize(source_path, source_root),
                    "to": self._virtualize(target_path, target_root),
                }
            )

        return {"renamed": moved, "count": len(moved)}

    def delete_paths(self, paths: list[str], root_hint: str | None = None) -> dict[str, Any]:
        if not paths:
            raise HTTPException(status_code=400, detail="api.files.error.delete_paths_missing")

        deleted: list[str] = []
        for path in paths:
            target, root = self._resolve_virtual_path(path, root_hint=root_hint, require_writable=True)
            if target == root:
                raise HTTPException(status_code=400, detail="api.files.error.delete_root_forbidden")
            if not target.exists():
                continue

            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            deleted.append(self._virtualize(target, root))

        return {"deleted": deleted, "count": len(deleted)}

    def resolve_download_file(self, path: str, root_hint: str | None = None) -> tuple[Path, str]:
        file_path, root = self._resolve_virtual_path(path, root_hint=root_hint)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="api.files.error.file_not_found")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="api.files.error.path_not_file")
        return file_path, self._virtualize(file_path, root)

    async def upload_file(
        self, directory: str, upload: UploadFile, root_hint: str | None = None
    ) -> dict[str, Any]:
        folder, root = self._resolve_virtual_path(
            directory, root_hint=root_hint, require_writable=True
        )
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail="api.files.error.upload_directory_invalid")

        filename = Path(upload.filename or "upload.bin").name
        if filename in {"", ".", ".."}:
            raise HTTPException(status_code=400, detail="api.files.error.upload_filename_invalid")

        target = (folder / filename).resolve(strict=False)
        if not self._is_within(folder, target):
            raise HTTPException(status_code=400, detail="api.files.error.upload_target_invalid")
        if not any(self._is_within(w, target) for w in self.writable):
            raise HTTPException(status_code=403, detail="api.files.error.upload_target_outside_writable_roots")

        written = 0
        with target.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > self.max_upload_bytes:
                    handle.close()
                    try:
                        target.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=413,
                        detail="api.files.error.upload_exceeds_limit",
                    )
                handle.write(chunk)

        return {
            "uploaded": True,
            "path": self._virtualize(target, root),
            "size": written,
            "filename": filename,
        }


async def build_server_file_service(settings: Settings, server_id: str) -> ServerFileService:
    action_service = ActionService(settings)
    server_data = await action_service.get_server(server_id)
    blocked_paths: set[Path] = set()
    for tls_path_raw in (settings.tls_certfile, settings.tls_keyfile):
        if not tls_path_raw:
            continue
        tls_path = Path(tls_path_raw).resolve(strict=False)
        blocked_paths.add(tls_path)
        parent = tls_path.parent
        if parent != Path(tls_path.anchor or ""):
            blocked_paths.add(parent)
    return ServerFileService(
        server_id=server_id,
        files_config=server_data.get("files"),
        max_read_bytes=settings.files_max_read_bytes,
        max_write_bytes=settings.files_max_write_bytes,
        max_upload_bytes=settings.files_max_upload_bytes,
        blocked_paths=sorted(blocked_paths),
    )


async def list_directory(settings: Settings, server_id: str, path: str, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.list_directory, path, root)


async def read_file(settings: Settings, server_id: str, path: str, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.read_file, path, root)


async def write_file(settings: Settings, server_id: str, path: str, content: str, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.write_file, path, content, root)


async def create_folder(settings: Settings, server_id: str, path: str, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.create_folder, path, root)


async def rename_items(settings: Settings, server_id: str, items: list[dict[str, str]], root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.rename_items, items, root)


async def delete_paths(settings: Settings, server_id: str, paths: list[str], root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.delete_paths, paths, root)


async def upload_file(settings: Settings, server_id: str, directory: str, upload, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await service.upload_file(directory, upload, root)


async def resolve_download_file(settings: Settings, server_id: str, path: str, root: str | None):
    service = await build_server_file_service(settings, server_id)
    return await asyncio.to_thread(service.resolve_download_file, path, root)
