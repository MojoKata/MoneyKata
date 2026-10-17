"""Output descriptors (requirements S1.6.1.4), as Sparrow, Nunchuk and Bitcoin Core export them:
single-key `pkh()`, `sh(wpkh())`, `wpkh()` and `tr()` (taproot, BIP 86), and multisig
`wsh(sortedmulti(k, …))` and `wsh(multi(k, …))`. Each key is an xpub with its origin
(`[fingerprint/path]`) and a `/0/*`, `/1/*` or `/<0;1>/*` ending. The checksum (BIP 380) is
checked when there is one. Only public keys are ever held: a private key in one is refused."""

import hashlib
import re
from dataclasses import dataclass

from . import keys as bk

INPUT_CHARSET = (
    "0123456789()[],'/*abcdefgh@:$%{}"
    "IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~"
    'ijklmnopqrstuvwxyzABCDEFGH`#"\\ '
)
CHECKSUM_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
GENERATORS = (0xF5DEE51989, 0xA9FDCA3312, 0x1BAB10E32D, 0x3706B1677A, 0x644D626FFD)
SCRIPTS = {"pkh": "p2pkh", "sh-wpkh": "p2sh-p2wpkh", "wpkh": "p2wpkh", "tr": "p2tr"}
KEY = re.compile(r"^(?:\[([0-9a-fA-F]{8})((?:/\d+['hH]?)*)\])?([1-9A-HJ-NP-Za-km-z]+)(/.*)?$")
ENDINGS = {"/0/*": (0,), "/1/*": (1,), "/<0;1>/*": (0, 1)}
MULTI = re.compile(r"^(sortedmulti|multi)\((\d+),(.*)\)$")


def _polymod(c: int, val: int) -> int:
    c0 = c >> 35
    c = ((c & 0x7FFFFFFFF) << 5) ^ val
    for i, g in enumerate(GENERATORS):
        if c0 & (1 << i):
            c ^= g
    return c


def checksum(desc: str) -> str:
    """The 8-character checksum of a descriptor without its `#`."""
    c = 1
    cls = 0
    clscount = 0
    for ch in desc:
        pos = INPUT_CHARSET.find(ch)
        if pos == -1:
            raise bk.Refused("descriptor-invalid", "A character a descriptor can't hold.")
        c = _polymod(c, pos & 31)
        cls = cls * 3 + (pos >> 5)
        clscount += 1
        if clscount == 3:
            c = _polymod(c, cls)
            cls = clscount = 0
    if clscount > 0:
        c = _polymod(c, cls)
    for _ in range(8):
        c = _polymod(c, 0)
    c ^= 1
    return "".join(CHECKSUM_CHARSET[(c >> (5 * (7 - i))) & 31] for i in range(8))


def looks_like(text: str) -> bool:
    return bool(re.match(r"^\s*(pkh|wpkh|sh|tr|wsh)\(", text))


@dataclass(frozen=True)
class Key:
    origin: str  # [fingerprint/path], as written, or ""
    xpub: str
    key: bk.ExtendedKey


@dataclass(frozen=True)
class Descriptor:
    kind: str  # pkh, sh-wpkh, wpkh, tr, wsh-sortedmulti, wsh-multi
    keys: tuple[Key, ...]
    chains: tuple[int, ...]  # 0 receive, 1 change
    threshold: int = 1
    ending: str = "/<0;1>/*"

    @property
    def script(self) -> str:
        return SCRIPTS.get(self.kind, "p2wsh")

    def body(self, ending: str | None = None) -> str:
        """The descriptor written out, without its checksum."""
        end = ending or self.ending
        ks = ",".join(f"{k.origin}{k.xpub}{end}" for k in self.keys)
        if self.kind == "sh-wpkh":
            return f"sh(wpkh({ks}))"
        if self.kind.startswith("wsh-"):
            return f"wsh({self.kind[4:]}({self.threshold},{ks}))"
        return f"{self.kind}({ks})"

    def text(self, ending: str | None = None) -> str:
        b = self.body(ending)
        return f"{b}#{checksum(b)}"

    def address(self, chain: int, index: int) -> str:
        pubs = [k.key.child(chain).child(index).key for k in self.keys]
        if self.kind == "tr":
            return taproot(pubs[0])
        if self.kind.startswith("wsh-"):
            if self.kind == "wsh-sortedmulti":
                pubs = sorted(pubs)
            script = bytes([0x50 + self.threshold])
            for p in pubs:
                script += bytes([len(p)]) + p
            script += bytes([0x50 + len(pubs), 0xAE])
            return bk.segwit_encode(0, hashlib.sha256(script).digest())
        return bk.address_of(pubs[0], self.script)


