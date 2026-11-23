"""One bank SMS in, at most one transaction out.

    parse -> find the account -> skip a duplicate -> match the merchant -> classify -> store

Every SMS is kept in `sms_messages` with what the parser made of it. The parser is code, so is
everything here: no model sees the SMS, and every amount stays in integer paise.

A payee the user has paid before keeps the category, merchant and bill of the last payment to
them, so a correction the user made once carries forward.

Limit (MVP): a reversal SMS is stored as an excluded credit and is not linked back to the debit
it reverses.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST
from core_api.ingest.sms import ParsedSms, parse_sms
from core_api.ledger.classify import SALARY_CATEGORIES, spend_class
from core_api.ledger.context import Ctx, bump
from core_api.ledger.mathx import budget_month_for

KINDS = {  # (mode, direction) -> the transaction kind the rest of the app uses
    ("upi", "debit"): "upi_p2m", ("upi", "credit"): "upi_in", ("imps", "debit"): "upi_p2p_out", ("imps", "credit"): "imps_in",
    ("neft", "debit"): "neft_out", ("neft", "credit"): "neft_in", ("nach", "debit"): "ach_dr", ("atm", "debit"): "atm_wd",
    ("card", "debit"): "card_spend", ("card", "credit"): "card_refund", ("cash", "credit"): "cash_dep",
    ("other", "credit"): "card_payment_in",
}


@dataclass
class Ingested:
    status: str  # created | ignored | duplicate | no_account
    sms: m.SmsMessage
    parsed: ParsedSms
    transaction: m.Transaction | None = None


def _norm(text: str) -> str:
    return " ".join(text.upper().split())


PAYOUT_CATEGORIES = frozenset({"salary", "gig_payout", "business_income", "allowance", "interest_income", "other_income"})
_MIN_NAME = 6  # shorter than this, a name is only matched whole
_MIN_CUT = 16  # banks cut names at about 20 characters: anything shorter was not cut, so it is not matched as the start of a longer name


class MerchantIndex:
    """Finds the merchant behind a payment: by VPA, then by name or alias, then by a name the bank cut short.

    Built once and asked many times (the feed loader asks for every statement row)."""

    def __init__(self, merchants: Iterable[m.Merchant]) -> None:
        self.by_vpa: dict[str, m.Merchant] = {}
        self.by_name: dict[str, m.Merchant] = {}
        for x in merchants:
            if x.vpa_pattern:
                self.by_vpa.setdefault(x.vpa_pattern.lower(), x)
            for name in (x.name, x.narration_name, *(x.aliases or "").split("|")):
                if name.strip():
                    self.by_name.setdefault(_norm(name), x)
        self._by_part: dict[tuple[str, bool | None], m.Merchant | None] = {}

    def find(self, counterparty: str | None, vpa: str | None, direction: str | None = None, mode: str | None = None) -> m.Merchant | None:
        """`direction` and `mode` settle a cut-short name that a company and its payout account share
        ("ROPPEN TRANSPORTATIO"): money going out is to the company; money coming in by bank transfer
        is a payout; money coming back by UPI or card is a refund from the company."""
        if vpa and vpa.lower() in self.by_vpa:
            return self.by_vpa[vpa.lower()]
        if not counterparty:
            return None
        want = _norm(counterparty)
        if want in self.by_name:
            return self.by_name[want]
        if len(want) < _MIN_NAME:
            return None
        pays_out: bool | None = None
        if direction == "debit":
            pays_out = False
        elif direction == "credit" and mode:
            pays_out = mode in ("imps", "neft")
        key = (want, pays_out)
        if key not in self._by_part:
            self._by_part[key] = self._by_part_of_name(want, pays_out)
        return self._by_part[key]

    def _starting_with(self, text: str, pays_out: bool | None) -> m.Merchant | None:
        """The one merchant with a name that starts with `text`. When two do, `pays_out` picks between
        a company and its payout account. None when there is no single answer."""
        hits = {x.key: x for name, x in self.by_name.items() if name.startswith(text)}
        if len(hits) > 1 and pays_out is not None:
            hits = {key: x for key, x in hits.items() if (x.category_id in PAYOUT_CATEGORIES) == pays_out}
        return next(iter(hits.values())) if len(hits) == 1 else None

    def _by_part_of_name(self, want: str, pays_out: bool | None) -> m.Merchant | None:
        if len(want) >= _MIN_CUT:
            # 1. the bank cut the name short ("LIFE INSURANCE CORPORATIO")
            hit = self._starting_with(want, pays_out)
            if hit is not None:
                return hit
            # 2. cut short with a remark after it ("ZOMATO LTD DELIVERY PA WEEKLY PAYOUT"): drop words from the end
            words = want.split()
            for n in range(len(words) - 1, 0, -1):
                shorter = " ".join(words[:n])
                if len(shorter) < _MIN_CUT:
                    break
                hit = self._starting_with(shorter, pays_out)
                if hit is not None:
                    return hit
        # 3. the whole name with something after it ("SWIGGY BANGALORE"): the longest name that fits, if only one merchant has it
        fits = [(len(name), x) for name, x in self.by_name.items() if len(name) >= _MIN_NAME and want.startswith(name)]
        if not fits:
            return None
        longest = max(length for length, _ in fits)
        best = {x.key: x for length, x in fits if length == longest}
        return next(iter(best.values())) if len(best) == 1 else None


def match_merchant(merchants: dict[str, m.Merchant], counterparty: str | None, vpa: str | None,
                   direction: str | None = None, mode: str | None = None) -> m.Merchant | None:
    """The merchant behind one SMS (see `MerchantIndex`)."""
    return MerchantIndex(merchants.values()).find(counterparty, vpa, direction, mode)


def _find_account(ctx: Ctx, parsed: ParsedSms) -> m.Account | None:
    if parsed.account_last4 is None:
        return None
    hits = [a for a in ctx.accounts if a.masked_number.endswith(parsed.account_last4)]
    if len(hits) > 1 and parsed.bank:
        same_bank = [a for a in hits if parsed.bank in (a.institution_code or a.institution or "").lower()]
        hits = same_bank or hits
    return hits[0] if len(hits) == 1 else None


def _from_history(ctx: Ctx, parsed: ParsedSms) -> m.Transaction | None:
    """The user's latest earlier payment to (or from) the same VPA or the same name. What they paid
    this payee for before is the best guide to what this payment is: it carries the category
    (including one the user corrected), the merchant and the bill it belongs to."""
    name = _norm(parsed.counterparty) if parsed.counterparty else None
    vpa = parsed.vpa.lower() if parsed.vpa else None
    for old in reversed(ctx.txns):
        if old.direction != parsed.kind or old.status != "success":
            continue
        if vpa and old.counterparty_vpa and old.counterparty_vpa.lower() == vpa:
            return old
        if name and old.counterparty_name and _norm(old.counterparty_name) == name:
            return old
    return None


def _result_json(parsed: ParsedSms) -> dict[str, Any]:
    out = asdict(parsed)
    out["txn_date"] = parsed.txn_date.isoformat() if parsed.txn_date else None
    return out


def _title(name: str) -> str:
    return " ".join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in name.split())


async def ingest_sms(
    session: AsyncSession, ctx: Ctx, merchants: dict[str, m.Merchant], sender_id: str, body: str, received_at: datetime,
) -> Ingested:
    known = {a.masked_number[-4:] for a in ctx.accounts if len(a.masked_number) >= 4}
    parsed = parse_sms(sender_id, body, received_at, known)
    sms = m.SmsMessage(user_id=ctx.user.id, sender_id=sender_id[:24], body=body, received_at=received_at,
                       parse_status="ignored", parse_result=_result_json(parsed))
    session.add(sms)
    if parsed.kind == "ignore" or parsed.amount_paise is None:
        return Ingested("ignored", sms, parsed)

    account = _find_account(ctx, parsed)
    if account is None:
        sms.parse_status = "no_account"
        return Ingested("no_account", sms, parsed)

    amount = parsed.amount_paise
    for old in ctx.txns:  # the same payment already came in from the account feed or an earlier SMS
        if old.account_id == account.id and old.direction == parsed.kind and old.amount_paise == amount and (
            (parsed.ref_no is not None and old.ref_no == parsed.ref_no)
            or (parsed.ref_no is None and old.ref_no is None and old.local_date == parsed.txn_date and old.source == "sms")
        ):
            sms.parse_status, sms.transaction_id = "duplicate", old.id
            return Ingested("duplicate", sms, parsed, old)

    merchant = match_merchant(merchants, parsed.counterparty, parsed.vpa, parsed.kind, parsed.mode)
    before = _from_history(ctx, parsed)
    is_reversal = parsed.kind == "credit" and "revers" in body.lower()
    item = next((r for r in ctx.recurring if before is not None and r.id == before.recurring_item_id and r.status == "active"), None)
    if before is not None:  # the same payee as before: same category, merchant and bill
        category_id = before.category
        merchant_key: str | None = before.merchant or (merchant.key if merchant else None)
        name = before.merchant_name or _title(parsed.counterparty or "") or (parsed.vpa or "")
    else:
        category_id = merchant.category_id if merchant else ("other_income" if parsed.kind == "credit" else "uncategorised")
        if parsed.kind == "credit" and merchant is not None and ctx.categories[merchant.category_id].kind == "expense":
            category_id = "refund" if "refund" in ctx.categories else category_id  # money back from a shop
        elif parsed.kind == "credit" and merchant is None and account.type == "credit_card" and "card_payment" in ctx.categories:
            category_id = "card_payment"  # money arriving on a card with no shop named is the bill being paid
        merchant_key = merchant.key if merchant else None
        name = merchant.name if merchant else _title(parsed.counterparty or "") or (parsed.vpa or "")
    category = ctx.categories.get(category_id) or ctx.categories["uncategorised"]
    local = parsed.txn_date or received_at.astimezone(IST).date()

    if parsed.balance_paise is not None and account.type != "credit_card":
        account.balance_paise = parsed.balance_paise  # the bank's own figure
    elif account.type == "credit_card":
        account.balance_paise += amount if parsed.kind == "debit" else -amount  # what is owed on the card
    else:
        account.balance_paise += amount if parsed.kind == "credit" else -amount
    account.balance_as_of = received_at

    mode = parsed.mode or "other"
    txn = m.Transaction(
        user_id=ctx.user.id, account_id=account.id, occurred_at=received_at, local_date=local,
        budget_month=budget_month_for(local, category.id in SALARY_CATEGORIES), amount_paise=amount,
        personal_amount_paise=amount, direction=parsed.kind, mode=mode, status="success",
        kind="upi_reversal" if is_reversal else (before.kind if before is not None and before.kind else None)
        or KINDS.get((mode, parsed.kind), "netbanking" if parsed.kind == "debit" else "neft_in"),
        merchant=merchant_key, merchant_name=name, counterparty_name=parsed.counterparty,
        counterparty_vpa=parsed.vpa, category=category.id, recurring_item_id=item.id if item else None,
        spend_class=spend_class(status="success", hidden=False, is_reversal=is_reversal, category_kind=category.kind,
                                category_default_class=category.default_class, recurring_kind=item.kind if item else None),
        narration=f"SMS/{(parsed.counterparty or parsed.vpa or mode).upper()}/{parsed.ref_no or ''}".rstrip("/"),
        ref_no=parsed.ref_no, balance_after_paise=account.balance_paise if account.type != "credit_card" else None,
        source="sms", hidden=False,
    )
    session.add(txn)
    await session.flush()
    sms.parse_status, sms.transaction_id = "parsed", txn.id
    await bump(session, ctx.user)
    return Ingested("created", sms, parsed, txn)
