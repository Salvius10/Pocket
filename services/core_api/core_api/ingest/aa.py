"""Account Aggregator statement parser (ReBIT-style deposit and credit-card JSON). No model.

Most of a statement row is already structured: the id, the amount, debit or credit, the time,
the balance after it and the reference number. Those are read as they are, with money parsed by
Decimal into integer paise. What the bank leaves in free text is the narration, and from it this
module reads three things: the channel (UPI, IMPS, NEFT, mandate, ATM, cash, card), the VPA when
one is printed, and the name of the other party.

Banks cut names short in narrations ("TNPDCL TNEB ELECTRIC"), so the name read here is the
bank's spelling, often a prefix of the real one. Matching a merchant from it is the ingest step's
job (VPA first, then name, alias and cut-short name).

Every bank writes narrations its own way, with `/`, `-` or `*` between the parts. The reader does
not keep a template per bank. It splits the narration into parts, drops what is clearly not a
name (channel words, bank codes, reference numbers, masked accounts) and takes the first part
that is left.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core_api.config import IST


@dataclass(frozen=True)
class AaTxn:
    txn_id: str
    direction: str  # debit | credit
    amount_paise: int
    occurred_at: datetime
    value_date: date | None
    balance_paise: int | None  # deposit accounts only
    ref_no: str | None
    mode: str  # upi | autopay | imps | neft | nach | atm | cash | card | interest | other
    counterparty: str | None  # as the bank printed it; may be cut short
    vpa: str | None
    narration: str
    is_reversal: bool = False
    is_self_transfer: bool = False
    mcc: int | None = None


@dataclass(frozen=True)
class AaAccount:
    kind: str  # deposit | credit_card
    masked_number: str
    last4: str
    transactions: tuple[AaTxn, ...]


# ---------- money and time ----------
def rupees_to_paise(text: object) -> int | None:
    """"23448.00" -> 2344800. Exact: Decimal, never float; more than two decimals is refused."""
    try:
        value = Decimal(str(text).replace(",", "")) * 100
    except (InvalidOperation, ValueError):
        return None
    return int(value) if value == value.to_integral_value() else None


def _when(text: str) -> datetime:
    stamp = datetime.fromisoformat(text)
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=IST)


# ---------- narration ----------
_VPA = re.compile(r"(?<![A-Za-z0-9._\-])([A-Za-z0-9][A-Za-z0-9._\-]*@[A-Za-z][A-Za-z0-9]{1,})(?![A-Za-z0-9])")
_SEPARATORS = re.compile(r"\s*[/*]\s*|\s*-+\s*")
_CHANNEL_WORDS = re.compile(
    r"^(?:TO TRANSFER|BY TRANSFER|TRANSFER|UPI(?: REV)?|IMPS|NEFT(?: DR| CR)?|RTGS|DR|CR|P2A|P2M|REV|INB|DEBIT|CREDIT|ACH(?: ?DR?)?|N?ACH|"
    r"NETBANKING TRF|IB BILLPAY DR|ATM(?: WDL| CASH)?|CASH(?: WDL)?|WDL|NWD|ATL|MMT|SELF|AUTOPAY|PAYMENT|SENT|MANDATE REG|BBPS BILLPAY)$",
    re.I,
)
_LEADING_WORDS = re.compile(r"^(?:(?:N?ACH ?D[Rr]?|ACHDr|NEFT(?: CR| DR)?|IMPS|RTGS|INB|ATM CASH|ATM WDL|ATM)\s+)+", re.I)
_CARD_TAIL = re.compile(r"\s+CC\s+X*\d+$|(?:\s+\d+)+$", re.I)  # "BILLDESK CC 3757", "BAJAJ FINANCE LTD 441905966095"
_TWO_WORD_CITY = ("NEW", "NAVI", "GREATER")
_BANK_CODE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$|^(?:SBIN|HDFC|ICIC|UTIB|KKBK|BARB|CNRB|YESB|PUNB|IDIB|IOBA|UBIN|IDFB|INDB|FDRL|AIRP|PYTM|CITI|HSBC|SCBL|MAHB|BKID|UCBA|RATN|AUBL|KVBL|TMBL|CSBK|DBSS|JAKA|ESFB|UTKS)$")
_REF_LIKE = re.compile(r"^(?=[A-Z0-9]*\d{4})[A-Z0-9]{6,}$")
_MASKED = re.compile(r"^X+\d*$|^CC\s+X*\d+$|^X{2,}\d+$", re.I)
_DIGITS = re.compile(r"\b\d{4,}\b")


def _parts(narration: str, vpa: str | None) -> list[str]:
    text = narration.replace(vpa, "/") if vpa else narration
    return [" ".join(p.split()) for p in _SEPARATORS.split(text) if p and p.strip()]


def _vpa_in(narration: str) -> str | None:
    """The VPA printed in a narration. Where the bank separates parts with hyphens, the match can
    run back into the part before it ("UPI-LAKSHMAMMA-lakshmamma86@okaxis"): a VPA is lower case, so
    everything up to the last part with a capital letter is dropped. "gpay-36034732876@okbizaxis" stays whole."""
    found = _VPA.search(narration)
    if found is None:
        return None
    local, _, handle = found.group(1).rpartition("@")
    kept: list[str] = []
    for segment in reversed(local.split("-")):
        if any(ch.isupper() for ch in segment):
            break
        kept.insert(0, segment)
    return f"{'-'.join(kept)}@{handle}" if kept and kept[0] else None


def _name_from(parts: list[str], reference: str | None) -> str | None:
    for raw in parts:
        if _CHANNEL_WORDS.match(raw):
            continue
        part = _LEADING_WORDS.sub("", raw).strip()
        if reference:
            part = " ".join(w for w in part.split() if w != reference)
        words = [w for w in part.split() if not _REF_LIKE.match(w)]
        part = _CARD_TAIL.sub("", " ".join(words)).strip(" .,:")
        if not part or _CHANNEL_WORDS.match(part) or _BANK_CODE.match(part) or _MASKED.match(part) or not re.search(r"[A-Za-z]{2}", part):
            continue
        if any(ch.islower() for ch in part):
            # Banks print the other party in capitals. A part in ordinary case is the payer's note
            # ("Payment from Ph", "For you") or the name of a bank ("Yes Bank"), never the payee.
            continue
        return part
    return None


def read_narration(narration: str, *, reference: str | None, aa_mode: str | None, direction: str, on_card: bool,
                   mcc: int | None = None) -> tuple[str, str | None, str | None, bool, bool]:
    """(mode, counterparty, vpa, is_reversal, is_self_transfer) from one narration."""
    text = narration.strip()
    upper = text.upper()
    vpa = _vpa_in(text)
    is_reversal = bool(re.search(r"\bREV\b|REVERSAL", upper))
    is_self = bool(re.search(r"(?:^|[/\-\s])SELF(?:$|[/\-\s])", upper))

    if on_card:
        if "FINANCE CHARGES" in upper:
            return "other", upper.rstrip("- "), None, False, False
        if "PAYMENT RECEIVED" in upper:
            return "other", "PAYMENT RECEIVED", None, False, False
        if upper.startswith("REFUND "):
            return "card", text[7:].strip(), None, False, False
        # "BATA INDIA LTD CHENNAI IN": the shop, then the city and the country code
        words = text.split()
        if len(words) >= 3 and words[-1] == "IN":
            words = words[:-2]
            if len(words) >= 2 and words[-1] in _TWO_WORD_CITY:  # "... NEW DELHI IN"
                words = words[:-1]
        return "card", " ".join(words) or None, None, False, False

    parts = _parts(text, vpa)
    if (aa_mode or "").upper() == "ATM" or re.search(r"\bATM\b|^NWD\b|^ATL\b", upper):
        place = _name_from([_DIGITS.sub("", p) for p in parts], reference)
        return "atm", f"ATM {place}" if place else None, None, False, False
    if (aa_mode or "").upper() == "CASH" or upper.startswith("BY CASH"):
        return "cash", "CASH DEPOSIT", None, False, False
    if re.search(r"\bINT(?:EREST)?\b|INT\.PD", upper) and direction == "credit":
        return "interest", "INTEREST", None, False, False
    fd = re.match(r"(?:TRF TO FD NO|FD BOOKED|TO FD)\s+(\d+)", upper)
    if fd:
        return "other", f"FD {fd.group(1)}", None, False, False
    if upper.startswith("TD CLOSURE"):
        return "other", "FD CLOSURE PROCEEDS", None, False, False

    if re.search(r"\bN?ACH\b|ACHDR|\bECS\b", upper):
        mode = "nach"
    elif "UPI" in upper or vpa:
        mode = "autopay" if re.search(r"AUTOPAY|MANDATE", upper) else "upi"
    elif "IMPS" in upper:
        mode = "imps"
    elif re.search(r"\bNEFT\b|\bRTGS\b", upper):
        mode = "neft"
    else:
        mode = "other"
    return mode, _name_from(parts, reference), vpa, is_reversal, is_self


# ---------- statement ----------
def parse_account(document: dict[str, Any]) -> AaAccount:
    """One account's statement: `{"Account": {...}}` as the Account Aggregator returns it."""
    account = document.get("Account") or document
    kind = str(account.get("type") or "deposit")
    on_card = kind == "credit_card"
    masked = str(account.get("maskedCardNumber") or account.get("maskedAccNumber") or "")
    digits = "".join(ch for ch in masked if ch.isdigit())
    rows = ((account.get("Transactions") or {}).get("Transaction")) or []
    out: list[AaTxn] = []
    for row in rows:
        amount = rupees_to_paise(row.get("amount"))
        kind_word = str(row.get("txnType") or row.get("type") or "").upper()
        stamp = row.get("txnDate") or row.get("transactionTimestamp")
        if amount is None or amount <= 0 or kind_word not in ("DEBIT", "CREDIT") or not stamp:
            continue  # not a posted money movement: skip rather than guess
        direction = "debit" if kind_word == "DEBIT" else "credit"
        reference = str(row.get("reference") or "").strip() or None
        mcc = row.get("mcc")
        narration = str(row.get("narration") or "")
        mode, name, vpa, is_reversal, is_self = read_narration(
            narration, reference=reference, aa_mode=row.get("mode"), direction=direction, on_card=on_card,
            mcc=int(mcc) if mcc is not None else None,
        )
        value_date = str(row.get("valueDate") or "")[:10]
        out.append(AaTxn(
            txn_id=str(row.get("txnId") or ""), direction=direction, amount_paise=amount, occurred_at=_when(str(stamp)),
            value_date=date.fromisoformat(value_date) if value_date else None,
            balance_paise=None if on_card else rupees_to_paise(row.get("currentBalance")),
            ref_no=reference, mode=mode, counterparty=name, vpa=vpa, narration=narration,
            is_reversal=is_reversal, is_self_transfer=is_self, mcc=int(mcc) if mcc is not None else None,
        ))
    return AaAccount(kind=kind, masked_number=masked, last4=digits[-4:], transactions=tuple(out))
