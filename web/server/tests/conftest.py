import pytest
from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.config import Config


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
