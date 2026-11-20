"""Money is integer paise. This module is the only place amounts become text.

Rules (ARCHITECTURE.md §6):
- Indian grouping (₹1,23,456), Western digits in every language, ASCII "-" for negatives.
- Half-up rounding everywhere (on the magnitude, so -₹1.50 rounds to -₹2).
- Spoken: under ₹1,000 exact to the rupee; under ₹1 lakh to the nearest ₹100; then lakh / crore.
"""

from __future__ import annotations

from typing import Final, TypedDict

RUPEE: Final = "₹"
PAISE_PER_RUPEE: Final = 100
LAKH_PAISE: Final = 1_00_000 * PAISE_PER_RUPEE
CRORE_PAISE: Final = 1_00_00_000 * PAISE_PER_RUPEE

LANGS: Final = ("en", "hi", "ta")

_UNIT_WORDS: Final[dict[str, dict[str, str]]] = {
    "en": {"lakh": "lakh", "crore": "crore"},
    "hi": {"lakh": "लाख", "crore": "करोड़"},
    "ta": {"lakh": "லட்சம்", "crore": "கோடி"},
}


class MoneyDict(TypedDict):
    paise: int
    display: str
    exact: str
    spoken: str


def div_half_up(n: int, d: int) -> int:
    """Integer division rounding half-up on the magnitude. d must be positive."""
    if d <= 0:
        raise ValueError("divisor must be positive")
    sign = -1 if n < 0 else 1
    return sign * ((abs(n) * 2 + d) // (2 * d))


def group_indian(n: int) -> str:
    """12345678 -> '1,23,45,678' (no sign handling: pass a non-negative int)."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def _sign(paise: int) -> str:
    return "-" if paise < 0 else ""


def display(paise: int) -> str:
    """Whole rupees, half-up: 12345650 -> '₹1,23,457'."""
    rupees = div_half_up(abs(paise), PAISE_PER_RUPEE)
    sign = "-" if paise < 0 and rupees != 0 else ""
    return f"{sign}{RUPEE}{group_indian(rupees)}"


def exact(paise: int) -> str:
    """Rupees and paise, always two decimals: 12345650 -> '₹1,23,456.50'."""
    a = abs(paise)
    return f"{_sign(paise)}{RUPEE}{group_indian(a // PAISE_PER_RUPEE)}.{a % PAISE_PER_RUPEE:02d}"


def _trim_decimal(hundredths: int) -> str:
    """125 -> '1.25', 120 -> '1.2', 100 -> '1'."""
    whole, frac = divmod(hundredths, 100)
    if frac == 0:
        return str(whole)
    if frac % 10 == 0:
        return f"{whole}.{frac // 10}"
    return f"{whole}.{frac:02d}"


def spoken(paise: int, lang: str = "en") -> str:
    """Ready-to-speak amount in the user's language (digits stay Western)."""
    words = _UNIT_WORDS.get(lang, _UNIT_WORDS["en"])
    a = abs(paise)
    sign = _sign(paise)
    rupees = div_half_up(a, PAISE_PER_RUPEE)
    if rupees < 1000:
        # "exact" for speech means to the rupee: nobody says paise aloud
        return f"{sign if rupees else ''}{RUPEE}{rupees}"
    if a < LAKH_PAISE:
        hundreds = div_half_up(a, 100 * PAISE_PER_RUPEE)
        rounded = hundreds * 100
        if rounded < 1_00_000:
            return f"{sign}{RUPEE}{group_indian(rounded)}"
        a = rounded * PAISE_PER_RUPEE  # rounded up into lakh territory
    if a < CRORE_PAISE:
        h = div_half_up(a, LAKH_PAISE // 100)  # hundredths of a lakh
        if h < 100 * 100:
            return f"{sign}{RUPEE}{_trim_decimal(h)} {words['lakh']}"
        a = h * (LAKH_PAISE // 100)
    h = div_half_up(a, CRORE_PAISE // 100)
    return f"{sign}{RUPEE}{_trim_decimal(h)} {words['crore']}"


def spoken_rupees(paise: int) -> int:
    """The rupee value `spoken()` stands for after its rounding (used by the guardrail)."""
    a = abs(paise)
    sign = -1 if paise < 0 else 1
    if a < 1000 * PAISE_PER_RUPEE:
        return sign * div_half_up(a, PAISE_PER_RUPEE)
    if a < LAKH_PAISE:
        return sign * div_half_up(a, 100 * PAISE_PER_RUPEE) * 100
    if a < CRORE_PAISE:
        return sign * div_half_up(a, LAKH_PAISE // 100) * 1000
    return sign * div_half_up(a, CRORE_PAISE // 100) * 1_00_000


def money(paise: int, lang: str = "en") -> MoneyDict:
    """The `Money` object every API amount uses."""
    return {"paise": paise, "display": display(paise), "exact": exact(paise), "spoken": spoken(paise, lang)}


def pct_half_up(part: int, whole: int) -> int:
    """Whole percent, half-up. 0 when `whole` is 0."""
    if whole <= 0:
        return 0
    return div_half_up(part * 100, whole)
