import uuid
from decimal import Decimal

import pytest

from moneykata import ids, money


def test_ids_have_the_schema_form_and_sort_by_time():
    made = [ids.new_id("Txn") for _ in range(5000)]
    assert made == sorted(made)
    assert len(set(made)) == len(made)
    for i in made[:50]:
        assert len(i) == len("Txn_") + 26
        assert ids.is_id(i, "Txn")
        assert ids.decode(i[4:]).version == 7


def test_encoding_matches_the_schema_example():
    u = uuid.UUID("0199d4b2-6f3a-7c21-9b4e-5a1d3c8e7f02")
    assert ids.encode(u) == "01k7ab4vstfggspkjt3my8wzr2"
    assert ids.decode("01k7ab4vstfggspkjt3my8wzr2") == u


@pytest.mark.parametrize(
    "bad",
    [
        "01K7AB4VSTFGGSPKJT3MY8WZR2",
        "01k7ab4vstfggspkjt3my8wzri",
        "01k7ab4vstfggspkjt3my8wzrl",
        "01k7ab4vstfggspkjt3my8wzro",
        "01k7ab4vstfggspkjt3my8wzru",
        "81k7ab4vstfggspkjt3my8wzr2",
        "01k7ab4vst",
    ],
)
def test_each_id_has_exactly_one_spelling(bad):
    with pytest.raises(ValueError):
        ids.decode(bad)


def test_amounts_refuse_floats_and_excess_places():
    assert money.parse("1234.50") == Decimal("1234.50")
    for bad in (1.5, True, None, "abc", "NaN", "Infinity"):
        with pytest.raises(money.AmountError):
            money.parse(bad)
    with pytest.raises(money.AmountError, match="2 decimal places"):
        money.parse("1.005", places=2)


def test_cents_round_half_even():
    assert money.to_cents(Decimal("0.125")) == 12
    assert money.to_cents(Decimal("0.135")) == 14
    assert money.cents_str(123450) == "1234.50"
    assert money.cents_str(-5) == "-0.05"
    assert money.quantity_str(Decimal("12.500000000000000000")) == "12.5"
    assert money.quantity_str(Decimal("1E+2")) == "100"
