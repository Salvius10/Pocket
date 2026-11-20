"""Guard core: number check and advice check on mascot text. Pure functions, no I/O.

Used on every sentence of live output transcription and on written AI text. The live model
speaks directly, so this cannot pre-screen speech: it detects, and the agent then stops audio
and makes the mascot correct itself (ARCHITECTURE.md §9).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# ---------- numbers ----------
_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr|k|thousand|hundred|लाख|करोड़|हज़ार|हजार|லட்சம்|கோடி|ஆயிரம்)?", re.IGNORECASE)
_MULT = {
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000, "लाख": 100_000, "லட்சம்": 100_000,
    "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000, "करोड़": 10_000_000, "கோடி": 10_000_000,
    "k": 1_000, "thousand": 1_000, "हज़ार": 1_000, "हजार": 1_000, "ஆயிரம்": 1_000, "hundred": 100,
}
_EN_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
             "seventeen": 17, "eighteen": 18, "nineteen": 19}
_EN_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_EN_SCALES = {"hundred": 100, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "crore": 10_000_000, "crores": 10_000_000}
SMALL_OK = 31  # integers 0-31 (days, counts, dates) never need a ledger match


def normalise_digits(text: str) -> str:
    """Devanagari/Tamil digits -> Western, so one regex reads every language."""
    return "".join(str(unicodedata.digit(ch)) if unicodedata.category(ch) == "Nd" and not ch.isascii() else ch for ch in text)


def _english_word_numbers(text: str) -> list[float]:
    out: list[float] = []
    total = current = 0
    active = False
    for raw in re.findall(r"[a-zA-Z]+", text.lower()) + ["."]:
        if raw in _EN_UNITS or raw in _EN_TENS:
            current += _EN_UNITS.get(raw, 0) + _EN_TENS.get(raw, 0)
            active = True
        elif raw in _EN_SCALES and active:
            scale = _EN_SCALES[raw]
            if scale == 100:
                current *= 100
            else:
                total += max(current, 1) * scale
                current = 0
        elif raw == "and" and active:
            continue
        else:
            if active:
                out.append(float(total + current))
            total = current = 0
            active = False
    return out


def extract_numbers(text: str) -> list[float]:
    """Every number a sentence states: digits with Indian commas, lakh/crore words, English number words."""
    text = normalise_digits(text)
    out: list[float] = []
    for m in _NUM.finditer(text):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        out.append(value * _MULT.get(unit, 1))
    out.extend(_english_word_numbers(text))
    return out


def numbers_in(obj: Any) -> set[float]:
    """All numbers a tool result exposes, in rupees: `paise` fields, display strings and plain counts."""
    found: set[float] = set()

    def walk(o: Any, key: str = "") -> None:
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, dict):
            if isinstance(o.get("paise"), int) and "display" in o:
                p = abs(int(o["paise"]))
                found.add(p / 100)
                found.add(float(round(p / 100)))
                for s in (o.get("spoken"), o.get("display")):
                    if isinstance(s, str):
                        found.update(extract_numbers(s))
                return
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)):
            if key.endswith("_paise"):
                found.add(abs(o) / 100)
            elif key.endswith("_bps"):
                found.add(abs(o) / 100)
                found.add(round(abs(o) / 100, 1))
            else:
                found.add(abs(float(o)))
        elif isinstance(o, str):
            found.update(extract_numbers(o))

    walk(obj)
    return found


def number_allowed(value: float, allowed: set[float], tolerance: float = 0.02) -> bool:
    """Match within 2% (which also covers the spoken rounding). Small integers are always fine."""
    v = abs(value)
    if v <= SMALL_OK and float(v).is_integer():
        return True
    return any(abs(v - a) <= max(tolerance * a, 0.5) for a in allowed)


# A bare four-digit year ("by March 2027"). Never an amount: "₹2,000" and "2000 rupees" do not match.
_YEAR = re.compile(r"(?<![₹\d,.])\b((?:19|20)\d{2})\b(?![,.]\d)(?!\s*(?:rupees?|rs\b|रुपय|ரூபா|lakh|crore|लाख|करोड़|லட்ச|கோடி))", re.IGNORECASE)


def unknown_numbers(text: str, allowed: set[float]) -> list[float]:
    normalised = normalise_digits(text)
    years = {float(m.group(1)) for m in _YEAR.finditer(normalised)}
    return [n for n in extract_numbers(text) if n not in years and not number_allowed(n, allowed)]


# ---------- advice ----------
_SECURITY = (
    r"fund|funds|stock|stocks|share|shares|sip|etf|bond|bonds|gold|crypto|bitcoin|nifty|sensex|equity|smallcap|midcap|"
    r"mutual|ipo|scheme|फंड|शेयर|स्टॉक|सोना|एसआईपी|क्रिप्टो|म्यूचुअल|ஃபண்ட்|பங்கு|தங்கம்|எஸ்ஐபி|கிரிப்டோ|மியூச்சுவல்"
)
_ACTION = (
    r"buy|sell|invest in|switch|redeem|exit|book profit|start (?:a |an )?sip|put (?:your )?money (?:in|into)|move (?:your )?(?:sip|money) to|"
    r"go for|pick|खरीद|बेच|निवेश कर|स्विच|रिडीम|लगाइए|लगा दो|वाली?ंगु|வாங்கு|வாங்குங்கள்|வாங்கலாம்|விற்க|விற்றுவிடு|முதலீடு செய்|மாற்று|"
    r"vaangu|vaangunga|vaangalam|vithudu|podunga|potrunga|kharido|kharid lo|bech do|laga do"
)
_DIRECTIVE = (
    r"you should|you must|you need to|i recommend|i suggest|i advise|my advice|better to|best to|it's time to|now is (?:a |the )?(?:good|right|best) time|"
    r"don't miss|आपको .* चाहिए|मेरी सलाह|अभी .* सही समय|நீங்கள் .* வேண்டும்|என் ஆலோசனை|இப்போதே|pannunga|panniru|kandippa"
)
_PREDICT = (
    r"(?:market|markets|nifty|sensex|price|prices|stock|fund|gold|बाज़ार|बाजार|சந்தை)\b.{0,40}\b(?:will|is going to|going to|sure to|bound to|"
    r"बढ़ेगा|गिरेगा|ஏறும்|இறங்கும்|yerum|irangum)\b.{0,40}\b(?:rise|go up|fall|crash|double|grow|बढ़|गिर|ஏற|இறங்)"
)
_GUARANTEE = r"guaranteed? returns?|assured returns?|risk[- ]free returns?|can't lose|cannot lose|sure profit|पक्का मुनाफ़ा|गारंटीड रिटर्न|உறுதியான லாபம்"
_REFUSAL = (
    r"can't tell you|cannot tell you|can't recommend|cannot recommend|can't advise|i don't give|not able to suggest|won't tell you (?:to|what)|"
    r"नहीं बता सकत|सलाह नहीं दे|சொல்ல முடியாது|பரிந்துரைக்க முடியாது|ஆலோசனை தர"
)

_RE_ADVICE = re.compile(rf"(?:{_ACTION})\b.{{0,60}}(?:{_SECURITY})|(?:{_SECURITY}).{{0,60}}(?:{_ACTION})", re.IGNORECASE)
_RE_DIRECTIVE = re.compile(_DIRECTIVE, re.IGNORECASE)
_RE_PREDICT = re.compile(_PREDICT, re.IGNORECASE)
_RE_GUARANTEE = re.compile(_GUARANTEE, re.IGNORECASE)
_RE_REFUSAL = re.compile(_REFUSAL, re.IGNORECASE)
_RE_NEGATED = re.compile(r"\b(?:not|never|don't|do not|won't|cannot|can't|नहीं|மாட்டேன்|இல்லை|வேண்டாம்)\b", re.IGNORECASE)


@dataclass
class GuardResult:
    ok: bool = True
    kind: str | None = None  # advice | number_mismatch
    banned: str | None = None  # personal_security_pick | market_prediction_call_to_action | guaranteed_returns | number_not_in_ledger
    borderline: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


def check_advice(sentence: str) -> GuardResult:
    """Lexicon check: an action verb next to a security, said as an instruction to this user.

    Plain statements of the user's own numbers ("your funds are down ₹2,100") and refusals
    ("I can't tell you which fund to buy") pass. A hit with no directive is `borderline`,
    which the agent may send to MODEL_FLASH for a second opinion.
    """
    s = sentence.strip()
    if not s:
        return GuardResult()
    if _RE_GUARANTEE.search(s):
        return GuardResult(False, "advice", "guaranteed_returns", detail={"sentence": s})
    if _RE_PREDICT.search(s):
        return GuardResult(False, "advice", "market_prediction_call_to_action", detail={"sentence": s})
    hit = _RE_ADVICE.search(s)
    if hit is None:
        return GuardResult()
    if _RE_REFUSAL.search(s) or _RE_NEGATED.search(s[: hit.end() + 20]) and not _RE_DIRECTIVE.search(s):
        return GuardResult()
    if s.endswith("?") and not _RE_DIRECTIVE.search(s):
        return GuardResult()
    return GuardResult(False, "advice", "personal_security_pick", borderline=not _RE_DIRECTIVE.search(s), detail={"sentence": s})


def check_sentence(sentence: str, allowed: set[float]) -> GuardResult:
    advice = check_advice(sentence)
    if not advice.ok:
        return advice
    unknown = unknown_numbers(sentence, allowed)
    if unknown:
        return GuardResult(False, "number_mismatch", "number_not_in_ledger", detail={"sentence": sentence, "numbers": unknown})
    return GuardResult()


def check_written(text: str) -> GuardResult:
    """Written AI text (layout reasons, report summaries): no digits at all, and no advice."""
    if any(unicodedata.category(ch) == "Nd" for ch in text):
        return GuardResult(False, "number_mismatch", "number_not_in_ledger", detail={"reason": "digits in written text"})
    return check_advice(text)


_SPLIT = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Complete sentences so far, plus the unfinished tail to keep buffering."""
    parts = _SPLIT.split(buffer)
    if len(parts) <= 1:
        return [], buffer
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]
