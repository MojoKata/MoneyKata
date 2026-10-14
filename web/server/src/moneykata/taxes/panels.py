"""The tax panels (requirements S8.1–S8.13): for one tax book's accounts and year, Form 8949
rows with wash sales and Schedule D totals, income, retirement, deductions and credits, giving,
education, gifts, loans, physical assets, and the missing or doubtful data to look at. Figures
and their sources only: MoneyKata never computes the tax."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Integer, cast, false, func, select
from sqlalchemy.orm import Session

from .. import assets, education, gifts, giving, loans
from ..ledger import types as atypes
from ..projections import taxtables
from ..store.entities.accounts import Account, Category, Instrument, Lot, Split, Transaction
from ..store.entities.assets import Item
from ..store.entities.receipts import ReceiptLink
from ..store.entities.taxes import EstimatedPayment, TaxBook
from ..store.entities.users import User
from ..store.repos import ledger as repo
from . import books

ZERO = Decimal(0)
CENT = Decimal("0.01")
WASH_DAYS = 30
# The Uniform Lifetime Table's distribution periods (Treas. Reg. 1.401(a)(9)-9), ages 72–100.
UNIFORM = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1, 80: 20.2,
    81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9,
    90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3,
    99: 6.8, 100: 6.4,
}  # fmt: skip


def _span(year: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, 1, 1), dt.date(year, 12, 31)


# ---------- Form 8949 and Schedule D (S8.1, S8.3, S8.13) ----------


@dataclass
class Row:
    """One Form 8949 line."""

    description: str
    acquired: dt.date | None
    sold: dt.date
    proceeds: Decimal
    basis: Decimal | None
    code: str  # adjustment codes: W wash sale, L nondeductible loss, C collectible
    adjustment: Decimal
    longTerm: bool
    box: str  # A–C short term, D–F long term (S8.1)
    account: str
    collectable: bool = False
    saleId: str | None = None
    instrumentId: str | None = None
    quantity: Decimal | None = None

    @property
    def gain(self) -> Decimal | None:
        if self.basis is None:
            return None
        return (self.proceeds - self.basis + self.adjustment).quantize(CENT)


@dataclass
class Wash:
    """A loss disallowed because the same instrument was bought within 30 days (S3.8)."""

    sold: dt.date
    symbol: str
    account: str
    loss: Decimal
    disallowed: Decimal
    replacedOn: dt.date
    replacementAccount: str
    replacementQty: Decimal
    adjustedBasis: Decimal | None  # the replacement lot's basis with the loss added


def _box(long_term: bool, reported: bool, covered: bool) -> str:
    """The 8949 box the broker's reporting decides: basis reported (A/D), not reported
    (B/E), or no 1099-B at all (C/F)."""
    if not reported:
        return "F" if long_term else "C"
    if not covered:
        return "E" if long_term else "B"
    return "D" if long_term else "A"


def _taxable(accounts: list[Account]) -> list[Account]:
    return [a for a in accounts if atypes.TAX.get(a.type) == "taxable"]


def _covered(cls: str, acquired: dt.date) -> bool:
    """Whether the broker reports the basis: equities from 2011, funds from 2012, other
    securities from 2014."""
    if cls == "equity":
        return acquired >= dt.date(2011, 1, 1)
    if cls in ("etf", "mutual-fund"):
        return acquired >= dt.date(2012, 1, 1)
    return acquired >= dt.date(2014, 1, 1)


def form_8949(s: Session, book: TaxBook, spouse_accounts: list[Account] | None = None):
    """Every sale in the book's taxable accounts in the year, and each sold item, as 8949 rows,
    with wash sales found across the book's accounts (IRAs included) and the spouse's."""
    first, last = _span(book.year)
    counted = books.counted(s, book).accounts
    rows: list[Row] = []
    washes: list[Wash] = []
    insts: dict[str, Instrument] = {}
    buys = _purchases(s, counted + (spouse_accounts or []), first, last)
    for a in _taxable(counted):
        if a.type not in ("brokerage", "crypto-exchange", "crypto-wallet"):
            continue
        led = repo.load(s, a)
        for d in led.replay().disposals:
            if not first <= d.soldOn <= last:
                continue
            inst = insts.get(d.instrumentId) or s.get(Instrument, d.instrumentId)
            insts[inst.id] = inst
            crypto = inst.instrumentClass == "crypto"
            row = Row(
                description=f"{_qty(d.quantity)} {inst.symbol}",
                acquired=d.acquiredOn if d.lotId else None,
                sold=d.soldOn,
                proceeds=d.proceeds,
                basis=d.basis,
                code="",
                adjustment=ZERO,
                longTerm=d.longTerm,
                box=_box(d.longTerm, not crypto, _covered(inst.instrumentClass, d.acquiredOn)),
                account=a.name,
                saleId=d.saleId,
                instrumentId=inst.id,
                quantity=d.quantity,
            )
            loss = -(row.gain or ZERO)
            if loss > 0 and inst.instrumentClass in ("equity", "etf", "mutual-fund"):
                w = _wash(row, d, buys, inst, loss)
                if w is not None:
                    row.code, row.adjustment = "W", w.disallowed
                    washes.append(w)
            rows.append(row)
    rows += _items(s, counted, first, last)
    return rows, washes


def _qty(q: Decimal) -> str:
    return f"{q.normalize():f}"


@dataclass
class Buy:
    accountName: str
    date: dt.date
    quantity: Decimal
    lot: Lot | None
    used: Decimal = ZERO  # shares already a replacement for an earlier loss


def _purchases(s: Session, accounts: list[Account], first: dt.date, last: dt.date):
    """Buys within the year and 30 days either side, by instrument."""
    names = {a.id: a.name for a in accounts}
    out: dict[str, list[Buy]] = defaultdict(list)
    if not names:
        return out
    lots = {
        lot.transactionId: lot
        for lot in s.scalars(select(Lot).where(Lot.accountId.in_(list(names))))
    }
    for t in s.scalars(
        select(Transaction).where(
            Transaction.accountId.in_(list(names)),
            Transaction.deleted == false(),
            Transaction.kind.in_(("buy", "reinvest")),
            Transaction.date >= first - dt.timedelta(days=WASH_DAYS),
            Transaction.date <= last + dt.timedelta(days=WASH_DAYS),
        )
    ):
        out[t.instrumentId].append(Buy(names[t.accountId], t.date, t.quantity, lots.get(t.id)))
    return out


def _wash(row: Row, d, buys, inst: Instrument, loss: Decimal) -> Wash | None:
    """The replacements bought within 30 days of a loss sale, nearest first and each share used
    once, other than the lot sold (S3.8)."""
    left = d.quantity
    disallowed = ZERO
    first = None
    for b in sorted(buys.get(inst.id, []), key=lambda b: abs((b.date - d.soldOn).days)):
        if left <= 0:
            break
        if abs((b.date - d.soldOn).days) > WASH_DAYS:
            break
        if b.lot is not None and b.lot.id == d.lotId:
            continue
        if b.date == d.acquiredOn and b.accountName == row.account and b.quantity == d.quantity:
            continue  # the lot that was sold
        take = min(left, b.quantity - b.used)
        if take <= 0:
            continue
        b.used += take
        left -= take
        part = (loss * take / d.quantity).quantize(CENT) if d.quantity else loss
        disallowed += part
        if first is None:
            basis = b.lot.costBasis if b.lot is not None else None
            first = (b, part, basis)
    if first is None:
        return None
    b, part, basis = first
    return Wash(
        d.soldOn,
        inst.symbol,
        row.account,
        loss,
        disallowed,
        b.date,
        b.accountName,
        b.quantity,
        basis + part if basis is not None else None,
    )


def _items(s: Session, accounts: list[Account], first: dt.date, last: dt.date) -> list[Row]:
    """Physical assets sold (S8.13): collectables marked; a personal-use loss not deductible
    (code L)."""
    out = []
    phys = {a.id: a for a in accounts if assets.is_physical(a.type)}
    if not phys:
        return out
    for it in s.scalars(
        select(Item).where(
            Item.accountId.in_(list(phys)),
            Item.deleted == false(),
            Item.soldOn >= first,
            Item.soldOn <= last,
        )
    ):
        a = phys[it.accountId]
        d = assets.details(s, [it])[it.id]
        basis = assets.basis(it, d, it.soldOn)
        proceeds = it.proceeds - (it.saleFees or ZERO)
        long_term = (it.soldOn - it.acquiredOn).days > 365
        collectable = assets.is_collectable(a.type, it)
        gain = proceeds - basis
        code, adj = ("C" if collectable else ""), ZERO
        if gain < 0 and it.personalUse:
            code, adj = "L", -gain
        out.append(
            Row(
                description=it.name,
                acquired=it.acquiredOn,
                sold=it.soldOn,
                proceeds=proceeds,
                basis=basis,
                code=code,
                adjustment=adj,
                longTerm=long_term,
                box="F" if long_term else "C",
                account=a.name,
                collectable=collectable,
            )
        )
    return out


@dataclass
class ScheduleD:
    byBox: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]]  # proceeds, basis, adj, gain
    shortTerm: Decimal
    longTerm: Decimal
    collectables: Decimal  # long-term collectables gain, taxed at its own rate
    carryoverShort: Decimal
    carryoverLong: Decimal

    @property
    def net(self) -> Decimal:
        return self.shortTerm + self.longTerm - self.carryoverShort - self.carryoverLong


def schedule_d(s: Session, book: TaxBook, rows: list[Row]) -> ScheduleD:
    by: dict[str, list[Decimal]] = {}
    for r in rows:
        t = by.setdefault(r.box, [ZERO, ZERO, ZERO, ZERO])
        t[0] += r.proceeds
        t[1] += r.basis or ZERO
        t[2] += r.adjustment
        t[3] += r.gain or ZERO
    carried = books.carried_from_last_year(s, book)
    short = long_ = ZERO
    for f, figures in carried:
        if f.jurisdiction == "federal":
            short = Decimal(str(figures.get("capitalLossShort") or 0))
            long_ = Decimal(str(figures.get("capitalLossLong") or 0))
    return ScheduleD(
        byBox={k: tuple(v) for k, v in sorted(by.items())},
        shortTerm=sum((r.gain or ZERO for r in rows if not r.longTerm), ZERO),
        longTerm=sum((r.gain or ZERO for r in rows if r.longTerm), ZERO),
        collectables=sum((r.gain or ZERO for r in rows if r.longTerm and r.collectable), ZERO),
        carryoverShort=short,
        carryoverLong=long_,
    )


# ---------- Income (S8.5) ----------


@dataclass
class Income:
    interest: list[tuple[str, Decimal]]  # by payer
    ordinary: Decimal
    qualified: Decimal
    capitalGainDistributions: Decimal
    returnOfCapital: Decimal
    byPayer: list[tuple[str, Decimal]]  # dividends by payer


def income(s: Session, book: TaxBook) -> Income:
    first, last = _span(book.year)
    interest: dict[str, Decimal] = defaultdict(lambda: ZERO)
    divs: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_payer: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for a in _taxable(books.counted(s, book).accounts):
        payer = a.institution or a.name
        for t in s.scalars(
            select(Transaction).where(
                Transaction.accountId == a.id,
                Transaction.deleted == false(),
                Transaction.kind.in_(("interest", "dividend", "reinvest", "capital-gain")),
                Transaction.date >= first,
                Transaction.date <= last,
            )
        ):
            if t.kind == "interest":
                interest[payer] += t.amount
            elif t.kind == "capital-gain":
                divs["capital-gain"] += t.amount
                by_payer[payer] += t.amount
            elif t.kind == "dividend" or (t.kind == "reinvest" and t.dividendType):
                amount = t.amount if t.kind == "dividend" else -t.amount
                divs[t.dividendType or "ordinary"] += amount
                by_payer[payer] += amount
    return Income(
        interest=sorted(((k, v) for k, v in interest.items() if v), key=lambda x: -x[1]),
        # Qualified dividends are part of ordinary dividends (1099-DIV box 1a includes 1b).
        ordinary=divs["ordinary"] + divs["qualified"],
        qualified=divs["qualified"],
        capitalGainDistributions=divs["capital-gain"],
        returnOfCapital=divs["return-of-capital"],
        byPayer=sorted(((k, v) for k, v in by_payer.items() if v), key=lambda x: -x[1]),
    )


# ---------- Retirement (S8.6) ----------


@dataclass
class Contribution:
    account: str
    kind: str
    owner: str
    contributed: Decimal
    limit: Decimal | None
    note: str


@dataclass
class Rmd:
    account: str
    owner: str
    age: int
    balance: Decimal  # at the end of last year
    factor: float
    due: Decimal


@dataclass
class Retirement:
    contributions: list[Contribution]
    distributions: list[tuple[str, Decimal]]
    rmds: list[Rmd]
    basis8606: Decimal | None


def retirement(s: Session, book: TaxBook) -> Retirement:
    y = book.year
    first, last = _span(y)
    figures = taxtables.figures(s, y)
    accounts = [a for a in books.counted(s, book).accounts if atypes.retirement(a.type)]
    contributions, distributions, rmds = [], [], []
    ira_by_owner: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for a in accounts:
        owner = s.get(User, a.ownerId)
        age = y - owner.birthYear if owner.birthYear else None
        put = (
            s.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.accountId == a.id,
                    Transaction.deleted == false(),
                    Transaction.amount > 0,
                    Transaction.instrumentId.is_(None),
                    Transaction.kind.in_(("deposit", "transfer")),
                    func.coalesce(
                        Transaction.contributionYear,
                        cast(func.strftime("%Y", Transaction.date), Integer),
                    )
                    == y,
                    func.coalesce(Transaction.contributionSource, "employee") == "employee",
                )
            )
            or ZERO
        )
        put = Decimal(str(put))
        limit, note = None, ""
        if a.type in ("ira", "roth-ira"):
            ira_by_owner[owner.id] += put
            limit = Decimal(str(figures["iraLimit"]))
            if age and age >= 50:
                limit += Decimal(str(figures["iraCatchUp"]))
                note = "with the catch-up at 50 and over"
            if a.type == "roth-ira":
                note = (note + "; " if note else "") + "Roth eligibility depends on MAGI"
        elif a.type in ("401k", "403b", "457b"):
            limit = Decimal(str(figures["k401Deferral"]))
            if age and 60 <= age <= 63:
                limit += Decimal(str(figures["k401CatchUp6063"]))
                note = "with the catch-up at 60–63"
            elif age and age >= 50:
                limit += Decimal(str(figures["k401CatchUp"]))
                note = "with the catch-up at 50 and over"
        elif a.type == "hsa":
            limit = Decimal(str(figures["hsaFamily"]))
            note = "the family limit; self-only is lower"
        if put or limit:
            contributions.append(
                Contribution(a.name, atypes.LABELS[a.type], owner.displayName, put, limit, note)
            )
        taken = (
            s.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.accountId == a.id,
                    Transaction.deleted == false(),
                    Transaction.amount < 0,
                    Transaction.instrumentId.is_(None),
                    Transaction.kind.in_(("withdrawal", "transfer")),
                    Transaction.date >= first,
                    Transaction.date <= last,
                )
            )
            or ZERO
        )
        if taken:
            distributions.append((a.name, -Decimal(str(taken))))
        rmd_age = int(figures["rmdAge"])
        if age and age >= rmd_age and a.type in ("ira", "401k", "403b", "457b") and age in UNIFORM:
            from .. import valuation

            led = repo.load(s, a)
            bal = valuation.account_value(s, led, True, dt.date(y - 1, 12, 31))
            factor = UNIFORM[age]
            rmds.append(
                Rmd(
                    a.name,
                    owner.displayName,
                    age,
                    bal,
                    factor,
                    (bal / Decimal(str(factor))).quantize(CENT),
                )
            )
    basis = None
    for f, figs in books.carried_from_last_year(s, book):
        if f.jurisdiction == "federal" and figs.get("basis8606"):
            basis = Decimal(str(figs["basis8606"]))
    return Retirement(contributions, distributions, rmds, basis)


# ---------- Deductions and credits (S8.7) ----------


@dataclass
class TagTotal:
    tag: str
    label: str
    total: Decimal
    count: int
    withReceipts: int


TAG_LABELS = {
    "medical": "Medical and dental",
    "childcare": "Childcare",
    "education": "Education",
    "charitable": "Charitable gifts",
    "business": "Business expenses",
    "loan-interest": "Loan interest",
    "property-tax": "Property tax",
    "retirement": "Retirement contributions",
}


def deductions(s: Session, book: TaxBook) -> tuple[list[TagTotal], list[tuple[str, int, Decimal]]]:
    """Totals of tax-tagged categories with how many have receipts; and estimated tax
    payments by quarter."""
    first, last = _span(book.year)
    ids = [a.id for a in books.counted(s, book).accounts]
    cats = {c.id: c for c in s.scalars(select(Category).where(Category.taxTag.is_not(None)))}
    out: dict[str, TagTotal] = {}
    if ids and cats:
        txns = s.scalars(
            select(Transaction).where(
                Transaction.accountId.in_(ids),
                Transaction.deleted == false(),
                Transaction.date >= first,
                Transaction.date <= last,
            )
        ).all()
        by_id = {t.id: t for t in txns}
        amounts: list[tuple[str, str, Decimal]] = []
        for t in txns:
            if t.categoryId in cats:
                amounts.append((t.id, cats[t.categoryId].taxTag, -t.amount))
        for sp in s.scalars(
            select(Split).where(
                Split.transactionId.in_(list(by_id)),
                Split.deleted == false(),
                Split.categoryId.in_(list(cats)),
            )
        ):
            amounts.append((sp.transactionId, cats[sp.categoryId].taxTag, sp.amount))
        with_receipts = set(
            s.scalars(
                select(ReceiptLink.itemId).where(
                    ReceiptLink.kind == "transaction",
                    ReceiptLink.deleted == false(),
                    ReceiptLink.itemId.in_(list(by_id)),
                )
            )
        )
        for t_id, tag, amount in amounts:
            row = out.setdefault(tag, TagTotal(tag, TAG_LABELS.get(tag, tag), ZERO, 0, 0))
            row.total += amount
            row.count += 1
            row.withReceipts += t_id in with_receipts
    quarters = []
    for f in books.filings(s, book):
        for p in s.scalars(
            select(EstimatedPayment).where(
                EstimatedPayment.filingId == f.id, EstimatedPayment.deleted == false()
            )
        ):
            where = "Federal" if f.jurisdiction == "federal" else (f.place or "State")
            quarters.append((where, p.quarter, p.amount))
    return sorted(out.values(), key=lambda x: -x.total), sorted(quarters, key=lambda q: q[:2])


# ---------- Giving, education, gifts, loans (S8.9–S8.12) ----------


def giving_panel(s: Session, book: TaxBook) -> list[giving.Gift]:
    who = [f.userId for f in books.filers(s, book) if f.acceptedAt is not None]
    return giving.donations(s, who, book.year)


@dataclass
class EducationRow:
    account: str
    beneficiary: str
    contributions: list[tuple[str, Decimal]]  # by contributor
    stateDeduction: Decimal | None
    distributions: Decimal
    expenses: Decimal
    notCovered: Decimal


def education_panel(s: Session, book: TaxBook) -> list[EducationRow]:
    out = []
    for a in books.counted(s, book).accounts:
        if a.type != "529":
            continue
        plan = education.plan_of(s, a)
        b = education.beneficiary(s, plan)
        by: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for r in education.contributions(s, a):
            if r.date.year == book.year:
                by[r.name] += r.amount
        w = next((x for x in education.withdrawals(s, a) if x.year == book.year), None)
        out.append(
            EducationRow(
                a.name,
                b.name if b else "—",
                sorted(by.items()),
                plan.stateDeduction if plan else None,
                w.distributions if w else ZERO,
                w.expenses if w else ZERO,
                w.notCovered if w else ZERO,
            )
        )
    return out


@dataclass
class GiftTax:
    giver: str
    person: str
    given: Decimal
    exclusion: Decimal


def gifts_panel(s: Session, book: TaxBook) -> tuple[list[GiftTax], list[str]]:
    """Each person who received more than the exclusion from a filer, and the five-year 529
    elections still running (S8.11)."""
    flagged, elections = [], []
    for f in books.filers(s, book):
        if f.acceptedAt is None:
            continue
        u = s.get(User, f.userId)
        sp = gifts.spending(s, u.id, book.year)
        for p, amount, limit in sp.flagged:
            flagged.append(GiftTax(u.displayName, p.name, amount, limit))
        for a in s.scalars(
            select(Account).where(
                Account.ownerId == u.id, Account.type == "529", Account.deleted == false()
            )
        ):
            for r in education.contributions(s, a):
                if r.fiveYear and r.date.year <= book.year <= r.date.year + 4:
                    year_n = book.year - r.date.year + 1
                    elections.append(
                        f"{r.name}'s {r.date.year} five-year election to {a.name}: "
                        f"year {year_n} of 5, {r.amount / 5:,.0f} a year"
                    )
    return flagged, elections


@dataclass
class LoanRow:
    account: str
    kind: str
    interest: Decimal
    pmi: Decimal
    propertyTax: Decimal
    securedBy: str | None


def loans_panel(s: Session, book: TaxBook) -> list[LoanRow]:
    out = []
    for a in books.counted(s, book).accounts:
        if a.type not in ("mortgage", "heloc", "student-loan"):
            continue
        payments, _ = loans.history(s, a)
        mine = [p for p in payments if p.date.year == book.year]
        row = loans.loan_of(s, a)
        secured = None
        if row is not None and row.securedById:
            it = s.get(Item, row.securedById)
            secured = it.name if it else None
        out.append(
            LoanRow(
                a.name,
                "1098-E" if a.type == "student-loan" else "1098",
                sum((p.interest for p in mine), ZERO),
                sum((p.pmi for p in mine), ZERO),
                sum((p.escrowTax for p in mine), ZERO),
                secured,
            )
        )
    return out


@dataclass
class Residence:
    name: str
    sold: dt.date
    gain: Decimal
    yearsOwned: float


def residences(s: Session, book: TaxBook) -> list[Residence]:
    """A sold primary residence: its gain and the years owned (S8.13); the exclusion is the
    preparer's to apply."""
    first, last = _span(book.year)
    out = []
    for a in books.counted(s, book).accounts:
        if a.type != "real-estate":
            continue
        for it in s.scalars(
            select(Item).where(
                Item.accountId == a.id,
                Item.deleted == false(),
                Item.primaryResidence,
                Item.soldOn >= first,
                Item.soldOn <= last,
            )
        ):
            g = assets.gain(it, assets.details(s, [it])[it.id]) or ZERO
            out.append(
                Residence(
                    it.name, it.soldOn, g, round((it.soldOn - it.acquiredOn).days / 365.25, 1)
                )
            )
    return out


