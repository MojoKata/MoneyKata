"""Categorisation and payee rules (requirements S2.7): which rule a transaction matches, first
match wins, and what checking a rule's pattern refuses. No tables here: the rules and the
transactions come in as plain objects."""

import re
from dataclasses import dataclass, field
from decimal import Decimal

MAX_PATTERN = 200
MAX_TAGS = 10
# A repeat inside a repeated group, such as (a+)+ or (\w*)*: on a payee that nearly matches it
# backtracks for ever.
NESTED = re.compile(r"\((?:[^()\\]|\\.)*[+*}](?:[^()\\]|\\.)*\)\s*[+*{]")


class Invalid(ValueError):
    """A rule that can't be kept; the message says why, for its field."""


@dataclass(frozen=True)
class Matcher:
    payeeMatch: str
    amountMin: Decimal | None = None
    amountMax: Decimal | None = None
    direction: str = "any"  # any, in, out
    accountId: str | None = None
    _regex: re.Pattern | None = field(default=None, compare=False)


def compile_pattern(text: str) -> re.Pattern | None:
    """A rule's payee pattern: None for plain text, else its regular expression. Refused when
    it is empty, too long, doesn't compile or nests a repeat."""
    t = text.strip()
    if not t or len(t) > MAX_PATTERN:
        raise Invalid(f"Some text of the payee, at most {MAX_PATTERN} characters.")
    if not t.lower().startswith("re:"):
        return None
    body = t[3:].strip()
    if not body:
        raise Invalid("A regular expression after re:, such as re:^AMZN.")
    if NESTED.search(body):
        raise Invalid("A repeat inside a repeated group, such as (a+)+, is refused.")
    try:
        return re.compile(body, re.IGNORECASE)
    except re.error as e:
        raise Invalid(f"Not a regular expression: {e.msg}.") from None


def matcher(rule) -> Matcher:
    return Matcher(
        rule.payeeMatch,
        rule.amountMin,
        rule.amountMax,
        rule.direction,
        rule.accountId,
        compile_pattern(rule.payeeMatch),
    )


def matches(m: Matcher, payee: str | None, amount: Decimal, account_id: str) -> bool:
    if m.accountId and m.accountId != account_id:
        return False
    if (m.direction == "in" and amount <= 0) or (m.direction == "out" and amount >= 0):
        return False
    size = abs(amount)
    if m.amountMin is not None and size < m.amountMin:
        return False
    if m.amountMax is not None and size > m.amountMax:
        return False
    text = (payee or "")[:500]
    if m._regex is not None:
        return m._regex.search(text) is not None
    return m.payeeMatch.strip().lower() in text.lower()


def first_match(rules: list, matchers: list[Matcher], payee, amount, account_id):
    """The first rule, in order, that the transaction matches; None when none does."""
    for rule, m in zip(rules, matchers, strict=True):
        if matches(m, payee, amount, account_id):
            return rule
    return None
