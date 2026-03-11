from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class PreferencesUpdateRequest(BaseModel):
    language: str | None = None
    timezone: str | None = None


class RunActionRequest(BaseModel):
    wait: bool = False


class PowerRequest(BaseModel):
    signal: Literal["start", "stop", "restart", "restart_safe"]
    wait: bool = False


class UpdateRequest(BaseModel):
    mode: Literal["run", "force"] = "run"
    wait: bool = False


class InstallUpdateRequest(BaseModel):
    tag: str | None = None
    restart: bool = True


class NewsReadRequest(BaseModel):
    read: bool = True


class MessageResponse(BaseModel):
    ok: bool
    message: str | None = None
    data: dict[str, Any] | list[Any] | None = None


class FileWriteRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str
    root: str | None = None


class FileCreateFolderRequest(BaseModel):
    path: str = Field(min_length=1)
    root: str | None = None


class FileRenameItem(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class FileRenameRequest(BaseModel):
    items: list[FileRenameItem]
    root: str | None = None


class FileDeleteRequest(BaseModel):
    paths: list[str]
    root: str | None = None
