import re

from moneykata import paths


def test_root_redirects_to_ui(bare_client):
    r = bare_client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/ui/"


def test_page_is_templated_with_version_and_a_fresh_nonce(bare_client):
    a = bare_client.get("/ui/")
    b = bare_client.get("/ui/accounts/Acct_x")
    assert a.status_code == b.status_code == 200
    assert a.headers["cache-control"] == "no-store"
    version = paths.version()
    assert f"/ui/v/{version}/app/main.js" in a.text
    nonce_a = re.search(r'nonce="([^"]+)"', a.text).group(1)
    nonce_b = re.search(r'nonce="([^"]+)"', b.text).group(1)
    assert nonce_a != nonce_b
    csp = a.headers["content-security-policy"]
    assert f"script-src 'self' 'nonce-{nonce_a}'" in csp
    assert "style-src 'self';" in csp
    assert "unsafe" not in csp
    assert "frame-ancestors 'none'" in csp


def test_versioned_files_are_cached_for_a_year(bare_client):
    version = paths.version()
    r = bare_client.get(f"/ui/v/{version}/app/main.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    assert "immutable" in r.headers["cache-control"]


def test_an_old_version_is_not_found(bare_client):
    r = bare_client.get("/ui/v/0.0.0-old/app/main.js")
    assert r.status_code == 404
    assert r.json()["code"] == "old-version"


def test_only_the_served_directories_are_reachable(bare_client):
    version = paths.version()
    for rel in (
        "index.html",
        "deno.json",
        "vendor/vendor.py",
        "vendor/manifest.json",
        "tests/run.js",
        "mockup/build.py",
        "app/../deno.json",
        "app/%2e%2e/deno.json",
    ):
        r = bare_client.get(f"/ui/v/{version}/{rel}")
        assert r.status_code == 404, rel


def test_unknown_api_paths_are_problems_not_the_page(bare_client):
    r = bare_client.get("/ui/api/nothing-here")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["status"] == 404
    assert body["errorId"].startswith("err_")
    assert body["errors"] == []


def test_demo_is_public_and_sandboxed(bare_client):
    r = bare_client.get("/demo")
    assert r.status_code == 200
    assert "MOCK" in r.text
    csp = r.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts allow-popups;")
    assert "allow-same-origin" not in csp
    assert "connect-src 'none'" in csp
