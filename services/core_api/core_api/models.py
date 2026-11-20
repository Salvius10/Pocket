"""Every table in ARCHITECTURE.md §5. Money is bigint `*_paise`; times are timestamptz (UTC)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core_api.config import now_utc
from core_api.db import UTCDateTime


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


def _uuid() -> str:
    return str(uuid4())


def pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=_uuid)


def user_fk() -> Mapped[str]:
    return mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)


def created() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=now_utc)


Paise = BigInteger


# ---------- people ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = pk()
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    first_name: Mapped[str] = mapped_column(String(60), default="")
    language: Mapped[str] = mapped_column(String(4), default="en")
    mascot_voice: Mapped[str] = mapped_column(String(40), default="warm")
    persona_id: Mapped[str | None] = mapped_column(String(20))
    income_pattern: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(60))
    occupation: Mapped[str | None] = mapped_column(String(120))
    onboarding_step: Mapped[str] = mapped_column(String(20), default="language")
    data_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created()


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nudge_daily_max: Mapped[int] = mapped_column(Integer, default=2)
    quiet_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="08:00")
    mute_voice: Mapped[bool] = mapped_column(Boolean, default=False)


class ProfileFact(Base):
    __tablename__ = "profile_facts"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    key: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="onboarding")
    language: Mapped[str | None] = mapped_column(String(4))


# ---------- reference ----------
class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))
    default_class: Mapped[str] = mapped_column(String(12))
    name_en: Mapped[str] = mapped_column(String(60))
    name_hi: Mapped[str] = mapped_column(String(80), default="")
    name_ta: Mapped[str] = mapped_column(String(80), default="")
    emoji: Mapped[str] = mapped_column(String(8), default="")


class Merchant(Base):
    __tablename__ = "merchants"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    narration_name: Mapped[str] = mapped_column(String(160), default="")
    category_id: Mapped[str] = mapped_column(String(40))
    subcategory: Mapped[str | None] = mapped_column(String(40))
    vpa_pattern: Mapped[str | None] = mapped_column(String(120))
    is_subscription_likely: Mapped[bool] = mapped_column(Boolean, default=False)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    aliases: Mapped[str] = mapped_column(Text, default="")


class NavPrice(Base):
    __tablename__ = "nav_prices"
    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    nav_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Any] = mapped_column(Numeric(16, 4))
    source: Mapped[str] = mapped_column(String(24), default="amfi")


# ---------- ledger ----------
class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    institution: Mapped[str] = mapped_column(String(80))
    institution_code: Mapped[str | None] = mapped_column(String(12))
    type: Mapped[str] = mapped_column(String(16))  # savings/current/credit_card/loan/wallet/cash
    masked_number: Mapped[str] = mapped_column(String(24), default="")
    nickname: Mapped[str | None] = mapped_column(String(60))
    role: Mapped[str | None] = mapped_column(String(16))
    balance_paise: Mapped[int] = mapped_column(Paise, default=0)
    balance_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime)
    credit_limit_paise: Mapped[int | None] = mapped_column(Paise)
    interest_rate_bps: Mapped[int | None] = mapped_column(Integer)
    statement_day: Mapped[int | None] = mapped_column(Integer)
    due_day: Mapped[int | None] = mapped_column(Integer)


class CardStatement(Base):
    __tablename__ = "card_statements"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    statement_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    total_due_paise: Mapped[int] = mapped_column(Paise)
    min_due_paise: Mapped[int] = mapped_column(Paise)
    paid_paise: Mapped[int | None] = mapped_column(Paise)
    finance_charges_paise: Mapped[int] = mapped_column(Paise, default=0)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_txn_user_time", "user_id", "occurred_at"),)
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    local_date: Mapped[date] = mapped_column(Date)  # IST date of occurred_at
    budget_month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    amount_paise: Mapped[int] = mapped_column(Paise)
    personal_amount_paise: Mapped[int] = mapped_column(Paise)
    direction: Mapped[str] = mapped_column(String(6))  # debit | credit
    mode: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12), default="success")
    kind: Mapped[str | None] = mapped_column(String(24))
    merchant: Mapped[str | None] = mapped_column(String(60))  # merchant key
    merchant_name: Mapped[str] = mapped_column(String(160), default="")  # what the app shows
    counterparty_name: Mapped[str | None] = mapped_column(String(160))
    counterparty_vpa: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), default="uncategorised")
    spend_class: Mapped[str] = mapped_column(String(12), default="flexible")
    narration: Mapped[str] = mapped_column(Text, default="")
    ref_no: Mapped[str | None] = mapped_column(String(40))
    balance_after_paise: Mapped[int | None] = mapped_column(Paise)
    recurring_item_id: Mapped[str | None] = mapped_column(String(36))
    transfer_pair_id: Mapped[str | None] = mapped_column(String(36))
    reversal_of_id: Mapped[str | None] = mapped_column(String(36))
    refund_of_id: Mapped[str | None] = mapped_column(String(36))
    group_expense_id: Mapped[str | None] = mapped_column(String(36))
    group_id: Mapped[str | None] = mapped_column(String(36))
    settlement_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(8), default="aa")  # aa | sms | manual
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, onupdate=now_utc)


class SmsMessage(Base):
    __tablename__ = "sms_messages"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    sender_id: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    parse_status: Mapped[str] = mapped_column(String(12), default="pending")
    parse_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ground_truth: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    transaction_id: Mapped[str | None] = mapped_column(String(36))


class RecurringItem(Base):
    __tablename__ = "recurring_items"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    key: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(16))  # salary/rent/emi/bill/subscription/sip/insurance
    source_kind: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    cadence: Mapped[str] = mapped_column(String(16))
    day: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str | None] = mapped_column(String(16))
    merchant: Mapped[str | None] = mapped_column(String(60))
    payee: Mapped[str | None] = mapped_column(String(120))
    amount_paise: Mapped[int] = mapped_column(Paise)
    amount_is_variable: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    next_due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="active")


class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    key: Mapped[str] = mapped_column(String(60))
    lender: Mapped[str] = mapped_column(String(120))
    loan_type: Mapped[str] = mapped_column(String(24))
    rate_type: Mapped[str] = mapped_column(String(12))
    principal_paise: Mapped[int] = mapped_column(Paise)
    outstanding_paise: Mapped[int] = mapped_column(Paise)
    interest_rate_bps: Mapped[int] = mapped_column(Integer)
    tenure_months: Mapped[int] = mapped_column(Integer)
    emi_paise: Mapped[int] = mapped_column(Paise)
    emi_day: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    emis_paid: Mapped[int] = mapped_column(Integer, default=0)
    months_left: Mapped[int] = mapped_column(Integer, default=0)
    zero_cost_emi: Mapped[bool] = mapped_column(Boolean, default=False)


class Holding(Base):
    __tablename__ = "holdings"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    kind: Mapped[str] = mapped_column(String(16))  # mutual_fund/fd/gold/ppf/epf
    name: Mapped[str] = mapped_column(String(200))
    scheme_code: Mapped[int | None] = mapped_column(Integer)
    units: Mapped[Any | None] = mapped_column(Numeric(18, 4))
    invested_paise: Mapped[int | None] = mapped_column(Paise)
    sip_amount_paise: Mapped[int | None] = mapped_column(Paise)
    sip_day: Mapped[int | None] = mapped_column(Integer)
    folio_masked: Mapped[str | None] = mapped_column(String(24))
    fd_principal_paise: Mapped[int | None] = mapped_column(Paise)
    fd_rate_bps: Mapped[int | None] = mapped_column(Integer)
    fd_start_date: Mapped[date | None] = mapped_column(Date)
    fd_maturity_date: Mapped[date | None] = mapped_column(Date)
    gold_grams: Mapped[Any | None] = mapped_column(Numeric(12, 3))
    balance_paise: Mapped[int | None] = mapped_column(Paise)
    balance_as_of: Mapped[date | None] = mapped_column(Date)


# ---------- plan ----------
class Pocket(Base):
    __tablename__ = "pockets"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    name: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(16), default="")
    monthly_limit_paise: Mapped[int] = mapped_column(Paise)
    category_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | paused | archived
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = created()


class PocketAdjustment(Base):
    __tablename__ = "pocket_adjustments"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    pocket_id: Mapped[str] = mapped_column(String(36), index=True)
    month: Mapped[str] = mapped_column(String(7))
    delta_paise: Mapped[int] = mapped_column(Paise)
    reason: Mapped[str] = mapped_column(String(120), default="")
    proposal_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = created()


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    name: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(16), default="")
    target_paise: Mapped[int] = mapped_column(Paise)
    deadline: Mapped[date | None] = mapped_column(Date)
    monthly_plan_paise: Mapped[int | None] = mapped_column(Paise)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_by: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = created()


class GoalContribution(Base):
    __tablename__ = "goal_contributions"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    goal_id: Mapped[str] = mapped_column(String(36), index=True)
    amount_paise: Mapped[int] = mapped_column(Paise)
    month: Mapped[str] = mapped_column(String(7))
    source: Mapped[str] = mapped_column(String(16), default="user")
    note: Mapped[str | None] = mapped_column(String(120))
    proposal_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = created()


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    kind: Mapped[str] = mapped_column(String(32))  # set_goal/create_pocket/move_between_pockets/add_transaction
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    preview: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # code-built card content
    source: Mapped[str] = mapped_column(String(16), default="mascot")  # mascot | insight
    insight_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending/accepted/declined/expired
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = created()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = created()


# ---------- insights / nudges / home / pulse ----------
class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    type: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(160), index=True)
    severity: Mapped[int] = mapped_column(Integer, default=1)  # 3 high, 2 medium, 1 low
    impact_paise: Mapped[int] = mapped_column(Paise, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    proposal_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | dismissed | resolved
    created_at: Mapped[datetime] = created()


class PlantedPattern(Base):
    __tablename__ = "planted_patterns"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    pattern_type: Mapped[str] = mapped_column(String(32))
    natural_key: Mapped[str] = mapped_column(String(160))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Nudge(Base):
    __tablename__ = "nudges"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    kind: Mapped[str] = mapped_column(String(24))
    dedupe_key: Mapped[str] = mapped_column(String(160), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime)
    local_day: Mapped[date] = mapped_column(Date)  # IST day it counts against
    status: Mapped[str] = mapped_column(String(12), default="scheduled")  # scheduled/shown/dismissed
    shown_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = created()


class HomeLayout(Base):
    __tablename__ = "home_layouts"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    version: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source: Mapped[str] = mapped_column(String(12), default="composer")  # composer/default/manual
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    a2ui: Mapped[list[Any]] = mapped_column(JSON, default=list)
    instruction: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = created()


class PulseItem(Base):
    __tablename__ = "pulse_items"
    id: Mapped[str] = pk()
    day: Mapped[date] = mapped_column(Date, index=True)
    topic: Mapped[str] = mapped_column(String(24))  # markets/rates/prices/world/policy
    title: Mapped[dict[str, Any]] = mapped_column(JSON)  # {en, hi, ta}
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(String(600))
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)  # mutual_funds/home_loan/fuel/gold/...
    rank: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created()


class PulseUserLink(Base):
    __tablename__ = "pulse_user_links"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    pulse_item_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ---------- collab ----------
class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = pk()
    type: Mapped[str] = mapped_column(String(12))  # family/trip/flatmates/custom
    name: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(24), default="")
    owner_user_id: Mapped[str] = mapped_column(String(36), index=True)
    budget_monthly_paise: Mapped[int | None] = mapped_column(Paise)
    pot_target_paise: Mapped[int | None] = mapped_column(Paise)
    pot_deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = created()


class GroupMember(Base):
    __tablename__ = "group_members"
    id: Mapped[str] = pk()
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)  # None = guest
    display_name: Mapped[str] = mapped_column(String(80))
    vpa: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(12), default="member")  # owner/member/guest
    join_order: Mapped[int] = mapped_column(Integer, default=0)
    sharing: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # nothing shared by default


class GroupExpense(Base):
    __tablename__ = "group_expenses"
    id: Mapped[str] = pk()
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    paid_by_member_id: Mapped[str] = mapped_column(String(36))
    amount_paise: Mapped[int] = mapped_column(Paise)
    description: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    split_method: Mapped[str] = mapped_column(String(8))  # equal/percent/exact
    split_input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    linked_transaction_id: Mapped[str | None] = mapped_column(String(36))
    created_by_member_id: Mapped[str | None] = mapped_column(String(36))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class GroupExpenseShare(Base):
    __tablename__ = "group_expense_shares"
    expense_id: Mapped[str] = mapped_column(String(36), ForeignKey("group_expenses.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(36), index=True)
    share_paise: Mapped[int] = mapped_column(Paise)


class GroupPotContribution(Base):
    __tablename__ = "group_pot_contributions"
    id: Mapped[str] = pk()
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[str] = mapped_column(String(36))
    amount_paise: Mapped[int] = mapped_column(Paise)
    method: Mapped[str] = mapped_column(String(8), default="upi")
    note: Mapped[str | None] = mapped_column(String(120))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Settlement(Base):
    __tablename__ = "settlements"
    id: Mapped[str] = pk()
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    from_member_id: Mapped[str] = mapped_column(String(36))
    to_member_id: Mapped[str] = mapped_column(String(36))
    amount_paise: Mapped[int] = mapped_column(Paise)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending/link_opened/marked_paid/confirmed
    upi_link: Mapped[str | None] = mapped_column(String(600))
    created_by_member_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = created()
    marked_paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class GroupInvite(Base):
    __tablename__ = "group_invites"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(String(36))
    max_uses: Mapped[int] = mapped_column(Integer, default=10)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[date | None] = mapped_column(Date)


# ---------- chat ----------
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    mode: Mapped[str] = mapped_column(String(16), default="chat")
    language: Mapped[str] = mapped_column(String(4), default="en")
    started_at: Mapped[datetime] = created()
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ChatTurn(Base):
    __tablename__ = "chat_turns"
    id: Mapped[str] = pk()
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = user_fk()
    role: Mapped[str] = mapped_column(String(12))  # user/mascot/tool
    text: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = created()


class GuardEvent(Base):
    __tablename__ = "guard_events"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = user_fk()
    session_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(24))  # number_mismatch | advice
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = created()


USER_TABLES: tuple[type[Base], ...] = (
    GuardEvent, ChatTurn, ChatSession, PulseUserLink, HomeLayout, Nudge, PlantedPattern, Insight, AuditLog,
    Proposal, GoalContribution, Goal, PocketAdjustment, Pocket, Holding, Loan, RecurringItem, SmsMessage,
    Transaction, CardStatement, Account, ProfileFact,
)
