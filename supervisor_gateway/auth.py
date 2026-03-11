from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .permissions import ALL_PERMISSIONS, normalize_permissions

_HASH_SCHEME = "pbkdf2_sha256"
_TOKEN_PREFIX = "ggw"
_DEFAULT_BOOTSTRAP_PASSWORD = "change-me"
_FILENAME_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_TEMPLATE_ENV_RE = re.compile(r"^AUTH_TEMPLATE_([A-Z0-9_]+)_ENABLED$")
_ROLE_ADMIN = "admin"
_DEFAULT_LANGUAGE = "en"
_DEFAULT_TIMEZONE = "Europe/London"
_LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class UserPreferences:
    language: str
    timezone: str

    def to_storage_dict(self) -> dict[str, str]:
        return {
            "language": self.language,
            "timezone": self.timezone,
        }


@dataclass(frozen=True)
class TemplateRecord:
    name: str
    username: str
    role: str
    permissions: list[str]
    allowed_servers: list[str]
    must_change_password: bool
    initial_password: str
    preferences: UserPreferences


@dataclass(frozen=True)
class UserRecord:
    username: str
    password_hash: str
    role: str
    permissions: list[str]
    allowed_servers: list[str]
    must_change_password: bool
    preferences: UserPreferences

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
            "permissions": self.permissions,
            "servers": self.allowed_servers,
            "must_change_password": self.must_change_password,
            "preferences": self.preferences.to_storage_dict(),
        }


@dataclass(frozen=True)
class AuthenticatedIdentity:
    username: str
    role: str
    permissions: list[str]
    allowed_servers: list[str]
    token_kind: str
    must_change_password: bool = False
    language: str = _DEFAULT_LANGUAGE
    timezone: str = _DEFAULT_TIMEZONE

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "role": self.role,
            "permissions": self.permissions,
            "allowed_servers": self.allowed_servers,
            "token_kind": self.token_kind,
            "must_change_password": self.must_change_password,
            "language": self.language,
            "timezone": self.timezone,
        }


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _hash_password(password: str, rounds: int = 600000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds).hex()
    return f"{_HASH_SCHEME}${rounds}${salt}${digest}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, rounds, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != _HASH_SCHEME:
        return False

    try:
        iterations = int(rounds)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return hmac.compare_digest(actual, expected)


