from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from .api.activity import create_activity_router
from .api.auth import create_auth_router
from .api.files import create_files_router
from .api.logs import create_logs_router
from .api.power import create_power_router
from .api.schemas import MessageResponse
from .api.servers import create_servers_router
from .config import Settings
from .security import is_https_request, is_local_request
from .services.action_service import ActionService
from .services.state_persistence_service import ensure_persistent_state_files


def _safe_panel_path(panel_root: Path, requested: str) -> Path:
    candidate = (panel_root / requested.lstrip("/")).resolve()
    try:
        candidate.relative_to(panel_root)
    except ValueError:
        return panel_root / "index.html"
    return candidate


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/") or path.startswith("/auth/") or path == "/health"


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    if not accept:
        return False
    return "text/html" in accept and "application/json" not in accept


def _status_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(url=f"/status/{code}", status_code=303)


def create_app() -> FastAPI:
    settings = Settings.from_env()
    ensure_persistent_state_files(settings)
    app = FastAPI(title="Supervisor Gateway", version="0.3.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Token"],
    )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        if settings.require_https and not is_https_request(request, settings):
            if _wants_html(request) and not _is_api_path(request.url.path):
                target = request.url.replace(scheme="https", path="/status/https-required", query="")
                return RedirectResponse(url=str(target), status_code=307)
            return JSONResponse(
                status_code=400,
                content={"ok": False, "detail": "https is required"},
            )
        if not settings.require_https and settings.insecure_http_local_only:
            if not is_local_request(request, settings):
                if _wants_html(request) and not _is_api_path(request.url.path):
                    return _status_redirect("403")
                return JSONResponse(
                    status_code=403,
                    content={"ok": False, "detail": "http mode is restricted to localhost"},
                )

        response = await call_next(request)

        if settings.enable_security_headers:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            response.headers.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "base-uri 'self'; "
                    "frame-ancestors 'none'; "
                    "object-src 'none'; "
                    "script-src 'self'; "
                    "connect-src 'self'; "
                    "img-src 'self' data:; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' data: https://fonts.gstatic.com"
                ),
            )
            if is_https_request(request, settings):
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )

        if request.url.path.startswith("/auth/"):
            response.headers.setdefault("Cache-Control", "no-store")

        return response

    @app.exception_handler(HTTPException)
    async def html_http_exception_handler(request: Request, exc: HTTPException):
        if _wants_html(request) and not _is_api_path(request.url.path):
            return _status_redirect(str(exc.status_code))
        return await http_exception_handler(request, exc)

    @app.get("/health", response_model=MessageResponse)
    async def health():
        service = ActionService(settings)
        try:
            ping = await service.ping()
            return MessageResponse(ok=True, data=ping)
        except Exception as error:  # noqa: BLE001
            return MessageResponse(ok=False, message=str(error))

    app.include_router(create_auth_router())
    app.include_router(create_servers_router())
    app.include_router(create_power_router())
    app.include_router(create_files_router())
    app.include_router(create_logs_router())
    app.include_router(create_activity_router())

    panel_root = Path(settings.panel_dir or "").resolve()
    index_file = panel_root / "index.html"
    if index_file.is_file():
        @app.get("/", include_in_schema=False)
        async def panel_index():
            return FileResponse(index_file)

        @app.get("/{path:path}", include_in_schema=False)
        async def panel_files(path: str):
            if path.startswith("api/") or path.startswith("auth/") or path == "health":
                return JSONResponse(status_code=404, content={"ok": False, "detail": "not found"})

            file_path = _safe_panel_path(panel_root, path)
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(index_file)

    return app


app = create_app()
