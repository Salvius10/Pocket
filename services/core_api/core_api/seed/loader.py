"""Loads reference data and links a demo persona to a user.

Linking copies the persona's processed state (data/demo/db) for that user. Every id is remapped
with uuid5(user_id, original_id) so any number of people can link the same persona and change it
independently. budget_month, personal_amount_paise and spend_class are computed here, in code.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST, get_settings, today_ist
from core_api.ingest.feed import GroupLinks, Row, SettlementLink, load_feed
from core_api.ingest.pipeline import MerchantIndex
from core_api.ingest.sms import parse_sms
from core_api.ledger.classify import RECURRING_KIND_MAP, SALARY_CATEGORIES, next_due_date, spend_class
from core_api.ledger.mathx import budget_month_for

PERSONAS = ("student", "first_job", "family", "gig", "shop", "investor")
LEDGER_SOURCES = ("processed", "feed")
# `profile_facts.source` for what the user said to the mascot themselves (the persona's own lines are "onboarding").
TOLD_BY_USER = "mascot"

CATEGORY_I18N: dict[str, tuple[str, str, str]] = {
    # id: (hi, ta, emoji)  — agent-written translations, x-review (BUILD_PLAN H4)
    "salary": ("वेतन", "சம்பளம்", "💼"), "gig_payout": ("गिग कमाई", "கிக் வருமானம்", "🛵"),
    "business_income": ("दुकान की आय", "வியாபார வருமானம்", "🏪"), "allowance": ("जेब खर्च", "கைச்செலவு பணம்", "🎒"),
    "interest_income": ("ब्याज", "வட்டி", "🏦"), "other_income": ("अन्य आय", "பிற வருமானம்", "➕"),
    "refund": ("रिफंड", "ரீஃபண்ட்", "↩️"), "self_transfer": ("अपने खातों में", "சொந்த கணக்கு மாற்றம்", "🔁"),
    "card_payment": ("कार्ड बिल भुगतान", "கார்டு பில் கட்டணம்", "💳"),
    "group_settlement": ("ग्रुप हिसाब", "குழு கணக்கு", "🤝"), "investment": ("निवेश", "முதலீடு", "📈"),
    "rent": ("किराया", "வாடகை", "🏠"), "emi": ("ईएमआई", "இஎம்ஐ", "🧾"),
    "utilities": ("बिजली व बिल", "மின்சாரம் & பில்கள்", "💡"), "mobile_internet": ("मोबाइल व इंटरनेट", "மொபைல் & இணையம்", "📱"),
    "insurance": ("बीमा", "காப்பீடு", "🛡️"), "education": ("पढ़ाई व फीस", "கல்வி & கட்டணம்", "🎓"),
    "subscriptions": ("सब्सक्रिप्शन", "சந்தாக்கள்", "🔄"), "groceries": ("किराना", "மளிகை", "🛒"),
    "food_delivery": ("फूड डिलीवरी", "உணவு டெலிவரி", "🍔"), "eating_out": ("बाहर खाना", "வெளியே சாப்பாடு", "🍽️"),
    "transport": ("सफर व कैब", "பயணம் & கேப்", "🚕"), "fuel": ("पेट्रोल", "எரிபொருள்", "⛽"),
    "shopping": ("खरीदारी", "ஷாப்பிங்", "🛍️"), "entertainment": ("मनोरंजन", "பொழுதுபோக்கு", "🎬"),
    "health": ("सेहत", "உடல்நலம்", "💊"), "personal_care": ("पर्सनल केयर", "தனிப்பட்ட பராமரிப்பு", "✂️"),
    "home_services": ("घर की सेवाएँ", "வீட்டு சேவைகள்", "🧹"), "travel": ("यात्रा", "சுற்றுலா", "🧳"),
    "family_support": ("परिवार को मदद", "குடும்ப உதவி", "🤲"), "gifts_donations": ("उपहार व दान", "பரிசு & நன்கொடை", "🎁"),
    "fees_charges": ("बैंक शुल्क", "வங்கி கட்டணம்", "🏧"), "card_interest": ("कार्ड ब्याज", "கார்டு வட்டி", "🔥"),
    "cash_withdrawal": ("नकद निकासी", "பணம் எடுத்தல்", "💵"), "business_supplies": ("दुकान का माल", "கடை சரக்கு", "📦"),
    "business_expenses": ("दुकान के खर्च", "வியாபார செலவு", "🧰"), "other_expense": ("अन्य", "பிற", "•"),
    "uncategorised": ("बिना श्रेणी", "வகைப்படுத்தாதது", "❓"),
}


def _read_csv(path: Path) -> list[dict[str, str | None]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: (v if v != "" else None) for k, v in row.items()} for row in csv.DictReader(f)]


def _i(v: str | None) -> int | None:
    return int(v) if v is not None else None


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v[:10]) if v else None


def _ts(v: str | None) -> datetime | None:
    if not v:
        return None
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(UTC)


def _b(v: str | None) -> bool:
    return str(v).lower() in ("true", "t", "1")


class DemoData:
    """The shipped dataset, read once and held in memory (about 7k transactions)."""

    def __init__(self, root: Path, dataset: str = "demo", skip: tuple[str, ...] = ()) -> None:
        """`dataset` is the folder under data/ ("demo" or "eval"). Tables named in `skip`, and tables
        the dataset does not ship, load as empty (the eval set is too big to hold its transactions)."""
        ref, db = root / "reference", root / dataset / "db"

        def table_rows(name: str) -> list[dict[str, str | None]]:
            path = db / f"{name}.csv"
            return _read_csv(path) if name not in skip and path.exists() else []

        self.db_dir = db
        self.categories = _read_csv(ref / "categories.csv")
        self.merchants = _read_csv(ref / "merchants.csv")
        self.funds = _read_csv(ref / "funds.csv")
        self.nav = _read_csv(ref / "nav_history_synthetic.csv")
        self.all_users = _read_csv(db / "users.csv")
        self.users = {u["persona_id"]: u for u in self.all_users if u["persona_id"]}
        self.by_user: dict[str, dict[str, list[dict[str, str | None]]]] = defaultdict(lambda: defaultdict(list))
        for table in ("accounts", "transactions", "recurring_items", "loans", "holdings", "pockets", "goals",
                      "goal_contributions", "profile_facts", "planted_patterns", "card_statements"):
            for row in table_rows(table):
                self.by_user[str(row["user_id"])][table].append(row)
        self.groups = table_rows("groups")
        self.by_group: dict[str, dict[str, list[dict[str, str | None]]]] = defaultdict(lambda: defaultdict(list))
        for table in ("group_members", "group_expenses", "group_pot_contributions", "settlements", "group_invites"):
            for row in table_rows(table):
                self.by_group[str(row["group_id"])][table].append(row)
        self.shares_by_expense: dict[str, list[dict[str, str | None]]] = defaultdict(list)
        for row in table_rows("group_expense_shares"):
            self.shares_by_expense[str(row["expense_id"])].append(row)
        self.category_map = {str(c["category_id"]): c for c in self.categories}
        self.merchant_map = {str(x["merchant_key"]): x for x in self.merchants}


@lru_cache
def demo_data() -> DemoData:
    return DemoData(get_settings().data_path)


def category_models(data: DemoData) -> list[m.Category]:
    return [
        m.Category(
            id=str(c["category_id"]), kind=str(c["kind"]), default_class=str(c["default_class"]),
            name_en=str(c["name_en"]),
            name_hi=CATEGORY_I18N.get(str(c["category_id"]), ("", "", ""))[0],
            name_ta=CATEGORY_I18N.get(str(c["category_id"]), ("", "", ""))[1],
            emoji=CATEGORY_I18N.get(str(c["category_id"]), ("", "", ""))[2],
        )
        for c in data.categories
    ]


def merchant_models(data: DemoData) -> list[m.Merchant]:
    return [
        m.Merchant(
            key=str(x["merchant_key"]), name=str(x["name"]), narration_name=x["narration_name"] or "",
            category_id=str(x["category_id"]), subcategory=x["subcategory"], vpa_pattern=x["vpa_pattern"],
            is_subscription_likely=_b(x["is_subscription_likely"]), is_local=_b(x["is_local"]),
            aliases=x["aliases"] or "",
        )
        for x in data.merchants
    ]


async def seed_reference(session: AsyncSession) -> None:
    """Idempotent: categories, merchants and NAV history."""
    data = demo_data()
    if (await session.execute(select(m.Category.id).limit(1))).first() is None:
        session.add_all(category_models(data))
    if (await session.execute(select(m.Merchant.key).limit(1))).first() is None:
        session.add_all(merchant_models(data))
    if (await session.execute(select(m.NavPrice.scheme_code).limit(1))).first() is None:
        await session.execute(
            insert(m.NavPrice),
            [
                {"scheme_code": int(str(r["scheme_code"])), "nav_date": _d(r["nav_date"]),
                 "nav": Decimal(str(r["nav"])), "source": r["source"] or "synthetic_backfill"}
                for r in data.nav
            ],
        )
    await session.commit()


def _title_case(name: str) -> str:
    return " ".join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in name.split())


async def wipe_user_data(session: AsyncSession, user_id: str) -> None:
    group_ids = list((await session.execute(select(m.Group.id).where(m.Group.owner_user_id == user_id))).scalars())
    if group_ids:
        group_tables: tuple[Any, ...] = (m.GroupInvite, m.Settlement, m.GroupPotContribution, m.GroupExpenseShare, m.GroupExpense, m.GroupMember)
        for gt in group_tables:
            await session.execute(delete(gt).where(gt.group_id.in_(group_ids)))
        await session.execute(delete(m.Group).where(m.Group.id.in_(group_ids)))
    await session.execute(delete(m.GroupMember).where(m.GroupMember.user_id == user_id))
    user_tables: tuple[Any, ...] = m.USER_TABLES
    for ut in user_tables:
        await session.execute(delete(ut).where(ut.user_id == user_id))


@dataclass
class UserRows:
    """One dataset user's rows shaped as app rows: plain dicts, ready to insert or to wrap in models."""

    accounts: list[dict[str, Any]]
    recurring: list[dict[str, Any]]
    txns: list[dict[str, Any]]
    loans: list[dict[str, Any]]
    holdings: list[dict[str, Any]]
    pockets: list[dict[str, Any]]
    goals: list[dict[str, Any]]
    contributions: list[dict[str, Any]]
    facts: list[dict[str, Any]]
    planted: list[dict[str, Any]]
    statements: list[dict[str, Any]]
    my_groups: list[dict[str, str | None]]


