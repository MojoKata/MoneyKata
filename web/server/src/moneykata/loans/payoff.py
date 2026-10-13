"""The payoff planner (requirements S6.10): a plan's overpayments against the schedule, a recast
after its lump sums, the same money invested instead, and whether the plan being followed is
ahead or behind."""

import dataclasses
import datetime as dt
import math
from dataclasses import dataclass, field
from decimal import Decimal

from . import ZERO, Payment, Row, Terms, add_months, cents, schedule


@dataclass
class Plan:
    monthly: Decimal = ZERO  # extra with every payment
    monthlyFrom: dt.date | None = None
    monthlyUntil: dt.date | None = None
    yearly: Decimal = ZERO  # extra once a year, with the payment in yearlyMonth
    yearlyMonth: int = 12
    lumps: list[tuple[dt.date, Decimal]] = field(default_factory=list)  # with the next payment
    biweekly: bool = False  # 26 half-payments a year: a twelfth of a payment more each month
    roundTo: Decimal = ZERO  # each payment, escrow included, rounded up to a multiple of this
    recast: bool = False  # after each lump sum, also show the loan recast instead of shortened
    recastFee: Decimal = ZERO
    investClass: str = "usStocks"  # the asset class the money is invested in, for comparison


@dataclass
class Outcome:
    payoffDate: dt.date | None
    months: int  # payments ahead
    interest: Decimal  # interest ahead
    paid: Decimal  # everything paid ahead: principal, interest, escrow, PMI, fees
    payment: Decimal  # principal and interest of the next payment
    paymentAfter: Decimal  # and after the first lump sum (lower when recast)
    fees: Decimal
    rows: list[Row]


@dataclass
class Invested:
    rate: float  # yearly %
    contributed: Decimal
    value: Decimal  # at the plan's payoff date


@dataclass
class Result:
    schedule: Outcome
    plan: Outcome
    recast: Outcome | None
    invested: Invested


class _Extras:
    """The plan's overpayment on each payment day, in order."""

    def __init__(self, plan: Plan, escrow: Decimal) -> None:
        self.plan = plan
        self.escrow = escrow
        self.lumps = sorted(plan.lumps)

    def __call__(self, day: dt.date, pi: Decimal) -> Decimal:
        p = self.plan
        extra = ZERO
        if (
            p.monthly
            and (p.monthlyFrom is None or day >= p.monthlyFrom)
            and (p.monthlyUntil is None or day <= p.monthlyUntil)
        ):
            extra += p.monthly
        if p.yearly and day.month == p.yearlyMonth:
            extra += p.yearly
        while self.lumps and self.lumps[0][0] <= day:
            extra += self.lumps.pop(0)[1]
        if p.biweekly:
            extra += cents(pi / 12)
        if p.roundTo > 0:
            total = pi + self.escrow + extra
            up = Decimal(math.ceil(total / p.roundTo)) * p.roundTo
            extra += up - total
        return extra


def lump_days(t: Terms, plan: Plan, ahead: list[Row]) -> list[dt.date]:
    """The payment day each lump sum goes with: the first on or after it."""
    days = [r.date for r in ahead]
    out = []
    for when, _ in plan.lumps:
        on = next((d for d in days if d >= when), None)
        if on is not None:
            out.append(on)
    return out


def _outcome(rows: list[Row], fees: Decimal, after: dt.date | None) -> Outcome:
    ahead = [r for r in rows if not r.past]
    pi = [r.principal + r.interest - r.overpayment for r in ahead]
    later = [r.principal + r.interest - r.overpayment for r in ahead if after and r.date > after]
    return Outcome(
        payoffDate=ahead[-1].date if ahead else None,
        months=len(ahead),
        interest=sum((r.interest for r in ahead), ZERO),
        paid=sum((r.payment for r in ahead), ZERO) + fees,
        payment=pi[0] if pi else ZERO,
        paymentAfter=later[0] if later else (pi[0] if pi else ZERO),
        fees=fees,
        rows=rows,
    )


def plan_outcomes(
    t: Terms,
    payments: list[Payment],
    draws,
    today: dt.date,
    plan: Plan,
    expected_return: float,
) -> Result:
    base_rows = schedule(t, payments, draws, today)
    base = _outcome(base_rows, ZERO, None)
    lumps = lump_days(t, plan, [r for r in base_rows if not r.past])
    first_lump = min(lumps) if lumps else None
    planned = _outcome(
        schedule(t, payments, draws, today, _Extras(plan, t.escrow + t.pmi)), ZERO, first_lump
    )
    recast = None
    if plan.recast and lumps:
        recast_terms = dataclasses.replace(
            t, recasts=[*t.recasts, *[(d, plan.recastFee) for d in lumps]]
        )
        fees = plan.recastFee * len(lumps)
        recast = _outcome(
            schedule(recast_terms, payments, draws, today, _Extras(plan, t.escrow + t.pmi)),
            fees,
            first_lump,
        )
    # The same money invested on the days it would have been paid, until the plan's payoff.
    monthly = (1 + expected_return / 100) ** (1 / 12) - 1
    end = planned.payoffDate or today
    value, contributed = 0.0, ZERO
    for r in planned.rows:
        if r.past or not r.overpayment:
            continue
        months = (end.year - r.date.year) * 12 + end.month - r.date.month
        value += float(r.overpayment) * (1 + monthly) ** months
        contributed += r.overpayment
    return Result(
        schedule=base,
        plan=planned,
        recast=recast,
        invested=Invested(expected_return, contributed, cents(Decimal(str(value)))),
    )


def expected_extra(t: Terms, plan: Plan, since: dt.date, today: dt.date, pi: Decimal) -> Decimal:
    """What the plan has the borrower overpay on the payment days after `since` up to today."""
    extras = _Extras(
        dataclasses.replace(plan, lumps=[x for x in plan.lumps if x[0] > since]),
        t.escrow + t.pmi,
    )
    total = ZERO
    k = 1
    day = add_months(t.start, k)
    while day <= today:
        if day > since:
            total += extras(day, pi)
        k += 1
        day = add_months(t.start, k)
    return cents(total)
