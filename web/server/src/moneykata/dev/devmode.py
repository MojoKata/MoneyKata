"""Dev mode (requirements S17.7): the whole server from a checkout, as the current user. It
relaxes the surroundings, never the rules: sessions, CSP, encryption and sharing behave as in
production."""

import hashlib
import logging

from .. import clock
from ..config import Config
from ..keys import cli as keys_cli
from ..keys import phrase

log = logging.getLogger("moneykata.dev")


def prepare(config: Config) -> None:
    """A dev server makes its own master key on first run, without the recovery-phrase step:
    its data is throwaway."""
    for d in (config.data_dir, config.backup_dir, config.mail_dir, config.key_file.parent):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not config.key_file.exists():
        if clock.frozen():
            # The generated mockup's build: a key made from fixed words, so its fingerprint
            # comes out the same every time.
            words = " ".join(phrase.to_words(hashlib.sha256(b"mockup").digest()[:16]))
            keys_cli.init(config, ask=lambda _: words, say=lambda _: None, from_phrase=True)
        else:
            keys_cli.init(config, say=lambda _: None, confirm=False)
        log.info("dev: made a master key in %s", config.key_file)


def after_start(server, seed: bool) -> None:
    if seed:
        from .seed import seed as run_seed

        run_seed(server)


def enable_stub_prices(server) -> None:
    """--stubs: the stub price source, first for every class it serves (S17.7)."""
    import json

    from sqlalchemy import false, select

    from .. import ids
    from ..prices import SOURCES
    from ..store.entities.prices import PriceSource

    cls = SOURCES["stub"]
    with server.db.tx() as s:
        row = s.scalars(
            select(PriceSource).where(PriceSource.name == "stub", PriceSource.deleted == false())
        ).first()
        if row is None:
            s.add(
                PriceSource(
                    id=ids.new_id("Src"),
                    name="stub",
                    enabled=True,
                    preference=json.dumps({c: 0 for c in sorted(cls.classes)}),
                )
            )
        else:
            row.enabled = True
