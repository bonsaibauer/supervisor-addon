from __future__ import annotations

import uvicorn

from .config import Settings
from .tls import ensure_runtime_tls


def main() -> None:
    settings = Settings.from_env()
    ensure_runtime_tls(settings)
    uvicorn.run(
        "supervisor_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
        ssl_certfile=settings.tls_certfile,
        ssl_keyfile=settings.tls_keyfile,
    )


if __name__ == "__main__":
    main()
