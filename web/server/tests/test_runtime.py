"""The server as main.py builds it: its background tasks and start-up work."""

from moneykata.runtime import build


def test_build_registers_every_background_task(keyed_config):
    server = build(keyed_config)
    try:
        assert set(server.tasks.status()) == {
            "backups",
            "pruning",
            "prices",
            "reencrypt",
            "mail",
            "alerts",
            "alert-summaries",
            "options",
            "bitcoin",
        }
        assert server.tasks.run_now("prices")
    finally:
        server.db.dispose()