def _parse_bool_env(name: str, value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AuthError(
        f"environment variable '{name}' must be a boolean (true/false/1/0/yes/no/on/off)"
    )


def _normalize_servers(raw_value: Any) -> list[str]:
    if raw_value is None:
        return ["*"]
    if not isinstance(raw_value, list):
        raise AuthError("user 'servers' must be a list")

    values = [str(item).strip() for item in raw_value if str(item).strip()]
    return values or ["*"]


def _validate_new_password(
    current_password: str,
    new_password: str,
    *,
    min_length: int,
) -> None:
    if len(new_password) < min_length:
        raise AuthError(f"new password must be at least {min_length} characters")
    if current_password == new_password:
        raise AuthError("new password must be different from current password")


def _username_file_name(username: str) -> str:
    safe = _FILENAME_SANITIZER.sub("_", username.strip())
    if not safe:
        raise AuthError("username cannot be mapped to a safe user file name")
    return f"{safe}.json"


def _normalize_permissions(raw: Any, *, source: str) -> list[str]:
    if not isinstance(raw, list):
        raise AuthError(f"{source} must define 'permissions' as array")
    return normalize_permissions(str(item) for item in raw)


def _normalize_language(raw_value: Any, *, source: str) -> str:
    value = str(raw_value or "").strip().replace("_", "-")
    if not value:
        raise AuthError(f"{source} must not be empty")
    parts = value.split("-", 1)
    if len(parts) == 2:
        normalized = f"{parts[0].lower()}-{parts[1].upper()}"
    else:
        normalized = parts[0].lower()
    if not _LANGUAGE_CODE_RE.fullmatch(normalized):
        raise AuthError(f"{source} must be a valid language code (e.g. en, de, en-US)")
    return normalized


def _normalize_timezone(raw_value: Any, *, source: str) -> str:
    timezone_value = str(raw_value or "").strip()
    if not timezone_value:
        raise AuthError(f"{source} must not be empty")
    try:
        ZoneInfo(timezone_value)
    except ZoneInfoNotFoundError as error:
        raise AuthError(f"{source} must be a valid IANA timezone, got '{timezone_value}'") from error
    return timezone_value


def _parse_preferences(payload: dict[str, Any], *, source: str) -> UserPreferences:
    raw_preferences = payload.get("preferences")
    if not isinstance(raw_preferences, dict):
        raise AuthError(f"{source} must define 'preferences' as object")
    if "language" not in raw_preferences:
        raise AuthError(f"{source} preferences.language is required")
    if "timezone" not in raw_preferences:
        raise AuthError(f"{source} preferences.timezone is required")
    language = _normalize_language(
        raw_preferences.get("language"),
        source=f"{source} preferences.language",
    )
    timezone = _normalize_timezone(
        raw_preferences.get("timezone"),
        source=f"{source} preferences.timezone",
    )
    return UserPreferences(language=language, timezone=timezone)


def _parse_template_payload(template_name: str, payload: Any, source: str) -> TemplateRecord:
    if not isinstance(payload, dict):
        raise AuthError(f"{source} must be an object")

    username = str(payload.get("username", "")).strip()
    role = str(payload.get("role", "")).strip().lower()
    if not username:
        raise AuthError(f"{source} requires non-empty 'username'")
    if not role:
        raise AuthError(f"{source} requires non-empty 'role'")

    permissions = _normalize_permissions(payload.get("permissions"), source=source)
    allowed_servers = _normalize_servers(payload.get("servers"))
    must_change_password = bool(payload.get("must_change_password", True))
    initial_password = str(payload.get("initial_password", _DEFAULT_BOOTSTRAP_PASSWORD)).strip()
    preferences = _parse_preferences(payload, source=source)
    if not initial_password:
        raise AuthError(f"{source} has empty 'initial_password'")

    return TemplateRecord(
        name=template_name,
        username=username,
        role=role,
        permissions=permissions,
        allowed_servers=allowed_servers,
        must_change_password=must_change_password,
        initial_password=initial_password,
        preferences=preferences,
    )


def _parse_user_payload(payload: Any, source: str) -> UserRecord:
    if not isinstance(payload, dict):
        raise AuthError(f"{source} must be an object")

    username = str(payload.get("username", "")).strip()
    password_hash = str(payload.get("password_hash", "")).strip()
    role = str(payload.get("role", "")).strip().lower()
    if not username or not password_hash:
        raise AuthError(f"{source} requires 'username' and 'password_hash'")
    if not role:
        raise AuthError(f"{source} requires non-empty 'role'")

    permissions = _normalize_permissions(payload.get("permissions"), source=source)
    allowed_servers = _normalize_servers(payload.get("servers"))
    must_change_password = bool(payload.get("must_change_password", False))
    preferences = _parse_preferences(payload, source=source)

    return UserRecord(
        username=username,
        password_hash=password_hash,
        role=role,
        permissions=permissions,
        allowed_servers=allowed_servers,
        must_change_password=must_change_password,
        preferences=preferences,
    )


def extract_token(
    authorization: str | None,
    x_api_token: str | None,
    session_cookie: str | None = None,
) -> str | None:
    if x_api_token:
        token = x_api_token.strip()
        return token or None

    if authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix):
            token = authorization[len(prefix) :].strip()
            return token or None

    if session_cookie:
        token = session_cookie.strip()
        return token or None

    return None


