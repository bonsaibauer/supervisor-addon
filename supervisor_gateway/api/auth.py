from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ..auth import AuthenticatedIdentity
from ..config import Settings
from ..security import (
    get_auth_service,
    get_settings,
    require_api_rate_limit,
    require_identity,
    require_login_rate_limit,
)
from ..services.activity_service import write_audit_event
from .schemas import LoginRequest
from .schemas import ChangePasswordRequest
from .schemas import PreferencesUpdateRequest


def create_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth")

    @router.post("/login", dependencies=[Depends(require_login_rate_limit)])
    async def login(
        body: LoginRequest,
        current: Settings = Depends(get_settings),
        auth_service=Depends(get_auth_service),
    ):
        if not auth_service.login_enabled:
            raise HTTPException(
                status_code=503,
                detail="api.auth.error.login_disabled",
            )

        try:
            identity = auth_service.authenticate_credentials(body.username.strip(), body.password)
            token = auth_service.issue_session_token(identity)
        except Exception:
            raise HTTPException(status_code=401, detail="api.auth.error.invalid_credentials")

        write_audit_event(
            current,
            "auth.login",
            {
                "actor": identity.username,
                "role": identity.role,
                "token_kind": identity.token_kind,
            },
        )

        payload = {
            "ok": True,
            "token": token,
            "token_type": "bearer",
            "expires_in": current.auth_token_ttl_seconds,
            "user": identity.to_public_dict(),
        }
        response = JSONResponse(content=payload)
        response.set_cookie(
            key="sgw_session",
            value=token,
            httponly=True,
            secure=current.require_https,
            samesite="strict",
            max_age=current.auth_token_ttl_seconds,
            path="/",
        )
        return response

    @router.get("/me", dependencies=[Depends(require_api_rate_limit)])
    async def me(identity: AuthenticatedIdentity = Depends(require_identity)):
        return {
            "ok": True,
            "user": identity.to_public_dict(),
        }

    @router.post("/change-password", dependencies=[Depends(require_api_rate_limit)])
    async def change_password(
        body: ChangePasswordRequest,
        identity: AuthenticatedIdentity = Depends(require_identity),
        current: Settings = Depends(get_settings),
        auth_service=Depends(get_auth_service),
    ):
        if identity.token_kind != "session":
            raise HTTPException(status_code=400, detail="api.auth.error.change_password_requires_session")

        try:
            updated_identity = auth_service.change_password(
                identity.username,
                body.current_password,
                body.new_password,
            )
            token = auth_service.issue_session_token(updated_identity)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error))

        write_audit_event(
            current,
            "auth.change_password",
            {
                "actor": identity.username,
            },
        )

        payload = {
            "ok": True,
            "token": token,
            "token_type": "bearer",
            "expires_in": current.auth_token_ttl_seconds,
            "user": updated_identity.to_public_dict(),
        }
        response = JSONResponse(content=payload)
        response.set_cookie(
            key="sgw_session",
            value=token,
            httponly=True,
            secure=current.require_https,
            samesite="strict",
            max_age=current.auth_token_ttl_seconds,
            path="/",
        )
        return response

    @router.post("/logout", dependencies=[Depends(require_api_rate_limit)])
    async def logout(current: Settings = Depends(get_settings)):
        response = JSONResponse(content={"ok": True})
        response.delete_cookie(
            key="sgw_session",
            path="/",
            httponly=True,
            secure=current.require_https,
            samesite="strict",
        )
        return response

    @router.patch("/preferences", dependencies=[Depends(require_api_rate_limit)])
    async def update_preferences(
        body: PreferencesUpdateRequest,
        identity: AuthenticatedIdentity = Depends(require_identity),
        current: Settings = Depends(get_settings),
        auth_service=Depends(get_auth_service),
    ):
        if identity.token_kind != "session":
            raise HTTPException(status_code=400, detail="api.auth.error.preferences_requires_session")

        if body.language is None and body.timezone is None:
            raise HTTPException(status_code=400, detail="api.auth.error.preferences_missing")

        try:
            updated_identity = auth_service.update_preferences(
                identity.username,
                language=body.language,
                timezone=body.timezone,
            )
            token = auth_service.issue_session_token(updated_identity)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error))

        write_audit_event(
            current,
            "auth.update_preferences",
            {
                "actor": identity.username,
                "language": updated_identity.language,
                "timezone": updated_identity.timezone,
            },
        )

        payload = {
            "ok": True,
            "token": token,
            "token_type": "bearer",
            "expires_in": current.auth_token_ttl_seconds,
            "user": updated_identity.to_public_dict(),
        }
        response = JSONResponse(content=payload)
        response.set_cookie(
            key="sgw_session",
            value=token,
            httponly=True,
            secure=current.require_https,
            samesite="strict",
            max_age=current.auth_token_ttl_seconds,
            path="/",
        )
        return response

    return router
