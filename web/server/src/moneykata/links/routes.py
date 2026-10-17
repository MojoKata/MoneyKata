"""The /link listener (requirements S11.1.3, S11.2): what a linked server calls. Everything but
`hello` is signed by a key this server has a link with, and every answer is signed back."""

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import false, select

from .. import clock, exactjson
from ..store.entities.links import Link
from . import PROTOCOL, SUPPORTED, keys, signing


def limit(request: Request) -> None:
    """Before a body is read (S13.7.5.4): a call naming a linked server's key counts against
    that link, 60 a minute; any other, against its address."""
    from .. import ratelimit

    srv = request.app.state.server
    key = request.headers.get("mk-link-key", "")
    link_id = None
    if key:
        with srv.db.read() as s:
            link_id = s.scalar(select(Link.id).where(Link.peerKey == key, Link.deleted == false()))
    if link_id:
        srv.link_limit.check(link_id, "calls from this linked server")
    else:
        host = request.client.host if request.client else None
        srv.link_unknown.check(ratelimit.address_key(host), "calls from this address")


router = APIRouter(prefix="/link/v1", include_in_schema=False, dependencies=[Depends(limit)])


def own(srv) -> tuple[object, str]:
    """This server's link key, to sign an answer, and its fingerprint."""
    return keys.signing_key(srv), keys.own_public(srv)[1]


# A call from a key with no link here is answered, signed, once its body is read, so a peer that
# lost its link learns it (S11.6); one with a larger body is refused unsigned on its headers,
# before the body is read (S13.7.5.4).
UNKNOWN_BODY = 1024 * 1024


def known(request: Request) -> bool:
    """Whether the key a call names has a link here, looked up in a read transaction."""
    srv = request.app.state.server
    key = request.headers.get("mk-link-key", "")
    if not key:
        raise signing.Refused("unsigned", "A linked server's call must be signed.")
    with srv.db.read() as s:
        return (
            s.scalar(select(Link.id).where(Link.peerKey == key, Link.deleted == false()))
            is not None
        )


async def body_of(request: Request) -> bytes:
    """The call's body, read only when its key is known or the body is small."""
    try:
        size = int(request.headers.get("content-length") or 0)
    except ValueError:
        size = UNKNOWN_BODY + 1
    if not known(request) and size > UNKNOWN_BODY:
        raise signing.Refused("not-linked", "This server has no link with yours.")
    return await request.body()


def answer(srv, data: dict, asked: signing.Asked, status: int = 200) -> Response:
    """Signed to the call it answers: its nonce, its caller and its body (link-protocol.md §3.3)."""
    body = exactjson.dumps(data, separators=(",", ":")).encode()
    k, _ = own(srv)
    headers = signing.sign_answer(k, status, body, asked)
    return Response(body, status_code=status, media_type="application/json", headers=headers)


def asked(request: Request) -> signing.Asked:
    """The call being answered; its body was read when it was verified."""
    return signing.asked_of(request.headers, getattr(request, "_body", b""))


async def verified(request: Request, states=("active",)) -> tuple[Link, signing.Caller, bytes]:
    """The link a signed call comes from, in one of these states; or a signed refusal."""
    srv = request.app.state.server
    body = await body_of(request)
    spoken = request.headers.get("mk-link-protocol", str(PROTOCOL))
    if not spoken.isdigit() or int(spoken) not in SUPPORTED:
        raise signing.Refused(
            "protocol-unsupported",
            f"This server speaks link protocol {', '.join(map(str, SUPPORTED))}; "
            f"yours sent {spoken}. The older server needs updating.",
        )
    _, fp = keys.own_public(srv)
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
        until = (
            f" until {link.pausedUntil:%b %-d, %H:%M} UTC"
            if link.state == "paused" and link.pausedUntil
            else ""
        )
        raise signing.Refused(
            f"link-{link.state}", f"The link is {link.state} on this side{until}."
        )
    return link, caller, body