class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.secret = (settings.auth_secret or "").encode("utf-8")
        self._users_dir = Path(settings.auth_users_dir).resolve()
        self._templates_dir = Path(settings.auth_templates_dir).resolve()
        self._default_templates_dir = Path(__file__).with_name("auth_templates").resolve()
        self._lock = threading.Lock()
        self._user_paths: dict[str, Path] = {}
        self.users = self._load_users()

    @property
    def login_enabled(self) -> bool:
        return bool(self.users and self.secret)

    def _user_file_path(self, username: str) -> Path:
        return self._users_dir / _username_file_name(username)

    def _write_user_file(self, path: Path, user: UserRecord) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(user.to_storage_dict(), indent=2), encoding="utf-8")

    def _persist_user(self, user: UserRecord) -> None:
        path = self._user_paths.get(user.username) or self._user_file_path(user.username)
        self._write_user_file(path, user)
        self._user_paths[user.username] = path

    def _ensure_default_templates(self) -> None:
        self._templates_dir.mkdir(parents=True, exist_ok=True)
        if not self._default_templates_dir.is_dir():
            raise AuthError(f"default auth template directory is missing: {self._default_templates_dir}")
        for template_path in sorted(self._default_templates_dir.glob("*.json")):
            target = self._templates_dir / template_path.name
            if target.is_file():
                continue
            shutil.copyfile(template_path, target)

    def _template_enabled_map(self) -> dict[str, bool]:
        enabled: dict[str, bool] = {
            "admin": True,
            "guest": bool(self.settings.auth_template_guest_enabled),
            "viewer": bool(self.settings.auth_template_viewer_enabled),
        }
        for env_name, raw_value in os.environ.items():
            match = _TEMPLATE_ENV_RE.match(env_name)
            if not match:
                continue
            template_name = match.group(1).strip().lower()
            if template_name in {"admin", "guest", "viewer"}:
                continue
            enabled[template_name] = _parse_bool_env(env_name, str(raw_value))
        return enabled

    def _template_path(self, template_name: str) -> Path:
        return self._templates_dir / f"{template_name}.json"

    def _load_template(self, template_name: str) -> TemplateRecord:
        template_path = self._template_path(template_name)
        if not template_path.is_file():
            raise AuthError(
                f"enabled auth template '{template_name}' is missing: {template_path} "
                f"(set AUTH_TEMPLATE_{template_name.upper()}_ENABLED=false or add template file)"
            )
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise AuthError(f"invalid auth template JSON: {template_path}") from error
        template = _parse_template_payload(template_name, payload, f"auth template '{template_path}'")
        if template_name == "admin":
            if template.username != "admin":
                raise AuthError("admin template must use username 'admin'")
            if "admin" not in template.permissions:
                raise AuthError("admin template must include permission 'admin'")
        return template

    def _sync_template_users(self) -> None:
        enabled_map = self._template_enabled_map()
        for template_name in sorted(enabled_map.keys()):
            enabled = enabled_map[template_name]
            if not enabled and template_name == "admin":
                enabled = True
            if not enabled and not self._template_path(template_name).is_file():
                continue
            template = self._load_template(template_name)
            user_path = self._user_file_path(template.username)
            if enabled:
                if user_path.is_file():
                    continue
                user = UserRecord(
                    username=template.username,
                    password_hash=_hash_password(template.initial_password),
                    role=template.role,
                    permissions=template.permissions,
                    allowed_servers=template.allowed_servers,
                    must_change_password=template.must_change_password,
                    preferences=template.preferences,
                )
                self._write_user_file(user_path, user)
                continue
            user_path.unlink(missing_ok=True)

    def _load_users(self) -> dict[str, UserRecord]:
        self._users_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_templates()
        self._sync_template_users()

        users: dict[str, UserRecord] = {}
        user_paths: dict[str, Path] = {}
        for path in sorted(self._users_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise AuthError(f"invalid auth user file JSON: {path}") from error
            user = _parse_user_payload(payload, f"auth user file '{path}'")
            if user.username in users:
                raise AuthError(f"duplicate auth user '{user.username}' in {path}")
            users[user.username] = user
            user_paths[user.username] = path

        admin = users.get("admin")
        if not admin:
            raise AuthError("admin user missing after template sync")
        if "admin" not in admin.permissions:
            raise AuthError("admin user must include permission 'admin'")

        self._user_paths = user_paths
        return users

    def authenticate_credentials(self, username: str, password: str) -> AuthenticatedIdentity:
        if not self.login_enabled:
            raise AuthError("interactive login is not configured")

        user = self.users.get(username)
        if not user:
            raise AuthError("invalid credentials")
        if not _verify_password(password, user.password_hash):
            raise AuthError("invalid credentials")

        return AuthenticatedIdentity(
            username=user.username,
            role=user.role,
            permissions=list(user.permissions),
            allowed_servers=list(user.allowed_servers),
            token_kind="session",
            must_change_password=user.must_change_password,
            language=user.preferences.language,
            timezone=user.preferences.timezone,
        )

    def change_password(self, username: str, current_password: str, new_password: str) -> AuthenticatedIdentity:
        current_password = current_password.strip()
        _validate_new_password(
            current_password,
            new_password,
            min_length=self.settings.auth_min_password_length,
        )

        with self._lock:
            user = self.users.get(username)
            if not user:
                raise AuthError("user does not exist")
            if not _verify_password(current_password, user.password_hash):
                raise AuthError("current password is invalid")

            updated = UserRecord(
                username=user.username,
                password_hash=_hash_password(new_password),
                role=user.role,
                permissions=user.permissions,
                allowed_servers=user.allowed_servers,
                must_change_password=False,
                preferences=user.preferences,
            )
            self.users[username] = updated
            self._persist_user(updated)

            return AuthenticatedIdentity(
                username=updated.username,
                role=updated.role,
                permissions=list(updated.permissions),
                allowed_servers=list(updated.allowed_servers),
                token_kind="session",
                must_change_password=False,
                language=updated.preferences.language,
                timezone=updated.preferences.timezone,
            )

    def update_preferences(
        self,
        username: str,
        *,
        language: str | None = None,
        timezone: str | None = None,
    ) -> AuthenticatedIdentity:
        if language is None and timezone is None:
            raise AuthError("at least one preference is required")

        with self._lock:
            user = self.users.get(username)
            if not user:
                raise AuthError("user does not exist")

            resolved_language = _normalize_language(
                user.preferences.language if language is None else language,
                source="language",
            )
            resolved_timezone = _normalize_timezone(
                user.preferences.timezone if timezone is None else timezone,
                source="timezone",
            )
            updated = UserRecord(
                username=user.username,
                password_hash=user.password_hash,
                role=user.role,
                permissions=user.permissions,
                allowed_servers=user.allowed_servers,
                must_change_password=user.must_change_password,
                preferences=UserPreferences(language=resolved_language, timezone=resolved_timezone),
            )
            self.users[username] = updated
            self._persist_user(updated)

            return AuthenticatedIdentity(
                username=updated.username,
                role=updated.role,
                permissions=list(updated.permissions),
                allowed_servers=list(updated.allowed_servers),
                token_kind="session",
                must_change_password=updated.must_change_password,
                language=updated.preferences.language,
                timezone=updated.preferences.timezone,
            )

    def issue_session_token(self, identity: AuthenticatedIdentity) -> str:
        if not self.secret:
            raise AuthError("session secret is not configured")

        now = int(time.time())
        payload = {
            "v": 3,
            "sub": identity.username,
            "role": identity.role,
            "perms": identity.permissions,
            "servers": identity.allowed_servers,
            "mcp": identity.must_change_password,
            "lang": identity.language,
            "tz": identity.timezone,
            "iat": now,
            "exp": now + self.settings.auth_token_ttl_seconds,
        }

        encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64url_encode(hmac.new(self.secret, encoded_payload.encode("utf-8"), hashlib.sha256).digest())
        return f"{_TOKEN_PREFIX}.{encoded_payload}.{signature}"

    def authenticate_token(self, token: str | None) -> AuthenticatedIdentity:
        if not token:
            raise AuthError("missing authentication token")

        if self.settings.api_token and hmac.compare_digest(token, self.settings.api_token):
            return AuthenticatedIdentity(
                username="service-token",
                role=_ROLE_ADMIN,
                permissions=normalize_permissions(ALL_PERMISSIONS),
                allowed_servers=["*"],
                token_kind="api-token",
                must_change_password=False,
                language=_DEFAULT_LANGUAGE,
                timezone=_DEFAULT_TIMEZONE,
            )
        return self._decode_session_token(token)

    def _decode_session_token(self, token: str) -> AuthenticatedIdentity:
        if not self.secret:
            raise AuthError("session authentication is not available")

        parts = token.split(".")
        if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
            raise AuthError("invalid token format")

        encoded_payload = parts[1]
        expected_signature = _b64url_encode(
            hmac.new(self.secret, encoded_payload.encode("utf-8"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_signature, parts[2]):
            raise AuthError("invalid token signature")

        try:
            payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            raise AuthError("invalid token payload") from error

        if not isinstance(payload, dict):
            raise AuthError("invalid token payload")
        if int(payload.get("v", 0)) != 3:
            raise AuthError("unsupported token version")

        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            raise AuthError("token expired")

        username = str(payload.get("sub", "")).strip()
        if not username:
            raise AuthError("invalid token subject")

        user = self.users.get(username)
        if user:
            return AuthenticatedIdentity(
                username=user.username,
                role=user.role,
                permissions=list(user.permissions),
                allowed_servers=list(user.allowed_servers),
                token_kind="session",
                must_change_password=user.must_change_password,
                language=user.preferences.language,
                timezone=user.preferences.timezone,
            )

        role = str(payload.get("role", "")).strip().lower()
        permissions = normalize_permissions(str(item) for item in (payload.get("perms") or []))
        if not role or not permissions:
            raise AuthError("invalid token permissions")
        allowed_servers = _normalize_servers(payload.get("servers"))
        must_change_password = bool(payload.get("mcp", False))
        if "lang" not in payload or "tz" not in payload:
            raise AuthError("invalid token locale")
        language = _normalize_language(payload.get("lang"), source="token language")
        timezone = _normalize_timezone(payload.get("tz"), source="token timezone")

        return AuthenticatedIdentity(
            username=username,
            role=role,
            permissions=permissions,
            allowed_servers=allowed_servers,
            token_kind="session",
            must_change_password=must_change_password,
            language=language,
            timezone=timezone,
        )
