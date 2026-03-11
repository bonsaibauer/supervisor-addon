from __future__ import annotations

from collections import defaultdict, deque
from functools import lru_cache
import ipaddress
import threading
import time

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from .auth import AuthService, AuthenticatedIdentity, AuthError, extract_token
from .config import Settings
from .permissions import has_permission, is_server_allowed


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_prune = 0.0
        self._max_keys = 20000

    def _prune(self, threshold: float, now: float) -> None:
        if now - self._last_prune < 30.0:
            return
        self._last_prune = now

        stale_keys: list[str] = []
        for key, queue in self._entries.items():
            while queue and queue[0] < threshold:
                queue.popleft()
            if not queue:
                stale_keys.append(key)
        for key in stale_keys:
            self._entries.pop(key, None)

        if len(self._entries) <= self._max_keys:
            return

        # Drop oldest-active keys first to cap memory under key-flood conditions.
        ranked = sorted(
            ((queue[-1], key) for key, queue in self._entries.items() if queue),
            key=lambda item: item[0],
        )
        overflow = len(self._entries) - self._max_keys
        for _, key in ranked[:overflow]:
            self._entries.pop(key, None)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        threshold = now - window_seconds

        with self._lock:
            self._prune(threshold, now)
            queue = self._entries[key]
            while queue and queue[0] < threshold:
                queue.popleft()

            if len(queue) >= limit:
                return False

            queue.append(now)
            return True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    try:
        return AuthService(get_settings())
    except (AuthError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"auth configuration error: {error}",
        ) from error


@lru_cache(maxsize=1)
def _get_limiter() -> _SlidingWindowLimiter:
    return _SlidingWindowLimiter()


def get_client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def is_https_request(request: Request, settings: Settings) -> bool:
    if request.url.scheme == "https":
        return True

    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-proto", "")
        if forwarded:
            first = forwarded.split(",")[0].strip().lower()
            if first == "https":
                return True

    return False


def is_local_request(request: Request, settings: Settings) -> bool:
    client_ip = get_client_ip(request, settings).strip().lower()
    if client_ip in {"127.0.0.1", "::1", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(client_ip).is_loopback
    except ValueError:
        return False


def require_identity(
    auth_service: AuthService = Depends(get_auth_service),
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    session_cookie: str | None = Cookie(default=None, alias="sgw_session"),
) -> AuthenticatedIdentity:
    token = extract_token(
        authorization,
        x_api_token,
        session_cookie,
    )

    try:
        return auth_service.authenticate_token(token)
    except AuthError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def require_permission(permission: str, *, server_scoped: bool = False):
    def _dependency(
        identity: AuthenticatedIdentity = Depends(require_identity),
        server_id: str | None = None,
    ) -> AuthenticatedIdentity:
        if identity.token_kind == "session" and identity.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="password change required before using this endpoint",
            )

        if not has_permission(identity.permissions, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"user '{identity.username}' is missing permission '{permission}'",
            )

        if server_scoped:
            if not server_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="server_id is required for this operation",
                )
            if not is_server_allowed(identity.allowed_servers, server_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"server '{server_id}' is not in allowed scope",
                )

        return identity

    return _dependency


def require_api_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    key = f"api:{get_client_ip(request, settings)}"
    if not _get_limiter().allow(key, settings.api_rate_limit_per_minute, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="API rate limit exceeded",
        )


def require_login_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    key = f"login:{get_client_ip(request, settings)}"
    if not _get_limiter().allow(key, settings.login_rate_limit_per_minute, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many login attempts",
        )
