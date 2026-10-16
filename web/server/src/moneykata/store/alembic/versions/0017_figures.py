"""Figures (requirements S2.3, S3.4, S14.3):

- the lot method on every sale: a sale or transfer out made before the method was recorded on
  all of them takes the method its account has, so a later change of the account's method
  leaves it as it was;
- an assignment's or exercise's premium is folded into its stock trade as the account is
  replayed, so the stock lots and proceeds written before keep only the strike's cash and the
  deliverable's;
- money kept as decimal text is integer cents, as every other amount is: each table is rebuilt
  with the column as an integer, and each value written again in cents, rounded half to even.

Revision: 0017
Follows: 0016
"""

from decimal import ROUND_HALF_EVEN, Decimal

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

TO_CENTS = {
    "Donation": ("amount", "basis"),
    "EducationPlan": ("stateDeduction",),
    "Filing": ("resultAmount",),
    "Gift": ("cost",),
    "GiftPlan": ("giftBudget",),
    "GivingPlan": ("amount", "income"),
    "Improvement": ("amount",),
    "Item": ("closingCosts", "costBasis", "insuredValue", "proceeds", "saleFees"),
    "ItemValuation": ("value",),
    "Loan": ("escrowInsurance", "escrowTax", "originalValue", "payment", "pmi", "principal"),
    "Occasion": ("budget",),
    "OptionContract": ("deliverableCash",),
    "Organisation": ("pledge",),
    "Receipt": ("amount",),
    "Transaction": ("proceedsAdjustment",),
    "WashSale": ("disallowed",),
}
CENT = Decimal("0.01")


def rebuild(conn, name: str, edits: list[tuple[str, str]], drop: tuple[str, ...] = ()) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
    stored = [
        r[1]
        for r in conn.exec_driver_sql(f'PRAGMA table_xinfo("{name}")').fetchall()
        if r[6] == 0 and r[1] not in drop
    ]
    indexes = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (name,),
    ).fetchall()
    new = sql
    for old, replacement in edits:
        if new.count(old) != 1:
            raise RuntimeError(f"{name}: unexpected declarations")
        new = new.replace(old, replacement)
    head = f'CREATE TABLE "{name}" ('
    conn.exec_driver_sql(f'CREATE TABLE "_new_{name}" (' + new[len(head) :])
    listed = ", ".join(f'"{c}"' for c in stored)
    # The names come from sqlite_master, not from input.
    conn.exec_driver_sql(f'INSERT INTO "_new_{name}" ({listed}) SELECT {listed} FROM "{name}"')  # noqa: S608
    conn.exec_driver_sql(f'DROP TABLE "{name}"')
    conn.exec_driver_sql(f'ALTER TABLE "_new_{name}" RENAME TO "{name}"')
    for (index_sql,) in indexes:
        conn.exec_driver_sql(index_sql)


def _retype(conn, table: str, columns: tuple[str, ...], old: str, new: str) -> list:
    """The edits that declare each column with the new type: a name is quoted in the stored
    SQL only when it needs to be (`amount`, but `"costBasis"`)."""
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).scalar_one()
    edits = []
    for c in columns:
        forms = [f"\t{q} {old}" for q in (c, f'"{c}"') if sql.count(f"\t{q} {old}") == 1]
        if len(forms) != 1:
            raise RuntimeError(f"{table}.{c}: unexpected declaration")
        edits.append((forms[0], forms[0].replace(f" {old}", f" {new}")))
    return edits


def _cents(v) -> int | None:
    if v is None:
        return None
    return int(Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_EVEN) * 100)


def _text(cents: int | None) -> str | None:
    return None if cents is None else str((Decimal(cents) / 100).quantize(CENT))


def _lot_methods(conn) -> None:
    conn.exec_driver_sql(
        'UPDATE "Transaction" SET "lotMethod" = (SELECT a."lotMethod" FROM "Account" a '
        'WHERE a.id = "Transaction"."accountId") '
        "WHERE \"kind\" IN ('sell', 'transfer-out') AND \"lotMethod\" IS NULL"
    )


def _unfold_premiums(conn) -> None:
    """A stock trade made by an assignment or exercise keeps the strike's cash and the
    deliverable's, never the premium: a buy's lot costs its cash less the deliverable's share,
    a sale's proceeds are adjusted by the deliverable's share only."""
    ends = conn.exec_driver_sql(
        "SELECT id FROM \"Transaction\" WHERE kind IN ('assign', 'exercise')"
    ).fetchall()
    for (end,) in ends:
        legs = conn.exec_driver_sql(
            'SELECT id, kind, amount FROM "Transaction" WHERE "optionTransactionId" = ? '
            "AND kind IN ('buy', 'sell') ORDER BY \"createdAt\", id",
            (end,),
        ).fetchall()
        extra = sum(
            abs(a)
            for (a,) in conn.exec_driver_sql(
                'SELECT amount FROM "Transaction" WHERE "optionTransactionId" = ? '
                "AND kind IN ('deposit', 'withdrawal')",
                (end,),
            ).fetchall()
        )
        paid = sum(abs(x[2]) for x in legs)
        given = 0
        for i, (leg, kind, amount) in enumerate(legs):
            share = (
                extra - given
                if i == len(legs) - 1
                else int(
                    (Decimal(extra) * abs(amount) / paid).quantize(1, rounding=ROUND_HALF_EVEN)
                )
                if paid
                else 0
            )
            given += share
            if kind == "buy":
                conn.exec_driver_sql(
                    'UPDATE "Lot" SET "costBasis" = ? WHERE "transactionId" = ?',
                    (abs(amount) - share, leg),
                )
            else:
                conn.exec_driver_sql(
                    'UPDATE "Transaction" SET "proceedsAdjustment" = ? WHERE id = ?',
                    (_text(-share) if share else None, leg),
                )


def _to_cents(conn) -> None:
    for table, columns in TO_CENTS.items():
        quoted = ", ".join(f'"{c}"' for c in columns)
        rows = conn.exec_driver_sql(f'SELECT id, {quoted} FROM "{table}"').fetchall()  # noqa: S608
        rebuild(conn, table, _retype(conn, table, columns, "TEXT", "INTEGER"))
        sets = ", ".join(f'"{c}" = ?' for c in columns)
        for row in rows:
            conn.exec_driver_sql(
                f'UPDATE "{table}" SET {sets} WHERE id = ?',  # noqa: S608
                (*(_cents(v) for v in row[1:]), row[0]),
            )


def _to_text(conn) -> None:
    for table, columns in TO_CENTS.items():
        quoted = ", ".join(f'"{c}"' for c in columns)
        rows = conn.exec_driver_sql(f'SELECT id, {quoted} FROM "{table}"').fetchall()  # noqa: S608
        rebuild(conn, table, _retype(conn, table, columns, "INTEGER", "TEXT"))
        sets = ", ".join(f'"{c}" = ?' for c in columns)
        for row in rows:
            conn.exec_driver_sql(
                f'UPDATE "{table}" SET {sets} WHERE id = ?',  # noqa: S608
                (*(_text(v) for v in row[1:]), row[0]),
            )


def upgrade() -> None:
    conn = op.get_bind()
    _lot_methods(conn)
    _unfold_premiums(conn)
    _to_cents(conn)


def downgrade() -> None:
    # The methods recorded and the premiums left to the replay are what this release works
    # out; going back, only the columns' form is undone.
    _to_text(conn=op.get_bind())
