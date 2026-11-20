"""Ledger engine: turns a UserSpec into a realistic, internally consistent ledger.

Order of work for one user:
1. accounts  2. income events  3. recurring payments  4. daily flexible spending  5. ATM, transfers,
charges, cashback  6. group events  7. mess (reversals, refunds)  8. planted patterns
9. chronological simulation with balances, card statements, interest, sweeps and top-ups.
"""
from __future__ import annotations

import hashlib
import heapq
import math
import random
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from . import refdata as R
from .spec import AccountSpec, FlexSpec, IncomeSpec, RecurringSpec, UserSpec

IST = ZoneInfo("Asia/Kolkata")
NS = uuid.UUID("6b1f3c1e-4d2a-4c55-9a0f-2f6d9b1c0e11")
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def P(rupees: float) -> int:
    return int(round(rupees * 100))


def dim(y: int, m: int) -> int:
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def add_months(d: date, n: int) -> date:
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, dim(y, m)))


def month_starts(start: date = R.START, end: date = R.END):
    d = date(start.year, start.month, 1)
    while d <= end:
        yield d
        d = add_months(d, 1)


def is_bank_working(d: date) -> bool:
    if d.weekday() == 6 or d in R.BANK_HOLIDAYS:
        return False
    if d.weekday() == 5 and (d.day - 1) // 7 in (1, 3):     # 2nd and 4th Saturdays
        return False
    return True


def is_office_day(d: date) -> bool:
    return d.weekday() < 5 and d not in R.BANK_HOLIDAYS


def next_working(d: date) -> date:
    while not is_bank_working(d):
        d += timedelta(days=1)
    return d


def prev_office(d: date) -> date:
    while not is_office_day(d):
        d -= timedelta(days=1)
    return d


def last_office_day(y: int, m: int) -> date:
    return prev_office(date(y, m, dim(y, m)))


def first_office_day(y: int, m: int) -> date:
    d = date(y, m, 1)
    while not is_office_day(d):
        d += timedelta(days=1)
    return d


HOURS = {
    "tea": [(7, 10, .45), (10, 12, .1), (15, 19, .4), (19, 22, .05)],
    "meal": [(12, 15, .45), (19, 23, .5), (8, 10, .05)],
    "late_meal": [(12, 15, .3), (19, 24, .6), (0, 2, .1)],
    "grocery": [(8, 12, .45), (17, 21, .5), (21, 23, .05)],
    "commute": [(7, 10, .45), (17, 21, .45), (10, 17, .1)],
    "day": [(9, 21, 1.0)],
    "evening": [(16, 23, 1.0)],
    "online": [(10, 24, .85), (0, 2, .15)],
    "night_payout": [(21, 24, .85), (6, 9, .15)],
    "office": [(8, 13, .8), (13, 18, .2)],
    "early": [(1, 6, 1.0)],
    "any": [(7, 23, 1.0)],
    "morning": [(6, 11, 1.0)],
}


@dataclass
class Account:
    id: str
    user_id: str
    role: str
    bank: str
    type: str
    masked: str
    last4: str
    ifsc: str
    opened: date
    opening_balance: int
    nickname: str | None = None
    card_limit: int | None = None
    card_rate_bps: int = 4200
    statement_day: int | None = None
    idle: bool = False
    sweep_cap: int | None = None
    balance: int = 0
    eod: dict = field(default_factory=dict)            # date -> balance (paise)
    statements: list = field(default_factory=list)
    last_ts: datetime | None = None                      # latest accepted txn time (keeps running balances time-ordered)


@dataclass
class Txn:
    id: str
    user_id: str
    account_id: str
    ts: datetime
    amount: int
    direction: str
    kind: str
    category: str
    status: str = "success"
    merchant_key: str | None = None
    cp_name: str | None = None
    cp_vpa: str | None = None
    ref: str | None = None
    mode: str = "upi"
    recurring_key: str | None = None
    transfer_pair: str | None = None
    refund_of: str | None = None
    group_expense_id: str | None = None
    planted: str | None = None
    note: str = ""
    balance_after: int | None = None
    must: bool = False
    narration: str = ""
    sms_ids: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


# Merchant name variants seen in real statements for the same merchant (legal names, typos, app names).
ALIASES = {
    "swiggy": ["SWIGGY", "SWIGGY LIMITED", "BUNDL TECHNOLOGIES", "SWIGY", "Swiggy"],
    "zomato": ["ZOMATO LTD", "ZOMATO", "ETERNAL LIMITED", "ZOMATO ORDER", "ZOMTO"],
    "amazon": ["AMAZON PAY INDIA PVT LTD", "AMAZON SELLER SERVICES", "AMAZON", "AMZN PAY INDIA"],
    "flipkart": ["FLIPKART INTERNET PVT LTD", "FLIPKART", "FLIPKART PAYMENTS", "FLIPKRT"],
    "uber": ["UBER INDIA SYSTEMS", "UBER", "UBER INDIA", "UBER TRIP"],
    "ola": ["ANI TECHNOLOGIES OLA", "OLA CABS", "OLACABS", "ANI TECHNOLOGIES"],
    "rapido": ["ROPPEN TRANSPORTATION RAPIDO", "RAPIDO", "RAPIDO BIKE TAXI"],
    "zepto": ["ZEPTO KIRANAKART", "KIRANAKART TECHNOLOGIES", "ZEPTO", "ZEPTONOW"],
    "blinkit": ["BLINKIT GROFERS INDIA", "BLINK COMMERCE", "BLINKIT", "GROFERS"],
    "instamart": ["SWIGGY INSTAMART", "INSTAMART", "SWIGGY IM"],
    "bigbasket": ["INNOVATIVE RETAIL BIGBASKET", "BIGBASKET", "BB NOW", "SUPERMARKET GROCERY SUPPLIES"],
    "dmart": ["AVENUE SUPERMARTS LTD", "DMART", "D MART", "AVENUE E COMMERCE"],
    "jio": ["RELIANCE JIO INFOCOMM", "JIO", "JIO PREPAID RECHARGE", "RJIL"],
    "airtel": ["BHARTI AIRTEL LTD", "AIRTEL", "AIRTEL PAYMENTS BANK", "AIRTEL RECHARGE"],
    "netflix": ["NETFLIX ENTERTAINMENT SERVICES", "NETFLIX", "NETFLIX.COM"],
    "spotify": ["SPOTIFY INDIA", "SPOTIFY", "SPOTIFY AB"],
    "myntra": ["MYNTRA DESIGNS", "MYNTRA", "MYNTRA JABONG"],
    "irctc": ["IRCTC", "IRCTC E TICKETING", "INDIAN RAILWAY CATERING"],
    "iocl": ["INDIAN OIL CORPORATION", "INDIAN OIL", "IOCL"],
    "starbucks": ["TATA STARBUCKS PVT LTD", "STARBUCKS", "TATA STARBUCKS"],
    "mcdonalds": ["HARDCASTLE RESTAURANTS MCDONALDS", "MCDONALDS", "CONNAUGHT PLAZA RESTAURANTS"],
    "bookmyshow": ["BIGTREE ENTERTAINMENT BOOKMYSHOW", "BOOKMYSHOW", "BIGTREE ENTERTAINMENT"],
    "cred": ["DREAMPLUG TECHNOLOGIES CRED", "CRED", "CRED CLUB"],
}

ATM_PREFIX = {"SBI": "S1AN", "HDFC": "NWD", "ICICI": "IC", "AXIS": "AX", "KOTAK": "KM", "CANARA": "CN", "BOB": "BB"}


