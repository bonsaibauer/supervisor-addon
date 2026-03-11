from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..permissions import PERM_FILES_READ, PERM_FILES_WRITE
from ..security import get_settings, require_api_rate_limit, require_permission
from ..services import file_service
from ..services.activity_service import write_audit_event
from ..services.rpc_errors import raise_http_from_rpc
from .schemas import FileCreateFolderRequest, FileDeleteRequest, FileRenameRequest, FileWriteRequest


def create_files_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_api_rate_limit)])

    @router.get("/servers/{server_id}/files/list")
    async def list_files(
        server_id: str,
        path: str = Query(default="/"),
        root: str | None = Query(default=None),
        current: Settings = Depends(get_settings),
        _: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_READ, server_scoped=True)),
    ):
        try:
            result = await file_service.list_directory(current, server_id, path, root)
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/files/contents")
    async def read_file_contents(
        server_id: str,
        path: str = Query(..., min_length=1),
        root: str | None = Query(default=None),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_READ, server_scoped=True)),
    ):
        try:
            result = await file_service.read_file(current, server_id, path, root)
            write_audit_event(
                current,
                "file.read",
                {
                    "server_id": server_id,
                    "path": result.get("path", path),
                    "root": result.get("root", root),
                    "size": result.get("size"),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/files/write")
    async def write_file_contents(
        server_id: str,
        body: FileWriteRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_WRITE, server_scoped=True)),
    ):
        try:
            result = await file_service.write_file(current, server_id, body.path, body.content, body.root)
            write_audit_event(
                current,
                "file.write",
                {
                    "server_id": server_id,
                    "path": result.get("path", body.path),
                    "root": result.get("root", body.root),
                    "size": result.get("size"),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/files/create-folder")
    async def create_folder(
        server_id: str,
        body: FileCreateFolderRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_WRITE, server_scoped=True)),
    ):
        try:
            result = await file_service.create_folder(current, server_id, body.path, body.root)
            write_audit_event(
                current,
                "file.create_folder",
                {
                    "server_id": server_id,
                    "path": result.get("path", body.path),
                    "root": result.get("root", body.root),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/files/rename")
    async def rename_files(
        server_id: str,
        body: FileRenameRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_WRITE, server_scoped=True)),
    ):
        try:
            items = [item.model_dump() for item in body.items]
            result = await file_service.rename_items(current, server_id, items, body.root)
            write_audit_event(
                current,
                "file.rename",
                {
                    "server_id": server_id,
                    "root": body.root,
                    "count": result.get("count", len(items)),
                    "items": result.get("renamed", []),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/files/delete")
    async def delete_files(
        server_id: str,
        body: FileDeleteRequest,
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_WRITE, server_scoped=True)),
    ):
        try:
            result = await file_service.delete_paths(current, server_id, body.paths, body.root)
            write_audit_event(
                current,
                "file.delete",
                {
                    "server_id": server_id,
                    "root": body.root,
                    "count": result.get("count", len(body.paths)),
                    "paths": result.get("deleted", []),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.post("/servers/{server_id}/files/upload")
    async def upload_file(
        server_id: str,
        upload: UploadFile = File(...),
        directory: str = Form(default="/"),
        root: str | None = Form(default=None),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_WRITE, server_scoped=True)),
    ):
        try:
            result = await file_service.upload_file(current, server_id, directory, upload, root)
            write_audit_event(
                current,
                "file.upload",
                {
                    "server_id": server_id,
                    "path": result.get("path"),
                    "root": root,
                    "size": result.get("size"),
                    "filename": result.get("filename"),
                    "actor": identity.username,
                },
            )
            return {"ok": True, "server_id": server_id, **result}
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    @router.get("/servers/{server_id}/files/download")
    async def download_file(
        server_id: str,
        path: str = Query(..., min_length=1),
        root: str | None = Query(default=None),
        current: Settings = Depends(get_settings),
        identity: AuthenticatedIdentity = Depends(require_permission(PERM_FILES_READ, server_scoped=True)),
    ):
        try:
            file_path, virtual_path = await file_service.resolve_download_file(current, server_id, path, root)
            size = 0
            try:
                size = int(file_path.stat().st_size)
            except Exception:
                size = 0
            write_audit_event(
                current,
                "file.download",
                {
                    "server_id": server_id,
                    "path": virtual_path,
                    "root": root,
                    "size": size,
                    "filename": file_path.name,
                    "actor": identity.username,
                },
            )
            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type="application/octet-stream",
                headers={"X-Addon-Virtual-Path": virtual_path},
            )
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001
            raise_http_from_rpc(error)

    return router


