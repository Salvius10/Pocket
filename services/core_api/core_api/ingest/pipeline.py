"""One bank SMS in, at most one transaction out.

    parse -> find the account -> skip a duplicate -> match the merchant -> classify -> store

Every SMS is kept in `sms_messages` with what the parser made of it. The parser is code, so is
everything here: no model sees the SMS, and every amount stays in integer paise.

Limits (MVP): a reversal SMS is stored as an excluded credit and is not linked back to the debit
it reverses; recurring items are not linked from an SMS.
"""

from __future__ import annotations

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


def match_merchant(merchants: dict[str, m.Merchant], counterparty: str | None, vpa: str | None) -> m.Merchant | None:
    """The merchant behind an SMS: by VPA, then by name or alias, then by a name the bank cut short."""
    if vpa:
        for x in merchants.values():
            if x.vpa_pattern and x.vpa_pattern.lower() == vpa.lower():
                return x
    if not counterparty:
        return None
    want = _norm(counterparty)
    names: dict[str, m.Merchant] = {}
    for x in merchants.values():
        for name in (x.name, x.narration_name, *(x.aliases or "").split("|")):
            if name.strip():
                names.setdefault(_norm(name), x)
    if want in names:
        return names[want]
    if len(want) >= 6:  # banks cut long names ("LIFE INSURANCE CORPORATIO"): accept one unambiguous prefix match
        hits = {x.key: x for name, x in names.items() if name.startswith(want) or (len(name) >= 6 and want.startswith(name))}
        if len(hits) == 1:
            return next(iter(hits.values()))
    return None


def _find_account(ctx: Ctx, parsed: ParsedSms) -> m.Account | None:
    if parsed.account_last4 is None:
        return None
    hits = [a for a in ctx.accounts if a.masked_number.endswith(parsed.account_last4)]
    if len(hits) > 1 and parsed.bank:
        same_bank = [a for a in hits if parsed.bank in (a.institution_code or a.institution or "").lower()]
        hits = same_bank or hits
    return hits[0] if len(hits) == 1 else None


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

    merchant = match_merchant(merchants, parsed.counterparty, parsed.vpa)
    is_reversal = parsed.kind == "credit" and "revers" in body.lower()
    category_id = merchant.category_id if merchant else ("other_income" if parsed.kind == "credit" else "uncategorised")
    if parsed.kind == "credit" and merchant is not None and ctx.categories[merchant.category_id].kind == "expense":
        category_id = "refund" if "refund" in ctx.categories else category_id  # money back from a shop
    category = ctx.categories.get(category_id) or ctx.categories["uncategorised"]
    local = parsed.txn_date or received_at.astimezone(IST).date()
    name = merchant.name if merchant else _title(parsed.counterparty or "") or (parsed.vpa or "")

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
        kind="upi_reversal" if is_reversal else KINDS.get((mode, parsed.kind), "netbanking" if parsed.kind == "debit" else "neft_in"),
        merchant=merchant.key if merchant else None, merchant_name=name, counterparty_name=parsed.counterparty,
        counterparty_vpa=parsed.vpa, category=category.id,
        spend_class=spend_class(status="success", hidden=False, is_reversal=is_reversal, category_kind=category.kind,
                                category_default_class=category.default_class, recurring_kind=None),
        narration=f"SMS/{(parsed.counterparty or parsed.vpa or mode).upper()}/{parsed.ref_no or ''}".rstrip("/"),
        ref_no=parsed.ref_no, balance_after_paise=account.balance_paise if account.type != "credit_card" else None,
        source="sms", hidden=False,
    )
    session.add(txn)
    await session.flush()
    sms.parse_status, sms.transaction_id = "parsed", txn.id
    await bump(session, ctx.user)
    return Ingested("created", sms, parsed, txn)