class Builder:
    def __init__(self, spec: UserSpec, nav: dict, extra_events: list[dict] | None = None):
        self.s = spec
        self.nav = nav
        self.r = random.Random(spec.seed)
        self.g = np.random.default_rng(spec.seed)
        self.seq = 0
        self.events: list[Txn] = []
        self.accepted: list[Txn] = []
        self.stats = Counter()
        self.planted: list[dict] = []
        self.rrns: set[str] = set()
        self.extra_events = extra_events or []
        self.recurring_out: dict[str, dict] = {}
        self.loans: list[dict] = []
        self.holdings: list[dict] = []
        self.fds: list[dict] = []
        self.pending_fin_charge: dict[str, int] = {}
        self._make_accounts()
        self._make_locals()
        self.salary_days: set[date] = set()

    # ------------------------------------------------------------------ ids and refs
    def tid(self) -> str:
        self.seq += 1
        return uid(self.s.user_id, "txn", self.seq)

    def rrn(self, ts: datetime) -> str:
        while True:
            v = f"{ts.year % 10}{ts.timetuple().tm_yday:03d}{ts.hour:02d}{self.r.randrange(10**6):06d}"
            if v not in self.rrns:
                self.rrns.add(v)
                return v

    def utr(self, ts: datetime, bank4: str) -> str:
        return f"{bank4}N{ts.year % 100:02d}{ts.timetuple().tm_yday:03d}{self.r.randrange(10**6):06d}"

    def time_on(self, d: date, profile: str) -> datetime:
        segs = HOURS[profile]
        x, acc = self.r.random(), 0.0
        a, b = segs[-1][0], segs[-1][1]
        for lo, hi, w in segs:
            acc += w
            if x <= acc:
                a, b = lo, hi
                break
        h = a + self.r.random() * (b - a)
        hour = min(int(h), 23)
        minute = int((h - int(h)) * 60) if h < 24 else 59
        return datetime(d.year, d.month, d.day, hour, min(minute, 59), self.r.randrange(60), tzinfo=IST)

    # ------------------------------------------------------------------ people and places
    def person(self, gender: str | None = None, region: str | None = None) -> tuple[str, str]:
        region = region or self.s.region
        pool = R.NAMES.get(region, R.NAMES["hindi"])
        gender = gender or self.r.choice(["male", "female"])
        first = self.r.choice(pool[gender])
        last = self.r.choice(pool["surname"])
        style = self.r.random()
        if region == "tamil" and style < 0.45:
            name = f"{last[0]} {first}".upper() if self.r.random() < 0.5 else f"{first} {last[0]}".upper()
        else:
            name = f"{first} {last}".upper()
        return name, self.vpa_for(first, last)

    def vpa_for(self, first: str, last: str) -> str:
        f, l = first.lower().replace("'", ""), last.lower().replace("'", "").replace(" ", "")
        pat = self.r.random()
        if pat < 0.3:
            local = f"{f}.{l}"
        elif pat < 0.55:
            local = f"{f}{l[0]}{self.r.randrange(10, 99)}"
        elif pat < 0.75:
            local = f"{f}{self.r.randrange(1985, 2007)}"
        else:
            local = f"{f}{l}{self.r.randrange(1, 999)}"
        handle = self.r.choices(R.PERSONAL_HANDLES, weights=[12, 9, 9, 8, 22, 8, 6, 4, 3, 2, 2, 4, 2, 2])[0]
        return f"{local}@{handle}"

    def _make_accounts(self):
        self.accounts: dict[str, Account] = {}
        self.by_id: dict[str, Account] = {}
        for i, a in enumerate(self.s.accounts):
            b = R.BANKS[a.bank]
            if a.type == "credit_card":
                last4 = f"{self.r.randrange(10000):04d}"
                masked = "XXXXXXXXXXXX" + last4
            else:
                digits = "".join(str(self.r.randrange(10)) for _ in range(b["acct_len"]))
                last4 = digits[-4:]
                masked = "X" * (len(digits) - 4) + last4
            ifsc = b["ifsc"] + f"{self.r.randrange(1, 9999):06d}"
            acc = Account(id=uid(self.s.user_id, "acct", i, a.role), user_id=self.s.user_id, role=a.role, bank=a.bank,
                          type=a.type, masked=masked, last4=last4, ifsc=ifsc, opened=a.opened,
                          opening_balance=P(a.opening_balance), nickname=a.nickname,
                          card_limit=P(a.card_limit) if a.card_limit else None, card_rate_bps=a.card_rate_bps,
                          statement_day=a.statement_day, idle=a.idle,
                          sweep_cap=P(a.sweep_cap) if a.sweep_cap else None)
            acc.balance = acc.opening_balance
            self.accounts[a.role] = acc
            self.by_id[acc.id] = acc
        self.card = next((a for a in self.accounts.values() if a.type == "credit_card"), None)
        self.primary = self.accounts["primary"]

    def _make_locals(self):
        city = self.s.city
        locs = [m for m in R.MERCHANTS if m["local"] and m["cities"] == [city]]
        by_cat = defaultdict(list)
        for m in locs:
            by_cat[m["category"]].append(m)
        self.local_known = by_cat
        n1, v1 = self.person("male")
        n2, v2 = self.person("female")
        n3, v3 = self.person("male")
        n4, v4 = self.person("male")
        area = self.s.area.upper()
        shop_words = {"tamil": "STORES", "hindi": "KIRANA STORE", "south": "PROVISION STORES", "west": "PROVISION STORES", "east": "GROCERY"}
        brand = self.r.choice(["iocl", "hpcl", "bpcl"])
        self.locals = {
            "kirana": (f"{n1.split()[-1]} {shop_words.get(self.s.region, 'STORES')}", self.qr_vpa(), "groceries", n1),
            "tea": (f"{n3.split()[0]} TEA STALL", self.qr_vpa(), "eating_out", n3),
            "veg": (n2, v2, "groceries", n2),
            "pharmacy": (f"{self.r.choice(['SRI SAI', 'NEW', 'CITY', 'LIFE CARE', 'JANATA'])} MEDICALS {area}", self.qr_vpa(), "health", None),
            "salon": (f"{self.r.choice(['CLASSIC', 'STYLE', 'TRENDY', 'ROYAL'])} SALON", self.qr_vpa(), "personal_care", None),
            "mess": (f"{self.r.choice(['ANNAPOORNA', 'SRI KRISHNA', 'GANGA', 'MAHALAXMI'])} {'MESS' if self.s.region == 'tamil' else 'BHOJANALAYA' if self.s.region == 'hindi' else 'CANTEEN'}", self.qr_vpa(), "eating_out", None),
            "fuel": (f"{self.r.choice(['SRI VINAYAGA', 'BALAJI', 'NEW INDIA', 'SHIV SHAKTI', 'SAI KRUPA', 'GANESH'])} {self.r.choice(['FUELS', 'SERVICE STATION', 'PETROLEUMS', 'FILLING STATION'])}", self.qr_vpa(), "fuel", brand),
            "water": (f"{n4.split()[0]} WATER SUPPLY", v4, "utilities", n4),
            "bakery": (f"{self.r.choice(['IYENGAR', 'SRI GANESH', 'NEW MODERN', 'AMBIKA'])} BAKERY", self.qr_vpa(), "eating_out", None),
            "xerox": (f"{self.r.choice(['SAI', 'STAR', 'CAMPUS', 'MODERN'])} XEROX AND STATIONERY", self.qr_vpa(), "education", None),
        }

    def qr_vpa(self) -> str:
        k = self.r.random()
        if k < 0.45:
            return f"q{self.r.randrange(10**8, 10**9)}@ybl"
        if k < 0.7:
            return f"paytmqr{self.r.randrange(10**13, 10**14)}@paytm"
        if k < 0.85:
            return f"gpay-{self.r.randrange(10**10, 10**11)}@okbizaxis"
        return f"bharatpe.{self.r.randrange(10**9, 10**10)}@fbpe"

    def merchant_pick(self, token: str) -> tuple[str | None, str, str, str]:
        """Returns (merchant_key, counterparty name, vpa, category_hint)."""
        if token.startswith("LOCAL:"):
            k = token[6:]
            known = self.local_known.get({"kirana": "groceries", "tea": "eating_out", "pharmacy": "health", "salon": "personal_care"}.get(k, ""), [])
            if known and self.r.random() < 0.35:
                m = self.r.choice(known)
                return m["key"], m["narr"], m["vpa"], m["category"]
            name, vpa, cat, owner = self.locals[k]
            if owner and self.r.random() < 0.3:
                return None, owner, vpa, cat       # small shops often show the owner's name
            return None, name, vpa, cat
        if token in ("P2P:auto", "P2P:any"):
            name, vpa = self.person("male")
            return None, name, vpa, "transport"
        if token == "P2P:friend":
            if not hasattr(self, "_friends"):
                self._friends = [self.person() for _ in range(6)]
            name, vpa = self.r.choice(self._friends)
            return None, name, vpa, "other_expense"
        if token.startswith("SUPPLIER:"):
            if not hasattr(self, "_supplier_vpa"):
                self._supplier_vpa = {}
            vpa = self._supplier_vpa.setdefault(token, self.qr_vpa())
            return None, token[9:], vpa, "business_supplies"
        if token == "CITY:metro":
            mk = R.CITIES[self.s.city]["metro"]
            m = R.MERCHANT_BY_KEY.get(mk) if mk else None
            if m:
                return m["key"], m["narr"], m["vpa"], m["category"]
            token = "rapido"
        m = R.MERCHANT_BY_KEY[token]
        narr = self.r.choice(ALIASES[token]) if token in ALIASES and self.r.random() < 0.35 else m["narr"]
        return m["key"], narr, m["vpa"], m["category"]

    # ------------------------------------------------------------------ txn creation
    def add(self, acct_role: str, ts: datetime, amount: int, direction: str, kind: str, category: str, **kw) -> Txn:
        acct = self.accounts[acct_role] if acct_role in self.accounts else self.by_id[acct_role]
        t = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acct.id, ts=ts, amount=amount, direction=direction,
                kind=kind, category=category, **kw)
        if t.ref is None and kind in ("upi_p2m", "upi_p2p_out", "upi_in", "autopay", "imps_in", "imps_out", "self_out", "self_in", "card_bill_pay"):
            t.ref = self.rrn(ts)
        self.events.append(t)
        return t

    # ------------------------------------------------------------------ 2. income
    def gen_income(self):
        for inc in self.s.incomes:
            getattr(self, f"_inc_{inc.kind}")(inc)

    def _amount_at(self, base: float, changes, d: date) -> float:
        amt = base
        for eff, new in sorted(changes):
            if d >= eff:
                amt = new
        return amt

    def _inc_salary(self, inc: IncomeSpec):
        for ms in month_starts(add_months(R.START, -1), R.END):
            y, m = ms.year, ms.month
            if inc.rule == "last_working_day":
                d, work_month = last_office_day(y, m), (y, m)
            elif inc.rule == "first_working_day":
                d = first_office_day(y, m)
                pm = add_months(ms, -1)
                work_month = (pm.year, pm.month)
            else:
                d = prev_office(date(y, m, min(inc.day, dim(y, m))))
                pm = add_months(ms, -1)
                work_month = (pm.year, pm.month)
            if not (R.START <= d <= R.END):
                continue
            amt = self._amount_at(inc.amount, inc.changes, d)
            if inc.jitter:
                amt *= 1 + self.g.normal(0, inc.jitter)
            ts = self.time_on(d, "office")
            purpose = f"SALARY {MONTHS[work_month[1] - 1]} {work_month[0]}"
            self.salary_days.add(d)
            self.add(inc.account, ts, P(round(amt)), "credit", "neft_in", inc.category, cp_name=inc.payer, mode="neft",
                     ref=self.utr(ts, inc.payer_bank), note=purpose, meta={"payer_bank": inc.payer_bank}, recurring_key="salary")

    def _inc_allowance(self, inc: IncomeSpec):
        payer_first = inc.payer.split()[-1].title()
        vpa = self.vpa_for(payer_first, inc.payer.split()[0].title())
        for ms in month_starts():
            d = date(ms.year, ms.month, min(inc.day + self.r.randrange(0, 3), dim(ms.year, ms.month)))
            if not (R.START <= d <= R.END):
                continue
            self.salary_days.add(d)
            self.add(inc.account, self.time_on(d, "evening"), P(self._amount_at(inc.amount, inc.changes, d)), "credit", "upi_in",
                     inc.category, cp_name=inc.payer, cp_vpa=vpa, note=self.r.choice(["Pocket money", "For month", "UPI", "Monthly"]),
                     recurring_key="allowance")

    def _inc_spouse_transfer(self, inc: IncomeSpec):
        first, last = inc.payer.title().split()[0], inc.payer.title().split()[-1]
        vpa = self.vpa_for(first, last)
        for ms in month_starts():
            d = date(ms.year, ms.month, min(inc.day + self.r.randrange(0, 2), dim(ms.year, ms.month)))
            if R.START <= d <= R.END:
                self.add(inc.account, self.time_on(d, "evening"), P(self._amount_at(inc.amount, inc.changes, d)), "credit",
                         "upi_in" if inc.mode == "upi" else "imps_in", inc.category, cp_name=inc.payer, cp_vpa=vpa,
                         note="Household", mode="upi" if inc.mode == "upi" else "imps", recurring_key="household_transfer")

    def _inc_one_off(self, inc: IncomeSpec):
        for d in inc.dates:
            if R.START <= d <= R.END:
                ts = self.time_on(d, "office")
                if inc.payer.startswith("FD"):
                    self.add(inc.account, ts, P(inc.amount), "credit", "fd_maturity", "self_transfer", cp_name=inc.payer,
                             mode="other", note=inc.purpose or "FD MATURITY PROCEEDS")
                    continue
                kind = {"neft": "neft_in", "imps": "imps_in", "upi": "upi_in"}[inc.mode]
                self.add(inc.account, ts, P(inc.amount), "credit", kind, inc.category, cp_name=inc.payer,
                         mode=inc.mode, ref=self.utr(ts, inc.payer_bank) if inc.mode == "neft" else None, note=inc.purpose,
                         cp_vpa=self.vpa_for(inc.payer.title().split()[0], inc.payer.title().split()[-1]) if inc.mode == "upi" else None)

    def _inc_p2p_irregular(self, inc: IncomeSpec):
        payers = [self.person() for _ in range(4)]
        for ms in month_starts():
            n = self.g.poisson(inc.per_month)
            for _ in range(n):
                d = ms + timedelta(days=self.r.randrange(dim(ms.year, ms.month)))
                if R.START <= d <= R.END:
                    name, vpa = self.r.choice(payers)
                    self.add(inc.account, self.time_on(d, "evening"), P(self.r.choice(inc.choices)), "credit", "upi_in",
                             inc.category, cp_name=name, cp_vpa=vpa, note=self.r.choice([inc.purpose or "Fees", "UPI", "Thanks", "Payment"]))

    def _season(self, d: date) -> float:
        """Delivery and ride demand rise in the festive sale, the Diwali weeks and around New Year."""
        if date(2026, 9, 23) <= d <= date(2026, 10, 3) or date(2026, 10, 25) <= d <= date(2026, 11, 11) or date(2025, 12, 24) <= d <= date(2026, 1, 1):
            return 1.18
        return 1.0

    def _inc_gig_daily(self, inc: IncomeSpec):
        m = R.MERCHANT_BY_KEY[inc.payer_merchant]
        d = R.START
        while d <= R.END:
            if self.r.random() < inc.days_per_week / 7.0:
                amt = self.g.lognormal(math.log(inc.amount), inc.sigma) * (1.15 if d.weekday() >= 5 else 1.0) * self._season(d)
                amt = max(150.0, min(amt, inc.amount * 3))
                ts = self.time_on(d, "night_payout")
                if ts.hour < 12:
                    ts += timedelta(days=1)
                    if ts.date() > R.END:
                        d += timedelta(days=1)
                        continue
                self.add(inc.account, ts, P(round(amt, 2)), "credit", "imps_in", inc.category, merchant_key=m["key"],
                         cp_name=m["narr"], mode="imps", note="Instant payout")
            d += timedelta(days=1)

    def _inc_gig_weekly(self, inc: IncomeSpec):
        m = R.MERCHANT_BY_KEY[inc.payer_merchant]
        d = R.START
        while d <= R.END:
            if d.weekday() == inc.day:
                amt = max(500.0, self.g.lognormal(math.log(inc.amount), inc.sigma) * self._season(d))
                ts = self.time_on(d, "office")
                self.add(inc.account, ts, P(round(amt, 2)), "credit", "neft_in", inc.category, merchant_key=m["key"],
                         cp_name=m["narr"], mode="neft", ref=self.utr(ts, inc.payer_bank), note="WEEKLY PAYOUT")
            d += timedelta(days=1)

    def _inc_business_daily(self, inc: IncomeSpec):
        m = R.MERCHANT_BY_KEY[inc.payer_merchant]
        d = R.START + timedelta(days=1)
        while d <= R.END:
            sale_day = d - timedelta(days=1)
            if self.r.random() < inc.days_per_week / 7.0:
                mult = 1.25 if sale_day.weekday() >= 5 else 1.0
                if sale_day.month == 6 or (sale_day.month == 7 and sale_day.day < 10):
                    mult *= 1.3                   # school reopening: stationery, bags
                if date(2026, 10, 15) <= sale_day <= date(2026, 11, 10):
                    mult *= 1.6                   # Diwali season
                if date(2026, 2, 25) <= sale_day <= date(2026, 3, 4):
                    mult *= 1.2                   # Holi
                amt = max(400.0, self.g.lognormal(math.log(inc.amount), inc.sigma) * mult)
                ts = self.time_on(d, "office")
                self.add(inc.account, ts, P(round(amt, 2)), "credit", "neft_in", inc.category, merchant_key=m["key"],
                         cp_name=m["narr"], mode="neft", ref=self.utr(ts, inc.payer_bank),
                         note=f"SETTLEMENT {sale_day.strftime('%d%m%y')}")
            d += timedelta(days=1)

    def _inc_cash_deposit(self, inc: IncomeSpec):
        d = R.START
        while d <= R.END:
            if d.weekday() == inc.day and is_bank_working(d):
                mult = 1.5 if date(2026, 10, 15) <= d <= date(2026, 11, 12) else 1.0
                amt = round(self.g.lognormal(math.log(inc.amount), inc.sigma) * mult / 100) * 100
                self.add(inc.account, self.time_on(d, "office"), P(max(2000, amt)), "credit", "cash_dep", inc.category,
                         cp_name="CASH DEPOSIT", mode="cash", note="SELF")
            d += timedelta(days=1)

    # ------------------------------------------------------------------ 3. recurring
    def gen_recurring(self):
        for rs in self.s.recurring:
            if rs.loan:
                self._loan(rs)
                continue
            dates = self._occurrences(rs)
            if rs.planted == "forgotten_subscription" and rs.mandate_date:
                md = rs.mandate_date
                mt = self.time_on(md, "evening")
                self._pay(rs, mt, P(self.r.choice([1, 2])), mandate=True)
            for due in dates:
                pay_day = due + timedelta(days=self.r.randint(*rs.lag_days)) if rs.lag_days != (0, 0) else due
                if rs.channel == "ach":
                    pay_day = next_working(pay_day)
                if not (R.START <= pay_day <= R.END):
                    continue
                amt = self._amount_at(rs.amount, rs.price_changes, pay_day)
                if rs.seasonal:
                    amt *= rs.seasonal.get(pay_day.month, 1.0)
                if rs.variable:
                    amt *= max(0.4, 1 + self.g.normal(0, rs.variable))
                paise = P(round(amt, 2)) if (rs.kind in ("bill", "subscription") and amt != int(amt)) else P(round(amt))
                profile = "early" if rs.channel in ("ach", "autopay") else ("online" if rs.channel == "card" else "evening")
                self._pay(rs, self.time_on(pay_day, profile), paise)
            self.recurring_out[rs.key] = dict(key=rs.key, kind=rs.kind, name=rs.name, category=rs.category,
                                              cadence=rs.cadence, day=rs.day, channel=rs.channel,
                                              merchant_key=rs.merchant, payee=rs.payee,
                                              amount_paise=P(self._amount_at(rs.amount, rs.price_changes, R.END)),
                                              amount_is_variable=bool(rs.variable or rs.seasonal),
                                              account_role="card" if rs.channel == "card" else rs.account,
                                              start_date=(rs.start or R.START).isoformat(), end_date=rs.end.isoformat() if rs.end else None,
                                              planted=rs.planted)
            if rs.kind == "sip":
                self._sip_holding(rs)

    def _occurrences(self, rs: RecurringSpec) -> list[date]:
        start = rs.start or date(2000, 1, 1)
        end = rs.end or date(2100, 1, 1)
        out = []
        if rs.planted == "forgotten_subscription" and rs.mandate_date:
            d = rs.mandate_date + timedelta(days=rs.trial_days)
            while d <= R.END:
                out.append(d)
                d = add_months(d, 1)
            return out
        if rs.cadence in ("every_28d", "every_n_days"):
            step = 28 if rs.cadence == "every_28d" else rs.every_days
            d = rs.start or (R.START + timedelta(days=rs.day))
            while d <= R.END:
                if d >= R.START:
                    out.append(d)
                d += timedelta(days=step + (self.r.choice([0, 0, 0, 1, 2]) if rs.kind == "recharge" else 0))
            return out
        months = rs.months
        if rs.cadence == "monthly":
            months = list(range(1, 13))
        for ms in month_starts():
            if months and ms.month not in months:
                continue
            d = date(ms.year, ms.month, min(rs.day, dim(ms.year, ms.month)))
            if start <= d <= end:
                out.append(d)
        return out

    def _pay(self, rs: RecurringSpec, ts: datetime, amount: int, mandate: bool = False):
        cat = rs.category
        mk, name, vpa = rs.merchant, None, None
        if mk:
            m = R.MERCHANT_BY_KEY[mk]
            name, vpa = m["narr"], m["vpa"]
            if mk in ALIASES and self.r.random() < 0.15:
                name = self.r.choice(ALIASES[mk])
        if rs.payee:
            name = rs.payee
            vpa = rs.meta_vpa if hasattr(rs, "meta_vpa") else None
            if vpa is None:
                parts = rs.payee.title().split()
                vpa = self.vpa_for(parts[0], parts[-1])
                rs.meta_vpa = vpa
        kw = dict(merchant_key=mk, cp_name=name, cp_vpa=vpa, recurring_key=rs.key, must=True, note=rs.note,
                  planted=rs.planted)
        if mandate:
            kw.update(note="Mandate registration", must=False, recurring_key=rs.key + ":mandate")
        ch = rs.channel
        if ch == "card" and self.card:
            self.add(self.card.id, ts, amount, "debit", "card_spend", cat, mode="card", **kw)
        elif ch == "ach":
            self.add(rs.account, ts, amount, "debit", "ach_dr", cat, mode="nach", ref=f"UMRN{self.r.randrange(10**15, 10**16)}", **kw)
        elif ch == "autopay":
            self.add(rs.account, ts, amount, "debit", "autopay", cat, mode="autopay", **kw)
        elif ch == "upi_p2p":
            self.add(rs.account, ts, amount, "debit", "upi_p2p_out", cat, mode="upi", **kw)
        elif ch == "neft":
            self.add(rs.account, ts, amount, "debit", "neft_out", cat, mode="neft", ref=self.utr(ts, R.BANKS[self.accounts[rs.account].bank]["ifsc"][:4]), **kw)
        elif ch == "billpay":
            self.add(rs.account, ts, amount, "debit", "billpay", cat, mode="upi", ref=self.rrn(ts), **kw)
        elif ch == "netbanking":
            self.add(rs.account, ts, amount, "debit", "netbanking", cat, mode="other", ref=f"IB{self.r.randrange(10**9, 10**10)}", **kw)
        else:
            self.add(rs.account, ts, amount, "debit", "upi_p2m", cat, mode="upi", **kw)

    def _loan(self, rs: RecurringSpec):
        L = rs.loan
        principal, rate_bps, n = P(L["principal"]), L["rate_bps"], L["tenure"]
        r = rate_bps / 10000 / 12
        if L.get("zero_cost") or rate_bps == 0:
            emi = int(round(principal / n / 100)) * 100
        else:
            emi = P(rs.amount) if rs.amount else int(round(principal * r * (1 + r) ** n / ((1 + r) ** n - 1) / 100)) * 100
        outstanding = principal
        d = L["start"]
        k = 0
        m = R.MERCHANT_BY_KEY.get(rs.merchant) if rs.merchant else None
        while k < n:
            due = date(d.year, d.month, min(rs.day, dim(d.year, d.month)))
            interest = 0 if L.get("zero_cost") else int(round(outstanding * r))
            principal_part = min(outstanding, emi - interest)
            pay_day = next_working(due)
            if R.START <= pay_day <= R.END:
                self.add(rs.account, self.time_on(pay_day, "early"), emi, "debit", "ach_dr", "emi",
                         merchant_key=rs.merchant, cp_name=m["narr"] if m else L["lender"].upper(),
                         recurring_key=rs.key, must=True, mode="nach", ref=f"UMRN{self.r.randrange(10**15, 10**16)}",
                         note=f"EMI {k + 1}/{n}")
            if pay_day > R.END:
                break
            outstanding -= principal_part
            k += 1
            d = add_months(d, 1)
        months_left = n - k
        end_date = add_months(L["start"], n - 1)
        self.loans.append(dict(key=rs.key, lender=L["lender"], loan_type=L["loan_type"], rate_type=L.get("rate_type", "fixed"),
                               principal_paise=principal, outstanding_paise=max(0, outstanding), interest_rate_bps=rate_bps,
                               tenure_months=n, emi_paise=emi, emi_day=rs.day, start_date=L["start"].isoformat(),
                               end_date=end_date.isoformat(), emis_paid=k, months_left=months_left,
                               zero_cost_emi=bool(L.get("zero_cost"))))
        self.recurring_out[rs.key] = dict(key=rs.key, kind="emi", name=rs.name, category="emi", cadence="monthly", day=rs.day,
                                          channel="ach", merchant_key=rs.merchant, payee=None, amount_paise=emi,
                                          amount_is_variable=False, account_role=rs.account,
                                          start_date=L["start"].isoformat(), end_date=end_date.isoformat(), planted=None)

    def _sip_holding(self, rs: RecurringSpec):
        code = rs.scheme_code
        units = rs.units_before
        invested = P(rs.invested_before)
        if units == 0 and rs.invested_before > 0:
            # bought steadily before START: average cost a little below the START price
            units = rs.invested_before / (self.nav_on(code, R.START) * self.r.uniform(0.82, 0.95))
        for t in self.events:
            if t.recurring_key == rs.key and t.direction == "debit":
                nd = next_working(t.ts.date() + timedelta(days=1))
                nav = self.nav_on(code, nd)
                units += (t.amount / 100) / nav
                invested += t.amount
        fund = R.FUND_BY_CODE[code]
        self.holdings.append(dict(kind="mutual_fund", name=fund[1], scheme_code=code, units=round(units, 3),
                                  invested_paise=invested, sip_amount_paise=P(rs.amount), sip_day=rs.day,
                                  folio=f"{self.r.randrange(10**7, 10**8)}/{self.r.randrange(10, 99)}",
                                  platform="BSE StAR MF" if rs.platform == "iccl" else "NSE NMF II"))

    def nav_on(self, code: int, d: date) -> float:
        series = self.nav[code]
        while d not in series and d > R.START - timedelta(days=10):
            d -= timedelta(days=1)
        return series.get(d) or next(iter(series.values()))

    # ------------------------------------------------------------------ 4. flexible spending
    def _day_weight(self, fs: FlexSpec, d: date) -> float:
        w = fs.weekend if d.weekday() >= 5 else 1.0
        if fs.payday != 1.0 and any(0 <= (d - p).days < 7 for p in self.salary_days):
            w *= fs.payday
        for name, a, b, regions, eff in R.FESTIVALS:
            if a <= d <= b and (regions is None or self.s.region in regions) and fs.category in eff:
                w *= eff[fs.category]
        return w

    def _sample_amount(self, fs: FlexSpec) -> float:
        a = float(self.g.lognormal(math.log(fs.median), fs.sigma))
        return min(max(a, fs.lo), fs.hi)

    def _round(self, fs: FlexSpec, a: float) -> int:
        a = min(max(a, fs.lo), fs.hi)
        if fs.paise:
            return max(100, int(round(a * 100)))
        rt = fs.round_to
        if rt > 1:
            return int(max(rt, round(a / rt) * rt)) * 100
        return int(max(1, round(a))) * 100

    def gen_flex(self):
        for fs in self.s.flex:
            mean_amt = float(np.mean([self._sample_amount(fs) for _ in range(400)]))
            for ms in month_starts():
                days = [ms + timedelta(days=i) for i in range(dim(ms.year, ms.month))]
                days = [d for d in days if R.START <= d <= R.END]
                if not days:
                    continue
                frac = len(days) / dim(ms.year, ms.month)
                trend = (fs.trend or {}).get(ms.strftime("%Y-%m"), 1.0)
                weights = [self._day_weight(fs, d) for d in days]
                if fs.habitual:
                    n = int(round(fs.monthly_count * frac * trend ** 0.6 + self.g.normal(0, 0.5)))
                    n = max(0, n)
                    if n == 0:
                        continue
                    picks = self.r.choices(days, weights=weights, k=n)
                    raw = [self._sample_amount(fs) for _ in range(n)]
                    target = fs.monthly_count * mean_amt * frac * trend * (1 + self.g.normal(0, fs.noise))
                    k = target / max(1.0, sum(raw))
                    amounts = [self._round(fs, a * k) for a in raw]
                else:
                    picks, amounts = [], []
                    lam_base = fs.monthly_count / 30.44
                    for d, w in zip(days, weights):
                        for _ in range(self.g.poisson(lam_base * w * trend)):
                            picks.append(d)
                            amounts.append(self._round(fs, self._sample_amount(fs)))
                for d, amt in zip(picks, amounts):
                    self._flex_txn(fs, d, amt)

    def _flex_txn(self, fs: FlexSpec, d: date, amount: int):
        token = self.r.choices([m for m, _ in fs.merchants], weights=[w for _, w in fs.merchants])[0]
        mk, name, vpa, _ = self.merchant_pick(token)
        ch = self.r.choices(list(fs.channel_mix), weights=list(fs.channel_mix.values()))[0]
        ts = self.time_on(d, fs.hours)
        if ch == "neft":
            bank4 = R.BANKS[self.accounts[fs.account].bank]["ifsc"][:4]
            t = self.add(fs.account, ts, amount, "debit", "neft_out", fs.category, cp_name=name, mode="neft",
                         ref=self.utr(ts, bank4), note=self.r.choice(["PAYMENT", "BILL PAYMENT", "INV PAYMENT", "PURCHASE"]))
            t.meta["flex"] = fs.key
            return
        if ch == "card" and self.card and not token.startswith(("LOCAL:", "P2P:")):
            t = self.add(self.card.id, ts, amount, "debit", "card_spend", fs.category, merchant_key=mk, cp_name=name, mode="card")
        elif ch == "debit_card" and not token.startswith(("LOCAL:", "P2P:")):
            t = self.add(fs.account, ts, amount, "debit", "pos_dr", fs.category, merchant_key=mk, cp_name=name, mode="card")
        else:
            kind = "upi_p2p_out" if token.startswith("P2P:") or (token == "LOCAL:veg") else "upi_p2m"
            notes = ["UPI", "Sent", "Paid", ""] if kind == "upi_p2p_out" else ["UPI", "Payment from Ph", "Pay to merchant", "", "UPI Payment"]
            t = self.add(fs.account, ts, amount, "debit", kind, fs.category, merchant_key=mk, cp_name=name, cp_vpa=vpa,
                         mode="upi", note=self.r.choice(notes))
        t.meta["flex"] = fs.key
        if fs.trend:
            t.must = True      # planted creep: a low balance triggers a top-up instead of silently dropping orders
        if fs.refund_rate and self.r.random() < fs.refund_rate:
            t.meta["refund"] = True

    # ------------------------------------------------------------------ 5. ATM, transfers, charges
    def gen_misc(self):
        s = self.s
        bank = self.primary.bank
        for ms in month_starts():
            n = self.g.poisson(s.atm_per_month)
            dates = sorted(ms + timedelta(days=self.r.randrange(dim(ms.year, ms.month))) for _ in range(n))
            for i, d in enumerate(dates):
                if not (R.START <= d <= R.END):
                    continue
                amt = self.r.choice(s.atm_amounts)
                atm_id = f"{ATM_PREFIX.get(bank, 'AT')}{self.r.choice(['CH', 'BL', 'DL', 'MU', 'JP', 'HY'])}{self.r.randrange(1000, 9999)}"
                ts = self.time_on(d, "day")
                self.add("primary", ts, P(amt), "debit", "atm_wd", "cash_withdrawal", mode="atm",
                         cp_name=f"ATM {s.area.upper()} {s.city.upper()}", ref=self.rrn(ts), meta={"atm_id": atm_id})
                if i >= 5:   # beyond the free monthly limit: Rs 23 + 18% GST
                    self.add("primary", ts + timedelta(minutes=2), 2714, "debit", "charge", "fees_charges",
                             mode="other", cp_name="ATM TXN CHARGES", note="ATM CHGS INCL GST")
        for st in s.self_transfers:
            if "date" in st:
                self.self_transfer(st["from"], st["to"], P(st["amount"]), self.time_on(st["date"], "evening"), must=True)
                continue
            for ms in month_starts():
                d = date(ms.year, ms.month, min(st["day"], dim(ms.year, ms.month)))
                if R.START <= d <= R.END and (not st.get("start") or d >= st["start"]):
                    self.self_transfer(st["from"], st["to"], P(st["amount"]), self.time_on(d, "evening"), must=True)
        for oo in s.one_offs:
            d = oo["date"]
            if not (R.START <= d <= R.END):
                continue
            ts = self.time_on(d, oo.get("hours", "online"))
            amt = P(oo["amount"])
            if oo.get("payee"):
                parts = oo["payee"].title().split()
                self.add(oo.get("account", "primary"), ts, amt, "debit", "upi_p2p_out", oo["category"], cp_name=oo["payee"],
                         cp_vpa=self.vpa_for(parts[0], parts[-1]), mode="upi", must=True, note=oo.get("note", ""))
                continue
            m = R.MERCHANT_BY_KEY[oo["merchant"]]
            if oo.get("channel") == "card" and self.card:
                t = self.add(self.card.id, ts, amt, "debit", "card_spend", oo["category"], merchant_key=m["key"], cp_name=m["narr"],
                             mode="card", must=True)
            else:
                t = self.add(oo.get("account", "primary"), ts, amt, "debit", "upi_p2m", oo["category"], merchant_key=m["key"],
                             cp_name=m["narr"], cp_vpa=m["vpa"], mode="upi", must=True, note=oo.get("note", "UPI"))
            t.meta["one_off"] = True
        # SMS alert charges each quarter and a debit card annual fee
        sms_fee = {"SBI": 1770, "HDFC": 2950, "ICICI": 2360, "AXIS": 2360, "KOTAK": 2360, "CANARA": 1770, "BOB": 1770}
        for acc in self.accounts.values():
            if acc.type not in ("savings", "current"):
                continue
            for q in (date(2025, 12, 20), date(2026, 3, 20), date(2026, 6, 20), date(2026, 9, 20)):
                d = q + timedelta(days=self.r.randrange(0, 8))
                self.add(acc.id, self.time_on(d, "early"), sms_fee.get(acc.bank, 1770), "debit", "charge", "fees_charges",
                         mode="other", cp_name="SMS ALERT CHARGES", note=f"SMS CHGS {MONTHS[q.month - 3]}-{MONTHS[q.month - 1]}{q.year % 100}")
            if acc.role == "primary":
                d = date(2026, acc.opened.month, min(acc.opened.day, 28))
                if d > R.END:
                    d = date(2025, acc.opened.month, min(acc.opened.day, 28))
                if R.START <= d <= R.END:
                    self.add(acc.id, self.time_on(d, "early"), 23600, "debit", "charge", "fees_charges", mode="other",
                             cp_name="DEBIT CARD ANNUAL FEE", note="DC AMC 200+GST")
        if s.cash_back:
            for _ in range(self.r.randint(2, 6)):
                d = R.START + timedelta(days=self.r.randrange((R.END - R.START).days))
                src = self.r.choice([("AMAZON PAY CASHBACK", "amazon"), ("CRED CASHBACK", "cred"), ("GOOGLE PAY REWARD", None)])
                self.add("primary", self.time_on(d, "any"), P(self.r.choice([5, 10, 11, 15, 21, 25, 50])), "credit", "upi_in",
                         "other_income", cp_name=src[0], merchant_key=src[1], note="Cashback", cp_vpa="rewards@okaxis")

    def self_transfer(self, from_role: str, to_role: str, amount: int, ts: datetime, must: bool = False, note: str = "Self transfer"):
        own = self.s.full_name.upper()
        a = self.add(from_role, ts, amount, "debit", "self_out", "self_transfer", mode="imps", cp_name=own, note=note, must=must)
        b = self.add(to_role, ts + timedelta(seconds=self.r.randrange(5, 90)), amount, "credit", "self_in", "self_transfer",
                     mode="imps", cp_name=own, note=note, ref=a.ref)
        a.transfer_pair, b.transfer_pair = b.id, a.id
        a.meta["to_masked"] = self.accounts[to_role].masked if to_role in self.accounts else ""
        b.meta["from_masked"] = self.accounts[from_role].masked if from_role in self.accounts else ""
        return a, b

    # ------------------------------------------------------------------ 6. group events
    def gen_group_events(self):
        for ge in self.extra_events:
            kw = dict(group_expense_id=ge.get("group_expense_id"), merchant_key=ge.get("merchant_key"),
                      cp_name=ge.get("cp_name"), cp_vpa=ge.get("cp_vpa"), note=ge.get("note", ""), must=ge["direction"] == "debit")
            kw["mode"] = "card" if ge["kind"] == "card_spend" else "upi"
            acct = self.card.id if ge["kind"] == "card_spend" and self.card else "primary"
            kind = ge["kind"] if (ge["kind"] != "card_spend" or self.card) else "upi_p2m"
            t = self.add(acct, ge["ts"], ge["amount"], ge["direction"], kind, ge["category"], **kw)
            t.meta["group"] = ge.get("group_id")
            if ge.get("settlement_id"):
                t.meta["settlement_id"] = ge["settlement_id"]

    # ------------------------------------------------------------------ 7. mess: reversals, refunds
    def gen_mess(self):
        new = []
        for t in list(self.events):
            if t.kind == "upi_p2m" and t.meta.get("flex") and t.amount >= 5000 and self.r.random() < 0.015:
                # A debit that failed at the merchant side and was auto-reversed, then a successful retry.
                fail = Txn(id=self.tid(), user_id=t.user_id, account_id=t.account_id, ts=t.ts - timedelta(minutes=self.r.randint(2, 6)),
                           amount=t.amount, direction="debit", kind="upi_p2m", category=t.category, status="reversed",
                           merchant_key=t.merchant_key, cp_name=t.cp_name, cp_vpa=t.cp_vpa, mode="upi", note=t.note)
                fail.ref = self.rrn(fail.ts)
                rev = Txn(id=self.tid(), user_id=t.user_id, account_id=t.account_id,
                          ts=fail.ts + timedelta(minutes=self.r.randint(3, 180)), amount=t.amount, direction="credit",
                          kind="upi_reversal", category=t.category, status="reversed", merchant_key=t.merchant_key,
                          cp_name=t.cp_name, cp_vpa=t.cp_vpa, mode="upi", ref=fail.ref, refund_of=fail.id, note="REVERSAL")
                fail.transfer_pair = rev.id
                new += [fail, rev]
            if t.meta.get("refund"):
                days = self.r.randint(1, 8)
                full = self.r.random() < 0.6
                amt = t.amount if full else max(100, int(t.amount * self.r.uniform(0.2, 0.7)) // 100 * 100)
                acct = self.by_id[t.account_id]
                kind = "card_refund" if acct.type == "credit_card" else "upi_in"
                ref = Txn(id=self.tid(), user_id=t.user_id, account_id=t.account_id, ts=t.ts + timedelta(days=days, hours=self.r.randint(0, 6)),
                          amount=amt, direction="credit", kind=kind, category="refund", merchant_key=t.merchant_key,
                          cp_name=t.cp_name, cp_vpa=t.cp_vpa, mode=t.mode, refund_of=t.id, note="REFUND")
                if kind == "upi_in":
                    ref.ref = self.rrn(ref.ts)
                if ref.ts.date() <= R.END:
                    new.append(ref)
        self.events += new

    # ------------------------------------------------------------------ 8. planted
    def plant_duplicate(self):
        p = self.s.planted.get("duplicate_charge")
        if not p:
            return
        pref = p.get("merchants", ["zepto", "swiggy", "uber", "blinkit", "zomato", "bigbasket", "amazon"])
        lo = R.END - timedelta(days=40)
        cands = [t for t in self.events if t.meta.get("flex") and t.merchant_key in pref and t.amount >= P(150)
                 and lo <= t.ts.date() <= R.END - timedelta(days=3) and t.status == "success" and not t.meta.get("refund")]
        if not cands:
            cands = [t for t in self.events if t.meta.get("flex") and t.merchant_key and t.amount >= P(150)
                     and lo <= t.ts.date() <= R.END - timedelta(days=3) and not t.meta.get("refund")]
        t = self.r.choice(cands)
        dup = Txn(id=self.tid(), user_id=t.user_id, account_id=t.account_id, ts=t.ts + timedelta(seconds=self.r.randint(50, 230)),
                  amount=t.amount, direction="debit", kind=t.kind, category=t.category, merchant_key=t.merchant_key,
                  cp_name=t.cp_name, cp_vpa=t.cp_vpa, mode=t.mode, note=t.note, planted="duplicate_charge")
        if t.ref:
            dup.ref = self.rrn(dup.ts)
        t.planted = "duplicate_charge"
        self.events.append(dup)
        self.planted.append(dict(pattern_type="duplicate_charge", first_txn_id=t.id, second_txn_id=dup.id,
                                 merchant_key=t.merchant_key, amount_paise=t.amount, account_id=t.account_id,
                                 first_at=t.ts.isoformat(), second_at=dup.ts.isoformat()))

    def remove_accidental_duplicates(self):
        """Non-planted data must not contain accidental duplicate charges (keeps the answer key clean)."""
        key = defaultdict(list)
        for t in self.events:
            if t.direction == "debit" and t.status == "success" and t.amount >= P(100) and t.planted != "duplicate_charge":
                key[(t.account_id, t.merchant_key or t.cp_vpa or t.cp_name, t.amount)].append(t)
        for lst in key.values():
            lst.sort(key=lambda x: x.ts)
            for a, b in zip(lst, lst[1:]):
                if (b.ts - a.ts) <= timedelta(minutes=10):
                    b.ts = b.ts + timedelta(minutes=self.r.randint(25, 90))
                    self.stats["accidental_dupes_moved"] += 1

    # ------------------------------------------------------------------ 9. simulation
    def simulate(self):
        evs = sorted(self.events, key=lambda t: t.ts)
        by_day = defaultdict(list)
        for t in evs:
            by_day[t.ts.date()].append(t)
        self.dynamic: list[tuple[datetime, int, Txn]] = []
        self.dyn_seq = 0
        dropped_pairs = set()
        dropped_ids = set()          # txns that never posted; their refunds/reversals must not post either
        self.posted_acct = {}        # txn id -> account it actually posted to (card declines move spends to UPI)
        d = R.START
        while d <= R.END:
            todays = list(by_day.get(d, []))
            while self.dynamic and self.dynamic[0][0].date() <= d:
                todays.append(heapq.heappop(self.dynamic)[2])
            if d.day == 6:
                todays += self._sweeps(d)
            for acc in self.accounts.values():
                if acc.type == "credit_card" and acc.statement_day == d.day and acc.id in self.pending_fin_charge:
                    todays += self._finance_charge(acc, d)
            todays.sort(key=lambda t: t.ts)
            for t in todays:
                if t.id in dropped_pairs or (t.refund_of and t.refund_of in dropped_ids):
                    dropped_ids.add(t.id)
                    if t.transfer_pair:
                        dropped_pairs.add(t.transfer_pair)
                    if t.refund_of in dropped_ids:
                        self.stats["refund_dropped_with_original"] += 1
                    continue
                if t.refund_of and self.posted_acct.get(t.refund_of, t.account_id) != t.account_id:
                    self._follow_original(t)
                ok = self._apply(t)
                if not ok:
                    dropped_ids.add(t.id)
                    if t.transfer_pair:
                        dropped_pairs.add(t.transfer_pair)
            for acc in self.accounts.values():
                if acc.type == "credit_card" and acc.statement_day == d.day:
                    self._statement(acc, d)
                if acc.type in ("savings", "current"):
                    acc.eod[d] = acc.balance
                    if (d.month, d.day) in ((3, 31), (6, 30), (9, 30), (12, 31)):
                        self._interest(acc, d)
            d += timedelta(days=1)
        self.accepted.sort(key=lambda t: t.ts)

    def push(self, t: Txn):
        self.dyn_seq += 1
        heapq.heappush(self.dynamic, (t.ts, self.dyn_seq, t))

    def _apply(self, t: Txn) -> bool:
        acc = self.by_id[t.account_id]
        if acc.last_ts and t.ts < acc.last_ts:
            # never post a txn earlier than one already posted on this account: statements must read in time order
            t.ts = acc.last_ts
            self.stats["ts_aligned"] += 1
        if acc.type == "credit_card":
            if t.direction == "debit":
                if acc.balance + t.amount > acc.card_limit:
                    if t.kind == "card_spend" and t.merchant_key:
                        # card declined at the limit: the person pays the same merchant by UPI instead
                        m = R.MERCHANT_BY_KEY[t.merchant_key]
                        t.account_id, t.kind, t.mode, t.cp_vpa = self.primary.id, "upi_p2m", "upi", m["vpa"]
                        t.ref = self.rrn(t.ts)
                        self.stats["card_declined_paid_by_upi"] += 1
                        return self._apply(t)
                    self.stats["card_limit_drop"] += 1
                    return False
                acc.balance += t.amount
            else:
                acc.balance -= t.amount
        else:
            if t.direction == "debit":
                if acc.balance - t.amount < 0:
                    if t.must or t.planted:
                        self._topup(acc, t)
                    else:
                        self.stats["insufficient_drop"] += 1
                        return False
                acc.balance -= t.amount
            else:
                acc.balance += t.amount
        t.balance_after = acc.balance
        if acc.last_ts is None or t.ts > acc.last_ts:
            acc.last_ts = t.ts
        self.posted_acct[t.id] = acc.id
        self.accepted.append(t)
        return True

    def _follow_original(self, t: Txn):
        """A refund goes back to where the money actually came from (e.g. a card spend that was declined and paid by UPI)."""
        acc = self.by_id[self.posted_acct[t.refund_of]]
        t.account_id = acc.id
        if acc.type != "credit_card" and t.kind == "card_refund":
            t.kind, t.mode = "upi_in", "upi"
            n = int(hashlib.md5(t.id.encode()).hexdigest(), 16)
            while True:   # deterministic, and leaves the random stream untouched
                v = f"{t.ts.year % 10}{t.ts.timetuple().tm_yday:03d}{t.ts.hour:02d}{n % 10**6:06d}"
                if v not in self.rrns:
                    self.rrns.add(v)
                    t.ref = v
                    break
                n += 7919
        self.stats["refund_followed_original"] += 1

    def _topup(self, acc: Account, t: Txn):
        need = t.amount - acc.balance
        amount = int(math.ceil((need + P(2000)) / P(1000))) * P(1000)
        base = t.ts - timedelta(minutes=self.r.randint(5, 40))
        for other in self.accounts.values():
            if other.id != acc.id and not other.idle and other.type in ("savings", "current") and other.balance >= amount + P(1000):
                ts = min(t.ts, max(x for x in (base, acc.last_ts, other.last_ts) if x is not None))
                a, b = self.self_transfer(other.role, acc.role, amount, ts, note="Self transfer")
                b.ts = min(b.ts, t.ts)
                self.events.remove(a)
                self.events.remove(b)
                self._apply(a)
                self._apply(b)
                self.stats["topup_self"] += 1
                return
        ts = min(t.ts, max(x for x in (base, acc.last_ts) if x is not None))
        name = self.s.topup_from or "FAMILY"
        parts = name.title().split()
        cat = "allowance" if self.s.income_pattern == "student" else "other_income"
        c = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts, amount=amount, direction="credit",
                kind="upi_in", category=cat, cp_name=name.upper(), cp_vpa=self.vpa_for(parts[0], parts[-1]), mode="upi",
                note=self.r.choice(["Sent", "For you", "UPI"]))
        c.ref = self.rrn(ts)
        self._apply(c)
        self.stats["topup_family"] += 1

    def _sweeps(self, d: date) -> list[Txn]:
        out = []
        for acc in self.accounts.values():
            if acc.idle or not acc.sweep_cap or acc.type != "savings":
                continue
            excess = acc.balance - acc.sweep_cap
            if excess >= P(10000):
                amt = excess // P(5000) * P(5000)
                ts = datetime(d.year, d.month, d.day, 11, self.r.randrange(60), tzinfo=IST)
                fdno = f"{self.r.randrange(10**10, 10**11)}"
                t = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts, amount=amt, direction="debit",
                        kind="fd_book", category="self_transfer", cp_name=f"FD {fdno}", mode="other", note="TRF TO FD", must=False)
                out.append(t)
                rate = self.r.choice([650, 675, 700, 710, 725])
                self.fds.append(dict(kind="fd", name=f"{R.BANKS[acc.bank]['name']} Fixed Deposit", fd_principal_paise=amt,
                                     fd_rate_bps=rate, fd_start_date=d.isoformat(), fd_maturity_date=add_months(d, 12).isoformat(),
                                     account_masked=acc.masked, fd_number_masked="XXXXXXX" + fdno[-4:], booked_by="sweep"))
        return out

    def _statement(self, acc: Account, d: date):
        bal = acc.balance
        # finance charges (+GST) posted in this cycle are billed on this statement
        prev_d = date.fromisoformat(acc.statements[-1]["statement_date"]) if acc.statements else None
        billed_fc = 0
        for x in reversed(self.accepted):
            xd = x.ts.date()
            if prev_d and xd <= prev_d:
                break
            if x.account_id == acc.id and x.kind in ("fin_charge", "fin_charge_gst") and xd <= d:
                billed_fc += x.amount
        due = d + timedelta(days=20)
        key = d.strftime("%Y-%m")
        st = dict(statement_date=d.isoformat(), due_date=due.isoformat(), total_due_paise=max(0, bal), min_due_paise=0,
                  paid_paise=0, finance_charges_paise=billed_fc)
        acc.statements.append(st)
        if bal <= 0:
            return
        min_due = max(P(200), int(round(bal * 0.05 / 100)) * 100) if bal > P(200) else bal
        st["min_due_paise"] = min_due
        if key in self.s.revolve_statements:
            pay = max(min_due, int(round(bal * self.s.revolve_pay_fraction / P(100))) * P(100))
            self.pending_fin_charge[acc.id] = int(round((bal - pay) * acc.card_rate_bps / 12 / 10000))
            st["revolving_after_due_paise"] = bal - pay
        else:
            pay = bal
        pay_day = due - timedelta(days=self.r.randint(1, 6))
        if pay_day <= d:
            pay_day = d + timedelta(days=2)
        ts = self.time_on(pay_day, "evening")
        if pay_day > R.END:
            st["paid_paise"] = None
            return
        st["paid_paise"] = pay
        via_cred = self.r.random() < 0.6
        m = R.MERCHANT_BY_KEY["cred" if via_cred else "billdesk"]
        payer = self.accounts.get(self.s.card_pay_from, self.primary)
        a = Txn(id=self.tid(), user_id=self.s.user_id, account_id=payer.id, ts=ts, amount=pay, direction="debit",
                kind="card_bill_pay", category="card_payment", merchant_key=m["key"], cp_name=m["narr"], cp_vpa=m["vpa"],
                mode="upi" if via_cred else "other", must=True, note=f"CC XX{acc.last4}")
        a.ref = self.rrn(ts)
        b = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts + timedelta(minutes=self.r.randint(1, 240)),
                amount=pay, direction="credit", kind="card_payment_in", category="card_payment",
                cp_name="PAYMENT RECEIVED", mode="other", note="THANK YOU", ref=a.ref)
        b.ts = min(b.ts, datetime(R.END.year, R.END.month, R.END.day, 23, 59, 59, tzinfo=IST))   # credit lands inside the window
        a.transfer_pair, b.transfer_pair = b.id, a.id
        a.meta["card_masked"] = acc.masked
        self.push(a)
        self.push(b)

    def _finance_charge(self, acc: Account, d: date) -> list[Txn]:
        fc = self.pending_fin_charge.pop(acc.id)
        ts = datetime(d.year, d.month, d.day, 20, 15, tzinfo=IST)
        a = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts, amount=fc, direction="debit",
                kind="fin_charge", category="card_interest", cp_name="FINANCE CHARGES", mode="other",
                planted="expensive_card_balance" if "expensive_card_balance" in self.s.planted else None)
        g = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts + timedelta(seconds=1),
                amount=int(round(fc * 0.18)), direction="debit", kind="fin_charge_gst", category="card_interest",
                cp_name="IGST ON FINANCE CHARGES", mode="other", planted=a.planted)
        if acc.statements:
            acc.statements[-1].setdefault("finance_charges_next_paise", fc + g.amount)
        return [a, g]

    def _interest(self, acc: Account, d: date):
        q_start = date(d.year, d.month - 2, 1)
        vals = [v for k, v in acc.eod.items() if q_start <= k <= d]
        if not vals:
            return
        avg = sum(vals) / len(vals)
        rate = R.BANKS[acc.bank]["rate_bps"] if acc.type == "savings" else 0
        amt = int(round(avg * rate / 10000 * len(vals) / 365))
        if amt >= 100:
            ts = datetime(d.year, d.month, d.day, 23, 30, tzinfo=IST)
            if acc.last_ts and acc.last_ts > ts:
                ts = acc.last_ts
            t = Txn(id=self.tid(), user_id=self.s.user_id, account_id=acc.id, ts=ts,
                    amount=amt, direction="credit", kind="interest", category="interest_income", cp_name="INTEREST", mode="interest",
                    note=f"{q_start.strftime('%d-%m-%Y')} to {d.strftime('%d-%m-%Y')}")
            self._apply(t)
            acc.eod[d] = acc.balance

    # ------------------------------------------------------------------ run
    def build(self):
        self.gen_income()
        self.gen_recurring()
        self.gen_flex()
        self.gen_misc()
        self.gen_group_events()
        self.gen_mess()
        self.plant_duplicate()
        self.remove_accidental_duplicates()
        self.simulate()
        self.holdings += self.fds
        return self
