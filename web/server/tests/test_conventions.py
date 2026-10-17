"""The API conventions every route keeps (requirements S13.8), checked on the routes themselves
so a new route can't drift from them."""

from fastapi.routing import APIRoute

from moneykata.app import Server, create_app
from moneykata.ui.conventions import Deleted, if_match

# Changes to what has no version of its own (S13.8.6): pairs that only link two records, and
# secrets, which are replaced outright. Signing out ends a session, not a record.
NO_VERSION = {
    ("PUT", "/ui/api/linked/{link_id}/colour"): "a pair: the user's colour for a household",
    ("PUT", "/ui/api/tax-books/{book_id}/accounts/{account_id}"): "a pair: a book counts it",
    ("PUT", "/ui/api/accounts/{account_id}/counted"): "a pair: counted in the user's totals",
    ("PUT", "/ui/api/projections/{projection_id}/shown"): "a pair: shown on the user's Dashboard",
    ("PUT", "/ui/api/settings/email/password"): "a secret, replaced outright",
    ("PUT", "/ui/api/settings/bitcoin/password"): "a secret, replaced outright",
    ("DELETE", "/ui/api/receipts/{receipt_id}/links/{transaction_id}"): "a pair",
    ("DELETE", "/ui/api/items/{item_id}/documents/{receipt_id}"): "a pair",
    ("DELETE", "/ui/api/session"): "signing out",
}


def _routes(store, keyed_config):
    app = create_app(Server(config=keyed_config, store=store, ready=True))
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/ui/api"):
            for m in r.methods & {"PATCH", "PUT", "DELETE"}:
                yield m, r


def _calls(dep) -> set:
    out = {dep.call}
    for d in dep.dependencies:
        out |= _calls(d)
    return out


def test_every_change_sends_the_version_it_was_made_against(store, keyed_config):
    """Every PATCH, PUT and DELETE requires If-Match (S13.8.6), but for the few with no
    version, each listed with why."""
    missing, needless = [], []
    for method, r in _routes(store, keyed_config):
        has = if_match in _calls(r.dependant)
        exempt = (method, r.path) in NO_VERSION
        if not has and not exempt:
            missing.append(f"{method} {r.path}")
        if has and exempt:
            needless.append(f"{method} {r.path}")
    assert missing == [] and needless == []


def test_every_delete_answers_what_went_and_its_parent(store, keyed_config):
    """Every DELETE answers {deleted, parent} (S13.8.1), signing out aside."""
    wrong = []
    for method, r in _routes(store, keyed_config):
        if method != "DELETE" or r.path == "/ui/api/session":
            continue
        model = r.response_model
        if not (isinstance(model, type) and issubclass(model, Deleted)):
            wrong.append(r.path)
    assert wrong == []


def test_every_list_is_paged(store, keyed_config):
    """Every GET that answers a list takes offset and limit and answers a Page (S13.8.5)."""
    app = create_app(Server(config=keyed_config, store=store, ready=True))
    doc = app.openapi() if app.openapi_url else None
    from moneykata import contract

    doc = doc or contract.openapi_document()
    bare = [
        p
        for p, ops in doc["paths"].items()
        for m, op in ops.items()
        if m == "get"
        and op.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("type")
        == "array"
    ]
    assert bare == []


def test_the_document_lists_the_problems_and_their_codes():
    # N16: the problem document and its stable codes are in the OpenAPI document (S13.8.3).
    from moneykata import contract

    doc = contract.openapi_document()
    codes = doc["components"]["schemas"]["Problem"]["properties"]["code"]["enum"]
    for code in ("closed-year", "version-required", "rule-sets-nothing", "uploads-in-flight"):
        assert code in codes, code
    for path, ops in doc["paths"].items():
        for method, op in ops.items():
            assert op["responses"]["default"] == {"$ref": "#/components/responses/Problem"}, (
                method,
                path,
            )
