"""The loader: account-feed statements in, ledger rows out. No model.

    parse (aa.py) -> account -> merge SMS -> merchant -> pairs by reference -> group links
    -> recurring item -> category -> refunds

The account feed states the facts of a payment exactly: amount, time, direction, balance and
reference. Everything else in a ledger row is worked out here by rule, and each rule uses only
what a bank feed, the merchant list and the user's own set-up (accounts, recurring items,
groups, how they earn) can say.

Limit: this module does not find recurring payments. It is given the user's list of recurring
items and ties each payment to the item it pays. Without that list no payment is tied to a
bill, so subscriptions and bills count as flexible spending and the committed / flexible split
is wrong (see `evals/eval_loader.py --without-bills`). The dataset supplies the list; it marks
it as a label, because a full pipeline would detect it.

What no rule can know is what a payment to a person was for: an auto fare, a friend, the
vegetable seller. Those rows are left `uncategorised` for the user to label. Once they have, the
SMS path keeps the label for that payee (ingest/pipeline.py).

Rows come out in the shape of the dataset's `transactions.csv`, so `seed.loader.build_user_rows`
turns them into app rows exactly as it does the processed dataset, and `evals/eval_loader.py`
compares the two column by column.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from core_api.ingest.aa import AaTxn, parse_account
from core_api.ingest.pipeline import KINDS, MerchantIndex
from core_api.ingest.sms import ParsedSms

Row = dict[str, str | None]


class FeedError(ValueError):
    """A statement that cannot be loaded (for example, one for an account the user has not linked)."""


@dataclass(frozen=True)
class SettlementLink:
    """A group settle-up the user marked as paid: the bank row for it is found by amount, side, name and time."""

    settlement_id: str
    group_id: str
    amount_paise: int
    direction: str  # for this user: debit when they paid, credit when they were paid
    other_name: str
    at: datetime | None


@dataclass(frozen=True)
class GroupLinks:
    """What the user's groups already say about their transactions."""

    expenses: Mapping[str, tuple[str, str, str | None]] = field(default_factory=dict)  # transaction id -> (expense id, group id, category)
    settlements: Sequence[SettlementLink] = ()


@dataclass
class _Pay:
    """One statement row while the loader works on it."""

    txn: AaTxn
    account: Row
    merchant_key: str | None = None
    merchant_category: str | None = None
    status: str = "success"
    kind: str | None = None
    category: str | None = None
    recurring_key: str | None = None
    transfer_pair_id: str | None = None
    reversal_of_id: str | None = None
    refund_of_id: str | None = None
    group_expense_id: str | None = None
    group_id: str | None = None
    settlement_id: str | None = None

    @property
    def on_card(self) -> bool:
        return self.account["type"] == "credit_card"

    @property
    def name(self) -> str:
        return _norm(self.txn.counterparty or "")


def _norm(text: str) -> str:
    return " ".join(text.upper().split())


def _same_payee(a: str, b: str) -> bool:
    """Banks cut names short, so one spelling may be the start of the other."""
    a, b = _norm(a), _norm(b)
    return min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))


def _vpa_spells(vpa: str | None, name: str) -> bool:
    """Some banks print only the VPA. Its letters are how the name starts: "kunal.fernandes@ptaxis"
    for KUNAL FERNANDES, "anitas93@upi" for ANITA SAINI. Used only together with the amount of the
    bill that person is paid."""
    if not vpa:
        return False
    letters = "".join(ch for ch in vpa.split("@")[0].upper() if ch.isalpha())
    return len(letters) >= 4 and "".join(ch for ch in name.upper() if ch.isalpha()).startswith(letters)


def _is_owner(name: str, owner: str) -> bool:
    """The account holder's own name: in full, or cut short by the bank (a first name alone is not enough)."""
    name, owner = _norm(name), _norm(owner)
    return bool(name) and (name == owner or (len(name) >= 12 and owner.startswith(name)))


