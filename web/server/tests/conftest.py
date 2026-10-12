import pytest
from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.config import Config
from moneykata.keys import cli as keys_cli
from moneykata.store.maintenance import open_store


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        name="test",
        mode="proxy",
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        key_file=tmp_path / "keys" / "master.key",
    )


@pytest.fixture
def bare_client(config):
    """The app with no database: static files, headers and middleware only."""
    server = Server(config=config, ready=True)
    with TestClient(create_app(server), base_url="http://mk.test") as c:
        yield c


@pytest.fixture
def keyed_config(config) -> Config:
    """A config whose master key and keyring exist (made without the phrase step)."""
    keys_cli.init(config, say=lambda _: None, confirm=False)
    return config


@pytest.fixture
def store(keyed_config):
    st = open_store(keyed_config)
    yield st
    st.db.dispose()


@pytest.fixture
def db(store):
    return store.db
