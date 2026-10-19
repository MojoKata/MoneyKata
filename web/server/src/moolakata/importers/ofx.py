"""OFX and QFX files (requirements S1.3.2), read with ofxtools: bank, card and investment
statements, with brokers' trades, positions and securities."""

import datetime as dt
import io
from decimal import Decimal

from ofxtools.Parser import OFXTree

from .parsed import ParsedFile, Position, ReadError, Row, Security, occ, occ_symbol

BANK_KINDS = {
    "INT": "interest",
    "DIV": "dividend",
    "FEE": "fee",
    "SRVCHG": "fee",
    "XFER": "transfer",
    "CREDIT": "deposit",
    "DEP": "deposit",
    "DIRECTDEP": "deposit",
    "DEBIT": "withdrawal",
    "ATM": "withdrawal",
    "POS": "withdrawal",
    "CHECK": "withdrawal",
    "PAYMENT": "withdrawal",
    "CASH": "withdrawal",
    "DIRECTDEBIT": "withdrawal",
    "REPEATPMT": "withdrawal",
}
INCOME_TYPES = {
    "DIV": "ordinary",
    "INTEREST": None,
    "CGLONG": "capital-gain",
    "CGSHORT": "capital-gain",
    "MISC": None,
}
SEC_CLASSES = {
    "STOCKINFO": "equity",
    "MFINFO": "mutual-fund",
    "DEBTINFO": "bond",
    "OPTINFO": "option",
    "OTHERINFO": "other",
}
# The four option trades and an option's three ends (S3.2-S3.4).
OPTION_TRADES = {
    "BUYTOOPEN": "buy-to-open",
    "BUYTOCLOSE": "buy-to-close",
    "SELLTOOPEN": "sell-to-open",
    "SELLTOCLOSE": "sell-to-close",
}
OPTION_ENDS = {"EXPIRE": "expire", "ASSIGN": "assign", "EXERCISE": "exercise"}


def looks_like_ofx(head: bytes) -> bool:
    text = head[:2048].decode("latin-1", "replace").upper()
    return "OFXHEADER" in text or "<OFX>" in text


def _raw_dates(root) -> dict[str, dt.date]:
    """Calendar dates as the institution wrote them, by FITID: ofxtools converts to UTC,
    which could move a late-evening posting to the next day (S14.9.3)."""
    out: dict[str, dt.date] = {}
    for el in root.iter():
        if el.tag not in ("STMTTRN", "INVTRAN"):
            continue
        fitid = el.findtext("FITID")
        raw = el.findtext("DTPOSTED") or el.findtext("DTTRADE")
        if fitid and raw and len(raw.strip()) >= 8:
            r = raw.strip()
            out[fitid] = dt.date(int(r[:4]), int(r[4:6]), int(r[6:8]))
    return out


def _day(value) -> dt.date | None:
    return value.date() if isinstance(value, dt.datetime) else value


def read(data: bytes) -> ParsedFile:
    tree = OFXTree()
    try:
        tree.parse(io.BytesIO(data))
        ofx = tree.convert()
    except Exception as e:
        raise ReadError(
            f"This is not an OFX or QFX file MoolaKata can read ({type(e).__name__})."
        ) from None
    dates = _raw_dates(tree.getroot())
    statements = list(ofx.statements)
    if not statements:
        raise ReadError("The file holds no statement.")
    if len(statements) > 1:
        raise ReadError(
            "The file holds statements for several accounts; download one account at a time."
        )
    st = statements[0]
    out = ParsedFile(format="ofx")
    try:
        out.institution = ofx.signonmsgsrsv1.sonrs.fi.org
    except AttributeError:
        out.institution = None
    out.accountNumber = getattr(st.account, "acctid", None)
    name = type(st).__name__
    if name == "INVSTMTRS":
        out.accountKind = "investment"
        _securities(ofx, out)
        _investment(st, out, dates)
    else:
        out.accountKind = "card" if name == "CCSTMTRS" else "bank"
        _bank(st, out, dates)
    out.cover()
    return out


def _bank(st, out: ParsedFile, dates: dict) -> None:
    tl = st.banktranlist
    if tl is not None:
        out.coveredFrom, out.coveredTo = _day(tl.dtstart), _day(tl.dtend)
        for t in tl:
            out.rows.append(
                Row(
                    date=dates.get(t.fitid) or _day(t.dtposted),
                    kind=BANK_KINDS.get(t.trntype, "deposit" if t.trnamt > 0 else "withdrawal"),
                    amount=t.trnamt,
                    fitId=t.fitid,
                    payee=(t.name or (t.payee and t.payee.name) or None),
                    memo=t.memo,
                )
            )
    if st.ledgerbal is not None:
        out.balances.append((_day(st.ledgerbal.dtasof), st.ledgerbal.balamt))


def _securities(ofx, out: ParsedFile) -> None:
    try:
        seclist = ofx.seclistmsgsrsv1
    except AttributeError:
        return
    if not seclist:
        return
    tickers = {
        s.secinfo.secid.uniqueid: (s.secinfo.ticker or "").strip().upper() for s in ofx.securities
    }
    for s in ofx.securities:
        info = s.secinfo
        cls = SEC_CLASSES.get(type(s).__name__, "other")
        if cls == "mutual-fund" and info.secname and "money market" in info.secname.lower():
            cls = "money-market"
        cusip = info.secid.uniqueid if info.secid.uniqueidtype == "CUSIP" else None
        symbol = (info.ticker or "").strip().upper() or None
        multiplier = None
        if cls == "option":
            # A contract by its OCC ticker, or, when the file's ticker isn't one, by the terms
            # OPTINFO gives: the underlying it names, the right, the strike and the expiry.
            symbol = occ_symbol(symbol) or occ_symbol(info.secname) or _occ_of(s, tickers) or symbol
            multiplier = int(s.shperctrct) if getattr(s, "shperctrct", None) else None
        out.securities[info.secid.uniqueid] = Security(
            key=info.secid.uniqueid,
            symbol=symbol,
            name=info.secname,
            instrumentClass=cls,
            cusip=cusip,
            multiplier=multiplier,
        )


