"""The server as main.py builds it at unlock: its background tasks and start-up work."""

from moolakata.app import Server
from moolakata.runtime import build


def test_build_registers_every_background_task(keyed_config, master_key):
    server = Server(config=keyed_config)
    build(server, master_key)
    try:
        assert set(server.tasks.status()) == {
            "backups",
            "pruning",
            "prices",
            "mail",
            "alerts",
            "alert-summaries",
            "options",
            "bitcoin",
            "links",
            "linked-copies",
            "host-events",
        }
        assert server.tasks.run_now("prices")
    finally:
        server.db.dispose()
