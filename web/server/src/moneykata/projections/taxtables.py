"""The tax tables (requirements S16.11): per year, figures that ship with MoneyKata and are
updated with it, which an admin can correct in Settings › Tax tables if the IRS changes one
before an update. Projections take contribution limits and the bitcoin models' published
figures from here; taxes, 529s and giving take the rest as they are built.

Each figure has a kind, which says how it is checked and shown: money (dollars), percent,
number, or a list of numbers (the bitcoin models' parameters and targets).
"""

import json
from dataclasses import dataclass

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from .. import clock
from ..store.entities.projections import TaxFigure


@dataclass(frozen=True)
class Figure:
    key: str
    label: str
    kind: str  # money, percent, number, numbers
    group: str
    source: str


FIGURES = [
    Figure("iraLimit", "IRA contribution limit", "money", "Retirement", "IRS"),
    Figure("iraCatchUp", "IRA catch-up (50+)", "money", "Retirement", "IRS"),
    Figure("k401Deferral", "401(k) employee deferral", "money", "Retirement", "IRS"),
    Figure("k401CatchUp", "401(k) catch-up (50–59, 64+)", "money", "Retirement", "IRS"),
    Figure("k401CatchUp6063", "401(k) catch-up (60–63)", "money", "Retirement", "IRS"),
    Figure("hsaSelf", "HSA, self-only", "money", "Retirement", "IRS"),
    Figure("hsaFamily", "HSA, family", "money", "Retirement", "IRS"),
    Figure("rmdAge", "RMD starting age", "number", "Retirement", "IRS"),
    Figure("giftExclusion", "Annual gift exclusion", "money", "Gifts and giving", "IRS"),
    Figure("rothFrom529", "529 to Roth IRA, lifetime", "money", "Gifts and giving", "IRS"),
    Figure("qcdLimit", "QCD limit", "money", "Gifts and giving", "IRS"),
    Figure("collectablesRate", "Collectables rate (max)", "percent", "Taxes", "IRS"),
    # Metal spot from the trusts' share prices (S4.3): troy ounces each share holds, which
    # falls a little each year by the trust's fee.
    Figure("slvOzPerShare", "Silver per SLV share (troy oz)", "number", "Metal spot", "iShares"),
    Figure("ppltOzPerShare", "Platinum per PPLT share (troy oz)", "number", "Metal spot", "abrdn"),
    Figure("pallOzPerShare", "Palladium per PALL share (troy oz)", "number", "Metal spot", "abrdn"),
    Figure(
        "btcPowerLaw",
        "Bitcoin power law (A, n)",
        "numbers",
        "Bitcoin models",
        "Santostasi's fit: price = A × days since the genesis block ^ n",
    ),
    Figure(
        "btcLogRegression",
        "Bitcoin log regression (a, b)",
        "numbers",
        "Bitcoin models",
        "the rainbow chart's curve: log10(price) = a × ln(days) − b",
    ),
    Figure(
        "btcStockToFlow",
        "Bitcoin stock-to-flow (a, b)",
        "numbers",
        "Bitcoin models",
        "PlanB (2019): market value = e^a × SF^b",
    ),
    Figure(
        "btcSaylor2045",
        "Saylor 2045 (bear, base, bull)",
        "numbers",
        "Bitcoin models",
        "Michael Saylor, Bitcoin24 (2024)",
    ),
    Figure(
        "btcArk2030",
        "ARK 2030 (bear, base, bull)",
        "numbers",
        "Bitcoin models",
        "ARK Invest, Big Ideas (2025)",
    ),
]
BY_KEY = {f.key: f for f in FIGURES}

_BTC = {
    "btcPowerLaw": [1e-17, 5.8],
    "btcLogRegression": [2.66167155, 17.91837619],
    "btcStockToFlow": [14.6, 3.3],
    "btcSaylor2045": [3_000_000, 13_000_000, 49_000_000],
    "btcArk2030": [500_000, 1_200_000, 2_400_000],
}

SHIPPED: dict[int, dict] = {
    2025: {
        "iraLimit": 7000,
        "iraCatchUp": 1000,
        "k401Deferral": 23500,
        "k401CatchUp": 7500,
        "k401CatchUp6063": 11250,
        "hsaSelf": 4300,
        "hsaFamily": 8550,
        "rmdAge": 73,
        "giftExclusion": 19000,
        "rothFrom529": 35000,
        "qcdLimit": 108000,
        "collectablesRate": 28,
        "slvOzPerShare": 0.8634,
        "ppltOzPerShare": 0.0915,
        "pallOzPerShare": 0.0915,
        **_BTC,
    },
    2026: {
        "iraLimit": 7500,
        "iraCatchUp": 1100,
        "k401Deferral": 24500,
        "k401CatchUp": 8000,
        "k401CatchUp6063": 11250,
        "hsaSelf": 4400,
        "hsaFamily": 8750,
        "rmdAge": 73,
        "giftExclusion": 19000,
        "rothFrom529": 35000,
        "qcdLimit": 111000,
        "collectablesRate": 28,
        "slvOzPerShare": 0.8591,
        "ppltOzPerShare": 0.0909,
        "pallOzPerShare": 0.0909,
        **_BTC,
    },
}


def years() -> list[int]:
    return sorted(SHIPPED)


def _year(year: int) -> int:
    """A year the tables don't reach yet uses the latest one shipped."""
    known = years()
    return year if year in SHIPPED else (known[-1] if year > known[-1] else known[0])


def figures(s: Session, year: int | None = None) -> dict[str, object]:
    """A year's figures, with any admin's corrections."""
    y = _year(year or clock.today().year)
    out = dict(SHIPPED[y])
    for row in s.scalars(
        select(TaxFigure).where(TaxFigure.year == y, TaxFigure.deleted == false())
    ):
        if row.key in BY_KEY:
            out[row.key] = json.loads(row.value)
    return out


def corrected(s: Session, year: int) -> set[str]:
    return {
        r.key
        for r in s.scalars(
            select(TaxFigure).where(TaxFigure.year == year, TaxFigure.deleted == false())
        )
    }


class Invalid(ValueError):
    pass


def check(key: str, value) -> object:
    f = BY_KEY.get(key)
    if f is None:
        raise Invalid("there is no such figure")
    if f.kind == "numbers":
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)
        ):
            raise Invalid("numbers separated by commas")
        if len(value) != len(_BTC.get(key, value)):
            raise Invalid(f"{len(_BTC[key])} numbers")
        return value
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise Invalid("a number, zero or more")
    if f.kind == "percent" and value > 100:
        raise Invalid("a percentage up to 100")
    return value