def feed_statements(data: DemoData, persona_id: str) -> list[dict[str, Any]]:
    """A demo persona's account statements, as the Account Aggregator would return them."""
    folder = data.db_dir.parent / "sources" / persona_id / "account_aggregator"
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def group_links(data: DemoData, src_uid: str) -> GroupLinks:
    """What the user's own groups say about their bank rows: which payment an expense was split
    from, and which settle-ups they marked as paid."""
    expenses: dict[str, tuple[str, str, str | None]] = {}
    settlements: list[SettlementLink] = []
    for g in data.groups:
        gdata = data.by_group[str(g["group_id"])]
        names = {mm["member_id"]: str(mm["display_name"] or "") for mm in gdata["group_members"]}
        me = next((mm["member_id"] for mm in gdata["group_members"] if mm["user_id"] == src_uid), None)
        if me is None:  # not one of this user's groups
            continue
        for e in gdata["group_expenses"]:
            if e["linked_transaction_id"] and e["paid_by_member_id"] == me and not _b(e["is_deleted"]):
                expenses[str(e["linked_transaction_id"])] = (str(e["expense_id"]), str(g["group_id"]), e["category_id"])
        for s in gdata["settlements"]:
            if s["status"] not in ("marked_paid", "confirmed") or me not in (s["from_member_id"], s["to_member_id"]):
                continue
            paid_by_me = s["from_member_id"] == me
            settlements.append(SettlementLink(
                settlement_id=str(s["settlement_id"]), group_id=str(g["group_id"]), amount_paise=_i(s["amount_paise"]) or 0,
                direction="debit" if paid_by_me else "credit",
                other_name=names.get(s["to_member_id"] if paid_by_me else s["from_member_id"], ""),
                at=_ts(s["marked_paid_at"]) or _ts(s["created_at"]),
            ))
    return GroupLinks(expenses, settlements)


