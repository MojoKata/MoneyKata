"""Loans (requirements S1.9): a loan account's terms, its schedule and summary, payments
recorded or linked from a bank account and split by the schedule, and the servicer's balance
against the computed one."""

import datetime as dt
import json
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import false, or_, select

from .. import access, activity, clock, ids, loans
from ..errors import FieldError, Problem, refuse
from ..store.entities.accounts import Account, Anchor, Category, Loan, Split, Transaction
from .conventions import Model, Money
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", tags=["loans"])


class Reset(Model):
    date: dt.date
    rate: Money


class Recast(Model):
    date: dt.date
    fee: Money = Decimal(0)


class TermsIn(Model):
    principal: Money
    startDate: dt.date
    termMonths: int
    rate: Money
    method: str = "amortized"
    payment: Money | None = None
    escrowTax: Money | None = None
    escrowInsurance: Money | None = None
    pmi: Money | None = None
    drawMonths: int | None = None
    resets: list[Reset] = Field(default_factory=list)
    recasts: list[Recast] = Field(default_factory=list)
    originalValue: Money | None = None


class ResetView(Model):
    date: dt.date
    rate: Money


class RecastView(Model):
    date: dt.date
    fee: Money


class TermsOut(Model):
    # Its own models for the dated rows, so the contract has one schema for each direction.
    principal: Money
    startDate: dt.date
    termMonths: int
    rate: Money
    method: str
    payment: Money | None
    escrowTax: Money | None
    escrowInsurance: Money | None
    pmi: Money | None
    drawMonths: int | None
    resets: list[ResetView]
    recasts: list[RecastView]
    originalValue: Money | None
    computedPayment: Money
    version: int


class RowOut(Model):
    date: dt.date
    payment: Money
    principal: Money
    interest: Money
    escrow: Money
    pmi: Money
    balance: Money
    past: bool
    overpayment: Money


class ServicerCheck(Model):
    date: dt.date
    servicer: Money
    computed: Money
    difference: Money


class LoanView(Model):
    terms: TermsOut | None
    balance: Money
    rate: Money
    payment: Money
    total: Money
    nextDate: dt.date | None
    payoffDate: dt.date | None
    originalPayoff: dt.date | None
    interestPaid: Money
    interestAhead: Money
    principalThisYear: Money
    overpaid: Money
    rows: list[RowOut]
    servicer: ServicerCheck | None
    canWrite: bool


class PaymentIn(Model):
    date: dt.date
    amount: Money
    fromAccountId: str | None = None  # a bank account: its half of the transfer is made too
    transactionId: str | None = None  # or an existing bank transaction to link
    # A split typed from the servicer's statement; else the schedule's.
    principal: Money | None = None
    interest: Money | None = None
    escrowTax: Money | None = None
    escrowInsurance: Money | None = None
    pmi: Money | None = None
    fees: Money | None = None


class SplitOut(Model):
    principal: Money
    interest: Money
    escrowTax: Money
    escrowInsurance: Money
    pmi: Money
    fees: Money
    overpayment: Money


class Candidate(Model):
    transactionId: str
    accountName: str
    date: dt.date
    amount: Money
    payee: str | None


def _account(s, c: Caller, account_id: str, need: str = "read") -> tuple[Account, str]:
    a, lvl = access.account(s, c.id, account_id, need)
    if not loans.is_loan(a.type):
        raise Problem(409, "not-a-loan", "This account is not a loan.")
    return a, lvl


def _terms_out(row: Loan) -> TermsOut:
    t = loans.terms_of(row)
    return TermsOut(
        principal=row.principal,
        startDate=row.startDate,
        termMonths=row.termMonths,
        rate=row.rate,
        method=row.method,
        payment=row.payment,
        escrowTax=row.escrowTax,
        escrowInsurance=row.escrowInsurance,
        pmi=row.pmi,
        drawMonths=row.drawMonths,
        resets=[ResetView(date=d, rate=r) for d, r in t.resets],
        recasts=[RecastView(date=d, fee=f) for d, f in t.recasts],
        originalValue=row.originalValue,
        computedPayment=loans.scheduled_payment(t),
        version=row.version,
    )


