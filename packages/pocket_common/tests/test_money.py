import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from pocket_common import money

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "money_format.json"


def test_hand_checked_anchors() -> None:
    # Written by hand from ARCHITECTURE.md §6, independent of the fixture generator.
    assert money.display(12345600) == "₹1,23,456"
    assert money.display(12345650) == "₹1,23,457"  # half-up
    assert money.display(-123400) == "-₹1,234"
    assert money.display(49) == "₹0"
    assert money.display(-49) == "₹0"  # never "-₹0"
    assert money.exact(12345650) == "₹1,23,456.50"
    assert money.exact(34900) == "₹349.00"
    assert money.spoken(38200) == "₹382"
    assert money.spoken(840000) == "₹8,400"
    assert money.spoken(843900) == "₹8,400"  # nearest ₹100
    assert money.spoken(845000) == "₹8,500"  # half-up
    assert money.spoken(12000000) == "₹1.2 lakh"
    assert money.spoken(1050000000) == "₹1.05 crore"
    assert money.spoken(12000000, "hi") == "₹1.2 लाख"
    assert money.spoken(1050000000, "ta") == "₹1.05 கோடி"
    assert money.spoken(9996000) == "₹1 lakh"  # rounding up crosses into lakh
    assert money.group_indian(12345678) == "1,23,45,678"


def test_shared_fixtures_match() -> None:
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert len(cases) == 100
    for c in cases:
        assert money.display(c["paise"]) == c["display"]
        assert money.exact(c["paise"]) == c["exact"]
        for lang, expected in c["spoken"].items():
            assert money.spoken(c["paise"], lang) == expected


def test_money_object_shape() -> None:
    m = money.money(840000, "en")
    assert m == {"paise": 840000, "display": "₹8,400", "exact": "₹8,400.00", "spoken": "₹8,400"}


@given(st.integers(min_value=-(10**13), max_value=10**13))
def test_display_never_loses_more_than_half_a_rupee(paise: int) -> None:
    shown = int(money.display(paise).replace("₹", "").replace(",", ""))
    assert abs(shown * 100 - paise) <= 50


@given(st.integers(min_value=0, max_value=10**13))
def test_exact_round_trips(paise: int) -> None:
    text = money.exact(paise).replace("₹", "").replace(",", "")
    rupees, frac = text.split(".")
    assert int(rupees) * 100 + int(frac) == paise


@given(st.integers(min_value=0, max_value=10**13))
def test_spoken_rounding_is_bounded(paise: int) -> None:
    # What the mascot says is the ledger value rounded to: the rupee, ₹100, 0.01 lakh, 0.01 crore.
    # (The guardrail accepts exactly this rounding, plus anything within 2%.)
    off = abs(money.spoken_rupees(paise) * 100 - paise)
    if paise < 1000 * 100:
        assert off <= 50
    elif paise < money.LAKH_PAISE:
        assert off <= 50 * 100
    elif paise < money.CRORE_PAISE:
        assert off <= 500 * 100
    else:
        assert off <= 50_000 * 100


@given(st.integers(min_value=-(10**12), max_value=10**12), st.integers(min_value=1, max_value=10**6))
def test_div_half_up_is_nearest(n: int, d: int) -> None:
    q = money.div_half_up(n, d)
    assert abs(q * d - n) * 2 <= d
