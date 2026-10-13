"""SMTP and emails (requirements S10.1.9, S16.2) and sign-up (S10.1.4)."""

import re
import smtplib
from typing import ClassVar

import pytest
from conftest import make_user, new_client
from test_users import kinds, mails, set_public_url

from moneykata import settings
from moneykata.mail import smtp_settings

PW = "a long user passphrase"


class FakeSmtp:
    """Stands in for smtplib.SMTP: records what was sent, or fails as told."""

    sent: ClassVar[list] = []
    logins: ClassVar[list] = []
    fail: ClassVar[Exception | None] = None
    starttls_done: ClassVar[bool] = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        FakeSmtp.starttls_done = True

    def login(self, user, password):
        FakeSmtp.logins.append((user, password))
        if password == "wrong":
            raise smtplib.SMTPAuthenticationError(535, b"no")

    def send_message(self, msg, from_addr=None):
        if FakeSmtp.fail:
            raise FakeSmtp.fail
        FakeSmtp.sent.append((from_addr, msg))


@pytest.fixture
def smtp(monkeypatch, server):
    FakeSmtp.sent, FakeSmtp.logins, FakeSmtp.fail, FakeSmtp.starttls_done = [], [], None, False
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)
    server.guard.allow(["smtp.home.lan"], allowed_by_name=["smtp.home.lan"])
    return FakeSmtp


def set_up_smtp(admin_client, password="app password"):
    r = admin_client.patch(
        "/ui/api/settings",
        json={
            "smtpHost": "smtp.home.lan",
            "smtpUsername": "money@home.lan",
            "smtpFrom": "MoneyKata <money@home.lan>",
        },
    )
    assert r.status_code == 200, r.text
    r = admin_client.put("/ui/api/settings/email/password", json={"password": password})
    assert r.status_code == 200 and r.json()["password"]["setBy"] == "Ada Admin"


def test_settings_check_the_smtp_fields(admin_client):
    for key, bad in (
        ("smtpHost", "not a host!"),
        ("smtpPort", 0),
        ("smtpSecurity", "ssl3"),
        ("smtpFrom", "nobody"),
    ):
        r = admin_client.patch("/ui/api/settings", json={key: bad})
        assert r.status_code == 422 and r.json()["errors"][0]["field"] == key, key


def test_the_password_is_a_secret_never_read_back(admin_client, server):
    set_up_smtp(admin_client)
    body = admin_client.get("/ui/api/settings/email").text
    assert (
        "app password" not in body
        and "app password" not in admin_client.get("/ui/api/settings").text
    )
    with server.db.read() as s:
        assert smtp_settings(s, server.keys.secrets).password == "app password"


def test_with_smtp_emails_go_through_the_outbox(admin_client, server, smtp):
    set_up_smtp(admin_client)
    set_public_url(server)
    before = len(mails(server))
    r = admin_client.post(
        "/ui/api/users", json={"displayName": "Dave", "username": "dave", "email": "dave@x.lan"}
    )
    assert r.status_code == 201
    assert len(mails(server)) == before, "not written to the mail folder"
    assert len(server.services.mailer.waiting()) == 1
    assert server.services.mailer.send_waiting(_smtp(server), server.guard) == 1
    assert server.services.mailer.waiting() == []
    from_addr, msg = smtp.sent[0]
    assert from_addr == "money@home.lan" and msg["From"] == "MoneyKata <money@home.lan>"
    assert msg["To"] == "dave@x.lan" and smtp.starttls_done
    assert smtp.logins == [("money@home.lan", "app password")]


def _smtp(server):
    with server.db.read() as s:
        return smtp_settings(s, server.keys.secrets)


def test_a_failure_keeps_the_email_and_says_why(admin_client, server, smtp):
    set_up_smtp(admin_client, password="wrong")
    set_public_url(server)
    admin_client.post(
        "/ui/api/users", json={"displayName": "Dave", "username": "dave", "email": "dave@x.lan"}
    )
    with pytest.raises(RuntimeError, match="refused the username or password"):
        server.services.mailer.send_waiting(_smtp(server), server.guard)
    assert len(server.services.mailer.waiting()) == 1
    # A recipient the server will never take is set aside, and the rest go on.
    smtp.fail = smtplib.SMTPRecipientsRefused({"dave@x.lan": (550, b"no such user")})
    admin_client.put("/ui/api/settings/email/password", json={"password": "right"})
    assert server.services.mailer.send_waiting(_smtp(server), server.guard) == 0
    assert admin_client.get("/ui/api/settings/email").json()["setAside"] == 1


def test_the_egress_guard_refuses_a_host_not_in_settings(admin_client, server, smtp):
    set_up_smtp(admin_client)
    server.guard.allow([])
    r = admin_client.post("/ui/api/settings/email/test")
    assert r.status_code == 502 and "not a host MoneyKata is set up to reach" in r.json()["detail"]