def refusal(request: Request, e: signing.Refused) -> Response:
    """Signed when the call carried a nonce, so the caller can tell a refusal from a forgery."""
    status = 426 if e.code == "protocol-unsupported" else 403
    body = {"code": e.code, "message": e.message}
    if e.code == "protocol-unsupported":
        body["protocols"] = sorted(SUPPORTED)  # those it speaks, for the caller to name
    # Signed to the call when its body was read; one refused on its headers alone can't be.
    call = asked(request) if getattr(request, "_body", None) is not None else None
    if call is None:
        return JSONResponse(body, status_code=status)
    return answer(request.app.state.server, body, call, status)


@router.get("/hello")
def hello(request: Request):
    """Unsigned: the protocol this server speaks and its key's fingerprint, so a joining server
    can check it against the link code before sending anything."""
    srv = request.app.state.server
    public, fp = keys.own_public(srv)
    return {
        "protocol": PROTOCOL,
        "version": srv.version,
        "fingerprint": fp,
        "key": keys.b64(public),
    }


@router.post("/ping")
async def ping(request: Request):
    srv = request.app.state.server
    try:
        link, _caller, _ = await verified(request, ("active", "paused", "pending", "requested"))
    except signing.Refused as e:
        return refusal(request, e)
    with srv.db.tx() as s:
        row = s.get(Link, link.id)
        row.lastOkAt = clock.now()
        row.peerVersion = request.headers.get("mk-link-version")
    return answer(
        srv, {"protocol": PROTOCOL, "version": srv.version, "state": link.state}, asked(request)
    )


@router.post("/join")
async def join(request: Request):
    """A server answering an invitation: signed by its own key, which the code vouches for."""
    srv = request.app.state.server
    body = await request.body()
    try:
        _, fp = keys.own_public(srv)
        path = request.url.path
        caller = signing.verify_request(
            request.headers, request.method, path, body, fp, srv.link_nonces
        )
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_join

    out = answer_join(srv, caller.public, exactjson.loads(body or b"{}"))
    if "error" in out:
        code, message = out["error"]
        return refusal(request, signing.Refused(code, message))
    return answer(srv, {**out, "state": "requested", "version": srv.version}, asked(request))


@router.post("/exchange")
async def exchange(request: Request):
    """Each side's directory for the other's: users and household (S11.3)."""
    srv = request.app.state.server
    try:
        link, _caller, body = await verified(request, ("active", "pending"))
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_exchange

    out = answer_exchange(
        srv, link, exactjson.loads(body or b"{}"), request.headers.get("mk-link-version")
    )
    return answer(srv, out, asked(request))


@router.post("/end")
async def end(request: Request):
    srv = request.app.state.server
    try:
        link, _caller, _ = await verified(request, ("requested", "pending", "active", "paused"))
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_end

    answer_end(srv, link)
    return answer(srv, {"state": "ended"}, asked(request))


@router.post("/next")
async def next_part(request: Request):
    """The next part of a large change the caller is pulling (S11.4), oldest first."""
    srv = request.app.state.server
    try:
        link, _caller, body = await verified(request)
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_next

    return answer(srv, answer_next(srv, link, exactjson.loads(body or b"{}")), asked(request))


@router.post("/deliver")
async def deliver(request: Request):
    """The caller's change for this server, after an exchange it made (S11.4); or, before it,
    one of the receipts that change sends, sealed by the caller to this side's copy key."""
    srv = request.app.state.server
    if request.headers.get("content-type", "").startswith("application/octet-stream"):
        return await _deliver_file(request)
    try:
        link, _caller, body = await verified(request, ("active",))
    except signing.Refused as e:
        return refusal(request, e)
    from .changes import ChangeError
    from .manage import answer_deliver

    try:
        out = answer_deliver(srv, link, exactjson.loads(body or b"{}"))
    except ChangeError as e:
        return refusal(request, signing.Refused("change-refused", str(e)))
    return answer(srv, out, asked(request))


