"""Bank SMS parser: per-bank regex families plus a generic fallback. No model, no network.

`parse_sms` turns one SMS into a `ParsedSms`: debit or credit with amount (integer paise), account,
counterparty or VPA, reference number, date and balance, or `ignore` for OTPs, promotions and
statement notices.

How it is put together:

- Amount, direction, account, date, balance, VPA and reference number are read by generic
  extractors. Banks word these in a few common ways, so one set of rules covers every bank.
- Who the money went to or came from is where banks differ most. Each bank has a small family of
  rules for its own wordings (`FAMILIES`), tried first. If none matches, the generic rules look
  for "to X", "from X", "at X", "towards X" and "by X".
- An SMS that shows only the last three digits of an account ("Acct XX219") is matched against
  the accounts the user has linked, passed in as `known_last4`.

Money is parsed with Decimal and returned as integer paise. Nothing here uses a float.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from core_api.config import IST

# ---------- result ----------


@dataclass(frozen=True)
class ParsedSms:
    kind: str  # debit | credit | ignore
    reason: str | None = None  # for ignore: otp | statement_notice | promo | not_a_transaction
    amount_paise: int | None = None
    account_ref: str | None = None  # the digits as the SMS shows them (may be only 3)
    account_last4: str | None = None
    counterparty: str | None = None
    vpa: str | None = None
    ref_no: str | None = None
    txn_date: date | None = None
    balance_paise: int | None = None
    mode: str | None = None  # upi | imps | neft | nach | atm | card | cash | other
    is_card: bool = False
    bank: str | None = None
    matched: str = "generic"  # "family" when one of the bank's own rules named the counterparty


# ---------- senders ----------

SENDER_BANKS = {
    "HDFCBK": "hdfc", "ICICIT": "icici", "ICICIB": "icici", "AXISBK": "axis", "KOTAKB": "kotak",
    "BOBTXN": "bob", "BOBSMS": "bob", "CANBNK": "canara",
}


def sender_bank(sender_id: str) -> tuple[str | None, bool]:
    """(bank, is_promotional) from a DLT header like `DM-HDFCBK-S`. `-P` marks a promotional sender."""
    parts = sender_id.upper().split("-")
    code = parts[1] if len(parts) >= 2 else parts[0]
    bank = SENDER_BANKS.get(code) or ("sbi" if "SBI" in code else None)
    return bank, len(parts) >= 3 and parts[2] == "P"


# ---------- money ----------

_NUM = r"\d[\d,]*(?:\.\d{1,2})?"
_MONEY = re.compile(rf"(?:Rs\.?|INR|₹)\s*({_NUM})", re.I)
_BARE_AMOUNT = re.compile(rf"\b(?:debited|credited)\s+(?:by|with|for|of)\s+({_NUM})", re.I)
_BALANCE = re.compile(
    rf"(?:avl|avail\.?|available|total|updated|\b)\s*bal(?:ance)?\s*(?:is)?\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*({_NUM})", re.I
)
_NOT_THE_AMOUNT = re.compile(r"(?:bal(?:ance)?|limit|lmt|avl\w*\s+amt|up\s?to)\s*(?:is)?\s*[:\-]?\s*$", re.I)


def to_paise(text: str) -> int | None:
    """"1,25,580.98" -> 12558098. Exact: Decimal, never float."""
    try:
        value = Decimal(text.replace(",", "")) * 100
    except InvalidOperation:
        return None
    return int(value) if value == value.to_integral_value() else None


def _amount(body: str) -> int | None:
    for m in _MONEY.finditer(body):
        if not _NOT_THE_AMOUNT.search(body[max(0, m.start() - 18) : m.start()]):
            return to_paise(m.group(1))
    bare = _BARE_AMOUNT.search(body)  # "debited by 420.0" with no currency mark
    return to_paise(bare.group(1)) if bare else None


def _balance(body: str) -> int | None:
    m = _BALANCE.search(body)
    return to_paise(m.group(1)) if m else None


# ---------- direction ----------

_DIRECTION = re.compile(
    r"\b(?:(?P<debit>debited|debit(?!\s*card)|dr\.|sent|spent|withdrawn|paid|purchase|deducted|charged)"
    r"|(?P<credit>credited|credit(?!\s*card)|cr\.|received|deposited|reversed|reversal|refund(?:ed)?))",
    re.I,
)
# Weaker wording, used only when none of the words above appears: "card has been used for a transaction of INR ..."
_SPEND_WORDING = re.compile(r"\bused\s+(?:for|at|on)\b|\b(?:transaction|txn)\s+of\b", re.I)


def _direction(body: str) -> str | None:
    """The first direction word decides: "Acct debited ...; SHOP credited" is a debit."""
    m = _DIRECTION.search(body)
    if m is None:
        return "debit" if _SPEND_WORDING.search(body) else None
    return "debit" if m.group("debit") else "credit"


# ---------- things to skip ----------

_OTP = re.compile(r"\bOTP\b|one[\s-]?time\s+password|verification code", re.I)
_STATEMENT = re.compile(r"statement\s+(?:is\s+)?(?:generated|ready)|(?:total|min(?:imum)?)\s+(?:amt|amount)\s+due", re.I)


# ---------- account ----------

_ACCOUNT = re.compile(
    r"(?P<kw>a/c|acct|account|card)\s*(?:no\.?|number)?\s*(?:ending(?:\s+with)?)?\s*[:\-]?\s*"
    r"(?:\d{0,4}[xX*.]+)*(?P<digits>\d{3,})(?!\d)",
    re.I,
)
_CREDIT_CARD = re.compile(r"credit\s+card", re.I)
_ATM = re.compile(r"\bATM\b")


def resolve_last4(ref: str | None, known_last4: Iterable[str]) -> str | None:
    """Four or more digits: the last four. Three digits: the one linked account that ends with them."""
    if ref is None:
        return None
    if len(ref) >= 4:
        return ref[-4:]
    hits = {k for k in known_last4 if k.endswith(ref)}
    return hits.pop() if len(hits) == 1 else None


# ---------- date ----------

_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_DATE_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
_DATE_COLON = re.compile(r"(?<!\d)(20\d{2}):(\d{2}):(\d{2})(?=\s+\d{2}:)")  # "(2025:11:06 01:29:04)"
_DATE_NAMED = re.compile(
    r"(?<![A-Za-z0-9])(\d{1,2})[-/ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ]?(\d{4}|\d{2})(?!\d)", re.I
)
_DATE_NUMERIC = re.compile(r"(?<![\d/-])(\d{1,2})([/-])(\d{1,2})\2(\d{4}|\d{2})(?!\d)")  # day first
_DATE_MONTH_FIRST = re.compile(  # "Nov 11, 2025"
    r"(?<![A-Za-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})(?!\d)", re.I
)


def _year(text: str) -> int:
    return int(text) if len(text) == 4 else 2000 + int(text)


def _txn_date(body: str) -> date | None:
    found: list[tuple[int, tuple[int, int, int]]] = []
    for m in _DATE_ISO.finditer(body):
        found.append((m.start(), (int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for m in _DATE_COLON.finditer(body):
        found.append((m.start(), (int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for m in _DATE_NAMED.finditer(body):
        found.append((m.start(), (_year(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))))
    for m in _DATE_NUMERIC.finditer(body):
        found.append((m.start(), (_year(m.group(4)), int(m.group(3)), int(m.group(1)))))
    for m in _DATE_MONTH_FIRST.finditer(body):
        found.append((m.start(), (int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))))
    for _, (y, mo, d) in sorted(found):
        try:
            return date(y, mo, d)
        except ValueError:
            continue
    return None


# ---------- reference number and VPA ----------

_REF = r"(?=[A-Z0-9]*\d{6})[A-Z0-9]{8,24}(?![A-Za-z0-9])"  # letters and digits, at least six digits
_REF_PATTERNS = (
    re.compile(rf"(?i:\bref(?:erence)?\.?\s*(?:no\.?|number|id)?)\s*[:.\-]?\s*({_REF})"),
    re.compile(rf"(?i:\bUTR\s*(?:no\.?)?)\s*[:.\-]?\s*({_REF})"),
    re.compile(rf"\b(?:UPI|IMPS|NEFT|RTGS)(?:\s+Cr|\s+Dr)?\s*[:/\- ]\s*(?:(?:P2A|P2M|REV|CR|DR)/)?({_REF})"),
)
_VPA = re.compile(r"(?<![A-Za-z0-9._\-])([A-Za-z0-9][A-Za-z0-9._\-]*@[A-Za-z][A-Za-z0-9]{1,})(?![A-Za-z0-9])(?!\.[A-Za-z])")


def _ref_no(body: str) -> str | None:
    for pattern in _REF_PATTERNS:
        m = pattern.search(body)
        if m:
            return m.group(1)
    return None


def _vpa(body: str) -> str | None:
    m = _VPA.search(body)
    return m.group(1) if m else None


# ---------- counterparty: generic ----------

# Where a name stops: a date ("on 05-12-25"), a channel word, a reference, the balance, or punctuation.
_END = (
    r"(?=\s+on\s+(?:date\s+)?\d|\s+(?:via|thru|through|using)\b|\s+(?:UPI\s+)?ref(?:no|erence)?\b|\s+UTR\b|\s+UPI\s*[:/]"
    r"|\s+(?:avl|avail|bal|info|not\s+you|if\s+not)\b|\s+(?:has\s+been\s+|is\s+|was\s+)?(?:credited|debited)\b"
    r"|\s*[,;(\n]|\s*$|(?-i:\.(?:\s|$|[A-Z][a-z]))|\s+-)"  # the sentence-end test stays case-sensitive
)
_NAME = r"(?P<cp>[A-Za-z0-9][^\n]*?)"
_TO_LINE = re.compile(r"(?mi)^To\s+(?P<cp>[^\n]+)$")
_TO = re.compile(rf"\bto\s+(?:VPA\s+)?{_NAME}{_END}", re.I)
_AT = re.compile(rf"\bat\s+{_NAME}{_END}", re.I)
# "spent ... on 07-Nov-25 on UBER INDIA SYSTEMS": the merchant is the "on" that is not followed by a date
_ON = re.compile(rf"\bon\s+(?P<cp>[A-Za-z][^\n]*?){_END}", re.I)
_TOWARDS = re.compile(rf"\btowards\s+(?:ACH\s+)?{_NAME}{_END}", re.I)
_FROM = re.compile(rf"\bfrom\s+(?:VPA\s+)?{_NAME}{_END}", re.I)
_BY = re.compile(rf"\bby\s+{_NAME}{_END}", re.I)
_INFO = re.compile(rf"\bInfo:\s*{_NAME}{_END}", re.I)  # "... on Nov 11, 2025 at 02:22:26. Info: TRENT LTD ZUDIO."
# Text after "to"/"from"/"by"/"at"/"on" that is not a person or a shop: the user's own account, a
# channel, a phone number, a time ("at 02:22:26") or a date ("on Nov 11").
_NOT_A_NAME = re.compile(
    r"^(?:your?\b|a/c|acct\b|account\b|card\b|vpa\b|upi\b|imps\b|neft\b|rtgs\b|n?ach\b|atm$|cash$|rs\.?\s*\d|inr\b|block\b"
    r"|\d{5,}|[^A-Za-z]*$|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d"
    r"|.*\bbank\s+(?:a/c|acct|account|card|credit|debit)\b)",
    re.I,
)


def _first_name(pattern: re.Pattern[str], body: str) -> str | None:
    for m in pattern.finditer(body):
        token = body[m.start("cp") :].split(None, 1)[0]
        if "@" in token:  # the payee is written as a VPA ("to spotify.rzp@icici"), not as a name
            continue
        name = " ".join(m.group("cp").split()).strip(" .,-:;")
        if name and "@" not in name and not _NOT_A_NAME.match(name):
            return name
    return None


def _generic_counterparty(body: str, kind: str, card_spend: bool) -> str | None:
    if kind == "credit":
        order: tuple[re.Pattern[str], ...] = (_FROM, _BY)
    elif card_spend:
        order = (_AT, _ON, _TO, _INFO)
    else:
        order = (_TO_LINE, _TO, _AT, _TOWARDS, _INFO)
    for pattern in order:
        name = _first_name(pattern, body)
        if name:
            return name
    return None


# ---------- counterparty: per-bank families ----------


@dataclass(frozen=True)
class Rule:
    """One wording a bank uses. Named groups `cp` and `ref` fill those fields; `no_counterparty`
    marks a wording that names nobody even though the generic rules would find a name in it."""

    pattern: re.Pattern[str]
    no_counterparty: bool = False


FAMILIES: dict[str, tuple[Rule, ...]] = {
    "hdfc": (
        # Update! INR 61,842.00 deposited ... for NEFT Cr-ICICN25332434198-BLUEWAVE TECHNOLOGIES PVT.Avl bal ...
        Rule(re.compile(rf"\b(?:NEFT|RTGS|IMPS)\s+Cr-(?P<ref>{_REF})-(?P<cp>[^\n]+?)\.\s*Avl\s+bal", re.I)),
    ),
    "icici": (
        # ICICI Bank Acct XX219 debited for Rs 700.00 on 01-Nov-25; TRENDY SALON credited. UPI:530517995677.
        Rule(re.compile(r";\s*(?P<cp>[^;\n]+?)\s+credited\.")),
        # ... debited with Rs 14,000.00 on 04-Nov-25 & Acct of ARNAB DUTTA credited. IMPS:530818850603.
        Rule(re.compile(r"&\s*Acct\s+of\s+(?P<cp>[^\n]+?)\s+credited\.", re.I)),
        # ... credited:Rs. 72,000.00 on 03-Nov-25. Info IMPS-530718714762-SOWMYA NATARAJAN. Available Balance ...
        Rule(re.compile(rf"\bInfo\s+(?:IMPS|NEFT|RTGS)-(?P<ref>{_REF})-(?P<cp>[^\n]+?)\.\s+Available", re.I)),
        # ... debited with INR 1,000.00 on 02-Nov-25 at ATM ATM THANE WEST MUMBAI.   (a place, not a payee)
        Rule(re.compile(r"\bat\s+ATM\b", re.I), no_counterparty=True),
    ),
    "sbi": (
        # Your A/C XXXXX7605 Debited INR 40,598.00 on 06/11/25 -ACH-SBI HOME LOAN. Avl Balance INR ...
        Rule(re.compile(r"-(?:N?ACH|ECS)-(?P<cp>[^\n]+?)\.\s+Avl", re.I)),
    ),
    "axis": (
        # INR 8,000.00 debited from A/c no. XX8950 ... Info- ACH-DR/NSE CLEARING LTD. Avl Bal-INR ...
        # INR 1,327.17 credited to A/c no. XX5149 ... Info- IMPS/622722821650/ROPPEN TRANSPORTATION CAP. Avl Bal-...
        Rule(re.compile(rf"\bInfo-\s*(?:ACH-DR|ACH-CR|IMPS|NEFT|RTGS)/(?:(?P<ref>{_REF})/)?(?P<cp>[^\n]+?)\.\s+Avl", re.I)),
        # INR 224.00 debited / A/c no. XX9553 / 29-09-26, 20:55:56 / UPI/P2A/627220451431/RITU CHOUDHARY
        Rule(re.compile(r"\bUPI/(?:P2A|P2M)/(?P<ref>\d{8,})/(?P<cp>[^\n]+)")),
        # INR 526.00 credited (reversal) / A/c no. XX7026 / ... / UPI/REV/601021101934
        Rule(re.compile(r"\bUPI/REV/(?P<ref>\d{8,})"), no_counterparty=True),
        # Spent / Card no. XX1500 / INR 3,838.73 / 30-07-26 11:30:57 / BHARAT PETROLEUM COR / Avl Lmt INR ...
        Rule(re.compile(r"^Spent\nCard no\.[^\n]*\n[^\n]*\n[^\n]*\n(?P<cp>[^\n]+)\nAvl Lmt", re.I)),
    ),
}


def _family(bank: str | None, body: str) -> tuple[bool, str | None, str | None]:
    """(matched, counterparty, ref_no) from the bank's own rules."""
    for rule in FAMILIES.get(bank or "", ()):
        m = rule.pattern.search(body)
        if m is None:
            continue
        groups = m.groupdict()
        name = None if rule.no_counterparty else " ".join((groups.get("cp") or "").split()).strip(" .,-:;") or None
        return True, name, groups.get("ref")
    return False, None, None


