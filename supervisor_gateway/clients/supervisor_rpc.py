from __future__ import annotations

import base64
import http.client
import socket
from typing import Any
from urllib.parse import urlparse
import xmlrpc.client

from ..config import Settings


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 10.0):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


class SupervisorRPCTransport(xmlrpc.client.Transport):
    def __init__(
        self,
        rpc_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ):
        super().__init__()
        self._timeout = timeout
        self._parsed = urlparse(rpc_url)
        self._auth_header = self._build_auth_header(username, password)

        if self._parsed.scheme not in {"unix", "http"}:
            raise ValueError(f"unsupported rpc url scheme '{self._parsed.scheme}'")

    @staticmethod
    def _build_auth_header(username: str | None, password: str | None) -> str | None:
        if username is None or password is None:
            return None
        raw = f"{username}:{password}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"Basic {encoded}"

    def make_connection(self, host):  # noqa: D401 - xmlrpc hook signature
        if self._parsed.scheme == "unix":
            socket_path = self._parsed.path
            return UnixSocketHTTPConnection(socket_path, timeout=self._timeout)

        port = self._parsed.port or 80
        hostname = self._parsed.hostname or "127.0.0.1"
        return http.client.HTTPConnection(hostname, port, timeout=self._timeout)

    def send_headers(self, connection, headers):
        super().send_headers(connection, headers)
        if self._auth_header:
            connection.putheader("Authorization", self._auth_header)


class SupervisorGatewayRPCClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._parsed = urlparse(settings.rpc_url)
        self._transport = SupervisorRPCTransport(
            settings.rpc_url,
            username=settings.rpc_username,
            password=settings.rpc_password,
        )
        self._proxy_url = self._build_proxy_url()

    def _build_proxy_url(self) -> str:
        if self._parsed.scheme == "unix":
            return "http://127.0.0.1/RPC2"

        path = self._parsed.path or "/RPC2"
        netloc = self._parsed.netloc
        return f"http://{netloc}{path}"

    def _proxy(self) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(
            self._proxy_url,
            transport=self._transport,
            allow_none=True,
        )

    def call(self, namespace: str, method: str, *params: Any) -> Any:
        proxy = self._proxy()
        ns = getattr(proxy, namespace)
        fn = getattr(ns, method)
        return fn(*params)

    def call_addon(self, method: str, *params: Any) -> Any:
        return self.call(self.settings.rpc_namespace, method, *params)


__all__ = ["SupervisorGatewayRPCClient", "SupervisorRPCTransport", "UnixSocketHTTPConnection"]

