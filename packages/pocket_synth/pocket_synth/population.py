"""The 6 demo personas (hand-tuned) and the 200 evaluation users (sampled)."""
from __future__ import annotations

import random
from datetime import date

from . import refdata as R
from .engine import uid
from .personas import BUILDERS, PLANT_TYPES, apply_planted, family, first_job, gig, investor, shop, student
from .spec import AccountSpec, IncomeSpec, RecurringSpec

ALL = set(PLANT_TYPES)


def _goal(name, emoji, target, saved, deadline=None, plan=None, start="2026-04-01", priority=0):
    return dict(name=name, emoji=emoji, target=target, saved=saved, deadline=deadline, monthly_plan=plan, start=start, priority=priority)


def demo_specs() -> list:
    out = []

    # 1. Student — Karthik, Chennai, Tamil -----------------------------------------------------------------
    cfg = dict(persona_id="student", name="Karthik Ramasamy", gender="male", age=20, city="Chennai", area="Velachery", language="ta",
               bank="KOTAK", opening=3200, allowance=6000, parent="R RAMASAMY", recharge=299, telco="jio", youtube=True, fd_median=250,
               fd_n=11, occupation="B.Com second-year student")
    s = student(uid("demo", "student"), 1001, cfg)
    s.accounts.append(AccountSpec("secondary", "SBI", "savings", 5600, date(2023, 6, 10), nickname="Scholarship account"))
    s.accounts.append(AccountSpec("card", "KOTAK", "credit_card", 1850, date(2025, 2, 14), card_limit=15000, card_rate_bps=4320, statement_day=12))
    s.incomes += [
        IncomeSpec("one_off", "PFMS POST MATRIC SCHOLARSHIP", 42000, account="secondary", category="other_income", mode="neft",
                   dates=[date(2026, 8, 7)], payer_bank="SBIN", purpose="SCHOLARSHIP 2026-27"),
        IncomeSpec("one_off", "S MUTHULAKSHMI", 2000, category="other_income", mode="upi", dates=[date(2026, 1, 15)], purpose="Pongal"),
        IncomeSpec("one_off", "S MUTHULAKSHMI", 1000, category="other_income", mode="upi", dates=[date(2026, 11, 7)], purpose="Deepavali"),
    ]
    s.one_offs += [dict(date=date(2026, 9, 25), merchant="flipkart", amount=6499, category="shopping", channel="card"),
                   dict(date=date(2026, 10, 3), merchant="amazon", amount=1299, category="shopping", channel="card")]
    apply_planted(s, ALL, random.Random(1), dict(demo=True, forgotten_merchant="spotify", forgotten_amount=59, mandate_date=date(2026, 3, 2),
                                                 trial_days=30, price_hike_key="recharge", price_hike_new=349, price_hike_date=date(2026, 10, 10),
                                                 creep=1.36, dup_merchants=["zepto", "swiggy"], idle_role="secondary", idle_opening=5600,
                                                 revolve_fraction=0.05))
    s.pockets = [dict(name="Food delivery", emoji="🍔", limit=2500, categories=["food_delivery"]),
                 dict(name="Snacks & eating out", emoji="☕", limit=1500, categories=["eating_out"]),
                 dict(name="Travel", emoji="🛵", limit=900, categories=["transport"]),
                 dict(name="Fun & shopping", emoji="🎬", limit=1500, categories=["shopping", "entertainment"]),
                 dict(name="Phone & apps", emoji="📱", limit=600, categories=["mobile_internet", "subscriptions"])]
    s.goals = [_goal("Laptop", "💻", 65000, 12000, "2027-06-30", None, "2026-05-01"),
               _goal("Emergency money", "🛟", 10000, 3500, None, 500, "2026-06-01", 1)]
    s.profile = dict(occupation="B.Com இரண்டாம் ஆண்டு மாணவன்",
                     income="அப்பா மாசம் ஆறாயிரம் ரூபாய் தருவார். வாரத்துக்கு ரெண்டு நாள் டியூஷன் எடுத்து கொஞ்சம் சம்பாதிக்கிறேன்.",
                     saving_for="அடுத்த வருஷம் ஜூனுக்குள் ஒரு லேப்டாப் வாங்கணும். டிசம்பரில் நண்பர்களோட பாண்டிச்சேரி ட்ரிப்.",
                     worries="மாச கடைசியில் காசு தீர்ந்துடுது. ஸ்விக்கியில் ரொம்ப செலவு பண்றேன்னு தோணுது.",
                     household="அப்பா, அம்மா, தங்கையுடன் வீட்டில் இருக்கிறேன்")
    s.household = "Lives with parents and younger sister"
    out.append(s)

    # 2. First job — Ananya, Bengaluru, English ------------------------------------------------------------
    cfg = dict(persona_id="first_job", name="Ananya Srinivasan", gender="female", age=24, city="Bengaluru", area="HSR Layout", language="en",
               bank="HDFC", opening=146000, opened=date(2025, 6, 20), bank2="SBI", opening2=4300, salary=61842,
               salary_changes=[(date(2026, 7, 31), 67215)], employer="BLUEWAVE TECHNOLOGIES PVT LTD", payer_bank="ICIC", rent=16000,
               rent_day=3, landlord="K NAGARAJ", rent_changes=[(date(2026, 6, 1), 16800)], recharge=349, telco="jio", fd_n=20, fd_median=270,
               eat_n=5, parent="S PADMA", card_bank="ICICI", card_opening=8400, card_limit=120000, statement_day=18,
               sips=[(120716, 3000, 10, "iccl"), (122639, 2000, 15, "nsccl")], sip_before=9000,
               subs=[("spotify", "spotify", 119, 5, "autopay"), ("netflix", "netflix", 199, 22, "card")])
    s = first_job(uid("demo", "first_job"), 1002, cfg)
    s.incomes += [IncomeSpec("one_off", "CBDT INCOME TAX REFUND", 4860, category="other_income", mode="neft", dates=[date(2026, 9, 17)],
                             payer_bank="SBIN", purpose="ITR REFUND AY 2026-27"),
                  IncomeSpec("one_off", "S PADMA", 2000, category="other_income", mode="upi", dates=[date(2026, 3, 14)], purpose="Happy birthday")]
    s.recurring.append(RecurringSpec("lic", "insurance", "LIC policy (taken by parents)", "insurance", 2312, "quarterly", day=20,
                                     months=[1, 4, 7, 10], channel="ach", merchant="lic", account="secondary"))
    s.self_transfers.append(dict({"from": "primary", "to": "secondary"}, amount=1000, day=2))
    s.one_offs += [dict(date=date(2026, 9, 26), merchant="flipkart", amount=32999, category="shopping", channel="card"),
                   dict(date=date(2026, 10, 4), merchant="myntra", amount=4850, category="shopping", channel="card")]
    apply_planted(s, ALL, random.Random(2), dict(demo=True, forgotten_merchant="audible", forgotten_amount=199, mandate_date=date(2026, 2, 8),
                                                 trial_days=30, price_hike_key="spotify", price_hike_new=139, price_hike_date=date(2026, 10, 5),
                                                 creep=1.38, dup_merchants=["uber"], idle_role="primary", idle_opening=146000,
                                                 revolve_fraction=0.06))
    s.pockets = [dict(name="Food delivery", emoji="🛵", limit=4200, categories=["food_delivery"]),
                 dict(name="Eating out", emoji="🍽️", limit=5000, categories=["eating_out"]),
                 dict(name="Groceries", emoji="🛒", limit=3500, categories=["groceries"]),
                 dict(name="Cabs", emoji="🚕", limit=3500, categories=["transport"]),
                 dict(name="Shopping & care", emoji="🛍️", limit=4000, categories=["shopping", "personal_care"]),
                 dict(name="Fun", emoji="🎟️", limit=1500, categories=["entertainment"])]
    s.goals = [_goal("Bike", "🏍️", 120000, 48000, "2027-03-31", None, "2026-03-01"),
               _goal("Emergency fund", "🛟", 150000, 60000, None, 4000, "2025-12-01", 1)]
    s.profile = dict(occupation="Software engineer, first job (joined July 2025)",
                     income="I get around 67 thousand a month after tax, on the last working day.",
                     saving_for="A Royal Enfield by next March, and an emergency fund.",
                     worries="I order food way too much and I'm not sure where the rest goes. My card bill also got big after the sale.",
                     household="Shares a 2BHK in HSR Layout with two flatmates")
    s.household = "Shares a flat with two flatmates"
    out.append(s)

    # 3. Family with a home loan — Lakshmi, Chennai, Tamil -------------------------------------------------
    cfg = dict(persona_id="family", name="Lakshmi Narayanan", gender="female", age=38, city="Chennai", area="Madipakkam", language="ta",
               bank="SBI", opening=338000, bank2="HDFC", opening2=21000, salary=78450, salary_changes=[(date(2026, 5, 1), 84120)],
               employer="KAVERI AUTO COMPONENTS PVT LTD", payer_bank="HDFC", spouse="RAMESH NARAYANAN", spouse_amount=45000,
               maid=3500, maid_name="SELVI M", broadband=942.82, isp="airtelfiber", recharge=379, telco="airtel", school_fee=63000,
               school="SRI VIDYA MANDIR MATRIC HR SEC SCHOOL", lic=6240, power_scale=1.15, fd_n=10, fd_median=420, fuel_n=3,
               monthly_to_secondary=15000, card_bank="HDFC", card_opening=12000, card_limit=150000, statement_day=25,
               loan=dict(lender="SBI Home Loan", loan_type="home", rate_type="floating", principal=4800000, rate_bps=815, tenure=240,
                         start=date(2021, 4, 5)),
               sips=[(118955, 5000, 5), (119598, 3000, 10)], sip_before_0=140000, sip_before_1=72000)
    s = family(uid("demo", "family"), 1003, cfg)
    s.incomes.append(IncomeSpec("one_off", "CBDT INCOME TAX REFUND", 6210, category="other_income", mode="neft", dates=[date(2026, 10, 6)],
                                payer_bank="SBIN", purpose="ITR REFUND AY 2026-27"))
    s.recurring += [
        RecurringSpec("milk", "milk", "Aavin milk card", "groceries", 1860, "monthly", day=25, merchant="aavin"),
        RecurringSpec("paper", "subscription", "Newspaper", "subscriptions", 420, "monthly", day=3, channel="upi_p2p", payee="R BALU"),
        RecurringSpec("veena", "fees", "Veena class", "education", 2000, "monthly", day=6, channel="upi_p2p", payee="GAYATHRI SRINIVASAN"),
        RecurringSpec("health_ins", "insurance", "Health insurance (family floater)", "insurance", 26480, "yearly", day=18, months=[6],
                      channel="card", merchant="starhealth"),
        RecurringSpec("car_ins", "insurance", "Car insurance", "insurance", 9860, "yearly", day=9, months=[2], channel="card", merchant="acko"),
        RecurringSpec("ppf", "ppf", "PPF deposit", "investment", 50000, "yearly", day=25, months=[3], channel="netbanking", payee="PPF ACCOUNT TRANSFER"),
    ]
    s.one_offs += [dict(date=date(2026, 9, 23), merchant="flipkart", amount=34990, category="shopping", channel="card"),
                   dict(date=date(2026, 10, 17), merchant="chennaisilks", amount=12800, category="shopping", channel="card"),
                   dict(date=date(2026, 11, 6), merchant="tanishq", amount=38500, category="shopping", channel="card"),
                   dict(date=date(2026, 11, 7), merchant="srikrishnasweets", amount=3240, category="eating_out", channel="card")]
    apply_planted(s, ALL, random.Random(3), dict(demo=True, forgotten_merchant="zee5", forgotten_amount=99, mandate_date=date(2026, 4, 2),
                                                 trial_days=7, price_hike_key="broadband", price_hike_new=1060.82, price_hike_date=date(2026, 10, 1),
                                                 creep=1.35, dup_merchants=["bigbasket"], idle_role="primary", idle_opening=338000,
                                                 revolve_fraction=0.1))
    s.pockets = [dict(name="Groceries", emoji="🛒", limit=16000, categories=["groceries"]),
                 dict(name="Food delivery", emoji="🍱", limit=4000, categories=["food_delivery"]),
                 dict(name="Eating out", emoji="🍛", limit=3000, categories=["eating_out"]),
                 dict(name="Car & travel", emoji="🚗", limit=5500, categories=["fuel", "transport"]),
                 dict(name="Shopping", emoji="🛍️", limit=6000, categories=["shopping", "personal_care"]),
                 dict(name="Health", emoji="💊", limit=2500, categories=["health"])]
    s.goals = [_goal("Kids' education fund", "🎓", 1000000, 210000, "2032-06-01", None, "2024-06-01"),
               _goal("Kodaikanal summer trip", "🏞️", 40000, 6000, "2027-05-15", None, "2026-08-01", 1)]
    s.static_holdings = [dict(kind="fd", name="SBI Fixed Deposit", fd_principal_paise=20000000, fd_rate_bps=710, fd_start_date="2025-03-18",
                              fd_maturity_date="2028-03-18", booked_by="user"),
                         dict(kind="gold", name="Sovereign Gold Bond 2021-22 Series VI", gold_grams=20.0),
                         dict(kind="ppf", name="PPF (SBI)", balance_paise=48500000, balance_as_of="2026-03-31"),
                         dict(kind="epf", name="EPF (EPFO)", balance_paise=68000000, balance_as_of="2026-03-31")]
    s.profile = dict(occupation="கணக்கு அதிகாரி, தனியார் நிறுவனம்",
                     income="எனக்கு மாசம் எண்பத்தி நாலாயிரம் சம்பளம், ஒன்றாம் தேதி வரும். கணவர் வீட்டு செலவுக்கு நாற்பத்தைந்தாயிரம் அனுப்புவார்.",
                     saving_for="பிள்ளைகளின் படிப்புக்கு சேமிக்கணும். அடுத்த மே மாதம் கொடைக்கானல் போக திட்டம்.",
                     worries="ஹோம் லோன் EMI பெருசா இருக்கு. தீபாவளி ஷாப்பிங் கார்டில் போட்டேன், அது எவ்வளவு ஆகும்னு பயமா இருக்கு.",
                     household="கணவர், இரண்டு பிள்ளைகள், மாமியார்")
    s.household = "Husband, two school-going children, mother-in-law"
    s.group_link = dict(group_key="demo_family")
    out.append(s)

    # 4. Gig worker — Rahul, Delhi, Hindi ------------------------------------------------------------------
    cfg = dict(persona_id="gig", name="Rahul Kumar", gender="male", age=29, city="Delhi", area="Laxmi Nagar", language="hi", bank="KOTAK",
               opening=6800, daily=900, daily_platform="blinkit_payout", weekly=1400, weekly_platform="zomato_payout", days=6.0, rent=6500,
               landlord="SURESH CHAND", remit=5000, mother="SUNITA DEVI", recharge=349, telco="jio", fd_n=11, fd_median=230, fuel_n=24, atm=3.5,
               bike_loan=dict(lender="Hero FinCorp", loan_type="vehicle", principal=72000, rate_bps=1150, tenure=24, start=date(2025, 3, 7)),
               card=True, card_bank="SBI", card_opening=11600, card_limit=30000, statement_day=8, bank2="SBI", opening2=65000, brother="VIKAS KUMAR")
    s = gig(uid("demo", "gig"), 1004, cfg)
    s.incomes.append(IncomeSpec("one_off", "BLINKIT COMMERCE PARTNER", 2500, category="gig_payout", mode="neft", dates=[date(2026, 11, 12)],
                                payer_bank="HDFC", purpose="DIWALI INCENTIVE"))
    s.recurring.append(RecurringSpec("phone_emi", "emi", "Phone EMI (no-cost)", "emi", 0, "monthly", day=2, channel="ach", merchant="bajajfinance",
                                     loan=dict(lender="Bajaj Finance", loan_type="consumer_durable", principal=13491, rate_bps=0, tenure=9,
                                               start=date(2026, 3, 2), zero_cost=True)))
    s.one_offs += [dict(date=date(2026, 11, 2), merchant="irctc", amount=1245, category="travel", channel="upi"),
                   dict(date=date(2026, 11, 6), payee="SUNITA DEVI", amount=3000, category="family_support", note="Diwali"),
                   dict(date=date(2026, 9, 24), merchant="flipkart", amount=4200, category="shopping", channel="card")]
    apply_planted(s, ALL, random.Random(4), dict(demo=True, forgotten_merchant="jiosaavn", forgotten_amount=99, mandate_date=date(2026, 1, 20),
                                                 trial_days=30, price_hike_key="recharge", price_hike_new=399, price_hike_date=date(2026, 10, 20),
                                                 creep=1.38, dup_merchants=["zomato"], idle_role="secondary", idle_opening=65000,
                                                 revolve_fraction=0.05))
    s.pockets = [dict(name="Petrol", emoji="⛽", limit=5500, categories=["fuel"]),
                 dict(name="Food delivery", emoji="🍲", limit=2500, categories=["food_delivery"]),
                 dict(name="Chai-nashta", emoji="☕", limit=2000, categories=["eating_out"]),
                 dict(name="Ghar ka saman", emoji="🧺", limit=1500, categories=["groceries"]),
                 dict(name="Mobile", emoji="📱", limit=500, categories=["mobile_internet", "subscriptions"])]
    s.goals = [_goal("Emergency fund", "🛟", 30000, 9000, None, 1500, "2026-02-01", 1),
               _goal("Behan ki shaadi", "🎁", 50000, 21000, "2027-02-15", None, "2026-01-01")]
    s.profile = dict(occupation="डिलीवरी पार्टनर (दो ऐप पर काम)",
                     income="रोज़ का पेमेंट आता है, सात सौ से पंद्रह सौ तक, और हफ़्ते में एक बार दूसरे ऐप से। महीने में लगभग तीस-पैंतीस हज़ार।",
                     saving_for="फरवरी में बहन की शादी है, उसके लिए पचास हज़ार जोड़ने हैं। थोड़ा इमरजेंसी के लिए भी।",
                     worries="पेट्रोल में बहुत पैसा जाता है। कभी कमाई कम होती है तो किराया और EMI की चिंता होती है।",
                     household="दो दोस्तों के साथ कमरे में रहता है; माँ बिहार में")
    s.household = "Shares a room with two friends; mother lives in Bihar"
    out.append(s)

    # 5. Small shop owner — Sunita, Jaipur, Hindi ----------------------------------------------------------
    cfg = dict(persona_id="shop", name="Sunita Agarwal", gender="female", age=45, city="Jaipur", area="Malviya Nagar", language="hi",
               bank="AXIS", opening=96000, bank_biz="BOB", opening_biz=185000, sales=6800, settlement="phonepe_biz", cash_weekly=18000,
               shop_rent=22000, shop_landlord="MAHESH CHAND KHANDELWAL", helper=9500, helper_name="MUKESH SAINI", shop_power=4300,
               gst=7850, home_power=1850, milk=1950, milkman="RAMESH GURJAR", maid=2500, maid_name="KAMLA DEVI", recharge=399, telco="jio",
               lic=24600, fd_n=10, fd_median=330, drawings=42000, spouse="RAJESH AGARWAL", card_bank="HDFC", card_opening=18000,
               card_limit=200000, statement_day=2, supplier_n=9, supplier_median=12500,
               suppliers=["SHREE GANESH TRADERS", "MAHALAXMI DISTRIBUTORS", "NAVKAR STATIONERS", "GUPTA WHOLESALE MART", "JAIN AGENCIES"],
               loan=dict(lender="Bajaj Finance", loan_type="business", principal=400000, rate_bps=1650, tenure=36, start=date(2025, 6, 5)))
    s = shop(uid("demo", "shop"), 1005, cfg)
    s.incomes.append(IncomeSpec("one_off", "FD CLOSURE PROCEEDS", 246850, category="self_transfer", mode="other", dates=[date(2026, 8, 18)],
                                purpose="FD MATURITY"))
    s.recurring += [
        RecurringSpec("coaching", "fees", "Daughter's coaching", "education", 18500, "quarterly", day=10, months=[1, 4, 7, 10], merchant="allen"),
        RecurringSpec("postpaid", "bill", "Airtel postpaid (shop phone)", "mobile_internet", 529.82, "monthly", day=11, channel="autopay", merchant="airtel"),
    ]
    s.one_offs += [dict(date=date(2026, 10, 24), merchant="metrocc", amount=42800, category="business_supplies", channel="card"),
                   dict(date=date(2026, 10, 28), merchant="metrocc", amount=26450, category="business_supplies", channel="card"),
                   dict(date=date(2026, 11, 5), merchant="tanishq", amount=21500, category="shopping", channel="card")]
    apply_planted(s, ALL, random.Random(5), dict(demo=True, forgotten_merchant="sonyliv", forgotten_amount=299, mandate_date=date(2026, 5, 3),
                                                 trial_days=7, price_hike_key="postpaid", price_hike_new=588.82, price_hike_date=date(2026, 10, 1),
                                                 creep=1.36, dup_merchants=["metrocc"], idle_role="primary", idle_opening=96000,
                                                 revolve_fraction=0.1))
    s.planted["duplicate_charge"]["merchants"] = ["metrocc", "zomato", "blinkit"]
    s.pockets = [dict(name="Ghar ka kharcha", emoji="🏠", limit=8000, categories=["groceries", "home_services"]),
                 dict(name="Food delivery", emoji="🍕", limit=3000, categories=["food_delivery"]),
                 dict(name="Bahar khana", emoji="🍽️", limit=2500, categories=["eating_out"]),
                 dict(name="Shopping", emoji="🛍️", limit=4000, categories=["shopping", "personal_care"]),
                 dict(name="Petrol & auto", emoji="🛺", limit=2500, categories=["fuel", "transport"])]
    s.goals = [_goal("Dukaan renovation", "🏪", 250000, 60000, "2027-06-30", None, "2026-01-01"),
               _goal("Beti ki college fees", "🎓", 600000, 180000, "2028-06-30", None, "2024-07-01", 1)]
    s.static_holdings = [dict(kind="gold", name="Sovereign Gold Bond 2020-21 Series XII", gold_grams=25.0)]
    s.profile = dict(occupation="किराना और स्टेशनरी की दुकान चलाती हैं",
                     income="रोज़ फ़ोनपे का सेटलमेंट आता है, पाँच-सात हज़ार, और हफ़्ते में कैश जमा करती हूँ। घर खर्च के लिए महीने में पैंतालीस हज़ार निकालती हूँ।",
                     saving_for="अगले साल दुकान का रेनोवेशन, और बेटी की कॉलेज की फीस।",
                     worries="दिवाली का स्टॉक कार्ड से लिया था, बिल पूरा नहीं भर पाई। बिज़नेस लोन की EMI भी है।",
                     household="पति, बेटी (कोचिंग में), बेटा")
    s.household = "Husband, daughter in coaching, son"
    s.group_link = dict(group_key="demo_shop")
    out.append(s)

    # 6. Investor — Vikram, Mumbai, English ----------------------------------------------------------------
    cfg = dict(persona_id="investor", name="Vikram Mehta", gender="male", age=42, city="Mumbai", area="Andheri West", language="en",
               bank="HDFC", opening=210000, sweep_cap=200000, bank2="KOTAK", opening2=140000, card_bank="AXIS", card_opening=62000,
               card_limit=500000, statement_day=15, salary=284650, salary_changes=[(date(2026, 4, 28), 305400)],
               employer="NORTHSTAR ANALYTICS PVT LTD", payer_bank="HDFC", society=6850, society_name="SHREE SAI HEIGHTS CHS LTD",
               maid=6000, maid_name="ROSHNI PAWAR", cook=8000, cook_name="SAVITA GAIKWAD", parents=15000, father="ARVIND MEHTA",
               power=3200, broadband=1178.82, isp="airtelfiber", postpaid=1298.82, school_fee=72500, school="LAKESHORE INTERNATIONAL SCHOOL",
               ppf=12500, netflix=649, fd_n=18, fd_median=520,
               car_loan=dict(lender="HDFC Bank Car Loan", loan_type="vehicle", principal=950000, rate_bps=910, tenure=60, start=date(2024, 2, 7)),
               sips=[(120716, 10000, 5), (118955, 10000, 10), (118989, 8000, 15), (118778, 7000, 20), (135781, 5000, 25)],
               sip_before_0=420000, sip_before_1=510000, sip_before_2=300000, sip_before_3=260000, sip_before_4=180000)
    s = investor(uid("demo", "investor"), 1006, cfg)
    s.incomes += [IncomeSpec("one_off", "NORTHSTAR ANALYTICS PVT LTD", 321800, category="salary", mode="neft", dates=[date(2026, 6, 19)],
                             payer_bank="HDFC", purpose="ANNUAL BONUS FY26"),
                  IncomeSpec("one_off", "CBDT INCOME TAX REFUND", 18940, category="other_income", mode="neft", dates=[date(2026, 8, 28)],
                             payer_bank="SBIN", purpose="ITR REFUND AY 2026-27")]
    s.self_transfers += [dict({"from": "primary", "to": "secondary"}, amount=300000, date=date(2026, 6, 22))]
    s.recurring += [RecurringSpec("chatgpt", "subscription", "ChatGPT Plus", "subscriptions", 1999, "monthly", day=11, channel="card", merchant="openai"),
                    RecurringSpec("timesprime", "subscription", "Times Prime (yearly)", "subscriptions", 1199, "yearly", day=4, months=[8],
                                  channel="card", merchant="timesprime"),
                    RecurringSpec("mgl", "bill", "Piped gas", "utilities", 720, "bimonthly", day=20, months=[1, 3, 5, 7, 9, 11], channel="billpay",
                                  merchant="mgl", variable=0.12)]
    s.one_offs += [dict(date=date(2026, 9, 12), merchant="croma", amount=68990, category="shopping", channel="card")]
    apply_planted(s, ALL, random.Random(6), dict(demo=True, forgotten_merchant="linkedin", forgotten_amount=1567, mandate_date=date(2026, 1, 14),
                                                 trial_days=30, price_hike_key="netflix", price_hike_new=749, price_hike_date=date(2026, 10, 9),
                                                 creep=1.34, dup_merchants=["bookmyshow", "uber", "zepto"], idle_role="secondary", idle_opening=140000,
                                                 revolve_fraction=0.35))
    for a in s.accounts:
        if a.role == "primary":
            a.sweep_cap = 200000
    s.pockets = [dict(name="Food delivery", emoji="🥡", limit=6000, categories=["food_delivery"]),
                 dict(name="Eating out", emoji="🍷", limit=10000, categories=["eating_out"]),
                 dict(name="Groceries", emoji="🛒", limit=14000, categories=["groceries"]),
                 dict(name="Shopping", emoji="🛍️", limit=12000, categories=["shopping"]),
                 dict(name="Fun", emoji="🎭", limit=4000, categories=["entertainment"]),
                 dict(name="Cabs & fuel", emoji="🚘", limit=9000, categories=["transport", "fuel"])]
    s.goals = [_goal("Daughter's education", "🎓", 3000000, 940000, "2034-06-01", None, "2022-04-01"),
               _goal("Europe trip", "✈️", 450000, 120000, "2027-05-31", None, "2026-02-01", 1)]
    s.static_holdings = [dict(kind="fd", name="HDFC Bank Fixed Deposit", fd_principal_paise=50000000, fd_rate_bps=725, fd_start_date="2025-12-10",
                              fd_maturity_date="2027-12-10", booked_by="user"),
                         dict(kind="gold", name="Sovereign Gold Bond 2019-20 Series IX", gold_grams=50.0),
                         dict(kind="ppf", name="PPF (HDFC Bank)", balance_paise=118000000, balance_as_of="2026-03-31"),
                         dict(kind="epf", name="EPF (EPFO)", balance_paise=186000000, balance_as_of="2026-03-31")]
    s.profile = dict(occupation="Senior manager, analytics firm",
                     income="Salary is about three lakh a month after tax, plus an annual bonus in June.",
                     saving_for="My daughter's education in 2034, and a Europe trip next summer.",
                     worries="Markets have been choppy. I have money sitting in my Kotak account and I'm not sure my card is being paid in full.",
                     household="Wife, one daughter (11)")
    s.household = "Wife and one daughter"
    out.append(s)
    return out