def feed_sms(data: DemoData, persona_id: str) -> list[dict[str, Any]]:
    """A demo persona's bank SMS for the same period: `{sender_id, body, received_at, ...}` per message."""
    path = data.db_dir.parent / "sources" / persona_id / "sms.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def feed_transactions(data: DemoData, src_uid: str, statements: list[dict[str, Any]], merchants: MerchantIndex,
                      sms: Iterable[dict[str, Any]] = (), *, given_bills: bool = True) -> list[Row]:
    """Dataset user `src_uid`'s transactions worked out from their account statements and bank SMS
    (`ingest/feed.py`), in the shape of `transactions.csv`. Besides the feed, the loader is given the
    user's set-up: accounts, groups, how they earn, and their list of recurring items.

    The dataset marks `recurring_items` (and `accounts.role`, which it refers to) as labels: it is
    what a recurring detector should find. The app has no such detector and loads the list as the
    user's bills, so the loader is given it too. `given_bills=False` withholds it, to measure what
    the loader does from the feed alone."""
    rows = data.by_user[src_uid]
    user = next(u for u in data.all_users if u["user_id"] == src_uid)
    known = {str(a["masked_number"])[-4:] for a in rows["accounts"] if a["masked_number"]}
    parsed = (parse_sms(str(s["sender_id"]), str(s["body"]), datetime.fromisoformat(str(s["received_at"])), known) for s in sms)
    return load_feed(
        statements, accounts=rows["accounts"], recurring=rows["recurring_items"] if given_bills else [], merchants=merchants,
        categories=data.category_map, owner_name=str(user["display_name"] or ""), income_pattern=user["income_pattern"],
        city=user["city"], links=group_links(data, src_uid), sms=parsed,
    )