# ---------- words that say what a shop sells (payees with no merchant entry) ----------
_SHOP_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (  # singular forms; a plural "S" is accepted
    ("eating_out", ("TEA STALL", "BAKERY", "BHOJANALAYA", "CANTEEN", "MESS", "TIFFIN", "DHABA", "RESTAURANT", "CAFE", "SWEETS", "JUICE", "CHAAT")),
    ("fuel", ("FILLING", "SERVICE STATION", "PETROL", "PETROLEUM", "FUEL", "HPCL", "IOCL", "BPCL")),
    ("groceries", ("KIRANA", "PROVISION", "STORE", "SUPERMARKET", "VEGETABLE", "FRUIT", "GROCERY", "GROCERIES")),
    ("health", ("MEDICAL", "PHARMACY", "CLINIC", "HOSPITAL", "DIAGNOSTIC")),
    ("personal_care", ("SALON", "PARLOUR", "BEAUTY")),
    ("education", ("XEROX", "STATIONERY", "SCHOOL", "COLLEGE", "TUITION", "COACHING")),
    ("utilities", ("WATER SUPPLY",)),
)
_TRADE_WORDS = ("TRADERS", "DISTRIBUTORS", "AGENCIES", "WHOLESALE", "STATIONERS")  # a shopkeeper's suppliers
_FEES = re.compile(r"\bCHARGES\b|\bCHGS\b|\bANNUAL FEE\b")


