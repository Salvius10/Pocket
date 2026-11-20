"""Six demo personas and a sampler for 200 evaluation users.

All people, employers, schools and landlords are invented. Merchants are real brands (as they
appear in real statements) or invented neighbourhood shops.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from . import refdata as R
from .spec import AccountSpec, FlexSpec, IncomeSpec, RecurringSpec, UserSpec

PLANT_TYPES = ["forgotten_subscription", "price_hike", "category_creep", "duplicate_charge", "idle_cash", "expensive_card_balance"]
CREEP_MONTHS = ["2026-08", "2026-09", "2026-10", "2026-11"]


def pool(city: str, items: list[tuple[str, float]]) -> list[tuple[str, float]]:
    out = []
    for k, w in items:
        if k.startswith(("LOCAL:", "P2P:", "CITY:", "SUPPLIER:")):
            out.append((k, w))
            continue
        m = R.MERCHANT_BY_KEY.get(k)
        if m and (m["cities"] is None or city in m["cities"]):
            out.append((k, w))
    return out or [("LOCAL:kirana", 1.0)]


def eat_out_pool(city: str, upscale: float = 1.0) -> list[tuple[str, float]]:
    items = []
    for m in R.MERCHANTS:
        if m["category"] != "eating_out" or m["local"]:
            continue
        if m["cities"] is None:
            items.append((m["key"], 0.6))
        elif city in m["cities"]:
            items.append((m["key"], 1.4 if len(m["cities"]) <= 3 else 0.9))
    for m in R.MERCHANTS:
        if m["local"] and m["category"] == "eating_out" and m["cities"] == [city]:
            items.append((m["key"], 1.0 / upscale))
    items.append(("LOCAL:mess", 1.5 / upscale))
    items.append(("LOCAL:bakery", 0.8))
    return items


def local_key(city: str, category: str, i: int = 0) -> list[str]:
    ks = [m["key"] for m in R.MERCHANTS if m["local"] and m["cities"] == [city] and m["category"] == category]
    return ks[i:i + 1] if len(ks) > i else []


def creep(f: float) -> dict[str, float]:
    return {m: f for m in CREEP_MONTHS[:-1]} | {CREEP_MONTHS[-1]: round(f * 1.02, 3)}


FOOD = [("swiggy", 0.48), ("zomato", 0.44), ("eatsure", 0.03), ("dominos", 0.03), ("box8", 0.02)]
QUICK = [("blinkit", 0.4), ("zepto", 0.35), ("instamart", 0.25)]
TRANSPORT = [("uber", 0.3), ("ola", 0.2), ("rapido", 0.25), ("P2P:auto", 0.15), ("CITY:metro", 0.1)]
SHOP = [("amazon", 0.28), ("flipkart", 0.22), ("myntra", 0.1), ("ajio", 0.05), ("meesho", 0.06), ("zudio", 0.06),
        ("trends", 0.05), ("westside", 0.04), ("decathlon", 0.03), ("croma", 0.03), ("lifestyle", 0.03), ("bata", 0.02),
        ("lenskart", 0.02), ("boat", 0.01)]
FUN = [("bookmyshow", 0.45), ("pvrinox", 0.35), ("district", 0.15), ("timezone", 0.05)]
HEALTH = [("apollopharmacy", 0.3), ("medplus", 0.2), ("LOCAL:pharmacy", 0.3), ("tata1mg", 0.1), ("pharmeasy", 0.05), ("lalpathlabs", 0.05)]
CARE = [("LOCAL:salon", 0.6), ("naturals", 0.2), ("greentrends", 0.1), ("lakmesalon", 0.1)]
GIFTS = [("amazon", 0.3), ("fnp", 0.25), ("igp", 0.2), ("giveindia", 0.15), ("cry", 0.1)]
TRAVEL = [("irctc", 0.35), ("redbus", 0.2), ("makemytrip", 0.15), ("indigo", 0.1), ("abhibus", 0.05), ("oyo", 0.1), ("goibibo", 0.05)]
FUEL = [("LOCAL:fuel", 0.55), ("iocl", 0.15), ("hpcl", 0.15), ("bpcl", 0.12), ("shell", 0.03)]
TEA = [("LOCAL:tea", 0.6), ("LOCAL:bakery", 0.25), ("chaipoint", 0.15)]
SUBS_PRICE = {"spotify": 139, "youtubepremium": 149, "jiosaavn": 99, "zee5": 99, "sonyliv": 299, "aha": 99, "sunnxt": 50,
              "audible": 199, "kindleunlimited": 169, "linkedin": 1567, "cultfit": 1999, "googleone": 130, "duolingo": 299,
              "microsoft365": 489, "openai": 1999, "netflix": 199, "primevideo": 299}
POWER_BASE = {"bimonthly": 1700, "monthly": 1100}
SUMMER = {3: 1.2, 4: 1.45, 5: 1.7, 6: 1.6, 7: 1.3, 8: 1.15, 9: 1.1, 10: 1.05, 11: 0.95, 12: 0.85, 1: 0.85, 2: 0.95}


def power_merchant(city: str, r: random.Random) -> str:
    p = R.CITIES[city]["power"]
    if p == "bses_r":
        return r.choice(["bses_r", "bses_y", "tpddl"])
    return p


def est_outflow(s: UserSpec) -> float:
    per_month = {"monthly": 1.0, "every_28d": 30.44 / 28, "bimonthly": 0.5, "quarterly": 1 / 3, "yearly": 1 / 12, "every_n_days": 1.0}
    total = 0.0
    for rs in s.recurring:
        if rs.loan:
            P_, r_, n_ = rs.loan["principal"], rs.loan["rate_bps"] / 120000, rs.loan["tenure"]
            total += P_ / n_ if rs.loan.get("zero_cost") else P_ * r_ * (1 + r_) ** n_ / ((1 + r_) ** n_ - 1)
            continue
        f = per_month.get(rs.cadence, 1.0)
        if rs.cadence in ("quarterly", "yearly", "bimonthly") and rs.months:
            f = len(rs.months) / 12
        if rs.cadence == "every_n_days":
            f = 30.44 / rs.every_days
        if rs.account != "business" and rs.channel != "card":
            total += rs.amount * f
    for fs in s.flex:
        if fs.account != "business":
            total += fs.monthly_count * fs.median * 1.12
    total += s.atm_per_month * (sum(s.atm_amounts) / len(s.atm_amounts))
    return total


# ---------------------------------------------------------------------------------------------- planted patterns
def apply_planted(s: UserSpec, planted: set[str], r: random.Random, cfg: dict):
    s.planted = {p: {} for p in planted}
    if "category_creep" in planted:
        for fs in s.flex:
            if fs.category == "food_delivery":
                fs.trend = creep(cfg.get("creep", round(r.uniform(1.32, 1.40), 3)))
                fs.noise = 0.03
                s.planted["category_creep"] = dict(category="food_delivery", multiplier=fs.trend[CREEP_MONTHS[0]],
                                                   earlier_months=["2026-05", "2026-06", "2026-07"], recent_months=CREEP_MONTHS[:3])
    if "forgotten_subscription" in planted:
        mk = cfg.get("forgotten_merchant") or r.choice(cfg.get("forgotten_choices", ["audible", "zee5", "sonyliv", "jiosaavn", "duolingo", "kindleunlimited"]))
        md = cfg.get("mandate_date") or (date(2026, 1, 5) + timedelta(days=r.randrange(195)))
        amt = cfg.get("forgotten_amount") or SUBS_PRICE.get(mk, 199)
        s.recurring.append(RecurringSpec(key=f"sub_{mk}", kind="subscription", name=R.MERCHANT_BY_KEY[mk]["name"], category="subscriptions",
                                         amount=amt, cadence="monthly", channel="autopay", merchant=mk, planted="forgotten_subscription",
                                         mandate_date=md, trial_days=cfg.get("trial_days", r.choice([7, 30]))))
        s.planted["forgotten_subscription"] = dict(merchant_key=mk, monthly_amount=amt, mandate_date=md.isoformat())
    if "price_hike" in planted:
        cands = [rs for rs in s.recurring if rs.kind in ("recharge", "subscription", "bill") and not rs.variable and not rs.seasonal
                 and not rs.planted and rs.channel != "ach" and rs.cadence in ("monthly", "every_28d")]
        pref = [rs for rs in cands if rs.key == cfg.get("price_hike_key")]
        rs = (pref or cands)[0] if (pref or cands) else None
        if rs:
            if cfg.get("price_hike_new"):
                new = cfg["price_hike_new"]
            elif rs.amount != int(rs.amount):
                # GST-inclusive bill (e.g. plan 799 + 18% = 942.82): raise the plan price, then add GST back
                base = round(rs.amount / 1.18)
                new = round((round(base * r.uniform(1.11, 1.2) / 10) * 10 - 1) * 1.18, 2)
            else:
                new = round(rs.amount * r.uniform(1.11, 1.2) / 10) * 10 - 1
            when = cfg.get("price_hike_date") or (date(2026, 10, 1) + timedelta(days=r.randrange(18)))
            rs.price_changes = [(when, new)]
            rs.planted = "price_hike"
            s.planted["price_hike"] = dict(recurring_key=rs.key, merchant_key=rs.merchant, old_amount=rs.amount, new_amount=new,
                                           effective=when.isoformat())
    if "duplicate_charge" in planted:
        s.planted["duplicate_charge"] = dict(merchants=cfg.get("dup_merchants", ["zepto", "swiggy", "uber", "blinkit", "zomato", "bigbasket", "amazon"]))
    out = est_outflow(s)
    if "idle_cash" in planted:
        role = cfg.get("idle_role")
        acc = next((a for a in s.accounts if a.role == role), None) if role else None
        if acc is None:
            acc = next((a for a in s.accounts if a.role == "secondary" and a.type == "savings"), None)
        if acc is None:
            # money often sits forgotten in an older, second account
            acc = AccountSpec("secondary", r.choice(["SBI", "CANARA", "BOB", "HDFC", "ICICI"]), "savings", 0,
                              date(r.randint(2012, 2020), r.randint(1, 12), r.randint(1, 28)), nickname="Old savings account")
            s.accounts.append(acc)
        acc.idle = True
        acc.sweep_cap = None
        if "idle_opening" in cfg:
            acc.opening_balance = cfg["idle_opening"]
        elif acc.role == "primary":
            acc.opening_balance = max(acc.opening_balance, round(out * r.uniform(2.6, 3.6) + 30000, -3))
        else:
            acc.opening_balance = max(acc.opening_balance, round(r.uniform(45000, 220000), -3))
        s.planted["idle_cash"] = dict(account_role=acc.role)
    for a in s.accounts:
        if a.type == "savings" and not a.idle and a.sweep_cap is None:
            a.sweep_cap = round(out + 15000, -3) if a.role == "primary" else 25000
    if "expensive_card_balance" in planted:
        card = next((a for a in s.accounts if a.type == "credit_card"), None)
        if card is None:
            card = AccountSpec(role="card", bank=cfg.get("card_bank", r.choice(["HDFC", "ICICI", "SBI", "AXIS"])), type="credit_card",
                               opening_balance=round(out * 0.2, -2), opened=date(2023, r.randint(1, 12), r.randint(1, 28)),
                               card_limit=max(30000, round(out * 2.5, -4)), statement_day=r.choice([3, 8, 12, 15, 18, 22]))
            s.accounts.append(card)
        sd = card.statement_day
        s.revolve_statements = ["2026-09", "2026-10", "2026-11"] if sd <= 18 else ["2026-09", "2026-10"]
        s.revolve_pay_fraction = cfg.get("revolve_fraction", r.choice([0.05, 0.05, 0.1, 0.25]))
        if not cfg.get("demo"):
            big = round(card.card_limit * r.uniform(0.3, 0.5), -2)
            when = date(2026, 9, max(1, sd - r.randint(3, 10)))     # lands in the September statement
            s.one_offs.append(dict(date=when, merchant=r.choice(["flipkart", "amazon", "croma", "reliancedigital"]),
                                   amount=big, category="shopping", channel="card"))
            s.one_offs.append(dict(date=date(2026, 10, max(1, sd - r.randint(2, 8))), merchant=r.choice(["myntra", "amazon", "ajio", "nykaa"]),
                                   amount=round(card.card_limit * r.uniform(0.04, 0.1), -2), category="shopping", channel="card"))
        s.planted["expensive_card_balance"] = dict(card_bank=card.bank, statement_day=sd, revolve_statements=s.revolve_statements)


# ---------------------------------------------------------------------------------------------- archetypes
def student(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    allowance = cfg.get("allowance", r.choice([4000, 5000, 6000, 7000, 8000]))
    fd_med = cfg.get("fd_median", r.choice([230, 250, 270]))
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="student", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(18, 22)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="student", occupation=cfg.get("occupation", "College student"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["KOTAK", "SBI", "CANARA", "AXIS"])), "savings",
                                       cfg.get("opening", r.choice([2200, 3400, 4800, 6100])), date(2024, r.randint(1, 12), r.randint(1, 28)))],
                 incomes=[IncomeSpec("allowance", cfg.get("parent", "PARENT"), allowance, category="allowance", mode="upi", day=1)],
                 recurring=[RecurringSpec("recharge", "recharge", "Mobile recharge", "mobile_internet", cfg.get("recharge", 299), "every_28d",
                                          merchant=cfg.get("telco", r.choice(["jio", "airtel", "vi"])), start=R.START + timedelta(days=r.randint(1, 20)))],
                 flex=[
                     FlexSpec("tea", "eating_out", cfg.get("tea_n", 18), 25, 0.5, 10, 120, pool(city, TEA), round_to=5, hours="tea", weekend=0.7),
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 11), fd_med, 0.35, 120, 550, pool(city, FOOD), hours="late_meal",
                              weekend=1.5, payday=1.3, noise=0.04, refund_rate=0.02),
                     FlexSpec("eat_out", "eating_out", 4, 180, 0.5, 60, 700, pool(city, eat_out_pool(city, 2.0)), hours="meal", weekend=1.6),
                     FlexSpec("transport", "transport", 10, 60, 0.6, 20, 350, pool(city, TRANSPORT), hours="commute", weekend=0.6),
                     FlexSpec("shopping", "shopping", 1.8, 600, 0.8, 99, 4000, pool(city, SHOP), channel_mix={"upi": 0.65, "card": 0.35},
                              hours="online", habitual=False, refund_rate=0.04),
                     FlexSpec("fun", "entertainment", 1.4, 190, 0.4, 99, 600, pool(city, FUN), hours="evening", habitual=False, weekend=2.0),
                     FlexSpec("quick", "groceries", 2, 220, 0.5, 60, 700, pool(city, QUICK), channel_mix={"upi": 0.75, "card": 0.25}, hours="evening"),
                     FlexSpec("friends", "other_expense", 4, 150, 0.6, 20, 1000, [("P2P:friend", 1.0)], round_to=10, hours="evening", weekend=1.5),
                     FlexSpec("care", "personal_care", 0.8, 150, 0.4, 60, 500, pool(city, CARE), round_to=10),
                     FlexSpec("xerox", "education", 3, 40, 0.6, 10, 300, [("LOCAL:xerox", 1.0)], round_to=5, hours="day", weekend=0.3),
                 ],
                 atm_per_month=0.3, atm_amounts=[500, 1000], topup_from=cfg.get("parent", "PARENT"))
    if cfg.get("tuition", True):
        s.incomes.append(IncomeSpec("p2p_irregular", "TUITION", 0, category="other_income", mode="upi", per_month=2.0,
                                    choices=[1200, 1500, 2000, 2500], purpose="Tuition fees"))
    if cfg.get("youtube", r.random() < 0.4):
        s.recurring.append(RecurringSpec("yt", "subscription", "YouTube Premium (student)", "subscriptions", 89, "monthly", day=18,
                                         channel="autopay", merchant="youtubepremium"))
    s.recurring.append(RecurringSpec("exam_fee", "fees", "Semester exam fee", "education", cfg.get("exam_fee", 1450), "yearly", day=12,
                                     months=[11, 4], merchant="sbcollect"))
    return s


def first_job(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    sal = cfg.get("salary", round(r.uniform(38000, 82000)))
    rent = cfg.get("rent", round(sal * r.uniform(0.2, 0.3), -2))
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="first_job", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(22, 27)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="salaried", occupation=cfg.get("occupation", "Software engineer"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["HDFC", "ICICI", "AXIS", "KOTAK", "SBI"])), "savings",
                                       cfg.get("opening", round(sal * r.uniform(0.6, 1.4), -2)), cfg.get("opened", date(2025, r.randint(1, 8), r.randint(1, 28)))),
                           AccountSpec("secondary", cfg.get("bank2", r.choice(["SBI", "CANARA", "BOB", "KOTAK"])), "savings",
                                       cfg.get("opening2", r.choice([1800, 4300, 7600, 9900])), date(2019, r.randint(1, 12), r.randint(1, 28)))],
                 incomes=[IncomeSpec("salary", cfg.get("employer", "ACME SOFTWARE SOLUTIONS PVT LTD"), sal, rule=cfg.get("salary_rule", "last_working_day"),
                                     changes=cfg.get("salary_changes", [(date(2026, r.choice([4, 6, 7]), 28), round(sal * r.uniform(1.06, 1.12)))]),
                                     payer_bank=cfg.get("payer_bank", r.choice(["ICIC", "HDFC", "UTIB", "CITI"])))],
                 recurring=[
                     RecurringSpec("rent", "rent", "Rent", "rent", rent, "monthly", day=cfg.get("rent_day", r.choice([1, 2, 3, 5])), channel="upi_p2p",
                                   payee=cfg.get("landlord", "LANDLORD"), lag_days=(0, 2),
                                   price_changes=cfg.get("rent_changes", [(date(2026, r.choice([5, 6, 7]), 1), round(rent * r.uniform(1.05, 1.08), -2))])),
                     RecurringSpec("recharge", "recharge", "Mobile recharge", "mobile_internet", cfg.get("recharge", 349), "every_28d",
                                   merchant=cfg.get("telco", r.choice(["jio", "airtel"])), start=R.START + timedelta(days=r.randint(1, 20))),
                 ],
                 flex=[
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 20), cfg.get("fd_median", 270), 0.4, 120, 900, pool(city, FOOD),
                              channel_mix={"upi": 0.8, "card": 0.2}, hours="late_meal", weekend=1.4, payday=1.25, noise=0.04, refund_rate=0.02),
                     FlexSpec("quick", "groceries", 9, 330, 0.5, 90, 1500, pool(city, QUICK), channel_mix={"upi": 0.7, "card": 0.3}, hours="evening",
                              refund_rate=0.02),
                     FlexSpec("eat_out", "eating_out", cfg.get("eat_n", 6), 380, 0.6, 120, 2500, pool(city, eat_out_pool(city)),
                              channel_mix={"upi": 0.75, "card": 0.25}, hours="meal", weekend=1.8),
                     FlexSpec("tea", "eating_out", 10, 35, 0.4, 15, 120, pool(city, TEA), round_to=5, hours="tea", weekend=0.6),
                     FlexSpec("transport", "transport", 18, 190, 0.5, 30, 900, pool(city, TRANSPORT), channel_mix={"upi": 0.8, "card": 0.2},
                              hours="commute", weekend=0.7),
                     FlexSpec("shopping", "shopping", 3, 900, 0.9, 149, 12000, pool(city, SHOP), channel_mix={"upi": 0.4, "card": 0.6},
                              hours="online", habitual=False, refund_rate=0.05),
                     FlexSpec("fun", "entertainment", 2, 420, 0.5, 150, 1500, pool(city, FUN), channel_mix={"upi": 0.5, "card": 0.5},
                              hours="evening", habitual=False, weekend=2.0),
                     FlexSpec("care", "personal_care", 1, 650, 0.5, 150, 2500, pool(city, CARE)),
                     FlexSpec("health", "health", 1.2, 350, 0.6, 60, 2500, pool(city, HEALTH)),
                     FlexSpec("friends", "other_expense", 3, 300, 0.6, 50, 2500, [("P2P:friend", 1.0)], round_to=10, hours="evening"),
                     FlexSpec("home", "home_services", 0.3, 600, 0.5, 200, 2500, pool(city, [("urbancompany", 0.8), ("tumbledry", 0.2)]), habitual=False),
                     FlexSpec("gifts", "gifts_donations", 0.5, 900, 0.6, 199, 5000, pool(city, GIFTS), habitual=False, hours="online"),
                     FlexSpec("travel", "travel", 0.4, 1800, 0.6, 400, 9000, pool(city, TRAVEL), channel_mix={"upi": 0.5, "card": 0.5}, habitual=False, hours="online"),
                 ],
                 atm_per_month=0.5, atm_amounts=[1000, 2000], topup_from=cfg.get("parent", "PARENT"))
    if cfg.get("card", True):
        s.accounts.append(AccountSpec("card", cfg.get("card_bank", r.choice(["ICICI", "HDFC", "AXIS", "SBI"])), "credit_card",
                                      cfg.get("card_opening", round(sal * 0.12, -2)), date(2025, r.randint(1, 9), r.randint(1, 28)),
                                      card_limit=cfg.get("card_limit", round(sal * 2, -4)), statement_day=cfg.get("statement_day", r.choice([5, 12, 15, 18, 22]))))
    for i, (code, amt, day, plat) in enumerate(cfg.get("sips", [(r.choice([120716, 122639, 118825]), r.choice([1000, 2000, 3000]), r.choice([5, 10, 15]), "iccl")])):
        s.recurring.append(RecurringSpec(f"sip_{i}", "sip", R.FUND_BY_CODE[code][1], "investment", amt, "monthly", day=day, channel="ach",
                                         merchant="iccl" if plat == "iccl" else "nsccl", scheme_code=code, platform=plat,
                                         invested_before=cfg.get("sip_before", amt * r.randint(2, 10))))
    for key, mk, price, day, ch in cfg.get("subs", [("spotify", "spotify", 119, 5, "autopay"), ("netflix", "netflix", 199, 22, "card")]):
        s.recurring.append(RecurringSpec(key, "subscription", R.MERCHANT_BY_KEY[mk]["name"], "subscriptions", price, "monthly", day=day,
                                         channel=ch, merchant=mk))
    return s


def family(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    sal = cfg.get("salary", round(r.uniform(55000, 140000)))
    spouse = cfg.get("spouse_amount", round(sal * r.uniform(0.3, 0.6), -3))
    bill = R.CITIES[city]["bill"]
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="family", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(32, 48)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="salaried", occupation=cfg.get("occupation", "Accounts manager"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["SBI", "HDFC", "ICICI", "CANARA", "BOB"])), "savings",
                                       cfg.get("opening", round(sal * r.uniform(0.5, 1.2), -3)), date(2012, r.randint(1, 12), r.randint(1, 28))),
                           AccountSpec("secondary", cfg.get("bank2", r.choice(["HDFC", "AXIS", "KOTAK", "SBI"])), "savings",
                                       cfg.get("opening2", round(r.uniform(8000, 22000), -2)), date(2016, r.randint(1, 12), r.randint(1, 28)))],
                 incomes=[IncomeSpec("salary", cfg.get("employer", "SUNRISE INDUSTRIES PVT LTD"), sal, rule=cfg.get("salary_rule", "first_working_day"),
                                     changes=cfg.get("salary_changes", [(date(2026, 5, 1), round(sal * r.uniform(1.05, 1.09)))]),
                                     payer_bank=cfg.get("payer_bank", r.choice(["HDFC", "ICIC", "UTIB"]))),
                          IncomeSpec("spouse_transfer", cfg.get("spouse", "SPOUSE"), spouse, category="other_income", mode="imps", day=2)],
                 recurring=[
                     RecurringSpec("power", "bill", "Electricity", "utilities", POWER_BASE[bill] * cfg.get("power_scale", r.uniform(0.9, 1.4)),
                                   bill, day=14, channel="billpay", merchant=power_merchant(city, r),
                                   months=[1, 3, 5, 7, 9, 11] if bill == "bimonthly" else None, seasonal=SUMMER, variable=0.1),
                     RecurringSpec("lpg", "lpg", "Cooking gas", "utilities", R.CITIES[city]["lpg"], "every_n_days", every_days=cfg.get("lpg_days", 48),
                                   merchant=r.choice(["indane", "hpgas", "bharatgas"]), start=R.START + timedelta(days=r.randint(3, 30))),
                     RecurringSpec("maid", "maid", "House help", "home_services", cfg.get("maid", r.choice([2500, 3000, 3500, 4000])), "monthly",
                                   day=5, channel="upi_p2p", payee=cfg.get("maid_name", "MAID"), lag_days=(0, 2)),
                     RecurringSpec("broadband", "bill", "Broadband", "mobile_internet", cfg.get("broadband", 942.82), "monthly", day=8, channel="autopay",
                                   merchant=cfg.get("isp", r.choice(["airtelfiber", "jiofiber", "act"]))),
                     RecurringSpec("recharge", "recharge", "Mobile recharge", "mobile_internet", cfg.get("recharge", 379), "every_28d",
                                   merchant=cfg.get("telco", r.choice(["jio", "airtel"])), start=R.START + timedelta(days=r.randint(1, 20))),
                     RecurringSpec("school", "fees", "School fees", "education", cfg.get("school_fee", round(r.uniform(18000, 45000), -2)), "yearly",
                                   day=10, months=[6, 10, 1], channel="netbanking", payee=cfg.get("school", "SCHOOL FEES"), account="secondary"),
                     RecurringSpec("lic", "insurance", "LIC premium", "insurance", cfg.get("lic", round(r.uniform(3000, 8000), -1)), "quarterly",
                                   day=20, months=[2, 5, 8, 11], channel="ach", merchant="lic", account="secondary"),
                 ],
                 flex=[
                     FlexSpec("daily_groceries", "groceries", 14, 260, 0.6, 30, 1500,
                              pool(city, [("LOCAL:kirana", 0.4), ("LOCAL:veg", 0.3), ("LOCAL:bakery", 0.12), ("amul", 0.05)] +
                                   [(k, 0.08) for k in local_key(city, "groceries")]), round_to=1, hours="grocery"),
                     FlexSpec("supermarket", "groceries", 2, 3200, 0.35, 1200, 8000,
                              pool(city, [("nilgiris", 0.3), ("dmart", 0.25), ("more", 0.15), ("kannan", 0.15), ("smartbazaar", 0.15),
                                          ("ratnadeep", 0.3), ("starbazaar", 0.2), ("spencers", 0.1)]),
                              channel_mix={"upi": 0.5, "card": 0.5}, paise=True, hours="grocery", weekend=1.6),
                     FlexSpec("quick", "groceries", 5, 380, 0.5, 100, 1800, pool(city, [("bigbasket", 0.4)] + QUICK),
                              channel_mix={"upi": 0.6, "card": 0.4}, hours="evening", refund_rate=0.02),
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 10), cfg.get("fd_median", 420), 0.4, 150, 1400, pool(city, FOOD),
                              channel_mix={"upi": 0.7, "card": 0.3}, hours="late_meal", weekend=1.6, noise=0.04, refund_rate=0.02),
                     FlexSpec("eat_out", "eating_out", 4, 650, 0.5, 150, 3000, pool(city, eat_out_pool(city)), channel_mix={"upi": 0.6, "card": 0.4},
                              hours="meal", weekend=2.0),
                     FlexSpec("fuel", "fuel", cfg.get("fuel_n", 3), 2000, 0.25, 800, 3500, pool(city, FUEL), round_to=100,
                              channel_mix={"upi": 0.6, "card": 0.4}, hours="day"),
                     FlexSpec("transport", "transport", 4, 220, 0.5, 50, 900, pool(city, [("uber", 0.3), ("ola", 0.3), ("P2P:auto", 0.4)]), hours="day"),
                     FlexSpec("shopping", "shopping", 3, 1100, 0.9, 150, 15000,
                              pool(city, SHOP + [("pothys", 0.1), ("saravanastores", 0.08), ("chennaisilks", 0.08), ("nalli", 0.04), ("firstcry", 0.06)]),
                              channel_mix={"upi": 0.45, "card": 0.55}, hours="day", habitual=False, weekend=1.8, refund_rate=0.03),
                     FlexSpec("health", "health", 3, 480, 0.6, 60, 4000, pool(city, HEALTH)),
                     FlexSpec("fun", "entertainment", 1, 900, 0.4, 200, 2500, pool(city, FUN), hours="evening", habitual=False, weekend=2.5),
                     FlexSpec("care", "personal_care", 1, 450, 0.5, 100, 2000, pool(city, CARE)),
                     FlexSpec("gifts", "gifts_donations", 0.6, 1000, 0.7, 200, 8000, pool(city, GIFTS), habitual=False),
                     FlexSpec("travel", "travel", 0.3, 3500, 0.6, 800, 15000, pool(city, TRAVEL), habitual=False, hours="online"),
                     FlexSpec("study", "education", 1, 450, 0.6, 50, 2500, pool(city, [("amazon", 0.5), ("LOCAL:xerox", 0.5)]), hours="day"),
                 ],
                 atm_per_month=1.2, atm_amounts=[1000, 2000, 3000, 5000], topup_from=cfg.get("spouse", "SPOUSE"),
                 self_transfers=[dict({"from": "primary", "to": "secondary"}, amount=cfg.get("monthly_to_secondary", 14000), day=4)])
    if cfg.get("home_loan", True):
        s.recurring.append(RecurringSpec("home_loan", "emi", "Home loan EMI", "emi", 0, "monthly", day=cfg.get("emi_day", 5), channel="ach",
                                         loan=cfg.get("loan", dict(lender=f"{R.BANKS[s.accounts[0].bank]['name']} Home Loan", loan_type="home", rate_type="floating",
                                                                   principal=round(r.uniform(2500000, 6000000), -5), rate_bps=r.choice([790, 815, 840, 865]),
                                                                   tenure=240, start=date(r.randint(2019, 2023), r.randint(1, 12), 5)))))
    for i, (code, amt, day) in enumerate(cfg.get("sips", [(r.choice([118955, 119598, 120586]), r.choice([2000, 3000, 5000]), r.choice([5, 10]))])):
        s.recurring.append(RecurringSpec(f"sip_{i}", "sip", R.FUND_BY_CODE[code][1], "investment", amt, "monthly", day=day, channel="ach",
                                         merchant="iccl", scheme_code=code, invested_before=cfg.get(f"sip_before_{i}", amt * r.randint(12, 40))))
    s.recurring.append(RecurringSpec("netflix", "subscription", "Netflix", "subscriptions", cfg.get("netflix", 499), "monthly", day=12, channel="card",
                                     merchant="netflix"))
    s.accounts.append(AccountSpec("card", cfg.get("card_bank", r.choice(["HDFC", "SBI", "ICICI"])), "credit_card", cfg.get("card_opening", round(sal * 0.15, -2)),
                                  date(2020, r.randint(1, 12), r.randint(1, 28)), card_limit=cfg.get("card_limit", round(sal * 1.8, -4)),
                                  statement_day=cfg.get("statement_day", r.choice([3, 12, 20, 25]))))
    return s


def gig(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="gig", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(21, 35)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="gig", occupation=cfg.get("occupation", "Delivery partner"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["KOTAK", "SBI", "AXIS", "BOB"])), "savings",
                                       cfg.get("opening", round(r.uniform(3000, 9000), -2)), date(2023, r.randint(1, 12), r.randint(1, 28)))],
                 incomes=[IncomeSpec("gig_daily", "PLATFORM", cfg.get("daily", round(r.uniform(750, 1150))), category="gig_payout", mode="imps",
                                     payer_merchant=cfg.get("daily_platform", r.choice(["blinkit_payout", "rapido_payout", "swiggy_payout"])),
                                     days_per_week=cfg.get("days", r.choice([5.5, 6.0, 6.5])), sigma=0.35),
                          IncomeSpec("gig_weekly", "PLATFORM", cfg.get("weekly", round(r.uniform(1200, 2400))), category="gig_payout", mode="neft", day=2,
                                     payer_merchant=cfg.get("weekly_platform", r.choice(["zomato_payout", "uber_payout"])), payer_bank="HDFC", sigma=0.4)],
                 recurring=[
                     RecurringSpec("rent", "rent", "Room rent", "rent", cfg.get("rent", round(r.uniform(4500, 8000), -2)), "monthly", day=5, channel="upi_p2p",
                                   payee=cfg.get("landlord", "LANDLORD"), lag_days=(0, 3)),
                     RecurringSpec("home", "remittance", "Money home", "family_support", cfg.get("remit", round(r.uniform(3000, 6000), -3)), "monthly", day=8,
                                   channel="upi_p2p", payee=cfg.get("mother", "MOTHER"), lag_days=(0, 4)),
                     RecurringSpec("bike_loan", "emi", "Bike loan EMI", "emi", 0, "monthly", day=7, channel="ach", merchant="herofincorp",
                                   loan=cfg.get("bike_loan", dict(lender="Hero FinCorp", loan_type="vehicle", principal=round(r.uniform(55000, 85000), -3),
                                                                  rate_bps=r.choice([1150, 1250, 1350]), tenure=24, start=date(2025, r.randint(1, 8), 7)))),
                     RecurringSpec("recharge", "recharge", "Mobile recharge", "mobile_internet", cfg.get("recharge", 349), "every_28d",
                                   merchant=cfg.get("telco", r.choice(["jio", "airtel"])), start=R.START + timedelta(days=r.randint(1, 20))),
                 ],
                 flex=[
                     FlexSpec("fuel", "fuel", cfg.get("fuel_n", 24), 180, 0.35, 50, 600, pool(city, FUEL), round_to=50, hours="any",
                              channel_mix={"upi": 0.85, "card": 0.15}),
                     FlexSpec("tea", "eating_out", cfg.get("tea_n", 30), 40, 0.6, 10, 250, pool(city, [("LOCAL:tea", 0.45), ("LOCAL:mess", 0.3)] +
                              [(k, 0.12) for k in local_key(city, "eating_out")] + [("haldirams", 0.05), ("bikanervala", 0.05)]),
                              round_to=5, hours="meal"),
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 11), cfg.get("fd_median", 230), 0.35, 99, 500,
                              pool(city, [("zomato", 0.55), ("swiggy", 0.45)]), hours="late_meal", noise=0.04),
                     FlexSpec("kirana", "groceries", 6, 180, 0.5, 30, 800, pool(city, [("LOCAL:kirana", 0.6)] + [(k, 0.2) for k in local_key(city, "groceries")]),
                              round_to=10, hours="grocery"),
                     FlexSpec("shopping", "shopping", 0.8, 450, 0.7, 99, 3000, pool(city, [("meesho", 0.35), ("flipkart", 0.3), ("amazon", 0.25), ("zudio", 0.1)]),
                              hours="online", habitual=False),
                     FlexSpec("metro", "transport", 2, 40, 0.4, 10, 80, [("CITY:metro", 1.0)], hours="commute"),
                     FlexSpec("repair", "transport", 0.5, 650, 0.5, 150, 3000, [("P2P:any", 1.0)], round_to=50, habitual=False),
                     FlexSpec("health", "health", 0.7, 180, 0.6, 40, 1500, pool(city, [("LOCAL:pharmacy", 0.7)] + [(k, 0.3) for k in local_key(city, "health")])),
                     FlexSpec("friends", "other_expense", 2, 200, 0.6, 20, 1500, [("P2P:friend", 1.0)], round_to=10),
                     FlexSpec("fun", "entertainment", 0.6, 200, 0.4, 100, 600, pool(city, FUN), habitual=False),
                     FlexSpec("care", "personal_care", 1, 80, 0.4, 40, 300, [("LOCAL:salon", 1.0)], round_to=10),
                 ],
                 atm_per_month=cfg.get("atm", 3.5), atm_amounts=[500, 1000, 2000], topup_from=cfg.get("brother", "BROTHER"))
    if cfg.get("card", r.random() < 0.3):
        s.accounts.append(AccountSpec("card", cfg.get("card_bank", "SBI"), "credit_card", cfg.get("card_opening", 2100), date(2024, r.randint(1, 12), 3),
                                      card_limit=cfg.get("card_limit", 30000), card_rate_bps=4500, statement_day=cfg.get("statement_day", 8)))
    if cfg.get("second_account", True):
        s.accounts.append(AccountSpec("secondary", cfg.get("bank2", "SBI"), "savings", cfg.get("opening2", round(r.uniform(800, 6000), -2)),
                                      date(2015, r.randint(1, 12), r.randint(1, 28))))
    return s


def shop(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    sales = cfg.get("sales", round(r.uniform(3500, 8000), -1))
    suppliers = cfg.get("suppliers", ["SHREE GANESH TRADERS", "MAHALAXMI DISTRIBUTORS", "NAVKAR STATIONERS", "GUPTA WHOLESALE MART", "JAIN AGENCIES"])
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="shop", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(35, 55)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="business", occupation=cfg.get("occupation", "Shop owner (kirana and stationery)"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["AXIS", "SBI", "HDFC"])), "savings", cfg.get("opening", round(r.uniform(30000, 90000), -3)),
                                       date(2011, r.randint(1, 12), r.randint(1, 28))),
                           AccountSpec("business", cfg.get("bank_biz", r.choice(["BOB", "SBI", "ICICI", "CANARA"])), "current",
                                       cfg.get("opening_biz", round(sales * r.uniform(15, 30), -3)), date(2014, r.randint(1, 12), r.randint(1, 28)))],
                 incomes=[IncomeSpec("business_daily", "PHONEPE", sales, account="business", category="business_income", mode="neft",
                                     payer_merchant=cfg.get("settlement", r.choice(["phonepe_biz", "paytm_biz"])), payer_bank="YESB",
                                     days_per_week=6.5, sigma=0.35),
                          IncomeSpec("cash_deposit", "CASH", cfg.get("cash_weekly", round(sales * r.uniform(2.0, 3.2), -2)), account="business",
                                     category="business_income", mode="cash", day=5, sigma=0.4)],
                 recurring=[
                     RecurringSpec("shop_rent", "rent", "Shop rent", "business_expenses", cfg.get("shop_rent", round(sales * 3.5, -3)), "monthly", day=5,
                                   channel="neft", payee=cfg.get("shop_landlord", "SHOP LANDLORD"), account="business"),
                     RecurringSpec("helper", "bill", "Shop helper salary", "business_expenses", cfg.get("helper", round(r.uniform(7000, 11000), -2)), "monthly",
                                   day=7, channel="upi_p2p", payee=cfg.get("helper_name", "HELPER"), account="business"),
                     RecurringSpec("shop_power", "bill", "Shop electricity", "business_expenses", cfg.get("shop_power", round(r.uniform(2500, 5000), -2)),
                                   "monthly", day=18, channel="billpay", merchant=power_merchant(city, r), seasonal=SUMMER, variable=0.1, account="business"),
                     RecurringSpec("gst", "fees", "GST (composition) payment", "business_expenses", cfg.get("gst", round(sales * 1.2, -1)), "quarterly",
                                   day=18, months=[1, 4, 7, 10], channel="netbanking", payee="GST CPIN PAYMENT", variable=0.2, account="business"),
                     RecurringSpec("home_power", "bill", "Home electricity", "utilities", cfg.get("home_power", round(r.uniform(1200, 2400), -1)), "monthly",
                                   day=21, channel="billpay", merchant=power_merchant(city, r), seasonal=SUMMER, variable=0.1),
                     RecurringSpec("milk", "milk", "Milkman", "groceries", cfg.get("milk", 1950), "monthly", day=1, channel="upi_p2p",
                                   payee=cfg.get("milkman", "MILKMAN")),
                     RecurringSpec("maid", "maid", "House help", "home_services", cfg.get("maid", 2500), "monthly", day=5, channel="upi_p2p",
                                   payee=cfg.get("maid_name", "MAID")),
                     RecurringSpec("recharge", "recharge", "Mobile recharge", "mobile_internet", cfg.get("recharge", 399), "every_28d",
                                   merchant=cfg.get("telco", "jio"), start=R.START + timedelta(days=r.randint(1, 20))),
                     RecurringSpec("lic", "insurance", "LIC premium", "insurance", cfg.get("lic", round(r.uniform(12000, 30000), -2)), "yearly", day=28,
                                   months=[3], channel="ach", merchant="lic"),
                 ],
                 flex=[
                     FlexSpec("suppliers", "business_supplies", cfg.get("supplier_n", 10), cfg.get("supplier_median", round(sales * 2.2, -2)), 0.55,
                              2000, 90000, [(f"SUPPLIER:{n}", 1.0) for n in suppliers], channel_mix={"neft": 1.0}, account="business",
                              hours="office", habitual=True, round_to=1),
                     FlexSpec("supplier_upi", "business_supplies", 6, 2400, 0.6, 300, 15000, [(f"SUPPLIER:{n}", 1.0) for n in suppliers[:3]] + [("udaan", 1.0)],
                              channel_mix={"upi": 1.0}, account="business", hours="office"),
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 10), cfg.get("fd_median", 330), 0.4, 120, 1100,
                              pool(city, [("zomato", 0.55), ("swiggy", 0.45)]), hours="late_meal", weekend=1.5, noise=0.04),
                     FlexSpec("eat_out", "eating_out", 4, 520, 0.5, 100, 2500, pool(city, eat_out_pool(city)), hours="meal", weekend=1.8),
                     FlexSpec("groceries", "groceries", 5, 450, 0.5, 50, 2000, pool(city, [("LOCAL:veg", 0.4), ("LOCAL:bakery", 0.15), ("blinkit", 0.15)] +
                              [(k, 0.3) for k in local_key(city, "groceries", 2)]), hours="grocery"),
                     FlexSpec("shopping", "shopping", 2.5, 1400, 0.9, 199, 20000, pool(city, SHOP + [("fabindia", 0.08)]), channel_mix={"upi": 0.5, "card": 0.5},
                              hours="day", habitual=False, refund_rate=0.03),
                     FlexSpec("fuel", "fuel", 4, 500, 0.3, 100, 2500, pool(city, FUEL), round_to=100, hours="day"),
                     FlexSpec("health", "health", 1.5, 600, 0.6, 80, 4000, pool(city, HEALTH)),
                     FlexSpec("gifts", "gifts_donations", 0.8, 1100, 0.7, 200, 10000, pool(city, GIFTS + [("tanishq", 0.1)]), habitual=False),
                     FlexSpec("fun", "entertainment", 0.5, 700, 0.4, 200, 2000, pool(city, FUN), habitual=False),
                     FlexSpec("care", "personal_care", 0.8, 500, 0.5, 100, 2500, pool(city, CARE)),
                     FlexSpec("transport", "transport", 2, 150, 0.5, 30, 600, pool(city, [("ola", 0.3), ("uber", 0.3), ("P2P:auto", 0.4)])),
                     FlexSpec("metro_cc", "business_supplies", 1.5, 6500, 0.5, 1500, 30000, pool(city, [("metrocc", 1.0)]),
                              channel_mix={"card": 1.0}, account="business", hours="day"),
                 ],
                 atm_per_month=1.5, atm_amounts=[2000, 5000, 10000], topup_from=cfg.get("spouse", "SPOUSE"),
                 self_transfers=[dict({"from": "business", "to": "primary"}, amount=cfg.get("drawings", round(sales * 7, -3)), day=2)],
                 card_pay_from="business")
    s.accounts.append(AccountSpec("card", cfg.get("card_bank", r.choice(["HDFC", "ICICI", "SBI"])), "credit_card", cfg.get("card_opening", 18000),
                                  date(2019, r.randint(1, 12), 2), card_limit=cfg.get("card_limit", 200000), statement_day=cfg.get("statement_day", r.choice([2, 10, 20]))))
    if cfg.get("business_loan", True):
        s.recurring.append(RecurringSpec("biz_loan", "emi", "Business loan EMI", "emi", 0, "monthly", day=5, channel="ach", merchant="bajajfinance",
                                         account="business",
                                         loan=cfg.get("loan", dict(lender="Bajaj Finance", loan_type="business", principal=round(r.uniform(200000, 600000), -4),
                                                                   rate_bps=r.choice([1550, 1650, 1750]), tenure=36, start=date(2025, r.randint(1, 9), 5)))))
    return s


def investor(uid, seed, cfg) -> UserSpec:
    r = random.Random(seed)
    city, region = cfg["city"], R.CITIES[cfg["city"]]["region"]
    sal = cfg.get("salary", round(r.uniform(160000, 340000)))
    s = UserSpec(user_id=uid, persona_id=cfg.get("persona_id"), archetype="investor", full_name=cfg["name"], first_name=cfg["name"].split()[0],
                 gender=cfg["gender"], age=cfg.get("age", r.randint(36, 50)), city=city, area=cfg.get("area", r.choice(R.CITIES[city]["areas"])),
                 language=cfg["language"], region=region, income_pattern="salaried", occupation=cfg.get("occupation", "Senior manager"), seed=seed,
                 accounts=[AccountSpec("primary", cfg.get("bank", r.choice(["HDFC", "ICICI", "AXIS"])), "savings", cfg.get("opening", round(sal * 0.8, -3)),
                                       date(2010, r.randint(1, 12), r.randint(1, 28)), sweep_cap=cfg.get("sweep_cap")),
                           AccountSpec("secondary", cfg.get("bank2", r.choice(["KOTAK", "SBI", "ICICI"])), "savings", cfg.get("opening2", round(r.uniform(8000, 24000), -3)),
                                       date(2018, r.randint(1, 12), r.randint(1, 28))),
                           AccountSpec("card", cfg.get("card_bank", r.choice(["AXIS", "HDFC", "ICICI"])), "credit_card", cfg.get("card_opening", round(sal * 0.25, -2)),
                                       date(2017, r.randint(1, 12), 15), card_limit=cfg.get("card_limit", round(sal * 2, -4)), card_rate_bps=4300,
                                       statement_day=cfg.get("statement_day", r.choice([5, 15, 20])))],
                 incomes=[IncomeSpec("salary", cfg.get("employer", "NORTHSTAR ANALYTICS PVT LTD"), sal, rule="last_working_day",
                                     changes=cfg.get("salary_changes", [(date(2026, 4, 28), round(sal * r.uniform(1.06, 1.1)))]),
                                     payer_bank=cfg.get("payer_bank", "HDFC"))],
                 recurring=[
                     RecurringSpec("car_loan", "emi", "Car loan EMI", "emi", 0, "monthly", day=7, channel="ach",
                                   loan=cfg.get("car_loan", dict(lender=f"{R.BANKS[cfg.get('bank', 'HDFC')]['name']} Car Loan", loan_type="vehicle",
                                                                 principal=round(r.uniform(600000, 1200000), -4), rate_bps=r.choice([890, 910, 940]),
                                                                 tenure=60, start=date(2024, r.randint(1, 12), 7)))),
                     RecurringSpec("society", "bill", "Society maintenance", "home_services", cfg.get("society", round(r.uniform(3500, 8000), -1)), "monthly",
                                   day=10, channel="neft", payee=cfg.get("society_name", "SOCIETY CHS LTD")),
                     RecurringSpec("maid", "maid", "House help", "home_services", cfg.get("maid", 6000), "monthly", day=1, channel="upi_p2p",
                                   payee=cfg.get("maid_name", "MAID"), lag_days=(0, 2)),
                     RecurringSpec("cook", "maid", "Cook", "home_services", cfg.get("cook", 8000), "monthly", day=1, channel="upi_p2p",
                                   payee=cfg.get("cook_name", "COOK"), lag_days=(0, 3)),
                     RecurringSpec("parents", "remittance", "Parents", "family_support", cfg.get("parents", round(r.uniform(10000, 25000), -3)), "monthly",
                                   day=5, channel="upi_p2p", payee=cfg.get("father", "FATHER")),
                     RecurringSpec("power", "bill", "Electricity", "utilities", cfg.get("power", round(r.uniform(2500, 4200), -1)), "monthly", day=14,
                                   channel="billpay", merchant=power_merchant(city, r), seasonal=SUMMER, variable=0.08),
                     RecurringSpec("broadband", "bill", "Broadband", "mobile_internet", cfg.get("broadband", 1178.82), "monthly", day=8, channel="autopay",
                                   merchant=cfg.get("isp", "airtelfiber")),
                     RecurringSpec("postpaid", "bill", "Mobile postpaid (family)", "mobile_internet", cfg.get("postpaid", 1298.82), "monthly", day=17,
                                   channel="card", merchant="airtel"),
                     RecurringSpec("school", "fees", "School fees", "education", cfg.get("school_fee", round(r.uniform(45000, 95000), -2)), "yearly",
                                   day=12, months=[4, 8, 12], channel="netbanking", payee=cfg.get("school", "SCHOOL FEES")),
                     RecurringSpec("ppf", "ppf", "PPF deposit", "investment", cfg.get("ppf", 12500), "monthly", day=3, channel="netbanking",
                                   payee="PPF ACCOUNT TRANSFER"),
                     RecurringSpec("term", "insurance", "Term insurance", "insurance", cfg.get("term", round(r.uniform(18000, 32000), -1)), "yearly", day=15,
                                   months=[3], channel="card", merchant=r.choice(["hdfclife", "iciciprulife", "sbilife"])),
                     RecurringSpec("health_ins", "insurance", "Health insurance", "insurance", cfg.get("health_ins", round(r.uniform(28000, 48000), -1)),
                                   "yearly", day=2, months=[7], channel="card", merchant=r.choice(["nivabupa", "starhealth", "carehealth"])),
                     RecurringSpec("car_ins", "insurance", "Car insurance", "insurance", cfg.get("car_ins", round(r.uniform(9000, 18000), -1)), "yearly", day=9,
                                   months=[2], channel="card", merchant=r.choice(["digit", "acko"])),
                     RecurringSpec("prime", "subscription", "Amazon Prime (yearly)", "subscriptions", 1499, "yearly", day=19, months=[3], channel="card", merchant="primevideo"),
                     RecurringSpec("hotstar", "subscription", "JioHotstar (quarterly)", "subscriptions", 299, "quarterly", day=6, months=[1, 4, 7, 10],
                                   channel="card", merchant="jiohotstar"),
                     RecurringSpec("netflix", "subscription", "Netflix Premium", "subscriptions", cfg.get("netflix", 649), "monthly", day=9, channel="card", merchant="netflix"),
                     RecurringSpec("googleone", "subscription", "Google One 2TB", "subscriptions", 650, "monthly", day=21, channel="card", merchant="googleone"),
                 ],
                 flex=[
                     FlexSpec("food_delivery", "food_delivery", cfg.get("fd_n", 18), cfg.get("fd_median", 520), 0.4, 180, 2200, pool(city, FOOD),
                              channel_mix={"upi": 0.5, "card": 0.5}, hours="late_meal", weekend=1.4, noise=0.04, refund_rate=0.02),
                     FlexSpec("quick", "groceries", 12, 560, 0.5, 120, 2500, pool(city, QUICK), channel_mix={"upi": 0.6, "card": 0.4}, hours="evening", refund_rate=0.02),
                     FlexSpec("supermarket", "groceries", 2, 3800, 0.35, 1500, 9000, pool(city, [("dmart", 0.3), ("naturesbasket", 0.3), ("starbazaar", 0.2),
                              ("smartbazaar", 0.2), ("nilgiris", 0.2), ("ratnadeep", 0.2)]), channel_mix={"upi": 0.3, "card": 0.7}, paise=True, hours="grocery", weekend=1.8),
                     FlexSpec("eat_out", "eating_out", 7, 1400, 0.7, 200, 9000, pool(city, eat_out_pool(city, 3.0)), channel_mix={"upi": 0.3, "card": 0.7},
                              hours="meal", weekend=1.8),
                     FlexSpec("coffee", "eating_out", 8, 380, 0.4, 150, 1200, pool(city, [("starbucks", 0.5), ("thirdwave", 0.2), ("bluetokai", 0.3), ("ccd", 0.1)]),
                              channel_mix={"upi": 0.5, "card": 0.5}, hours="day"),
                     FlexSpec("transport", "transport", 12, 320, 0.5, 60, 1500, pool(city, [("uber", 0.55), ("ola", 0.3), ("P2P:auto", 0.15)]),
                              channel_mix={"upi": 0.6, "card": 0.4}, hours="commute"),
                     FlexSpec("fuel", "fuel", 3, 2600, 0.25, 1000, 4500, pool(city, [("shell", 0.3), ("hpcl", 0.3), ("bpcl", 0.2), ("iocl", 0.2)]),
                              channel_mix={"card": 0.9, "upi": 0.1}, paise=True),
                     FlexSpec("fastag", "transport", 1.5, 1000, 0.3, 500, 2000, [("fastag", 1.0)], round_to=500, habitual=False),
                     FlexSpec("shopping", "shopping", 4, 1900, 1.0, 199, 60000, pool(city, SHOP + [("uniqlo", 0.07), ("hm", 0.07), ("ikea", 0.06), ("nykaa", 0.05),
                              ("fabindia", 0.05), ("vijaysales", 0.04)]), channel_mix={"upi": 0.15, "card": 0.85}, hours="online", habitual=False, refund_rate=0.05),
                     FlexSpec("fun", "entertainment", 2.5, 1300, 0.5, 300, 5000, pool(city, FUN), channel_mix={"card": 1.0}, hours="evening", habitual=False, weekend=2.0),
                     FlexSpec("health", "health", 2, 900, 0.6, 150, 8000, pool(city, HEALTH + [("wellnessforever", 0.3)])),
                     FlexSpec("care", "personal_care", 1.5, 1200, 0.5, 300, 5000, pool(city, CARE)),
                     FlexSpec("travel", "travel", 0.5, 8000, 0.7, 1500, 60000, pool(city, [("indigo", 0.35), ("makemytrip", 0.25), ("airbnb", 0.15),
                              ("airindia", 0.15), ("irctc", 0.1)]), channel_mix={"card": 1.0}, habitual=False, hours="online"),
                     FlexSpec("gifts", "gifts_donations", 0.8, 2500, 0.7, 300, 20000, pool(city, GIFTS + [("tanishq", 0.1)]), habitual=False),
                     FlexSpec("home", "home_services", 1, 1400, 0.5, 300, 6000, pool(city, [("urbancompany", 0.9), ("tumbledry", 0.1)])),
                 ],
                 atm_per_month=0.6, atm_amounts=[2000, 5000, 10000])
    for i, (code, amt, day) in enumerate(cfg.get("sips", [(120716, 10000, 5), (118955, 10000, 10), (118989, 8000, 15), (118778, 7000, 20), (135781, 5000, 25)])):
        s.recurring.append(RecurringSpec(f"sip_{i}", "sip", R.FUND_BY_CODE[code][1], "investment", amt, "monthly", day=day, channel="ach",
                                         merchant=r.choice(["iccl", "nsccl"]), scheme_code=code, invested_before=cfg.get(f"sip_before_{i}", amt * r.randint(30, 80))))
    return s


BUILDERS = {"student": student, "first_job": first_job, "family": family, "gig": gig, "shop": shop, "investor": investor}
