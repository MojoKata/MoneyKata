"""A user's categorisation and payee rules (requirements S2.7): loaded in order, applied to
transactions on import and on demand, and to the merchant a receipt names."""

import json

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from ... import clock
from ...ledger import rules as match
from ..entities.accounts import Category, Rule, Transaction, TransactionTag


def of_user(s: Session, user_id: str) -> list[Rule]:
    return list(
        s.scalars(
            select(Rule)
            .where(Rule.ownerId == user_id, Rule.deleted == false())
            .order_by(Rule.position, Rule.createdAt)
        )
    )


class Rules:
    """A user's rules, compiled once for a batch of transactions."""

    def __init__(self, s: Session, user_id: str):
        self.s, self.user_id = s, user_id
        self.rules = of_user(s, user_id)
        self.matchers = []
        live = []
        for r in self.rules:
            try:
                self.matchers.append(match.matcher(r))
                live.append(r)
            except match.Invalid:
                continue  # kept before the checks of today; it matches nothing
        self.rules = live
        self._cats = {
            c.id
            for c in s.scalars(
                select(Category).where(
                    Category.id.in_([r.categoryId for r in live if r.categoryId]),
                    Category.deleted == false(),
                )
            )
        }

    def __bool__(self) -> bool:
        return bool(self.rules)

    def first(self, payee: str | None, amount, account_id: str) -> Rule | None:
        return match.first_match(self.rules, self.matchers, payee, amount, account_id)

    def apply(self, t: Transaction, only_uncategorised: bool = True) -> bool:
        """The first matching rule's settings on a bank transaction that isn't a transfer:
        its category where there is none, the payee shown, and tags. True when it changed."""
        if t.instrumentId or t.transferId or t.deleted:
            return False
        if only_uncategorised and t.categoryId:
            return False
        rule = self.first(t.payeeRaw or t.payee, t.amount, t.accountId)
        if rule is None:
            return False
        changed = False
        if rule.categoryId in self._cats and t.categoryId is None and not self._split(t):
            t.categoryId, changed = rule.categoryId, True
        if rule.payee and t.payee != rule.payee:
            t.payee, changed = rule.payee, True
        for tag in json.loads(rule.tags or "[]"):
            changed = self._tag(t, tag) or changed
        return changed

    def rename(self, payee: str | None) -> str | None:
        """A payee as the rules show it: renamed by the first rule that matches it alone, on
        its text, and that renames (a receipt's merchant, S9.8.2.5.3)."""
        if not payee:
            return payee
        for rule, m in zip(self.rules, self.matchers, strict=True):
            if rule.payee and match.matches(
                match.Matcher(m.payeeMatch, _regex=m._regex), payee, 0, ""
            ):
                return rule.payee
        return payee

    def _split(self, t: Transaction) -> bool:
        from ..entities.accounts import Split

        return (
            self.s.scalars(
                select(Split.id).where(Split.transactionId == t.id, Split.deleted == false())
            ).first()
            is not None
        )

    def _tag(self, t: Transaction, tag: str) -> bool:
        row = self.s.get(TransactionTag, (t.id, self.user_id, tag))
        if row is not None and not row.deleted:
            return False
        if row is not None:
            row.restore()
        else:
            self.s.add(
                TransactionTag(
                    transactionId=t.id, userId=self.user_id, tag=tag, createdAt=clock.now()
                )
            )
        return True
