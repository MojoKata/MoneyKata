import pytest
from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.auth import passwords
from moneykata.auth import users as accounts
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


passwords.use_fast_hashing_for_tests()
ORIGIN = "https://mk.test"


@pytest.fixture
def server(store, keyed_config):
    from moneykata.store.repos.ledger import ensure_categories

    srv = Server(config=keyed_config, store=store, ready=True)
    with srv.db.tx() as s:
        accounts.ensure_default_admin(s)
        ensure_categories(s)
    return srv


def new_client(srv) -> TestClient:
    return TestClient(create_app(srv), base_url=ORIGIN, headers={"Origin": ORIGIN})


@pytest.fixture
def client(server):
    with new_client(server) as c:
        yield c


@pytest.fixture
def admin_client(server):
    """Signed in as an admin who has finished the setup step."""
    with new_client(server) as c:
        r = c.post("/ui/api/session", json={"login": "admin", "password": "moneykata-setup"})
        assert r.status_code == 200, r.text
        r = c.post(
            "/ui/api/session/setup",
            json={
                "password": "a long admin passphrase",
                "email": "admin@home.lan",
                "displayName": "Ada Admin",
            },
        )
        assert r.status_code == 200, r.text
        yield c


def make_user(
    srv,
    username: str,
    password: str = "a long user passphrase",
    admin: bool = False,
    email: str | None = None,
):
    """A user who has joined, made straight in the database."""
    from moneykata import ids
    from moneykata.store.entities.users import User, UserGroup

    with srv.db.tx() as s:
        u = User(
            id=ids.new_id("User"),
            username=username,
            displayName=username.title(),
            email=email or f"{username}@home.lan",
            passwordHash=passwords.hash_password(password),
        )
        s.add(u)
        s.flush()
        if admin:
            s.add(
                UserGroup(
                    userId=u.id, groupId=accounts.admins_group(s).id, createdAt=accounts.now()
                )
            )
        return u


def sign_in(srv, username: str, password: str = "a long user passphrase") -> TestClient:
    c = new_client(srv)
    c.__enter__()
    r = c.post("/ui/api/session", json={"login": username, "password": password})
    assert r.status_code == 200, r.text
    return c