def test_send_a_test_email(admin_client, server, smtp):
    r = admin_client.post("/ui/api/settings/email/test")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "smtpHost"
    set_up_smtp(admin_client)
    r = admin_client.post("/ui/api/settings/email/test")
    assert r.status_code == 200 and r.json()["to"] == "admin@home.lan"
    assert smtp.sent[0][1]["Subject"] == "MoneyKata test email"
    smtp.fail = OSError("Connection refused")
    r = admin_client.post("/ui/api/settings/email/test")
    assert r.status_code == 502 and "could not reach the SMTP server" in r.json()["detail"]


# ---------- sign-up (S10.1.4) ----------


def open_signup(admin_client, server, domains=()):
    set_up_smtp(admin_client)
    set_public_url(server)
    r = admin_client.patch(
        "/ui/api/settings", json={"signupEnabled": True, "signupDomains": list(domains)}
    )
    assert r.status_code == 200, r.text


def sign_up(server, email="erin@shaw.family", username="erin"):
    with new_client(server) as c:
        return c.post(
            "/ui/api/signup",
            json={"displayName": "Erin Shaw", "username": username, "email": email, "password": PW},
        )


def outbox_link(server) -> tuple[str, str]:
    import email

    path = server.services.mailer.waiting()[-1]
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    url = re.search(r"https://\S+", msg.get_body().get_content()).group(0)
    p, _, token = url.partition("#")
    return p, token


def test_sign_up_needs_smtp_and_the_public_url(admin_client, server):
    r = admin_client.patch("/ui/api/settings", json={"signupEnabled": True})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "signupEnabled"
    with new_client(server) as c:
        assert c.get("/ui/api/signup").json() == {"open": False, "domains": []}
    assert sign_up(server).status_code == 403


def test_sign_up_confirm_and_approve(admin_client, server, smtp):
    open_signup(admin_client, server)
    with new_client(server) as c:
        assert c.get("/ui/api/signup").json()["open"] is True
    assert sign_up(server).status_code == 202
    path, token = outbox_link(server)
    assert path.endswith("/ui/signup/confirm")
    assert admin_client.get("/ui/api/signup-requests").json() == [], "not until confirmed"
    with new_client(server) as c:
        r = c.post("/ui/api/signup/confirm", json={"token": token})
        assert r.status_code == 200 and r.json()["displayName"] == "Erin Shaw"
        assert c.post("/ui/api/signup/confirm", json={"token": token}).status_code == 404
        # Not a user yet.
        r = c.post("/ui/api/session", json={"login": "erin", "password": PW})
        assert r.status_code == 401
    rows = admin_client.get("/ui/api/signup-requests").json()
    assert [r["username"] for r in rows] == ["erin"]
    groups = admin_client.get("/ui/api/groups").json()
    r = admin_client.post(
        f"/ui/api/signup-requests/{rows[0]['id']}/approve", json={"groupIds": [groups[0]["id"]]}
    )
    assert r.status_code == 200 and r.json()["groupIds"] == [groups[0]["id"]]
    assert admin_client.get("/ui/api/signup-requests").json() == []
    with new_client(server) as c:
        r = c.post("/ui/api/session", json={"login": "erin@shaw.family", "password": PW})
        assert r.status_code == 200
    assert {"signup.requested", "signup.approved"} <= set(kinds(server))
    import email

    last = server.services.mailer.waiting()[-1]
    assert (
        "Your MoneyKata account is ready"
        in email.message_from_bytes(last.read_bytes(), policy=email.policy.default)["Subject"]
    )


def test_sign_up_rejected(admin_client, server, smtp):
    open_signup(admin_client, server)
    sign_up(server)
    _, token = outbox_link(server)
    with new_client(server) as c:
        c.post("/ui/api/signup/confirm", json={"token": token})
    rid = admin_client.get("/ui/api/signup-requests").json()[0]["id"]
    assert admin_client.post(f"/ui/api/signup-requests/{rid}/reject").status_code == 204
    assert admin_client.post(f"/ui/api/signup-requests/{rid}/approve", json={}).status_code == 404
    assert "signup.rejected" in kinds(server)


def test_sign_up_never_says_an_email_has_an_account(admin_client, server, smtp):
    open_signup(admin_client, server)
    make_user(server, "bob", email="bob@home.lan")
    waiting = len(server.services.mailer.waiting())
    r = sign_up(server, email="Bob@home.lan", username="bobby")
    assert r.status_code == 202
    assert len(server.services.mailer.waiting()) == waiting, "no link for a known address"


def test_sign_up_checks_its_fields_and_domains(admin_client, server, smtp):
    open_signup(admin_client, server, domains=["shaw.family"])
    make_user(server, "bob")
    r = sign_up(server, email="erin@elsewhere.lan")
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "email-domain"
    r = sign_up(server, username="bob")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "username"
    with new_client(server) as c:
        r = c.post(
            "/ui/api/signup",
            json={
                "displayName": "Erin",
                "username": "erin",
                "email": "erin@shaw.family",
                "password": "short",
            },
        )
        assert r.status_code == 422 and r.json()["errors"][0]["field"] == "password"


def test_signup_settings_are_off_by_default(server):
    with server.db.read() as s:
        assert settings.get(s, "signupEnabled") is False