def _occ_of(s, tickers: dict[str, str]) -> str | None:
    under = getattr(s, "secid", None)
    root = tickers.get(under.uniqueid) if under is not None else None
    if not root or s.opttype not in ("CALL", "PUT") or not s.strikeprice or not s.dtexpire:
        return None
    return occ(root, _day(s.dtexpire), s.opttype[0], s.strikeprice)


def _investment(st, out: ParsedFile, dates: dict) -> None:
    tl = st.invtranlist
    if tl is not None:
        out.coveredFrom, out.coveredTo = _day(tl.dtstart), _day(tl.dtend)
        for t in tl:
            out.rows += _inv_rows(t, dates)
    if st.invposlist is not None:
        for p in st.invposlist:
            pos = p.invpos
            out.positions.append(
                Position(
                    security=pos.secid.uniqueid,
                    asOf=_day(pos.dtpriceasof) or _day(st.dtasof),
                    quantity=pos.units,
                    marketValue=pos.mktval,
                )
            )
    if st.invbal is not None and st.invbal.availcash is not None:
        out.balances.append((_day(st.dtasof), st.invbal.availcash))


def _inv_rows(t, dates: dict) -> list[Row]:
    row = _inv_row(t, dates)
    if row is None:
        return []
    if row.kind != "reinvest":
        return [row]
    # A reinvestment is a dividend plus a buy (S2.5): the dividend row carries the income, and
    # the buy carries none, so the income panel counts it once.
    income = Row(
        date=row.date,
        kind="dividend",
        amount=-row.amount,
        fitId=f"{row.fitId}-in",
        memo=row.memo,
        security=row.security,
        dividendType=row.dividendType or "ordinary",
    )
    row.dividendType = None
    return [income, row]


def _inv_row(t, dates: dict) -> Row | None:
    name = type(t).__name__
    if name == "INVBANKTRAN":
        s = t.stmttrn
        return Row(
            date=dates.get(s.fitid) or _day(s.dtposted),
            kind=BANK_KINDS.get(s.trntype, "deposit" if s.trnamt > 0 else "withdrawal"),
            amount=s.trnamt,
            fitId=s.fitid,
            payee=s.name,
            memo=s.memo,
        )
    tran = t.invtran
    date = dates.get(tran.fitid) or _day(tran.dttrade)
    base = {"date": date, "fitId": tran.fitid, "memo": tran.memo}
    sec = getattr(t, "secid", None)
    key = sec.uniqueid if sec is not None else None
    fees = (getattr(t, "commission", None) or Decimal(0)) + (getattr(t, "fees", None) or Decimal(0))
    if name in ("BUYOPT", "SELLOPT"):
        return Row(
            kind=OPTION_TRADES[t.optbuytype if name == "BUYOPT" else t.optselltype],
            amount=t.total,
            security=key,
            quantity=abs(t.units),
            price=t.unitprice,
            fees=fees or None,
            **base,
        )
    if name == "CLOSUREOPT":
        return Row(
            kind=OPTION_ENDS[t.optaction],
            amount=Decimal(0),
            security=key,
            quantity=abs(t.units),
            relFitId=t.relfitid,
            **base,
        )
    if name.startswith("BUY"):
        return Row(
            kind="buy",
            amount=t.total,
            security=key,
            quantity=abs(t.units),
            price=t.unitprice,
            fees=fees or None,
            **base,
        )
    if name.startswith("SELL"):
        return Row(
            kind="sell",
            amount=t.total,
            security=key,
            quantity=abs(t.units),
            price=t.unitprice,
            fees=fees or None,
            **base,
        )
    if name == "INCOME":
        kind = {"INTEREST": "interest", "CGLONG": "capital-gain", "CGSHORT": "capital-gain"}.get(
            t.incometype, "dividend"
        )
        return Row(
            kind=kind,
            amount=t.total,
            security=key,
            dividendType=INCOME_TYPES.get(t.incometype),
            **base,
        )
    if name == "REINVEST":
        return Row(
            kind="reinvest",
            amount=-abs(t.total),
            security=key,
            quantity=t.units,
            price=t.unitprice,
            fees=fees or None,
            dividendType=INCOME_TYPES.get(t.incometype),
            **base,
        )
    if name == "TRANSFER":
        kind = "transfer-in" if t.tferaction == "IN" else "transfer-out"
        return Row(kind=kind, amount=Decimal(0), security=key, quantity=abs(t.units), **base)
    if name == "SPLIT":
        ratio = (t.numerator / t.denominator) if t.denominator else None
        return Row(kind="split", amount=Decimal(0), security=key, splitRatio=ratio, **base)
    if name == "RETOFCAP":
        return Row(kind="return-of-capital", amount=t.total, security=key, **base)
    if name in ("INVEXPENSE", "MARGININTEREST"):
        return Row(kind="fee", amount=-abs(t.total), security=key, **base)
    return None
