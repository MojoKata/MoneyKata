"""The ASGI application: routes, middleware and the server's run-time state."""

import logging
from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import errors, middleware, paths, static
from .config import Config

log = logging.getLogger("moneykata")


@dataclass
class Server:
    """Everything a request may reach, built once at start (main.py) and kept on app.state."""

    config: Config
    version: str = field(default_factory=paths.version)
    ready: bool = False
    upload_limit: int = 25 * 1024 * 1024


def create_app(server: Server) -> FastAPI:
    app = FastAPI(
        title="MoneyKata",
        version=server.version,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.server = server
    errors.install(app)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        status = 200 if server.ready else 503
        return JSONResponse(
            {"status": "ok" if server.ready else "starting", "version": server.version},
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )

    app.include_router(static.router(static.Static(server.version, server.config.dev)))

    # The last added runs first: the client's address, then the log, the headers, the Origin
    # check and the body limit.
    app.add_middleware(middleware.BodyLimit, upload_limit=lambda: server.upload_limit)
    app.add_middleware(middleware.OriginCheck)
    app.add_middleware(middleware.SecurityHeaders, tls=server.config.mode == "tls")
    app.add_middleware(middleware.AccessLog)
    app.add_middleware(
        middleware.ClientAddress, mode=server.config.mode, trusted=server.config.trusted_proxies
    )
    return app