# ---------- mode ----------

_MODE_WORDS = (
    ("imps", re.compile(r"\bIMPS\b")),
    ("neft", re.compile(r"\b(?:NEFT|RTGS)\b")),
    ("nach", re.compile(r"\b(?:N?ACH|ECS|UMRN\w*)\b|\bACH-", re.I)),
    ("cash", re.compile(r"\bcash\b", re.I)),
)


def _mode(body: str, vpa: str | None, is_card: bool, is_atm: bool, kind: str) -> str:
    if is_atm:
        return "atm"
    if is_card:
        return "other" if kind == "credit" and not re.search(r"\brefund", body, re.I) else "card"
    if vpa or re.search(r"\bUPI\b", body):
        return "upi"
    for mode, pattern in _MODE_WORDS:
        if pattern.search(body):
            return mode
    return "other"


# ---------- entry point ----------


def parse_sms(
    sender_id: str, body: str, received_at: datetime | None = None, known_last4: Iterable[str] = (),
    *, use_families: bool = True,
) -> ParsedSms:
    """Parse one bank SMS. `received_at` dates a message that prints no date; `known_last4` is the
    last four digits of each account the user has linked. `use_families=False` forces the generic
    rules (the eval uses it to measure the fallback on its own)."""
    bank, promotional = sender_bank(sender_id)
    if _OTP.search(body):
        return ParsedSms("ignore", reason="otp", bank=bank)
    if _STATEMENT.search(body):
        return ParsedSms("ignore", reason="statement_notice", bank=bank)
    if promotional:
        return ParsedSms("ignore", reason="promo", bank=bank)
    kind = _direction(body)
    amount = _amount(body)
    if kind is None or amount is None or amount <= 0:
        return ParsedSms("ignore", reason="not_a_transaction", bank=bank)

    account = _ACCOUNT.search(body)
    account_ref = account.group("digits") if account else None
    is_atm = bool(_ATM.search(body))
    on_card = account is not None and (account.group("kw").lower() == "card" or bool(_CREDIT_CARD.search(body)))
    is_card = on_card and not is_atm

    vpa = _vpa(body)
    ref_no = _ref_no(body)
    matched, counterparty, family_ref = _family(bank, body) if use_families else (False, None, None)
    if matched:
        ref_no = family_ref or ref_no
    else:
        counterparty = _generic_counterparty(body, kind, card_spend=is_card and kind == "debit")
    if counterparty and "@" in counterparty:
        counterparty = None

    when = _txn_date(body)
    if when is None and received_at is not None:
        when = received_at.astimezone(IST).date()
    return ParsedSms(
        kind=kind, amount_paise=amount, account_ref=account_ref, account_last4=resolve_last4(account_ref, known_last4),
        counterparty=counterparty, vpa=vpa, ref_no=ref_no, txn_date=when, balance_paise=_balance(body),
        mode=_mode(body, vpa, is_card, is_atm, kind), is_card=is_card, bank=bank, matched="family" if matched else "generic",
    )
