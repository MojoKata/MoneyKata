"""Starting and stopping the server: everything that happens before the first request and
after the last."""

import logging

from . import listener
from .app import Server, create_app
from .config import Config

log = logging.getLogger("moneykata")


async def start(config: Config, seed: bool = False) -> int:
    server = Server(config=config)
    app = create_app(server)

    async def on_stop() -> None:
        server.ready = False

    server.ready = True
    scheme = "https" if config.mode == "tls" else "http"
    log.info(
        "MoneyKata %s%s listening on %s://%s:%s",
        server.version,
        " (dev)" if config.dev else "",
        scheme,
        config.host,
        config.port,
    )
    await listener.run(app, config, on_stop)
    log.info("stopped")
    return 0