@lru_cache
def demo_merchant_index() -> MerchantIndex:
    return MerchantIndex(merchant_models(demo_data()))


def ledger_source() -> str:
    """The configured source of a persona's transactions. An unknown value fails loudly."""
    source = get_settings().ledger_source
    if source not in LEDGER_SOURCES:
        raise ValueError(f"LEDGER_SOURCE must be one of {LEDGER_SOURCES}, not {source!r}")
    return source


def check_ledger_source() -> None:
    """Called at start-up: with the feed as the source, every persona's statements and SMS must be on disk.
    Failing here stops a deploy that left them out, instead of failing when someone links a persona."""
    if ledger_source() != "feed":
        return
    data = demo_data()
    for persona_id in PERSONAS:
        folder = data.db_dir.parent / "sources" / persona_id
        if not any((folder / "account_aggregator").glob("*.json")) or not (folder / "sms.jsonl").exists():
            raise RuntimeError(f"LEDGER_SOURCE=feed but {folder} has no account statements or SMS. "
                               "Ship data/demo/sources, or set LEDGER_SOURCE=processed.")


@lru_cache(maxsize=len(PERSONAS))
def persona_feed_rows(persona_id: str) -> tuple[Row, ...]:
    """A persona's transactions from their statements and SMS. The same for everyone who links that
    persona (ids are remapped per user afterwards), so they are worked out once and kept."""
    data = demo_data()
    src_uid = str(data.users[persona_id]["user_id"])
    return tuple(feed_transactions(data, src_uid, feed_statements(data, persona_id), demo_merchant_index(), feed_sms(data, persona_id)))


