"""Dev mode's seed data (requirements §20.7). It grows with each part of the app."""

import logging

log = logging.getLogger("moneykata.dev")


def seed(server) -> None:
    log.info("dev: nothing to seed yet")