def view(s, a: Account, level: str) -> LoanView:
    row = loans.loan_of(s, a)
    today = clock.today()
    if row is None:
        return LoanView(
            terms=None,
            balance=Decimal(0),
            rate=Decimal(0),
            payment=Decimal(0),
            total=Decimal(0),
            nextDate=None,
            payoffDate=None,
            originalPayoff=None,
            interestPaid=Decimal(0),
            interestAhead=Decimal(0),
            principalThisYear=Decimal(0),
            overpaid=Decimal(0),
            rows=[],
            servicer=None,
            canWrite=level in ("owner", "write"),
        )
    terms = loans.terms_of(row)
    payments, draws = loans.history(s, a)
    sm, rows = loans.summary(terms, payments, draws, today)
    anchor = s.scalars(
        select(Anchor)
        .where(Anchor.accountId == a.id, Anchor.deleted == false(), Anchor.source == "typed")
        .order_by(Anchor.date.desc())
    ).first()
    servicer = None
    if anchor is not None:
        computed = loans.balance_on(terms, payments, draws, anchor.date)
        servicer = ServicerCheck(
            date=anchor.date,
            servicer=-anchor.balance,
            computed=computed,
            difference=-anchor.balance - computed,
        )
    return LoanView(
        terms=_terms_out(row),
        balance=sm.balance,
        rate=sm.rate,
        payment=sm.payment,
        total=sm.total,
        nextDate=sm.nextDate,
        payoffDate=sm.payoffDate,
        originalPayoff=sm.originalPayoff,
        interestPaid=sm.interestPaid,
        interestAhead=sm.interestAhead,
        principalThisYear=sm.principalThisYear,
        overpaid=sm.overpaid,
        rows=[RowOut(**r.__dict__) for r in rows],
        servicer=servicer,
        canWrite=level in ("owner", "write"),
    )


def _check(body: TermsIn) -> list[FieldError]:
    e = []
    if body.principal < 0:
        e.append(FieldError("principal", "principal-invalid", "Zero or more."))
    if not 1 <= body.termMonths <= 600:
        e.append(FieldError("termMonths", "term-invalid", "Between 1 and 600 months."))
    if not 0 <= body.rate <= 40:
        e.append(FieldError("rate", "rate-invalid", "Between 0% and 40%."))
    if body.method not in ("amortized", "daily"):
        e.append(FieldError("method", "method-invalid", "Monthly or daily."))
    if body.drawMonths is not None and not 0 <= body.drawMonths < body.termMonths:
        e.append(FieldError("drawMonths", "draw-invalid", "Shorter than the term."))
    for f in ("payment", "escrowTax", "escrowInsurance", "pmi", "originalValue"):
        v = getattr(body, f)
        if v is not None and v < 0:
            e.append(FieldError(f, "amount-invalid", "Zero or more."))
    return e