def _says(name: str, phrase: str) -> bool:
    """`phrase` is in `name` as whole words, or `name` stops part-way through it because the bank
    cut the name short ("SAI KRUPA SERVICE ST" for a service station). A cut-short match needs
    at least five characters and three fifths of the phrase."""
    padded = f" {name} "
    if f" {phrase} " in padded or f" {phrase}S " in padded:
        return True
    least = max(5, (len(phrase) * 3 + 4) // 5)
    return any(padded.endswith(f" {phrase[:k]} ") for k in range(least, len(phrase)))


def _shop_category(name: str, income_pattern: str | None) -> str | None:
    if income_pattern == "business" and any(_says(name, w) for w in _TRADE_WORDS):
        return "business_supplies"
    return next((category for category, words in _SHOP_WORDS if any(_says(name, w) for w in words)), None)


_REWARD = re.compile(r"CASHBACK|REWARD")
_BILLPAY = re.compile(r"BBPS|BILLPAY")
_SALARY = re.compile(r"\bSALARY\b|\bSAL\b")
_BANK_TRANSFER = ("imps", "neft", "other")
# how the user earns -> (category of their regular income, channels it arrives by)
_INCOME: dict[str, tuple[str, tuple[str, ...]]] = {
    "salaried": ("salary", ("neft",)),
    "student": ("allowance", ("upi", "imps", "neft")),
}
_MIN_INCOME_MONTHS = 3
_AMOUNT_BAND = (0.7, 1.4)  # a fixed bill still matches its item after a price change; a much smaller or larger payment is something else
_SETTLE_WINDOW = timedelta(days=3)
_REFUND_WINDOW = timedelta(days=45)


# ---------- steps ----------
def _read(statements: Iterable[dict[str, Any]], accounts: Sequence[Row]) -> list[_Pay]:
    pays: list[_Pay] = []
    for document in statements:
        parsed = parse_account(document)
        on_card = parsed.kind == "credit_card"
        hits = [a for a in accounts if (a["masked_number"] or "").endswith(parsed.last4) and (a["type"] == "credit_card") == on_card]
        if not parsed.last4 or len(hits) != 1:
            raise FeedError(f"a statement for the account ending {parsed.last4!r} matches {len(hits)} linked accounts")
        pays.extend(_Pay(t, hits[0]) for t in parsed.transactions)
    pays.sort(key=lambda p: (p.txn.occurred_at, p.txn.txn_id))
    return pays


def _merge_sms(pays: list[_Pay], sms: Iterable[ParsedSms]) -> None:
    """The bank's SMS and the statement row are the same payment when the account, reference,
    direction and amount agree. The statement row is kept, so nothing is counted twice; the SMS
    adds what the statement did not print (some banks leave the VPA out of the narration)."""
    by_key: dict[tuple[str, str, str, int], _Pay] = {}
    for p in pays:
        if p.txn.ref_no:
            by_key.setdefault(((p.account["masked_number"] or "")[-4:], p.txn.ref_no, p.txn.direction, p.txn.amount_paise), p)
    for s in sms:
        if s.kind not in ("debit", "credit") or not s.ref_no or s.amount_paise is None or not s.account_last4:
            continue
        same = by_key.get((s.account_last4, s.ref_no, s.kind, s.amount_paise))
        if same is None:
            continue
        if s.vpa and not same.txn.vpa:
            same.txn = replace(same.txn, vpa=s.vpa)
        if s.counterparty and not same.txn.counterparty:
            same.txn = replace(same.txn, counterparty=s.counterparty)


def _pair_by_reference(pays: list[_Pay]) -> None:
    """A debit and a credit with the same reference and amount are one movement seen twice.

    On the same account the money came back: a reversal. On two of the user's accounts it is their
    own transfer, or the card bill being paid when the receiving account is a credit card."""
    groups: dict[tuple[str, int], list[_Pay]] = defaultdict(list)
    for p in pays:
        if p.txn.ref_no:
            groups[(p.txn.ref_no, p.txn.amount_paise)].append(p)
    for group in groups.values():
        debits = [p for p in group if p.txn.direction == "debit"]
        credits = [p for p in group if p.txn.direction == "credit"]
        if len(debits) != 1 or len(credits) != 1:
            continue
        debit, credit = debits[0], credits[0]
        if debit.account is credit.account:
            credit.reversal_of_id = debit.txn.txn_id
            credit.kind = "upi_reversal"
            debit.status = credit.status = "reversed"
            continue
        debit.transfer_pair_id, credit.transfer_pair_id = credit.txn.txn_id, debit.txn.txn_id
        if credit.on_card:
            debit.kind, credit.kind, debit.category, credit.category = "card_bill_pay", "card_payment_in", "card_payment", "card_payment"
        else:
            debit.kind, credit.kind, debit.category, credit.category = "self_out", "self_in", "self_transfer", "self_transfer"


def _link_groups(pays: list[_Pay], links: GroupLinks) -> None:
    open_rows: dict[tuple[str, int], list[_Pay]] = defaultdict(list)
    for p in pays:
        expense = links.expenses.get(p.txn.txn_id)
        if expense is not None:
            p.group_expense_id, p.group_id = expense[0], expense[1]
            if p.category is None and expense[2]:
                p.category = expense[2]
        elif p.category is None and not p.on_card and p.status == "success":
            open_rows[(p.txn.direction, p.txn.amount_paise)].append(p)
    for s in links.settlements:
        hits = [
            p for p in open_rows.get((s.direction, s.amount_paise), ())
            if p.settlement_id is None and (not p.name or _same_payee(p.name, s.other_name))
            and (s.at is None or abs(p.txn.occurred_at - s.at) <= _SETTLE_WINDOW)
        ]
        if hits:
            best = min(hits, key=lambda p: abs(p.txn.occurred_at - s.at) if s.at is not None else timedelta(0))
            best.settlement_id, best.group_id, best.category = s.settlement_id, s.group_id, "group_settlement"


def _day(text: str | None) -> date | None:
    return date.fromisoformat(text[:10]) if text else None


def _link_recurring(pays: list[_Pay], recurring: Sequence[Row]) -> dict[str, Row]:
    """Tie each debit to the bill, subscription, rent, EMI or SIP it pays.

    The payee decides (the merchant, or the name the user gave), then the kind of account, then
    the amount: the exact amount first, otherwise the item whose amount is nearest."""
    items = {str(r["key"]): r for r in recurring}
    for p in pays:
        t = p.txn
        if t.direction != "debit" or p.transfer_pair_id or p.settlement_id:
            continue
        local = t.occurred_at.date()
        found: list[tuple[int, float, float, str]] = []
        for key, r in items.items():
            amount = int(str(r["amount_paise"] or 0))
            if (r["channel"] == "card") != p.on_card:
                continue
            if r["merchant_key"]:
                if r["merchant_key"] != p.merchant_key:
                    continue
            elif r["payee"]:
                if not (_same_payee(p.name, str(r["payee"])) if p.name else _vpa_spells(t.vpa, str(r["payee"]))):
                    continue
            elif not (r["channel"] == "ach" and t.mode == "nach" and t.amount_paise == amount):
                continue  # an item with no payee on record (a loan EMI) is known only by its mandate and amount
            start, end = _day(r["start_date"]), _day(r["end_date"])
            if (start and local < start - timedelta(days=5)) or (end and local > end + timedelta(days=5)):
                continue
            ratio = t.amount_paise / amount if amount else 1.0
            fixed = str(r["amount_is_variable"]).lower() != "true"
            if fixed and not _AMOUNT_BAND[0] <= ratio <= _AMOUNT_BAND[1]:
                continue
            other_account = 0 if r["account_role"] in (None, p.account["role"]) else 1
            amount_off = abs(ratio - 1.0)
            due = int(str(r["day"])) if r["day"] else local.day
            days_off = min(abs(local.day - due), 31 - abs(local.day - due)) / 31
            # a fixed bill is known by its amount, a bill that changes every month by its day
            found.append((other_account, amount_off, days_off, key) if fixed else (other_account, days_off, amount_off, key))
        if found:
            p.recurring_key = min(found)[3]
    return items


def _regular_income(pays: list[_Pay], income_pattern: str | None) -> tuple[str, str] | None:
    """(payer, category) for the user's main regular income, by the channel that kind of income
    arrives on: the payer who sent the same amount in the most months (at least three), then the
    one who sent the most. None when it cannot be told."""
    rule = _INCOME.get(income_pattern or "")
    if rule is None:
        return None
    category, channels = rule
    total: dict[str, int] = defaultdict(int)
    months_by_amount: dict[str, dict[int, set[tuple[int, int]]]] = defaultdict(lambda: defaultdict(set))
    for p in pays:
        t = p.txn
        if t.direction == "credit" and not p.on_card and p.category is None and p.merchant_key is None and p.name and t.mode in channels:
            total[p.name] += t.amount_paise
            months_by_amount[p.name][t.amount_paise].add((t.occurred_at.year, t.occurred_at.month))
    steady = {name: max(len(months) for months in by_amount.values()) for name, by_amount in months_by_amount.items()}
    regular = [name for name, months in steady.items() if months >= _MIN_INCOME_MONTHS]
    return (max(regular, key=lambda name: (steady[name], total[name])), category) if regular else None


def _default_kind(p: _Pay, shop: bool) -> str:
    t = p.txn
    if t.mode == "autopay":
        return "autopay"
    if t.mode == "upi" and t.direction == "debit":
        if _BILLPAY.search(t.narration.upper()):
            return "billpay"
        return "upi_p2m" if shop else "upi_p2p_out"
    return KINDS.get((t.mode, t.direction), "netbanking" if t.direction == "debit" else "neft_in")


def _categorise(p: _Pay, *, items: Mapping[str, Row], categories: Mapping[str, Mapping[str, str | None]], owner_name: str,
                income_pattern: str | None, income: tuple[str, str] | None) -> tuple[str, str]:
    """(category, kind) for one row. The first rule that applies wins."""
    t = p.txn
    credit = t.direction == "credit"
    narration = t.narration.upper()
    if p.on_card and "FINANCE CHARGES" in narration:
        return "card_interest", "fin_charge_gst" if "GST" in narration else "fin_charge"
    if p.on_card and credit and p.name == "PAYMENT RECEIVED":
        return "card_payment", "card_payment_in"
    if not p.on_card and not credit and p.merchant_key is None and _FEES.search(narration):
        return "fees_charges", "charge"
    if t.mode == "atm":
        return "cash_withdrawal", "atm_wd"
    if t.mode == "interest":
        return "interest_income", "interest"
    if p.name.startswith("FD "):
        return "self_transfer", "fd_maturity" if credit else "fd_book"
    if t.mode == "cash" and credit:
        return "business_income" if income_pattern == "business" else "other_income", "cash_dep"
    if p.category is not None:  # a group expense or a settle-up: the group already says what it was
        return p.category, _default_kind(p, shop=p.merchant_key is not None)
    if p.recurring_key is not None:
        return str(items[p.recurring_key]["category"]), _default_kind(p, shop=p.merchant_key is not None)
    if t.is_self_transfer or (t.mode in _BANK_TRANSFER and _is_owner(p.name, owner_name)):
        return "self_transfer", "self_in" if credit else "self_out"

    if p.merchant_key is not None and p.merchant_category is not None:
        kind_of = (categories.get(p.merchant_category) or {}).get("kind")
        if not credit or kind_of == "income":
            return p.merchant_category, _default_kind(p, shop=True)
        if _REWARD.search(p.name):
            return "other_income", _default_kind(p, shop=True)
        if kind_of == "expense":  # money back from a shop
            return "refund", "card_refund" if p.on_card else _default_kind(p, shop=True)
        return "other_income", _default_kind(p, shop=True)

    if credit:
        if t.mode in _BANK_TRANSFER and _SALARY.search(narration):  # the employer's bank says so
            return "salary", _default_kind(p, shop=False)
        if income is not None and p.name == income[0]:
            return income[1], _default_kind(p, shop=False)
        return "other_income", _default_kind(p, shop=False)
    sells = _shop_category(p.name, income_pattern)
    return (sells, _default_kind(p, shop=True)) if sells else ("uncategorised", _default_kind(p, shop=False))


def _same_payee_same_category(pays: list[_Pay]) -> None:
    """A payee has one VPA however the bank prints their name ("SELVAM STORES" one day, "R SELVAM"
    the next), and a person the user pays a regular bill to is the same person on other days.
    A payment the rules could not place takes the category that payee has elsewhere. The payee is
    their VPA when one is known, and their name only when it is not: two people can share a name."""
    seen: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def payee(p: _Pay) -> str | None:
        if p.txn.vpa:
            return f"vpa:{p.txn.vpa.lower()}"
        return f"name:{p.name}" if p.name else None

    open_rows = []
    for p in pays:
        key = payee(p)
        if key is None or p.txn.direction != "debit" or p.on_card or p.transfer_pair_id or p.group_expense_id or p.settlement_id:
            continue
        if p.category == "uncategorised":
            open_rows.append((key, p))
        elif p.category is not None:
            seen[key][p.category] += 1
    for key, p in open_rows:
        if key in seen:
            p.category = max(seen[key].items(), key=lambda kv: (kv[1], kv[0]))[0]


def _link_refunds(pays: list[_Pay]) -> None:
    """A refund belongs to an earlier payment to the same merchant on the same account: the latest
    one of exactly that amount (a full refund), otherwise the latest one it fits inside. Which
    order a part refund was for is not in the feed, so that second choice is a best guess."""
    paid: dict[tuple[str, str], list[_Pay]] = defaultdict(list)
    taken: set[str] = set()
    for p in pays:
        if p.merchant_key is None:
            continue
        key = (str(p.account["account_id"]), p.merchant_key)
        if p.txn.direction == "debit" and p.status == "success":
            paid[key].append(p)
        elif p.category == "refund":
            recent = [old for old in paid[key] if old.txn.txn_id not in taken
                      and p.txn.occurred_at - old.txn.occurred_at <= _REFUND_WINDOW and old.txn.amount_paise >= p.txn.amount_paise]
            full = [old for old in recent if old.txn.amount_paise == p.txn.amount_paise]
            if recent:
                original = (full or recent)[-1]
                p.refund_of_id = original.txn.txn_id
                taken.add(original.txn.txn_id)


def _row(p: _Pay) -> Row:
    t = p.txn
    return {
        "txn_id": t.txn_id, "account_id": p.account["account_id"], "occurred_at": t.occurred_at.isoformat(),
        "value_date": t.value_date.isoformat() if t.value_date else None, "amount_paise": str(t.amount_paise),
        "direction": t.direction, "mode": t.mode, "status": p.status, "kind": p.kind, "merchant_key": p.merchant_key,
        "counterparty_name": t.counterparty, "counterparty_vpa": t.vpa, "category_id": p.category, "narration": t.narration,
        "ref_no": t.ref_no, "balance_after_paise": str(t.balance_paise) if t.balance_paise is not None else None,
        "recurring_key": p.recurring_key, "transfer_pair_id": p.transfer_pair_id, "reversal_of_id": p.reversal_of_id,
        "refund_of_id": p.refund_of_id, "group_expense_id": p.group_expense_id, "group_id": p.group_id,
        "settlement_id": p.settlement_id, "source": "aa",
    }


def load_feed(
    statements: Iterable[dict[str, Any]], *, accounts: Sequence[Row], recurring: Sequence[Row], merchants: MerchantIndex,
    categories: Mapping[str, Mapping[str, str | None]], owner_name: str, income_pattern: str | None,
    city: str | None = None, links: GroupLinks | None = None, sms: Iterable[ParsedSms] = (),
) -> list[Row]:
    """One user's ledger rows from their account statements, in time order.

    `accounts` and `recurring` are that user's rows in the dataset's shape; `categories` maps a
    category id to its row (`kind` is what the rules read); `sms` is the same period's bank SMS,
    already parsed."""
    pays = _read(statements, accounts)
    _merge_sms(pays, sms)
    home = f"local_{'_'.join((city or '').lower().split())}_"
    for p in pays:
        merchant = merchants.find(p.txn.counterparty, p.txn.vpa, p.txn.direction, p.txn.mode)
        if merchant is not None and merchant.is_local and city and not merchant.key.startswith(home) and (
            not p.txn.vpa or (merchant.vpa_pattern or "").lower() != p.txn.vpa.lower()
        ):
            merchant = None  # a neighbourhood shop of that name in another city is not this one
        if merchant is not None:
            p.merchant_key, p.merchant_category = merchant.key, merchant.category_id
    _pair_by_reference(pays)
    _link_groups(pays, links or GroupLinks())
    items = _link_recurring(pays, recurring)
    income = _regular_income(pays, income_pattern)
    by_id = {p.txn.txn_id: p for p in pays}
    for p in pays:
        if p.transfer_pair_id is None and p.reversal_of_id is None:
            p.category, p.kind = _categorise(p, items=items, categories=categories, owner_name=owner_name,
                                             income_pattern=income_pattern, income=income)
    _same_payee_same_category(pays)
    for p in pays:  # a reversal is filed with the payment it undoes
        if p.reversal_of_id is not None:
            original = by_id[p.reversal_of_id]
            p.category, p.merchant_key = original.category, original.merchant_key
    _link_refunds(pays)
    return [_row(p) for p in pays]
