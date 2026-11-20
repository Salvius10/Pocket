"""Collab groups: members, expenses, exact splits, settle-ups and pot contributions.

Expenses paid by app users become real debits in that user's ledger (linked by group_expense_id); settle-ups between
an app user and anyone else become real UPI debits/credits. Guests have no ledger.
Guest UPI IDs use the non-existent handle @pocketdemo so a demo payment link can never reach a real person.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import refdata as R
from .engine import IST, P, add_months, dim, month_starts, uid

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def split(amount: int, method: str, member_ids: list[str], r: random.Random) -> tuple[dict, dict[str, int]]:
    n = len(member_ids)
    if method == "equal":
        base, rem = divmod(amount, n)
        shares = {m: base + (1 if i < rem else 0) for i, m in enumerate(member_ids)}
        return {"member_ids": member_ids}, shares
    if method == "percent":
        raw = [r.uniform(0.6, 1.6) for _ in member_ids]
        tot = sum(raw)
        bps = [int(x / tot * 10000) for x in raw]
        bps[0] += 10000 - sum(bps)
        exact = [amount * b / 10000 for b in bps]
        floors = [int(x) for x in exact]
        rem = amount - sum(floors)
        order = sorted(range(n), key=lambda i: (-(exact[i] - floors[i]), i))
        for i in order[:rem]:
            floors[i] += 1
        return {"bps": dict(zip(member_ids, bps))}, dict(zip(member_ids, floors))
    # exact: someone skipped or had more
    weights = [r.choice([0, 1, 1, 1, 2]) for _ in member_ids]
    if sum(weights) == 0:
        weights[0] = 1
    tot = sum(weights)
    vals = [amount * w // tot for w in weights]
    vals[weights.index(max(weights))] += amount - sum(vals)
    vals = [v // 100 * 100 for v in vals]
    vals[0] += amount - sum(vals)
    return {"paise": dict(zip(member_ids, vals))}, dict(zip(member_ids, vals))


def settle_plan(net: dict[str, int], order: list[str]) -> list[tuple[str, str, int]]:
    pos = order.index
    cred = sorted([[m, v] for m, v in net.items() if v > 0], key=lambda x: (-x[1], pos(x[0])))
    debt = sorted([[m, -v] for m, v in net.items() if v < 0], key=lambda x: (-x[1], pos(x[0])))
    plan, i, j = [], 0, 0
    while i < len(debt) and j < len(cred):
        amt = min(debt[i][1], cred[j][1])
        if amt > 0:
            plan.append((debt[i][0], cred[j][0], amt))
        debt[i][1] -= amt
        cred[j][1] -= amt
        if debt[i][1] == 0:
            i += 1
        if cred[j][1] == 0:
            j += 1
    return plan


class GroupMaker:
    def __init__(self, seed: int = 99):
        self.r = random.Random(seed)
        self.groups: list[dict] = []
        self.events: dict[str, list[dict]] = defaultdict(list)     # user_id -> events
        self.link_requests: list[dict] = []

    # ------------------------------------------------------------------ members
    def member(self, g, display, user_id=None, role="member", region="hindi"):
        first = display.split()[0].lower()
        last = display.split()[-1].lower()
        m = dict(member_id=uid(g["group_id"], "member", len(g["members"])), user_id=user_id, display_name=display.title(),
                 vpa=f"{first}.{last}@pocketdemo", role=role if user_id else "guest", join_order=len(g["members"]),
                 sharing=dict(category_ids=[], show_transactions=False, goal_ids=[]),
                 _statement_vpa=f"{first}{last[0]}{self.r.randrange(10, 99)}@{self.r.choice(['okaxis', 'ybl', 'okhdfcbank', 'oksbi', 'ibl'])}")
        g["members"].append(m)
        return m

    def new_group(self, key, gtype, name, emoji, owner_spec, created: date, budget=None, pot=None, pot_deadline=None):
        g = dict(group_id=uid("group", key), key=key, type=gtype, name=name, emoji=emoji, owner_user_id=owner_spec.user_id,
                 created_at=created.isoformat(), budget_monthly_paise=P(budget) if budget else None,
                 pot_target_paise=P(pot) if pot else None, pot_deadline=pot_deadline, status="active",
                 members=[], expenses=[], settlements=[], pot_contributions=[],
                 invites=[dict(code="".join(self.r.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6)),
                               expires_at=(created + timedelta(days=7)).isoformat(), uses=0)])
        self.groups.append(g)
        return g

    # ------------------------------------------------------------------ expenses
    def expense(self, g, payer, amount_paise, desc, category, when: datetime, method="equal", members=None, merchant_key=None,
                payee=None, channel="upi"):
        members = members or g["members"]
        ids = [m["member_id"] for m in members]
        split_input, shares = split(amount_paise, method, ids, self.r)
        e = dict(expense_id=uid(g["group_id"], "exp", len(g["expenses"])), paid_by_member_id=payer["member_id"], amount_paise=amount_paise,
                 description=desc, category_id=category, occurred_at=when.isoformat(), split_method=method, split_input=split_input,
                 shares=[dict(member_id=k, share_paise=v) for k, v in shares.items()], linked_transaction_id=None,
                 created_by_member_id=payer["member_id"], is_deleted=False)
        g["expenses"].append(e)
        if payer["user_id"] and when.date() <= R.END:
            if merchant_key:
                m = R.MERCHANT_BY_KEY[merchant_key]
                kind = "card_spend" if channel == "card" else "upi_p2m"
                self.events[payer["user_id"]].append(dict(ts=when, kind=kind, direction="debit", amount=amount_paise, category=category,
                                                          merchant_key=merchant_key, cp_name=m["narr"], cp_vpa=m["vpa"],
                                                          group_expense_id=e["expense_id"], group_id=g["group_id"], note=desc[:20]))
            else:
                name = (payee or "PAYEE").upper()
                parts = name.title().split()
                vpa = f"{parts[0].lower()}{self.r.randrange(10, 99)}@{self.r.choice(['ybl', 'okaxis', 'ibl', 'oksbi'])}"
                self.events[payer["user_id"]].append(dict(ts=when, kind="upi_p2p_out", direction="debit", amount=amount_paise, category=category,
                                                          cp_name=name, cp_vpa=vpa, group_expense_id=e["expense_id"], group_id=g["group_id"],
                                                          note=desc[:20]))
        return e

    def net(self, g, until: datetime) -> dict[str, int]:
        net = {m["member_id"]: 0 for m in g["members"]}
        for e in g["expenses"]:
            if datetime.fromisoformat(e["occurred_at"]) <= until:
                net[e["paid_by_member_id"]] += e["amount_paise"]
                for s in e["shares"]:
                    net[s["member_id"]] -= s["share_paise"]
        for s in g["settlements"]:
            if s["status"] in ("marked_paid", "confirmed") and datetime.fromisoformat(s["created_at"]) <= until:
                net[s["from_member_id"]] += s["amount_paise"]
                net[s["to_member_id"]] -= s["amount_paise"]
        return net

    def settle(self, g, when: datetime, status_fn=None, round_to_rupee=True):
        net = self.net(g, when)
        order = [m["member_id"] for m in g["members"]]
        by_id = {m["member_id"]: m for m in g["members"]}
        for frm, to, amt in settle_plan(net, order):
            status = status_fn(when) if status_fn else "confirmed"
            ts = when + timedelta(minutes=self.r.randint(5, 600))
            a, b = by_id[frm], by_id[to]
            s = dict(settlement_id=uid(g["group_id"], "settle", len(g["settlements"])), from_member_id=frm, to_member_id=to,
                     amount_paise=amt, status=status, created_by_member_id=to, created_at=ts.isoformat(),
                     upi_link=f"upi://pay?pa={b['vpa']}&pn={b['display_name'].replace(' ', '%20')}&am={amt / 100:.2f}&cu=INR&tn={g['name'][:30].replace(' ', '%20')}",
                     marked_paid_at=ts.isoformat() if status in ("marked_paid", "confirmed") else None,
                     confirmed_at=(ts + timedelta(hours=self.r.randint(1, 30))).isoformat() if status == "confirmed" else None)
            g["settlements"].append(s)
            if status in ("marked_paid", "confirmed") and ts.date() <= R.END:
                if a["user_id"]:
                    self.events[a["user_id"]].append(dict(ts=ts, kind="upi_p2p_out", direction="debit", amount=amt, category="group_settlement",
                                                          cp_name=b["display_name"].upper(), cp_vpa=b["_statement_vpa"], group_id=g["group_id"],
                                                          settlement_id=s["settlement_id"], note=g["name"][:20]))
                if b["user_id"]:
                    self.events[b["user_id"]].append(dict(ts=ts + timedelta(seconds=self.r.randint(2, 40)), kind="upi_in", direction="credit",
                                                          amount=amt, category="group_settlement", cp_name=a["display_name"].upper(),
                                                          cp_vpa=a["_statement_vpa"], group_id=g["group_id"], settlement_id=s["settlement_id"],
                                                          note=g["name"][:20]))

    def at(self, d: date, h0=9, h1=21) -> datetime:
        return datetime(d.year, d.month, d.day, self.r.randint(h0, h1), self.r.randrange(60), self.r.randrange(60), tzinfo=IST)

    # ------------------------------------------------------------------ templates
    def flatmates(self, g, city, start: date, payers: dict, maid=4500, cook=0, isp="airtelfiber", wifi=942.82, last_pending=True):
        power = R.CITIES[city]["power"] if R.CITIES[city]["power"] != "bses_r" else "bses_y"
        mem = g["members"]
        for ms in month_starts(start, R.END):
            mon = MON[ms.month - 1]
            last_day = min(R.END, date(ms.year, ms.month, dim(ms.year, ms.month)))
            if date(ms.year, ms.month, 3) <= R.END:
                self.expense(g, payers["maid"], P(maid), f"Maid salary – {mon}", "home_services", self.at(date(ms.year, ms.month, self.r.randint(1, 4)), 8, 11),
                             payee=payers.get("maid_name", "LAKSHMAMMA"))
                if cook:
                    self.expense(g, payers["maid"], P(cook), f"Cook salary – {mon}", "home_services", self.at(date(ms.year, ms.month, self.r.randint(1, 4)), 8, 11),
                                 payee=payers.get("cook_name", "MANJULA"))
            if date(ms.year, ms.month, 9) <= R.END:
                self.expense(g, payers["wifi"], P(wifi), "Wi-Fi bill", "mobile_internet", self.at(date(ms.year, ms.month, 8), 9, 22), merchant_key=isp)
            pd = date(ms.year, ms.month, 16)
            if pd <= R.END:
                amt = P(round(1100 * {3: 1.2, 4: 1.45, 5: 1.7, 6: 1.5, 7: 1.2}.get(ms.month, 1.0) * self.r.uniform(0.85, 1.2), 2))
                self.expense(g, payers["power"], amt, "Electricity bill", "utilities", self.at(pd, 10, 22), merchant_key=power)
            for _ in range(self.r.randint(3, 6)):
                d = ms + timedelta(days=self.r.randrange(dim(ms.year, ms.month)))
                if d <= R.END:
                    mk = self.r.choice(["instamart", "zepto", "blinkit", "bigbasket"])
                    self.expense(g, self.r.choice(mem), P(self.r.randint(350, 2200)), f"Groceries – {R.MERCHANT_BY_KEY[mk]['name']}", "groceries",
                                 self.at(d, 10, 23), merchant_key=mk, method=self.r.choice(["equal"] * 5 + ["exact"]))
            for wk in range(4):
                d = ms + timedelta(days=wk * 7 + self.r.randint(0, 3))
                if d <= R.END and d.month == ms.month:
                    self.expense(g, payers["water"], P(self.r.choice([4, 5, 6]) * self.r.choice([40, 45, 50])), "Water cans (20 L)", "utilities",
                                 self.at(d, 7, 11), payee=payers.get("water_name", "RAJU WATER SUPPLY"))
            if self.r.random() < 0.7:
                d = ms + timedelta(days=self.r.randrange(dim(ms.year, ms.month)))
                if d <= R.END:
                    mk = self.r.choice(["instamart", "zepto", "blinkit"])
                    self.expense(g, self.r.choice(mem), P(self.r.randint(450, 1600)), "Snacks & drinks run", "groceries", self.at(d, 19, 23), merchant_key=mk)
            if ms.month % 2 == 0:
                d = date(ms.year, ms.month, self.r.randint(5, 25))
                if d <= R.END:
                    self.expense(g, payers["gas"], P(R.CITIES[city]["lpg"]), "Gas cylinder", "utilities", self.at(d, 9, 18),
                                 merchant_key=self.r.choice(["indane", "hpgas", "bharatgas"]))
            settle_day = add_months(ms, 1) + timedelta(days=self.r.randint(1, 5))
            if settle_day <= R.END:
                self.settle(g, self.at(settle_day, 18, 23), status_fn=lambda w: "confirmed" if self.r.random() < 0.85 else "marked_paid")
        if not last_pending:
            self.settle(g, self.at(R.END, 18, 22))

    def trip(self, g, start: date, days: int, destination: str, booking: list[tuple], spots: list[str], settle_after=6, pending_ok=True):
        mem = g["members"]
        for (offset, desc, mk, amount, payer_idx) in booking:
            d = start - timedelta(days=offset)
            self.expense(g, mem[payer_idx], P(amount), desc, "travel", self.at(d, 10, 23), merchant_key=mk)
        for k in range(days):
            d = start + timedelta(days=k)
            if d > R.END:
                break
            items = [("Breakfast", "eating_out", (300, 900), None), (f"Lunch at {self.r.choice(spots)}", "eating_out", (900, 2600), None),
                     (f"Dinner at {self.r.choice(spots)}", "eating_out", (1400, 4800), None), ("Cab / taxi", "transport", (400, 2400), "driver"),
                     ("Snacks & water", "groceries", (150, 650), None)]
            if k in (0, days - 1):
                items.append(("Fuel", "fuel", (1200, 2600), "fuel"))
                items.append(("Toll", "transport", (160, 640), "fastag"))
            if self.r.random() < 0.7:
                items.append((self.r.choice(["Entry tickets", "Boating", "Scuba diving", "Trek guide", "Parasailing", "Kayaking"]), "entertainment",
                              (600, 6000), None))
            for desc, cat, (lo, hi), how in items:
                payer = self.r.choice(mem)
                amt = P(self.r.randint(lo, hi))
                if how == "fastag":
                    self.expense(g, payer, amt, desc, cat, self.at(d, 7, 20), merchant_key="fastag")
                elif how == "fuel":
                    self.expense(g, payer, amt, desc, cat, self.at(d, 7, 20), merchant_key=self.r.choice(["iocl", "hpcl", "bpcl"]))
                else:
                    self.expense(g, payer, amt, desc, cat, self.at(d, 8, 23), payee=f"{destination.upper()} {cat.replace('_', ' ').upper()}" if how is None
                                 else self.r.choice(["MAHESH NAIK", "JOSEPH D SOUZA", "SURESH GOWDA", "ABDUL RAHMAN"]),
                                 method=self.r.choice(["equal"] * 6 + ["exact", "percent"]))
        settle_day = start + timedelta(days=days + settle_after)
        if settle_day <= R.END:
            self.settle(g, self.at(settle_day, 18, 23), status_fn=lambda w: "confirmed" if self.r.random() < 0.7 else "marked_paid")
        elif pending_ok:
            pass   # recent trip: balances still open

    def household(self, g, start: date, guest_payers: list, extra_items: list[tuple]):
        for ms in month_starts(start, R.END):
            for payer, desc, cat, lo, hi, n in extra_items:
                for _ in range(n):
                    d = ms + timedelta(days=self.r.randrange(dim(ms.year, ms.month)))
                    if d <= R.END:
                        self.expense(g, guest_payers[payer], P(self.r.randint(lo, hi)), desc, cat, self.at(d), method=self.r.choice(["equal", "percent"]))


def build_groups(demo: list, evals: list, seed: int = 99) -> GroupMaker:
    gm = GroupMaker(seed)
    by_p = {s.persona_id: s for s in demo}
    r = gm.r

    # Karthik: upcoming Pondicherry trip with a pot
    s = by_p["student"]
    g = gm.new_group("demo_student", "trip", "Pondy trip", "🏖️", s, date(2026, 10, 20), pot=16000, pot_deadline="2026-12-15")
    me = gm.member(g, s.full_name, s.user_id, "owner")
    friends = [gm.member(g, n) for n in ["ARUN KUMAR", "DIVYA SUBRAMANIAN", "VIGNESH RAJAN", "SNEHA PRAKASH"]]
    gm.expense(g, friends[0], P(5000), "Homestay advance (White Town)", "travel", gm.at(date(2026, 11, 10)), payee="AROMA HOMESTAY")
    gm.expense(g, me, P(2640), "Bus tickets (redBus) Chennai–Pondy", "travel", gm.at(date(2026, 11, 12)), merchant_key="redbus")
    gm.expense(g, friends[2], P(1200), "Scooter rental advance", "transport", gm.at(date(2026, 11, 15)), payee="PONDY BIKE RENTALS")
    gm.settle(g, gm.at(date(2026, 11, 16)), status_fn=lambda w: r.choice(["marked_paid", "pending", "pending"]))
    for i, m in enumerate(g["members"]):
        for k in range(r.randint(1, 3)):
            g["pot_contributions"].append(dict(id=uid(g["group_id"], "pot", i, k), member_id=m["member_id"], amount_paise=P(r.choice([500, 1000, 1500])),
                                               method="upi", note="For Pondy", occurred_at=gm.at(date(2026, 10, 25) + timedelta(days=r.randint(0, 22))).isoformat()))

    # Ananya: flat in HSR Layout
    s = by_p["first_job"]
    g = gm.new_group("demo_first_job", "flatmates", "HSR 2BHK flat", "🏠", s, date(2025, 11, 1), budget=9000)
    me = gm.member(g, s.full_name, s.user_id, "owner")
    megha, riya = gm.member(g, "MEGHA RAO"), gm.member(g, "RIYA SHETTY")
    gm.flatmates(g, "Bengaluru", date(2025, 11, 1), dict(maid=me, wifi=me, power=megha, water=riya, gas=riya, maid_name="LAKSHMAMMA",
                                                          water_name="SRI RAMA WATER SUPPLY"), maid=4500, isp="airtelfiber", wifi=942.82)
    for m in g["members"]:
        m["sharing"] = dict(category_ids=["groceries"] if m is me else [], show_transactions=False, goal_ids=[])

    # Lakshmi: household group, links to her own ledger after build
    s = by_p["family"]
    g = gm.new_group("demo_family", "family", "Narayanan family", "👨‍👩‍👧‍👦", s, date(2026, 4, 1), budget=45000, pot=40000, pot_deadline="2027-05-15")
    me = gm.member(g, s.full_name, s.user_id, "owner")
    ramesh, amma = gm.member(g, "RAMESH NARAYANAN"), gm.member(g, "KAMALA NARAYANAN")
    gm.household(g, date(2026, 4, 1), {"ramesh": ramesh, "amma": amma},
                 [("ramesh", "Amma's medicines", "health", 1400, 2600, 1), ("ramesh", "Vegetables & fruits (Koyambedu)", "groceries", 900, 2200, 2),
                  ("ramesh", "Car service / petrol", "fuel", 1500, 3200, 1), ("amma", "Temple & pooja items", "gifts_donations", 200, 900, 1)])
    gm.link_requests.append(dict(group=g, user_id=s.user_id, payer=me, members=[me, ramesh], categories=["groceries", "utilities", "health", "education"],
                                 per_month=4, method="percent"))
    for k, ms in enumerate(month_starts(date(2026, 8, 1), R.END)):
        for m in (me, ramesh):
            g["pot_contributions"].append(dict(id=uid(g["group_id"], "pot", k, m["member_id"]), member_id=m["member_id"], amount_paise=P(3000),
                                               method="upi", note="Kodai trip", occurred_at=gm.at(ms + timedelta(days=4)).isoformat()))
    me["sharing"] = dict(category_ids=["groceries", "utilities"], show_transactions=True, goal_ids=[])

    # Rahul: shared room in Laxmi Nagar
    s = by_p["gig"]
    g = gm.new_group("demo_gig", "flatmates", "Laxmi Nagar room", "🛏️", s, date(2025, 11, 1), budget=4500)
    me = gm.member(g, s.full_name, s.user_id, "owner")
    vikas, sonu = gm.member(g, "VIKAS YADAV"), gm.member(g, "SONU KUMAR")
    gm.flatmates(g, "Delhi", date(2025, 11, 1), dict(maid=vikas, wifi=sonu, power=me, water=vikas, gas=sonu, maid_name="REKHA DEVI",
                                                      water_name="SHIV WATER SUPPLY"), maid=1500, isp="excitel", wifi=589.0)

    # Sunita: family group linked to her ledger
    s = by_p["shop"]
    g = gm.new_group("demo_shop", "family", "Agarwal parivaar", "🪔", s, date(2026, 5, 1), budget=40000)
    me = gm.member(g, s.full_name, s.user_id, "owner")
    rajesh, aman = gm.member(g, "RAJESH AGARWAL"), gm.member(g, "AMAN AGARWAL")
    gm.household(g, date(2026, 5, 1), {"rajesh": rajesh, "aman": aman},
                 [("rajesh", "Petrol (car)", "fuel", 1500, 3000, 1), ("rajesh", "Sabzi mandi", "groceries", 600, 1800, 2),
                  ("aman", "Coaching books & notes", "education", 300, 1500, 1)])
    gm.link_requests.append(dict(group=g, user_id=s.user_id, payer=me, members=[me, rajesh, aman], categories=["groceries", "utilities", "health", "gifts_donations"],
                                 per_month=3, method="equal"))

    # Vikram: college friends' trips (Goa done and settled; Lonavala recent and open)
    s = by_p["investor"]
    g = gm.new_group("demo_investor", "trip", "College gang trips", "🌴", s, date(2025, 11, 15), pot=100000, pot_deadline="2027-02-28")
    me = gm.member(g, s.full_name, s.user_id, "owner")
    gang = [gm.member(g, n) for n in ["ROHAN DESAI", "SIDDHARTH JOSHI", "KUNAL SHAH", "PRATIK PATIL"]]
    gm.trip(g, date(2025, 12, 26), 5, "Goa", [(40, "Villa booking (Assagao)", "airbnb", 64000, 0), (35, "Flights BOM–GOI (group)", "indigo", 41250, 2)],
            ["Gunpowder", "Britto's", "Fisherman's Wharf", "Thalassa", "beach shack"], settle_after=8)
    gm.trip(g, date(2026, 10, 31), 2, "Lonavala", [(12, "Bungalow booking", "airbnb", 22500, 0)], ["Della Adventure cafe", "Tiger Point stall", "Rama Krishna"],
            settle_after=25)
    for i, m in enumerate(g["members"]):
        g["pot_contributions"].append(dict(id=uid(g["group_id"], "pot", i), member_id=m["member_id"], amount_paise=P(5000), method="upi",
                                           note="Coorg 2027", occurred_at=gm.at(date(2026, 11, 3) + timedelta(days=i)).isoformat()))

    # 30 eval groups ----------------------------------------------------------------------------------------
    pools = {"family": [s for s in evals if s.archetype == "family"], "trip": [s for s in evals if s.archetype in ("student", "first_job", "investor")],
             "flatmates": [s for s in evals if s.archetype in ("first_job", "gig", "student")]}
    used = set()
    dest = [("Goa", ["beach shack", "Curlies", "Souza Lobo"]), ("Coorg", ["Raintree", "Coorg Cuisine"]), ("Manali", ["Johnson's Cafe", "Cafe 1947"]),
            ("Ooty", ["Earl's Secret", "Nahar"]), ("Rishikesh", ["Little Buddha Cafe", "Chotiwala"]), ("Hampi", ["Mango Tree", "Laughing Buddha"]),
            ("Udaipur", ["Ambrai", "Natraj"]), ("Munnar", ["Saravana Bhavan", "Rapsy"]), ("Pondicherry", ["Villa Shanti", "Cafe des Arts"]),
            ("Jaipur", ["LMB", "Tapri"])]
    for gtype in ("family", "trip", "flatmates"):
        for k in range(10):
            cands = [s for s in pools[gtype] if s.user_id not in used]
            n_app = 1 if gtype == "family" else r.choice([1, 1, 2, 2, 3])
            same_city = [s for s in cands if s.city == cands[0].city]
            app = (same_city if len(same_city) >= n_app else cands)[:n_app]
            for s in app:
                used.add(s.user_id)
            owner = app[0]
            region = owner.region
            if gtype == "family":
                g = gm.new_group(f"eval_family_{k}", "family", f"{owner.full_name.split()[-1]} family", "👪", owner, date(2026, r.randint(1, 6), 1),
                                 budget=round(r.uniform(20000, 60000), -3))
                me = gm.member(g, owner.full_name, owner.user_id, "owner")
                guests = [gm.member(g, _guest(region, r)) for _ in range(r.randint(1, 3))]
                start = date.fromisoformat(g["created_at"])
                for ms in month_starts(start, R.END):
                    for _ in range(r.randint(2, 5)):
                        d = ms + timedelta(days=r.randrange(dim(ms.year, ms.month)))
                        if d > R.END:
                            continue
                        desc, cat, lo, hi, mk = r.choice([("Monthly groceries", "groceries", 1500, 6000, "dmart"), ("Medicines", "health", 300, 2500, "apollopharmacy"),
                                                          ("Electricity", "utilities", 900, 3500, None), ("Dinner out", "eating_out", 800, 3500, None),
                                                          ("Festival shopping", "shopping", 1500, 9000, "amazon"), ("Vegetables", "groceries", 300, 1200, None)])
                        payer = r.choice([me] + guests)
                        gm.expense(g, payer, P(r.randint(lo, hi)), desc, cat, gm.at(d), method=r.choice(["equal", "percent", "exact"]),
                                   merchant_key=mk, payee=None if mk else _guest(region, r))
                    if r.random() < 0.3:
                        gm.settle(g, gm.at(min(R.END, add_months(ms, 1) + timedelta(days=3))))
            elif gtype == "trip":
                place, spots = dest[k]
                g = gm.new_group(f"eval_trip_{k}", "trip", f"{place} trip", "🧳", owner, date(2026, r.randint(1, 9), r.randint(1, 25)),
                                 pot=round(r.uniform(15000, 80000), -3))
                for s in app:
                    gm.member(g, s.full_name, s.user_id, "owner" if s is owner else "member")
                for _ in range(r.randint(2, 4)):
                    gm.member(g, _guest(region, r))
                start = date.fromisoformat(g["created_at"]) + timedelta(days=r.randint(20, 50))
                if start > R.END:
                    start = R.END - timedelta(days=r.randint(5, 20))
                gm.trip(g, start, r.randint(2, 5), place, [(r.randint(10, 30), "Train / bus tickets", r.choice(["irctc", "redbus"]), r.randint(2400, 9000), 0),
                                                           (r.randint(8, 25), "Stay booking", r.choice(["oyo", "makemytrip", "airbnb"]), r.randint(6000, 30000),
                                                            r.randrange(len(g["members"])))], spots, settle_after=r.randint(3, 12))
            else:
                g = gm.new_group(f"eval_flat_{k}", "flatmates", f"{owner.area} flat", "🏠", owner, date(2025, 11, 1), budget=round(r.uniform(4000, 12000), -3))
                for s in app:
                    gm.member(g, s.full_name, s.user_id, "owner" if s is owner else "member")
                for _ in range(r.randint(1, 3)):
                    gm.member(g, _guest(region, r))
                m = g["members"]
                gm.flatmates(g, owner.city, date(2025, 11, 1), dict(maid=m[0], wifi=m[-1], power=m[len(m) // 2], water=r.choice(m), gas=r.choice(m)),
                             maid=r.choice([1500, 2500, 3500, 4500]), isp=r.choice(["airtelfiber", "jiofiber", "act" if owner.city in ("Bengaluru", "Chennai", "Hyderabad", "Delhi") else "jiofiber"]),
                             wifi=r.choice([589.0, 799.0, 942.82, 1178.82]))
    return gm


def _guest(region: str, r: random.Random) -> str:
    pool = R.NAMES[region]
    g = r.choice(["male", "female"])
    return f"{r.choice(pool[g])} {r.choice(pool['surname'])}".upper()


def link_household(gm: GroupMaker, builder, req: dict):
    """Turn some of the owner's own ledger transactions into group expenses ("split with group" from the Money tab)."""
    g = req["group"]
    start = date.fromisoformat(g["created_at"])
    cands = [t for t in builder.accepted if t.direction == "debit" and t.status == "success" and t.category in req["categories"]
             and t.ts.date() >= start and t.amount >= P(300) and not t.group_expense_id and builder.by_id[t.account_id].type != "credit_card"]
    by_month = defaultdict(list)
    for t in cands:
        by_month[(t.ts.year, t.ts.month)].append(t)
    for key in sorted(by_month):
        picks = gm.r.sample(by_month[key], min(req["per_month"], len(by_month[key])))
        for t in picks:
            desc = {"groceries": "Groceries", "utilities": "Electricity / gas", "health": "Medicines", "education": "School things",
                    "gifts_donations": "Gifts & pooja"}.get(t.category, "Household") + f" – {(t.cp_name or '').title()[:24]}"
            e = gm.expense(g, req["payer"], t.amount, desc, t.category, t.ts, method=req["method"], members=req["members"])
            e["linked_transaction_id"] = t.id
            t.group_expense_id = e["expense_id"]
            gm.events[req["user_id"]] = [ev for ev in gm.events[req["user_id"]] if ev.get("group_expense_id") != e["expense_id"]]