# ---------------------------------------------------------------------------------------------- 200 eval users
EVAL_MIX = [("student", 35), ("first_job", 40), ("family", 40), ("gig", 30), ("shop", 20), ("investor", 35)]
CITY_BY_ARCH = {
    "student": ["Chennai", "Coimbatore", "Madurai", "Bengaluru", "Hyderabad", "Delhi", "Lucknow", "Patna", "Jaipur", "Pune", "Kolkata", "Kochi", "Indore"],
    "first_job": ["Bengaluru", "Bengaluru", "Bengaluru", "Hyderabad", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi", "Kolkata", "Kochi", "Ahmedabad"],
    "family": list(R.CITIES),
    "gig": ["Delhi", "Delhi", "Bengaluru", "Mumbai", "Hyderabad", "Chennai", "Pune", "Kolkata", "Jaipur", "Lucknow", "Patna"],
    "shop": ["Jaipur", "Lucknow", "Patna", "Indore", "Ahmedabad", "Coimbatore", "Madurai", "Delhi", "Kolkata", "Pune", "Chennai"],
    "investor": ["Mumbai", "Mumbai", "Bengaluru", "Delhi", "Pune", "Hyderabad", "Chennai", "Ahmedabad", "Kolkata"],
}
EMPLOYERS = ["ORBITAL SOFTWARE SERVICES LLP", "GREENLEAF FOODS PVT LTD", "MERIDIAN HEALTHCARE LTD", "TRIVENI LOGISTICS PVT LTD",
             "ZENITH CONSULTANCY SERVICES", "BRIGHTPATH EDUCATION TRUST", "ASHOKA MOTORS PVT LTD", "COASTLINE FINTECH PVT LTD",
             "VEDA PHARMACEUTICALS LTD", "SILVERLINE INFRA PROJECTS", "PRAGATI TEXTILES PVT LTD", "NIMBUS CLOUD SYSTEMS PVT LTD",
             "SAPTAGIRI ENGINEERING WORKS", "HORIZON RETAIL VENTURES", "INDUS ANALYTICS PVT LTD", "LOTUS HOSPITALITY GROUP"]


def _lang(city: str, r: random.Random) -> str:
    reg = R.CITIES[city]["region"]
    if reg == "tamil":
        return "ta" if r.random() < 0.75 else "en"
    if reg == "hindi":
        return "hi" if r.random() < 0.75 else "en"
    if reg in ("west", "east"):
        return "hi" if r.random() < 0.35 else "en"
    return "hi" if r.random() < 0.15 else "en"


def _name(region: str, gender: str, r: random.Random) -> str:
    if r.random() < 0.2:
        region = r.choice(list(R.NAMES))
    pool = R.NAMES[region]
    return f"{r.choice(pool[gender])} {r.choice(pool['surname'])}"


def _person(region: str, r: random.Random, gender: str | None = None) -> str:
    return _name(region, gender or r.choice(["male", "female"]), r).upper()


def eval_specs(n_seed: int = 7) -> list:
    r = random.Random(n_seed)
    out = []
    i = 0
    for arch, count in EVAL_MIX:
        for _ in range(count):
            i += 1
            seed = 50000 + i
            city = r.choice(CITY_BY_ARCH[arch])
            region = R.CITIES[city]["region"]
            gender = "male" if arch == "gig" and r.random() < 0.9 else r.choice(["male", "female"])
            name = _name(region, gender, r)
            cfg = dict(name=name, gender=gender, city=city, language=_lang(city, r), parent=_person(region, r, "male"),
                       employer=r.choice(EMPLOYERS), landlord=_person(region, r, "male"), spouse=_person(region, r, "male" if gender == "female" else "female"),
                       maid_name=_person(region, r, "female"), mother=_person(region, r, "female"), brother=_person(region, r, "male"),
                       helper_name=_person(region, r, "male"), shop_landlord=_person(region, r, "male"), milkman=_person(region, r, "male"),
                       cook_name=_person(region, r, "female"), father=_person(region, r, "male"),
                       school=r.choice(["ST JOSEPH'S", "DELHI PUBLIC", "KENDRIYA VIDYALAYA", "SRI CHAITANYA", "NARAYANA", "VIDYA MANDIR"]) + " SCHOOL")
            if arch == "student":
                cfg["fd_median"] = r.choice([230, 250, 270])
            s = BUILDERS[arch](uid("eval", arch, i), seed, cfg)
            k = 0 if r.random() < 0.3 else r.randint(1, 6)
            planted = set(r.sample(PLANT_TYPES, k))
            apply_planted(s, planted, random.Random(seed + 1), dict(demo=False))
            s.pockets = default_pockets(s, r)
            s.goals = [_goal("Emergency fund", "🛟", round(r.uniform(20000, 300000), -3), round(r.uniform(2000, 40000), -3), None,
                             round(r.uniform(500, 5000), -2), "2026-03-01", 1)]
            out.append(s)
    return out


def default_pockets(s, r: random.Random) -> list[dict]:
    est = {fs.category: 0.0 for fs in s.flex}
    for fs in s.flex:
        if fs.account != "business":
            est[fs.category] = est.get(fs.category, 0) + fs.monthly_count * fs.median * 1.1
    picks = sorted([(v, c) for c, v in est.items() if c in ("food_delivery", "eating_out", "groceries", "transport", "fuel", "shopping",
                                                            "entertainment", "personal_care")], reverse=True)[:r.randint(3, 6)]
    names = {"food_delivery": ("Food delivery", "🍔"), "eating_out": ("Eating out", "🍽️"), "groceries": ("Groceries", "🛒"),
             "transport": ("Travel", "🚕"), "fuel": ("Fuel", "⛽"), "shopping": ("Shopping", "🛍️"), "entertainment": ("Fun", "🎬"),
             "personal_care": ("Personal care", "💇")}
    return [dict(name=names[c][0], emoji=names[c][1], limit=max(500, round(v * r.uniform(0.85, 1.15), -2)), categories=[c]) for v, c in picks]