# ---------- Missing or doubtful data (S8.4) ----------


@dataclass
class Issue:
    kind: str
    text: str
    link: str | None = None


def issues(s: Session, book: TaxBook, rows: list[Row]) -> list[Issue]:
    out = []
    counted = books.counted(s, book)
    for a in counted.leftOut:
        out.append(Issue("left-out", f"{a.name} is left out of this tax book."))
    for a in _taxable(counted.accounts):
        if not atypes.investing(a.type):
            continue
        led = repo.load(s, a)
        rp = led.replay()
        for p in rp.problems:
            inst = s.get(Instrument, p.instrumentId)
            if p.kind == "sale-without-lot" and p.date.year == book.year:
                out.append(
                    Issue(
                        p.kind,
                        f"{a.name}: {inst.symbol} sold on {p.date:%b %-d} without a lot to match",
                        f"/ui/accounts/{a.id}/holdings",
                    )
                )
        for lot in rp.open:
            if lot.basis is None:
                inst = s.get(Instrument, lot.instrumentId)
                out.append(
                    Issue(
                        "basis-missing",
                        f"{a.name}: a lot of {inst.symbol} has no cost basis",
                        f"/ui/accounts/{a.id}/holdings",
                    )
                )
    for r in rows:
        if r.basis is None:
            out.append(
                Issue(
                    "sale-basis",
                    f"{r.account}: the sale of {r.description} on {r.sold:%b %-d} has no basis",
                )
            )
    # Transfers between users' accounts carry a gift's basis over (S8.4).
    ids = {a.id: a for a in counted.accounts}
    first, last = _span(book.year)
    for t in s.scalars(
        select(Transaction).where(
            Transaction.accountId.in_(list(ids)),
            Transaction.deleted == false(),
            Transaction.kind == "transfer-in",
            Transaction.date >= first,
            Transaction.date <= last,
            Transaction.transferId.is_not(None),
        )
    ):
        other = s.get(Transaction, t.transferId)
        oa = s.get(Account, other.accountId) if other else None
        if oa is not None and oa.ownerId != ids[t.accountId].ownerId:
            out.append(
                Issue(
                    "gift-basis",
                    f"{ids[t.accountId].name}: shares from {oa.name} on {t.date:%b %-d} keep "
                    "the giver's basis",
                )
            )
    return out


def spouse_accounts(s: Session, book: TaxBook) -> list[Account]:
    """For wash sales: the filers' spouses' accounts, when filing separately (S3.8)."""
    who = {f.userId for f in books.filers(s, book)}
    out = []
    for uid in who:
        u = s.get(User, uid)
        if u.spouseId and u.spouseId not in who:
            out += list(
                s.scalars(
                    select(Account).where(Account.ownerId == u.spouseId, Account.deleted == false())
                )
            )
    return out