@router.get("/accounts/{account_id}/loan", response_model=LoanView)
def get_loan(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, lvl = _account(s, c, account_id)
        return view(s, a, lvl)


@router.put("/accounts/{account_id}/loan", response_model=LoanView)
def put_terms(account_id: str, body: TermsIn, request: Request, c: Caller = Depends(caller)):
    """The terms, set when the loan is made and corrected later (an ARM's resets, a recast)."""
    errors = _check(body)
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        row = loans.loan_of(s, a)
        values = {
            "principal": body.principal,
            "startDate": body.startDate,
            "termMonths": body.termMonths,
            "rate": body.rate,
            "method": body.method,
            "payment": body.payment,
            "escrowTax": body.escrowTax,
            "escrowInsurance": body.escrowInsurance,
            "pmi": body.pmi,
            "drawMonths": body.drawMonths,
            "resets": json.dumps(
                [{"date": r.date.isoformat(), "rate": str(r.rate)} for r in body.resets]
            ),
            "recasts": json.dumps(
                [{"date": r.date.isoformat(), "fee": str(r.fee)} for r in body.recasts]
            ),
            "originalValue": body.originalValue,
        }
        if row is None:
            s.add(Loan(id=ids.new_id("Loan"), accountId=a.id, **values))
        else:
            for k, v in values.items():
                setattr(row, k, v)
            row.updatedAt = clock.now()
        activity.record(
            s,
            "account.updated",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
            detail={"fields": ["terms"]},
        )
        s.flush()
        return view(s, a, lvl)


def _categories(s) -> dict[str, str]:
    keys = set(loans.PARTS.values())
    return {c.builtIn: c.id for c in s.scalars(select(Category).where(Category.builtIn.in_(keys)))}


@router.post("/accounts/{account_id}/loan/split", response_model=SplitOut)
def suggest_split(account_id: str, body: PaymentIn, request: Request, c: Caller = Depends(caller)):
    """How the schedule would split a payment of this amount on this day."""
    with server(request).db.read() as s:
        a, _ = _account(s, c, account_id)
        row = loans.loan_of(s, a)
        if row is None:
            raise Problem(409, "no-terms", "Set the loan's terms first.")
        payments, draws = loans.history(s, a)
        p = loans.split_for(loans.terms_of(row), payments, draws, body.date, body.amount)
        return SplitOut(
            principal=p.principal,
            interest=p.interest,
            escrowTax=p.escrowTax,
            escrowInsurance=p.escrowInsurance,
            pmi=p.pmi,
            fees=p.fees,
            overpayment=p.overpayment,
        )


@router.post("/accounts/{account_id}/loan/payments", response_model=LoanView, status_code=201)
def add_payment(account_id: str, body: PaymentIn, request: Request, c: Caller = Depends(caller)):
    """A payment on the loan, split into its parts. With a bank account, its half of the
    transfer is made as well; with a bank transaction, that one is linked (S1.9.3)."""
    if body.amount <= 0:
        raise refuse("amount", "amount-invalid", "A payment is more than zero.")
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        row = loans.loan_of(s, a)
        if row is None:
            raise Problem(409, "no-terms", "Set the loan's terms first.")
        payments, draws = loans.history(s, a)
        p = loans.split_for(loans.terms_of(row), payments, draws, body.date, body.amount)
        typed = [
            f
            for f in ("principal", "interest", "escrowTax", "escrowInsurance", "pmi", "fees")
            if getattr(body, f) is not None
        ]
        if typed:
            for f in ("principal", "interest", "escrowTax", "escrowInsurance", "pmi", "fees"):
                setattr(p, f, getattr(body, f) or Decimal(0))
            parts = p.principal + p.interest + p.escrowTax + p.escrowInsurance + p.pmi + p.fees
            if parts != body.amount:
                raise refuse(
                    "principal",
                    "split-does-not-add-up",
                    f"The parts come to {parts:,.2f}, not {body.amount:,.2f}.",
                )
        other = None
        if body.transactionId:
            other = s.get(Transaction, body.transactionId)
            if other is None or other.deleted or other.transferId:
                raise refuse("transactionId", "not-found", "That bank transaction isn't free.")
            access.account(s, c.id, other.accountId, "write")
            if other.amount != -body.amount:
                raise refuse("amount", "amount-mismatch", "The amounts differ.")
        elif body.fromAccountId:
            access.account(s, c.id, body.fromAccountId, "write")
            other = Transaction(
                id=ids.new_id("Txn"),
                accountId=body.fromAccountId,
                date=body.date,
                kind="transfer",
                amount=-body.amount,
                payee=a.name,
                createdById=c.id,
            )
            s.add(other)
        txn = Transaction(
            id=ids.new_id("Txn"),
            accountId=a.id,
            date=body.date,
            kind="transfer" if other else "deposit",
            amount=body.amount,
            payee="Payment",
            createdById=c.id,
        )
        s.add(txn)
        s.flush()
        if other is not None:
            txn.transferId, other.transferId = other.id, txn.id
        cats = _categories(s)
        for part, key in loans.PARTS.items():
            amount = getattr(p, part)
            if amount:
                s.add(
                    Split(
                        id=ids.new_id("Split"),
                        transactionId=txn.id,
                        amount=amount,
                        categoryId=cats.get(key),
                    )
                )
        activity.record(
            s,
            "loan.payment",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        s.flush()
        return view(s, a, lvl)


@router.get("/accounts/{account_id}/loan/candidates", response_model=list[Candidate])
def candidates(account_id: str, request: Request, c: Caller = Depends(caller)):
    """Bank transactions of the last 90 days that look like this loan's payment (within 2% of
    it, not yet a transfer, and not filed under some other category, as rent is), to link
    with one click."""
    with server(request).db.read() as s:
        a, _ = _account(s, c, account_id)
        row = loans.loan_of(s, a)
        if row is None:
            return []
        payments, draws = loans.history(s, a)
        sm, _ = loans.summary(loans.terms_of(row), payments, draws, clock.today())
        want = sm.total
        if not want:
            return []
        banks = [
            x
            for x, lvl in access.visible_accounts(s, c.id)
            if lvl in ("owner", "write") and not loans.is_loan(x.type) and x.id != a.id
        ]
        names = {x.id: x.name for x in banks}
        rows = s.scalars(
            select(Transaction).where(
                Transaction.accountId.in_(list(names)),
                Transaction.deleted == false(),
                Transaction.transferId.is_(None),
                Transaction.amount < 0,
                Transaction.date >= clock.today() - dt.timedelta(days=90),
                or_(
                    Transaction.categoryId.is_(None),
                    Transaction.categoryId == _categories(s).get("transfer.loan"),
                ),
            )
        ).all()
        out = []
        for t in rows:
            if abs(-t.amount - want) <= want * Decimal("0.02"):
                out.append(
                    Candidate(
                        transactionId=t.id,
                        accountName=names[t.accountId],
                        date=t.date,
                        amount=-t.amount,
                        payee=t.payee,
                    )
                )
        return sorted(out, key=lambda x: x.date, reverse=True)