def _tagged(tag: str, msg: bytes) -> bytes:
    t = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(t + t + msg).digest()


def taproot(pub: bytes) -> str:
    """A BIP 86 address: the key, with an even y, tweaked by its own hash with no script."""
    x = pub[1:]
    internal = bk._point(b"\x02" + x)
    t = int.from_bytes(_tagged("TapTweak", x), "big")
    if t >= bk.N:
        raise bk.Refused("descriptor-invalid", "A key that can't make a taproot address.")
    q = bk._add(internal, bk._mul(t))
    return bk.segwit_encode(1, q[0].to_bytes(32, "big"))


def _split_top(args: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out]


def _key(text: str) -> tuple[Key, str]:
    m = KEY.match(text)
    if not m:
        raise bk.Refused("descriptor-invalid", "A descriptor key MoneyKata can't read.")
    fp, path, xpub, rest = m.groups()
    if xpub[:4] in ("xprv", "tprv", "yprv", "zprv"):
        raise bk.Refused(
            "private-key",
            "That descriptor holds an extended private key. MoneyKata never accepts one: export "
            "the wallet's public descriptor instead. Nothing was saved.",
        )
    if len(xpub) in (51, 52) and xpub[0] in "5KLc9":
        raise bk.Refused(
            "private-key",
            "That descriptor holds a private key. MoneyKata never accepts one: export the "
            "wallet's public descriptor instead. Nothing was saved.",
        )
    if not xpub.startswith("xpub"):
        if xpub.startswith("tpub"):
            raise bk.Refused("testnet", "A testnet key: MoneyKata follows mainnet bitcoin only.")
        raise bk.Refused("descriptor-invalid", "Each descriptor key is an xpub.")
    ending = (rest or "").replace("h", "'").replace("H", "'")
    if ending not in ENDINGS:
        raise bk.Refused("descriptor-ending", "A descriptor's keys end /0/*, /1/* or /<0;1>/*.")
    origin = f"[{fp}{path}]" if fp else ""
    return Key(origin, xpub, bk.extended(xpub)), ending


def parse(text: str) -> Descriptor:
    """A descriptor, read and its checksum checked; Refused, naming the first problem."""
    text = "".join(text.split())
    body, _, given = text.partition("#")
    if given and checksum(body) != given:
        raise bk.Refused(
            "descriptor-checksum",
            "The descriptor's checksum doesn't match: check it was copied whole.",
        )
    m = re.match(r"^(\w+)\((.*)\)$", body)
    if not m:
        raise bk.Refused("descriptor-invalid", "Not a descriptor MoneyKata reads.")
    outer, inner = m.groups()
    if outer == "sh":
        m2 = re.match(r"^wpkh\((.*)\)$", inner)
        if not m2:
            raise bk.Refused(
                "descriptor-unsupported", "Of sh() descriptors, only sh(wpkh(…)) is read."
            )
        outer, inner = "sh-wpkh", m2.group(1)
    if outer in ("pkh", "wpkh", "tr", "sh-wpkh"):
        if "," in inner:
            raise bk.Refused(
                "descriptor-unsupported",
                "A taproot descriptor with scripts isn't read yet: its key path only.",
            )
        k, ending = _key(inner)
        return Descriptor(outer, (k,), ENDINGS[ending], 1, ending)
    if outer == "wsh":
        mm = MULTI.match(inner)
        if not mm:
            raise bk.Refused(
                "descriptor-unsupported",
                "Of wsh() descriptors, only sortedmulti and multi are read.",
            )
        kind, k, rest = mm.groups()
        parsed = [_key(x) for x in _split_top(rest)]
        endings = {e for _, e in parsed}
        threshold = int(k)
        if len(endings) != 1 or not 1 <= threshold <= len(parsed) <= 15:
            raise bk.Refused("descriptor-invalid", "A multisig descriptor MoneyKata can't read.")
        ending = endings.pop()
        return Descriptor(
            f"wsh-{kind}", tuple(k for k, _ in parsed), ENDINGS[ending], threshold, ending
        )
    raise bk.Refused("descriptor-unsupported", f"{outer}() descriptors aren't read.")
