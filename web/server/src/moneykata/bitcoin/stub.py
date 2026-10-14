"""Dev mode's and the tests' bitcoin source (requirements S17.7): made-up transactions, the same
for an address every time, so a wallet has a history without reaching any explorer. About one
address in six received coins, and about one in four of those spent some later."""

import datetime as dt
import hashlib

from .. import clock
from .sources import Tx


class Stub:
    def test(self) -> str:
        return "The stub source answered: block 919,402"

    def history(self, addresses: list[str]) -> list[Tx]:
        now = clock.now().replace(hour=12, minute=0, second=0, microsecond=0)
        out = []
        for a in addresses:
            h = hashlib.sha256(a.encode()).digest()
            if h[0] >= 42:
                continue
            sats = (h[1] * 256 + h[2]) * 700 + 1_000_000
            got = now - dt.timedelta(days=60 + h[3] * 5)
            out.append(Tx(hashlib.sha256(b"in" + h).hexdigest(), got, sats, 0, {a}))
            if h[4] < 64:
                fee = 1_420
                spent = now - dt.timedelta(days=5 + h[5] % 50)
                out.append(
                    Tx(hashlib.sha256(b"out" + h).hexdigest(), spent, -(sats // 2) - fee, fee, {a})
                )
        return out