def build_user_rows(data: DemoData, src_uid: str, user_id: str, today: date, nid: Callable[[str | None], str | None],
                    txn_rows: list[Row] | None = None) -> UserRows:
    """Pure (no database): shape dataset user `src_uid`'s rows for app user `user_id`.

    `nid` maps dataset ids to this user's ids. Linking a persona remaps them with uuid5; the evals
    pass an identity function so the ids still match the dataset's answer key. `txn_rows` replaces
    the dataset's processed transactions (the feed loader's rows, or one streamed user's)."""
    rows = data.by_user[src_uid]
    ns = UUID(user_id)

    # --- accounts ---
    accounts = [
        {
            "id": nid(a["account_id"]), "user_id": user_id, "institution": a["institution_name"],
            "institution_code": a["institution_code"], "type": a["type"], "masked_number": a["masked_number"] or "",
            "nickname": a["nickname"], "role": a["role"], "balance_paise": _i(a["current_balance_paise"]) or 0,
            "balance_as_of": _ts(a["balance_as_of"]), "credit_limit_paise": _i(a["credit_limit_paise"]),
            "interest_rate_bps": _i(a["interest_rate_bps"]), "statement_day": _i(a["statement_day"]),
            "due_day": _i(a["due_day"]),
        }
        for a in rows["accounts"]
    ]

    # --- recurring items (app kinds) ---
    rec_id_by_key: dict[str, str] = {}
    rec_kind_by_key: dict[str, str] = {}
    recurring: list[dict[str, Any]] = []
    for r in rows["recurring_items"]:
        rid = str(uuid5(ns, f"recurring:{r['key']}"))
        key = str(r["key"])
        rec_id_by_key[key] = rid
        rec_kind_by_key[key] = RECURRING_KIND_MAP.get(str(r["kind"]), "bill")
        recurring.append(
            {
                "id": rid, "user_id": user_id, "key": key, "kind": rec_kind_by_key[key], "source_kind": r["kind"],
                "name": r["name"], "category": r["category"], "cadence": r["cadence"], "day": _i(r["day"]),
                "channel": r["channel"], "merchant": r["merchant_key"], "payee": r["payee"],
                "amount_paise": _i(r["amount_paise"]) or 0, "amount_is_variable": _b(r["amount_is_variable"]),
                "start_date": _d(r["start_date"]), "end_date": _d(r["end_date"]), "next_due_date": None,
                "status": "active",
            }
        )

    # --- group shares this user owes, so split transactions count only the user's part ---
    my_share_by_expense: dict[str, int] = {}
    my_groups = [g for g in data.groups if g["owner_user_id"] == src_uid]
    for g in my_groups:
        gdata = data.by_group[str(g["group_id"])]
        me = next((mm for mm in gdata["group_members"] if mm["user_id"] == src_uid), None)
        if me is None:
            continue
        for e in gdata["group_expenses"]:
            for s in data.shares_by_expense[str(e["expense_id"])]:
                if s["member_id"] == me["member_id"]:
                    my_share_by_expense[str(e["expense_id"])] = int(str(s["share_paise"]))

    # --- transactions ---
    last_paid: dict[str, list[date]] = defaultdict(list)
    txns: list[dict[str, Any]] = []
    for t in rows["transactions"] if txn_rows is None else txn_rows:
        occurred = _ts(t["occurred_at"])
        assert occurred is not None
        local = occurred.astimezone(IST).date()
        cat_id = t["category_id"] or "uncategorised"
        cat = data.category_map.get(cat_id, {"kind": "expense", "default_class": "flexible"})
        rkey = t["recurring_key"]
        rkind = rec_kind_by_key.get(rkey) if rkey else None
        amount = int(str(t["amount_paise"]))
        is_reversal = t["reversal_of_id"] is not None or t["kind"] == "upi_reversal"
        sc = spend_class(
            status=str(t["status"]), hidden=False, is_reversal=is_reversal,
            category_kind=str(cat["kind"]), category_default_class=str(cat["default_class"]), recurring_kind=rkind,
        )
        personal = amount
        if t["group_expense_id"] and str(t["group_expense_id"]) in my_share_by_expense:
            personal = min(amount, my_share_by_expense[str(t["group_expense_id"])])
        merchant = data.merchant_map.get(t["merchant_key"] or "")
        name = str(merchant["name"]) if merchant else _title_case(t["counterparty_name"] or "") or str(t["kind"] or "")
        if rkey and sc != "excluded" and t["direction"] == "debit":
            last_paid[rkey].append(local)
        txns.append(
            {
                "id": nid(t["txn_id"]), "user_id": user_id, "account_id": nid(t["account_id"]),
                "occurred_at": occurred, "local_date": local,
                "budget_month": budget_month_for(local, cat_id in SALARY_CATEGORIES),
                "amount_paise": amount, "personal_amount_paise": personal, "direction": t["direction"],
                "mode": {"interest": "other"}.get(str(t["mode"]), t["mode"]), "status": t["status"], "kind": t["kind"],
                "merchant": t["merchant_key"], "merchant_name": name, "counterparty_name": t["counterparty_name"],
                "counterparty_vpa": t["counterparty_vpa"], "category": cat_id, "spend_class": sc,
                "narration": t["narration"] or "", "ref_no": t["ref_no"],
                "balance_after_paise": _i(t["balance_after_paise"]),
                "recurring_item_id": rec_id_by_key.get(rkey) if rkey else None,
                "transfer_pair_id": nid(t["transfer_pair_id"]), "reversal_of_id": nid(t["reversal_of_id"]),
                "refund_of_id": nid(t["refund_of_id"]), "group_expense_id": nid(t["group_expense_id"]),
                "group_id": nid(t["group_id"]), "settlement_id": nid(t["settlement_id"]),
                "source": t["source"] or "aa", "hidden": False, "note": None, "updated_at": datetime.now(UTC),
            }
        )

    for rec in recurring:
        paid = sorted(last_paid.get(rec["key"], []))
        gaps = [(b - a).days for a, b in zip(paid, paid[1:], strict=False)]
        rec["next_due_date"] = next_due_date(
            cadence=rec["cadence"], day=rec["day"], start_date=rec["start_date"], end_date=rec["end_date"],
            last_paid=paid[-1] if paid else None,
            typical_gap_days=sorted(gaps)[len(gaps) // 2] if gaps else None, today=today,
        )
        if rec["end_date"] is not None and rec["end_date"] < today:
            rec["status"] = "ended"

    loans = [
        {
            "id": str(uuid5(ns, f"loan:{ln['key']}")), "user_id": user_id, "key": ln["key"], "lender": ln["lender"],
            "loan_type": ln["loan_type"], "rate_type": ln["rate_type"], "principal_paise": _i(ln["principal_paise"]),
            "outstanding_paise": _i(ln["outstanding_paise"]), "interest_rate_bps": _i(ln["interest_rate_bps"]),
            "tenure_months": _i(ln["tenure_months"]), "emi_paise": _i(ln["emi_paise"]), "emi_day": _i(ln["emi_day"]),
            "start_date": _d(ln["start_date"]), "end_date": _d(ln["end_date"]), "emis_paid": _i(ln["emis_paid"]) or 0,
            "months_left": _i(ln["months_left"]) or 0, "zero_cost_emi": _b(ln["zero_cost_emi"]),
        }
        for ln in rows["loans"]
    ]
    holdings = [
        {
            "id": str(uuid5(ns, f"holding:{i}")), "user_id": user_id, "kind": h["kind"], "name": h["name"],
            "scheme_code": _i(h["scheme_code"]), "units": Decimal(h["units"]) if h["units"] else None,
            "invested_paise": _i(h["invested_paise"]), "sip_amount_paise": _i(h["sip_amount_paise"]),
            "sip_day": _i(h["sip_day"]), "folio_masked": h["folio_masked"],
            "fd_principal_paise": _i(h["fd_principal_paise"]), "fd_rate_bps": _i(h["fd_rate_bps"]),
            "fd_start_date": _d(h["fd_start_date"]), "fd_maturity_date": _d(h["fd_maturity_date"]),
            "gold_grams": Decimal(h["gold_grams"]) if h["gold_grams"] else None,
            "balance_paise": _i(h["balance_paise"]), "balance_as_of": _d(h["balance_as_of"]),
        }
        for i, h in enumerate(rows["holdings"])
    ]
    pockets = [
        {
            "id": nid(p["pocket_id"]), "user_id": user_id, "name": p["name"], "emoji": p["emoji"] or "",
            "monthly_limit_paise": _i(p["monthly_limit_paise"]) or 0,
            "category_ids": (p["category_ids"] or "").split("|") if p["category_ids"] else [],
            "status": p["status"] or "active", "sort_order": _i(p["sort_order"]) or 0, "created_by": "loader",
            "created_at": datetime.now(UTC),
        }
        for p in rows["pockets"]
    ]
    goals = [
        {
            "id": nid(g["goal_id"]), "user_id": user_id, "name": g["name"], "emoji": g["emoji"] or "",
            "target_paise": _i(g["target_paise"]) or 0, "deadline": _d(g["deadline"]),
            "monthly_plan_paise": _i(g["monthly_plan_paise"]), "priority": _i(g["priority"]) or 0,
            "status": g["status"] or "active", "created_by": "loader", "created_at": datetime.now(UTC),
        }
        for g in rows["goals"]
    ]
    contributions = [
        {
            "id": str(uuid5(ns, f"contrib:{i}")), "user_id": user_id, "goal_id": nid(c["goal_id"]),
            "amount_paise": _i(c["amount_paise"]) or 0, "month": str(c["month"])[:7], "source": "loader",
            "note": c["note"], "proposal_id": None, "created_at": datetime.now(UTC),
        }
        for i, c in enumerate(rows["goal_contributions"])
    ]
    facts = [
        {"id": str(uuid5(ns, f"fact:{f['key']}")), "user_id": user_id, "key": f["key"], "value": f["value"] or "",
         "source": f["source"] or "onboarding", "language": f["language"]}
        for f in rows["profile_facts"]
    ]
    planted = [
        {"id": str(uuid5(ns, f"planted:{p['natural_key']}")), "user_id": user_id, "pattern_type": p["pattern_type"],
         "natural_key": _remap_natural_key(str(p["natural_key"]), nid),
         "data": {k: v for k, v in p.items() if v is not None and k not in ("user_id",)}}
        for p in rows["planted_patterns"]
    ]
    statements = [
        {"id": str(uuid5(ns, f"stmt:{s['account_id']}:{s['statement_date']}")), "user_id": user_id,
         "account_id": nid(s["account_id"]), "statement_date": _d(s["statement_date"]), "due_date": _d(s["due_date"]),
         "total_due_paise": _i(s["total_due_paise"]) or 0, "min_due_paise": _i(s["min_due_paise"]) or 0,
         "paid_paise": _i(s["paid_paise"]), "finance_charges_paise": _i(s["finance_charges_paise"]) or 0}
        for s in rows["card_statements"]
    ]

    return UserRows(accounts, recurring, txns, loans, holdings, pockets, goals, contributions, facts, planted, statements, my_groups)


async def link_persona(session: AsyncSession, user: m.User, persona_id: str) -> dict[str, int]:
    """Replace the user's data with a fresh copy of the persona. Returns row counts."""
    if persona_id not in PERSONAS:
        raise ValueError(f"unknown persona: {persona_id}")
    data = demo_data()
    src_user = data.users[persona_id]
    src_uid = str(src_user["user_id"])
    ns = UUID(user.id)
    today = today_ist()

    def nid(old: str | None) -> str | None:
        return str(uuid5(ns, old)) if old else None

    # What this person told the mascot is theirs, not the persona's: keep it across the wipe.
    told = [
        {"key": f.key, "value": f.value, "language": f.language}
        for f in (await session.execute(
            select(m.ProfileFact).where(m.ProfileFact.user_id == user.id, m.ProfileFact.source == TOLD_BY_USER)
        )).scalars()
    ]
    await wipe_user_data(session, user.id)

    user.persona_id = persona_id
    user.display_name = str(src_user["display_name"])
    user.first_name = str(src_user["first_name"])
    user.income_pattern = src_user["income_pattern"]
    user.city = src_user["city"]
    user.occupation = src_user["occupation"]
    user.data_version = (user.data_version or 0) + 1

    txn_rows = list(persona_feed_rows(persona_id)) if ledger_source() == "feed" else None
    built = build_user_rows(data, src_uid, user.id, today, nid, txn_rows)
    my_groups = built.my_groups
    # Their own words replace the persona's line for the same thing (what they save for, what worries them).
    told_keys = {row["key"] for row in told}
    facts = [f for f in built.facts if f["key"] not in told_keys] + [
        {"id": str(uuid5(ns, f"told:{row['key']}")), "user_id": user.id, "key": row["key"], "value": row["value"],
         "source": TOLD_BY_USER, "language": row["language"]}
        for row in told
    ]

    for table, payload in (
        (m.Account, built.accounts), (m.RecurringItem, built.recurring), (m.Transaction, built.txns), (m.Loan, built.loans),
        (m.Holding, built.holdings), (m.Pocket, built.pockets), (m.Goal, built.goals), (m.GoalContribution, built.contributions),
        (m.ProfileFact, facts), (m.PlantedPattern, built.planted), (m.CardStatement, built.statements),
    ):
        for chunk_start in range(0, len(payload), 500):
            await session.execute(insert(table), payload[chunk_start : chunk_start + 500])

    # --- groups this persona owns ---
    n_groups = 0
    for g in my_groups:
        gid = nid(g["group_id"])
        gdata = data.by_group[str(g["group_id"])]
        await session.execute(
            insert(m.Group),
            [{"id": gid, "type": g["type"], "name": g["name"], "emoji": g["emoji"] or "", "owner_user_id": user.id,
              "budget_monthly_paise": _i(g["budget_monthly_paise"]), "pot_target_paise": _i(g["pot_target_paise"]),
              "pot_deadline": _d(g["pot_deadline"]), "status": g["status"] or "active",
              "created_at": datetime.combine(_d(g["created_at"]) or today, datetime.min.time(), tzinfo=UTC)}],
        )
        members = [
            {"id": nid(mm["member_id"]), "group_id": gid, "user_id": user.id if mm["user_id"] == src_uid else None,
             "display_name": mm["display_name"], "vpa": mm["vpa"],
             "role": "owner" if mm["user_id"] == src_uid else "guest", "join_order": _i(mm["join_order"]) or 0,
             "sharing": json.loads(mm["sharing"]) if mm["sharing"] else {}}
            for mm in gdata["group_members"]
        ]
        expenses: list[dict[str, Any]] = []
        shares: list[dict[str, Any]] = []
        for e in gdata["group_expenses"]:
            eid = nid(e["expense_id"])
            split_input = json.loads(e["split_input"]) if e["split_input"] else {}
            expenses.append(
                {"id": eid, "group_id": gid, "paid_by_member_id": nid(e["paid_by_member_id"]),
                 "amount_paise": _i(e["amount_paise"]) or 0, "description": e["description"] or "",
                 "category": e["category_id"], "occurred_at": _ts(e["occurred_at"]), "split_method": e["split_method"],
                 "split_input": _remap_split_input(split_input, nid),
                 "linked_transaction_id": nid(e["linked_transaction_id"]),
                 "created_by_member_id": nid(e["created_by_member_id"]), "is_deleted": _b(e["is_deleted"])}
            )
            shares.extend(
                {"expense_id": eid, "member_id": nid(s["member_id"]), "group_id": gid,
                 "share_paise": int(str(s["share_paise"]))}
                for s in data.shares_by_expense[str(e["expense_id"])]
            )
        pots = [
            {"id": nid(p["id"]), "group_id": gid, "member_id": nid(p["member_id"]), "amount_paise": _i(p["amount_paise"]) or 0,
             "method": p["method"] or "upi", "note": p["note"], "occurred_at": _ts(p["occurred_at"])}
            for p in gdata["group_pot_contributions"]
        ]
        settlements = [
            {"id": nid(s["settlement_id"]), "group_id": gid, "from_member_id": nid(s["from_member_id"]),
             "to_member_id": nid(s["to_member_id"]), "amount_paise": _i(s["amount_paise"]) or 0, "status": s["status"],
             "upi_link": s["upi_link"], "created_by_member_id": nid(s["created_by_member_id"]),
             "created_at": _ts(s["created_at"]), "marked_paid_at": _ts(s["marked_paid_at"]),
             "confirmed_at": _ts(s["confirmed_at"])}
            for s in gdata["settlements"]
        ]
        group_rows: tuple[tuple[Any, list[dict[str, Any]]], ...] = (
            (m.GroupMember, members), (m.GroupExpense, expenses), (m.GroupExpenseShare, shares),
            (m.GroupPotContribution, pots), (m.Settlement, settlements),
        )
        for g_table, g_payload in group_rows:
            for chunk_start in range(0, len(g_payload), 500):
                await session.execute(insert(g_table), g_payload[chunk_start : chunk_start + 500])
        n_groups += 1

    if (await session.get(m.UserSettings, user.id)) is None:
        session.add(m.UserSettings(user_id=user.id))
    await session.flush()
    return {"accounts": len(built.accounts), "transactions": len(built.txns), "recurring": len(built.recurring), "groups": n_groups}


def _remap_natural_key(key: str, nid: Any) -> str:
    """Planted keys embed transaction/account ids (dup:<txn>, idle:<account>:<month>); remap those."""
    parts = key.split(":")
    out = []
    for p in parts:
        out.append(nid(p) if len(p) == 36 and p.count("-") == 4 else p)
    return ":".join(out)


def _remap_split_input(split_input: dict[str, Any], nid: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in split_input.items():
        if isinstance(v, list):
            out[k] = [nid(x) for x in v]
        elif isinstance(v, dict):
            out[k] = {nid(mk): mv for mk, mv in v.items()}
        else:
            out[k] = v
    return out


def persona_cards() -> list[dict[str, Any]]:
    """What the persona picker shows (no money values)."""
    data = demo_data()
    return [
        {"persona_id": p, "first_name": data.users[p]["first_name"], "display_name": data.users[p]["display_name"],
         "age": _i(data.users[p]["age"]), "city": data.users[p]["city"], "language": data.users[p]["language"],
         "occupation": data.users[p]["occupation"], "household": data.users[p]["household"],
         "income_pattern": data.users[p]["income_pattern"]}
        for p in PERSONAS
    ]


def data_end() -> date:
    return date.fromisoformat(str(demo_data().users["student"]["data_end"]))


_ = (timedelta, NAMESPACE_URL)  # re-exported for callers that build ids
