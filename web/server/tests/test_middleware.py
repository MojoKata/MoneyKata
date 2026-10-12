from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.config import Config


def test_every_response_carries_the_security_headers(bare_client):
    for path in ("/ui/", "/ui/api/none", "/healthz", "/demo"):
        h = bare_client.get(path).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["referrer-policy"] == "no-referrer"
        assert h["cross-origin-opener-policy"] == "same-origin"
        assert h["cross-origin-resource-policy"] == "same-origin"
        assert "camera=()" in h["permissions-policy"]
        assert "frame-ancestors 'none'" in h["content-security-policy"]
        assert "strict-transport-security" not in h


def test_tls_mode_adds_hsts(config):
    server = Server(config=Config(**{**config.__dict__, "mode": "tls"}), ready=True)
    with TestClient(create_app(server)) as c:
        assert c.get("/healthz").headers["strict-transport-security"] == "max-age=31536000"


def test_changes_need_the_apps_own_origin(bare_client):
    for headers in ({}, {"Origin": "https://evil.example"}, {"Origin": "http://mk.test.evil"}):
        r = bare_client.post("/ui/api/anything", json={}, headers=headers)
        assert r.status_code == 403, headers
        assert r.json()["code"] == "origin-refused"
    r = bare_client.post("/ui/api/anything", json={}, headers={"Origin": "http://mk.test"})
    assert r.status_code == 404


def test_json_bodies_are_limited_to_1_mb(bare_client):
    big = b"[" + b"0," * 600_000 + b"0]"
    r = bare_client.post(
        "/ui/api/anything",
        content=big,
        headers={"Origin": "http://mk.test", "Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_healthz_says_starting_until_ready(config):
    server = Server(config=config)
    with TestClient(create_app(server)) as c:
        assert c.get("/healthz").status_code == 503
        server.ready = True
        assert c.get("/healthz").json()["status"] == "ok"


def test_forwarded_headers_only_from_trusted_proxies(config):
    import ipaddress

    from moneykata.middleware import ClientAddress

    seen = {}

    async def app(scope, receive, send):
        seen.update(client=scope["client"][0], scheme=scope["scheme"])

    import asyncio

    def call(peer, headers, trusted):
        mw = ClientAddress(app, "proxy", tuple(ipaddress.ip_network(t) for t in trusted))
        scope = {
            "type": "http",
            "client": (peer, 1),
            "scheme": "http",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        }
        asyncio.run(mw(scope, None, None))
        return dict(seen)

    fwd = {"x-forwarded-for": "203.0.113.9, 10.0.0.2", "x-forwarded-proto": "https"}
    assert call("10.0.0.1", fwd, ["10.0.0.0/8"]) == {"client": "203.0.113.9", "scheme": "https"}
    assert call("192.0.2.1", fwd, ["10.0.0.0/8"]) == {"client": "192.0.2.1", "scheme": "http"}
