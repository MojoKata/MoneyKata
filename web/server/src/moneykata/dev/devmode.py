"""Dev mode (requirements §20.7): the whole server from a checkout, as the current user. It
relaxes the surroundings, never the rules: sessions, CSP, encryption and sharing behave as in
production."""

import logging

from ..config import Config
from ..keys import cli as keys_cli

log = logging.getLogger("moneykata.dev")


def prepare(config: Config) -> None:
    """A dev server makes its own master key on first run, without the recovery-phrase step:
    its data is throwaway."""
    for d in (config.data_dir, config.backup_dir, config.mail_dir, config.key_file.parent):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not config.key_file.exists():
        keys_cli.init(config, say=lambda _: None, confirm=False)
        log.info("dev: made a master key in %s", config.key_file)


def after_start(server, seed: bool) -> None:
    if seed:
        from .seed import seed as run_seed

        run_seed(server)
