"""The /link listener (requirements S11.1.3, S11.2): what a linked server calls. Everything but
`hello` is signed by a key this server has a link with, and every answer is signed back."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import false, select

from .. import clock
from ..store.entities.links import Link
from . import PROTOCOL, SUPPORTED, keys, signing

router = APIRouter(prefix="/link/v1", include_in_schema=False)


def own(srv) -> tuple[object, str]:
    """This server's link key and its fingerprint."""
    with srv.db.tx() as s:
        k = keys.private_key(s, srv.keys.secrets)
    return k, keys.fingerprint(keys.raw_public(k.public_key()))


def answer(srv, data: dict, nonce: str, status: int = 200) -> Response:
    body = json.dumps(data, separators=(",", ":"), default=str).encode()
    k, _ = own(srv)
    headers = signing.sign_answer(k, status, body, nonce)
    return Response(body, status_code=status, media_type="application/json", headers=headers)


async def verified(request: Request, states=("active",)) -> tuple[Link, signing.Caller, bytes]:
    """The link a signed call comes from, in one of these states; or a signed refusal."""
    srv = request.app.state.server
    asked = request.headers.get("mk-link-protocol", str(PROTOCOL))
    if not asked.isdigit() or int(asked) not in SUPPORTED:
        raise signing.Refused(
            "protocol-unsupported",
            f"This server speaks link protocol {', '.join(map(str, SUPPORTED))}; "
            f"yours sent {asked}. The older server needs updating.",
        )
    body = await request.body()
    _, fp = own(srv)
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    caller = signing.verify_request(
        request.headers, request.method, path, body, fp, srv.link_nonces
    )
    with srv.db.read() as s:
        link = s.scalars(
            select(Link).where(Link.peerKey == keys.b64(caller.public), Link.deleted == false())
        ).first()
    if link is None:
        raise signing.Refused("not-linked", "This server has no link with yours.")
    if link.state not in states:
        raise signing.Refused(f"link-{link.state}", f"The link is {link.state} on this side.")
    return link, caller, body


def refusal(request: Request, e: signing.Refused) -> Response:
    """Signed when the call carried a nonce, so the caller can tell a refusal from a forgery."""
    status = 426 if e.code == "protocol-unsupported" else 403
    nonce = request.headers.get("mk-link-nonce")
    if not nonce:
        return JSONResponse({"code": e.code, "message": e.message}, status_code=status)
    return answer(request.app.state.server, {"code": e.code, "message": e.message}, nonce, status)


@router.get("/hello")
def hello(request: Request):
    """Unsigned: the protocol this server speaks and its key's fingerprint, so a joining server
    can check it against the link code before sending anything."""
    srv = request.app.state.server
    k, fp = own(srv)
    return {
        "protocol": PROTOCOL,
        "version": srv.version,
        "fingerprint": fp,
        "key": keys.b64(keys.raw_public(k.public_key())),
    }


@router.post("/ping")
async def ping(request: Request):
    srv = request.app.state.server
    try:
        link, caller, _ = await verified(request, ("active", "paused", "pending", "requested"))
    except signing.Refused as e:
        return refusal(request, e)
    with srv.db.tx() as s:
        row = s.get(Link, link.id)
        row.lastOkAt = clock.now()
        row.peerVersion = request.headers.get("mk-link-version")
    return answer(
        srv, {"protocol": PROTOCOL, "version": srv.version, "state": link.state}, caller.nonce
    )


@router.post("/join")
async def join(request: Request):
    """A server answering an invitation: signed by its own key, which the code vouches for."""
    srv = request.app.state.server
    body = await request.body()
    try:
        _, fp = own(srv)
        path = request.url.path
        caller = signing.verify_request(
            request.headers, request.method, path, body, fp, srv.link_nonces
        )
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_join

    out = answer_join(srv, caller.public, json.loads(body or b"{}"))
    if "error" in out:
        code, message = out["error"]
        return refusal(request, signing.Refused(code, message))
    return answer(srv, {**out, "state": "requested", "version": srv.version}, caller.nonce)


@router.post("/exchange")
async def exchange(request: Request):
    """Each side's directory for the other's: users and household (S11.3)."""
    srv = request.app.state.server
    try:
        link, caller, body = await verified(request, ("active", "pending"))
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_exchange

    out = answer_exchange(
        srv, link, json.loads(body or b"{}"), request.headers.get("mk-link-version")
    )
    return answer(srv, out, caller.nonce)


@router.post("/end")
async def end(request: Request):
    srv = request.app.state.server
    try:
        link, caller, _ = await verified(request, ("requested", "pending", "active", "paused"))
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_end

    answer_end(srv, link)
    return answer(srv, {"state": "ended"}, caller.nonce)