DELIVERED: dict[str, dict[str, str]] = {}  # receipts delivered for the change to come, by link
FILE_ID = re.compile(r"[A-Za-z]{2,8}_[0-9a-z]{26}")


async def _deliver_file(request: Request) -> Response:
    """A receipt the caller sends with its change (link-protocol.md §4.3): its sealed bytes as
    the body, `MK-Link-File` naming it, read as they arrive, never whole in memory, and kept as
    they came once the signature over them checks."""
    import hashlib
    import secrets

    srv = request.app.state.server
    fid = request.headers.get("mk-link-file", "")
    try:
        if not known(request):  # before a byte of the body
            raise signing.Refused("not-linked", "This server has no link with yours.")
    except signing.Refused as e:
        return JSONResponse({"code": e.code, "message": e.message}, status_code=403)
    folder = srv.config.data_dir / "links-in"
    folder.mkdir(mode=0o700, exist_ok=True)
    tmp = folder / (secrets.token_hex(12) + ".tmp")
    h = hashlib.sha256()
    try:
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                h.update(chunk)
                f.write(chunk)
        digest = h.hexdigest()
        _, fp = keys.own_public(srv)
        try:
            caller = signing.verify_request(
                request.headers, "POST", request.url.path, b"", fp, srv.link_nonces, digest=digest
            )
            with srv.db.read() as s:
                link = s.scalars(
                    select(Link).where(
                        Link.peerKey == keys.b64(caller.public), Link.deleted == false()
                    )
                ).first()
            if link is None or link.state != "active":
                raise signing.Refused("not-linked", "This server has no active link with yours.")
            if not FILE_ID.fullmatch(fid):
                raise signing.Refused("file-refused", "The file isn't named.")
        except signing.Refused as e:
            call = signing.asked_of(request.headers, b"", digest=digest)
            body = {"code": e.code, "message": e.message}
            if call is None:
                return JSONResponse(body, status_code=403)
            return answer(srv, body, call, 403)
        from .receive import keep_delivered

        with open(tmp, "rb") as f:
            name = keep_delivered(srv, link.id, iter(lambda: f.read(1 << 16), b""))
        DELIVERED.setdefault(link.id, {})[fid] = name
    finally:
        tmp.unlink(missing_ok=True)
    return answer(srv, {"ok": True}, signing.asked_of(request.headers, b"", digest=digest))


@router.post("/certificate")
async def certificate(request: Request):
    """The peer's next TLS certificate key, announced before it is used (link-protocol.md
    §4.5): accepted beside the pinned one until it is in use."""
    srv = request.app.state.server
    try:
        link, _, body = await verified(request, ("active", "paused"))
    except signing.Refused as e:
        return refusal(request, e)
    from .manage import answer_certificate

    return answer(
        srv, answer_certificate(srv, link, exactjson.loads(body or b"{}")), asked(request)
    )


@router.post("/file")
async def file(request: Request):
    """One receipt, for a peer whose people may have it (S11.5.1): sealed to the caller's copy
    key, so only that copy opens it, and its answer signed over the sealed bytes' hash."""
    from fastapi.responses import StreamingResponse

    from .serve import allowed_file

    srv = request.app.state.server
    try:
        link, _caller, body = await verified(request, ("active",))
    except signing.Refused as e:
        return refusal(request, e)
    rid = str(exactjson.loads(body or b"{}").get("id") or "")
    if not allowed_file(srv, link.id, rid):
        return refusal(request, signing.Refused("not-shared", "That receipt isn't shared."))
    from .changes import ChangeError
    from .serve import sealed_receipt, stream_file

    try:
        path, digest = sealed_receipt(srv, link.id, rid)
    except ChangeError as e:
        return refusal(request, signing.Refused("not-shared", str(e)))
    k, _ = own(srv)
    # Sealed to the caller's copy key, and signed over the sealed bytes (link-protocol.md §4).
    headers = signing.sign_answer(k, 200, b"", asked(request), digest=digest)
    return StreamingResponse(
        stream_file(path), media_type="application/octet-stream", headers=headers
    )
