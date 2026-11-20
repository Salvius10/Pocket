"""Specs describing one synthetic user. Amounts in specs are RUPEES (readable); the engine converts to paise."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class AccountSpec:
    role: str                       # primary | secondary | card | business | idle
    bank: str                       # key in refdata.BANKS
    type: str                       # savings | current | credit_card
    opening_balance: float          # rupees; for cards = outstanding at START
    opened: date
    card_limit: float | None = None
    card_rate_bps: int = 4200       # 3.5% a month
    statement_day: int | None = None
    nickname: str | None = None
    idle: bool = False              # planted idle cash: never swept
    sweep_cap: float | None = None  # rupees; balance above this is moved to an FD each month


@dataclass
class IncomeSpec:
    kind: str                       # salary | allowance | gig_daily | gig_weekly | business_daily | cash_deposit | p2p_irregular | one_off | spouse_transfer
    payer: str                      # counterparty as it appears in bank data
    amount: float                   # rupees: monthly / per event median
    account: str = "primary"
    category: str = "salary"
    mode: str = "neft"              # neft | imps | upi | cash
    rule: str = "fixed"             # last_working_day | first_working_day | fixed
    day: int = 1
    changes: list[tuple[date, float]] = field(default_factory=list)   # (effective pay date, new amount)
    jitter: float = 0.0
    dates: list[date] = field(default_factory=list)                    # one_off dates
    per_month: float = 0.0          # p2p_irregular events a month
    choices: list[float] = field(default_factory=list)                 # p2p_irregular amounts
    days_per_week: float = 6.0      # gig/business
    payer_merchant: str | None = None
    payer_bank: str = "ICIC"        # bank code of the payer (for UTR/IFSC)
    purpose: str = ""
    sigma: float = 0.35


@dataclass
class RecurringSpec:
    key: str
    kind: str                       # rent | emi | bill | subscription | sip | insurance | fees | maid | milk | society | remittance | lpg | recharge | ppf
    name: str
    category: str
    amount: float                   # rupees
    cadence: str                    # monthly | every_28d | bimonthly | quarterly | yearly | every_n_days
    day: int = 1
    channel: str = "upi_p2m"        # upi_p2m | upi_p2p | autopay | ach | card | neft | billpay | netbanking
    account: str = "primary"
    merchant: str | None = None
    payee: str | None = None
    start: date | None = None
    end: date | None = None
    months: list[int] | None = None
    seasonal: dict[int, float] | None = None
    variable: float = 0.0
    price_changes: list[tuple[date, float]] = field(default_factory=list)
    planted: str | None = None      # price_hike | forgotten_subscription
    mandate_date: date | None = None
    trial_days: int = 30
    every_days: int = 28
    lag_days: tuple[int, int] = (0, 0)   # paid this many days after the due day (min, max)
    loan: dict | None = None        # {lender, loan_type, principal, rate_bps, tenure, start, rate_type}
    scheme_code: int | None = None  # sip
    units_before: float = 0.0       # sip: units held at START
    invested_before: float = 0.0    # sip: rupees invested before START
    platform: str = "iccl"          # sip clearing: iccl | nsccl
    note: str = ""


@dataclass
class FlexSpec:
    key: str
    category: str
    monthly_count: float
    median: float                   # rupees
    sigma: float
    lo: float
    hi: float
    merchants: list[tuple[str, float]]
    round_to: int = 1
    channel_mix: dict[str, float] = field(default_factory=lambda: {"upi": 1.0})
    hours: str = "day"
    habitual: bool = True           # monthly totals follow a smooth target (low noise)
    weekend: float = 1.0
    payday: float = 1.0
    trend: dict[str, float] | None = None   # 'YYYY-MM' -> multiplier
    paise: bool = False
    account: str = "primary"
    noise: float = 0.05
    refund_rate: float = 0.0


@dataclass
class UserSpec:
    user_id: str
    persona_id: str | None
    archetype: str
    full_name: str
    first_name: str
    gender: str
    age: int
    city: str
    area: str
    language: str                   # en | hi | ta
    region: str                     # names/festival region
    income_pattern: str             # salaried | gig | business | student | mixed
    occupation: str
    seed: int
    accounts: list[AccountSpec]
    incomes: list[IncomeSpec]
    recurring: list[RecurringSpec]
    flex: list[FlexSpec]
    atm_per_month: float = 1.0
    atm_amounts: list[float] = field(default_factory=lambda: [500, 1000, 2000])
    self_transfers: list[dict] = field(default_factory=list)       # {from, to, amount, day, mode}
    revolve_statements: list[str] = field(default_factory=list)     # 'YYYY-MM' statements paid partially (planted)
    revolve_pay_fraction: float = 0.05
    planted: dict[str, dict] = field(default_factory=dict)
    pockets: list[dict] = field(default_factory=list)
    goals: list[dict] = field(default_factory=list)
    static_holdings: list[dict] = field(default_factory=list)       # fd / gold / ppf / epf
    profile: dict = field(default_factory=dict)
    topup_from: str = ""            # family member who sends money if a must-pay bill would bounce
    cash_back: bool = True
    household: str = ""
    one_offs: list[dict] = field(default_factory=list)   # {date, merchant | payee, amount, category, channel, account}
    group_link: dict = field(default_factory=dict)       # link existing txns into a household group
    card_pay_from: str = "primary"                       # account role that pays the credit card bill
