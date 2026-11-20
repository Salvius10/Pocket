"""The bank SMS parser: one message per kind of wording, the things it must skip, and exact money."""

from datetime import UTC, date, datetime

import pytest
from core_api.ingest.sms import parse_sms, resolve_last4, sender_bank, to_paise
from hypothesis import given
from hypothesis import strategies as st
from pocket_common.money import group_indian

RECEIVED = datetime(2026, 11, 10, 6, 30, tzinfo=UTC)

# (sender, body, the fields that must come out). Wordings are from the synthetic dataset's seen templates.
CASES: list[tuple[str, str, dict[str, object]]] = [
    ("DM-HDFCBK", "Sent Rs.4500.00\nFrom HDFC Bank A/C *9168\nTo LAKSHMAMMA\nOn 01/11/25\nRef 530509919924\nNot You?\n"
     "Call 18002586161/SMS BLOCK UPI to 7308080808",
     {"kind": "debit", "amount_paise": 450000, "account_last4": "9168", "counterparty": "LAKSHMAMMA", "vpa": None,
      "ref_no": "530509919924", "txn_date": date(2025, 11, 1), "balance_paise": None, "mode": "upi", "is_card": False}),
    ("CP-HDFCBK-T", "Money Sent! Rs.119.00 from HDFC Bank A/c XX9168 on 05-11-25 to spotify.rzp@icici "
     "(UPI Ref No 530904687697). Not you? Call 18002586161",
     {"kind": "debit", "amount_paise": 11900, "counterparty": None, "vpa": "spotify.rzp@icici", "ref_no": "530904687697",
      "txn_date": date(2025, 11, 5)}),
    ("AD-HDFCBK-T", "Spent Rs.3373.00 On HDFC Bank Card 3757 At BATA INDIA LTD On 2025-11-11:11:56:50.Not You? "
     "To Block+Reissue Call 18002586161/SMS BLOCK CC 3757 to 7308080808",
     {"kind": "debit", "amount_paise": 337300, "account_last4": "3757", "counterparty": "BATA INDIA LTD", "ref_no": None,
      "txn_date": date(2025, 11, 11), "mode": "card", "is_card": True}),
    ("DM-HDFCBK-T", "Rs.2000.00 withdrawn from HDFC Bank Card x9168 at ATM HSR LAYOUT BENGALURU on 05-12-25 17:53. "
     "Avl bal: Rs 1,25,580.98. Not you? Call 18002586161",
     {"kind": "debit", "amount_paise": 200000, "account_last4": "9168", "counterparty": "ATM HSR LAYOUT BENGALURU",
      "balance_paise": 12558098, "mode": "atm", "is_card": False}),
    ("AX-HDFCBK", "Update! INR 61,842.00 deposited in HDFC Bank A/c XX9168 on 28-NOV-25 for NEFT Cr-ICICN25332434198-"
     "BLUEWAVE TECHNOLOGIES PVT.Avl bal INR 1,60,979.18. Cheque deposits in A/C are subject to clearing",
     {"kind": "credit", "amount_paise": 6184200, "counterparty": "BLUEWAVE TECHNOLOGIES PVT", "ref_no": "ICICN25332434198",
      "txn_date": date(2025, 11, 28), "balance_paise": 16097918, "mode": "neft"}),
    ("BP-HDFCBK-T", "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 23,448.00 RECEIVED TOWARDS YOUR CREDIT CARD ENDING WITH 3757 "
     "ON 12-12-2025.YOUR AVAILABLE LIMIT IS Rs. 1,49,146.00",
     {"kind": "credit", "amount_paise": 2344800, "account_last4": "3757", "counterparty": None, "balance_paise": None,
      "txn_date": date(2025, 12, 12), "is_card": True}),
    ("JM-ICICIT", "ICICI Bank Acct XX219 debited for Rs 700.00 on 01-Nov-25; TRENDY SALON credited. UPI:530517995677. "
     "Call 18002662 for dispute. SMS BLOCK 219 to 9215676766.",
     {"kind": "debit", "amount_paise": 70000, "account_ref": "219", "account_last4": "3219", "counterparty": "TRENDY SALON",
      "ref_no": "530517995677", "txn_date": date(2025, 11, 1), "mode": "upi"}),
    ("VK-ICICIT", "INR 179.00 spent using ICICI Bank Card XX4602 on 07-Nov-25 on UBER INDIA SYSTEMS. "
     "Avl Limit: INR 1,11,421.00. If not you, call 1800 2662/SMS BLOCK 4602 to 9215676766.",
     {"kind": "debit", "amount_paise": 17900, "account_last4": "4602", "counterparty": "UBER INDIA SYSTEMS",
      "balance_paise": None, "is_card": True}),
    ("CP-ICICIT", "ICICI Bank Account XX448 credited:Rs. 72,000.00 on 03-Nov-25. Info IMPS-530718714762-SOWMYA NATARAJAN. "
     "Available Balance is Rs. 2,54,440.00.",
     {"kind": "credit", "amount_paise": 7200000, "counterparty": "SOWMYA NATARAJAN", "ref_no": "530718714762",
      "balance_paise": 25444000, "mode": "imps"}),
    ("AD-ICICIT-S", "ICICI Bank Acct XX219 debited with INR 1,000.00 on 02-Nov-25 at ATM ATM THANE WEST MUMBAI. "
     "Avl Bal INR 77,500.00.",
     {"kind": "debit", "amount_paise": 100000, "counterparty": None, "balance_paise": 7750000, "mode": "atm"}),
    ("VM-SBIUPI", "Dear UPI user A/C X7605 debited by 420.0 on date 03Nov25 trf to R BALU Refno 530719713120 "
     "If not u? call-1800111109 for other services-18001234-SBI",
     {"kind": "debit", "amount_paise": 42000, "account_last4": "7605", "counterparty": "R BALU", "ref_no": "530719713120",
      "txn_date": date(2025, 11, 3)}),
    ("DM-CBSSBI", "Dear Customer, INR 78,450.00 credited to your A/c No XX7605 on 03/11/2025 through NEFT with UTR "
     "HDFCN25307402695 by KAVERI AUTO COMPONENTS PV, INFO: SALARY OCT 2025. -SBI",
     {"kind": "credit", "amount_paise": 7845000, "counterparty": "KAVERI AUTO COMPONENTS PV", "ref_no": "HDFCN25307402695",
      "txn_date": date(2025, 11, 3)}),
    ("BP-CBSSBI-T", "Dear Customer, INR 6,210.00 credited to your A/c No XX7605 on 06/10/2026 through NEFT with UTR "
     "SBINN26279471590 by CBDT INCOME TAX REFUND, INFO: ITR REFUND AY 2026-27. -SBI",
     {"kind": "credit", "counterparty": "CBDT INCOME TAX REFUND"}),
    ("TM-CBSSBI-T", "Your A/C XXXXX7605 Debited INR 40,598.00 on 06/11/25 -ACH-SBI HOME LOAN. Avl Balance INR 4,03,164.00-SBI",
     {"kind": "debit", "amount_paise": 4059800, "counterparty": "SBI HOME LOAN", "balance_paise": 40316400, "mode": "nach"}),
    ("QP-ATMSBI-S", "Dear Customer, Your A/C XXXXX7605 has a debit by ATM withdrawal of Rs 2,000.00 on 27Dec25. "
     "Avl Bal Rs 3,50,152.84.If not done by you, forward this SMS to 7400165218/ call 1800111109 to block card. -SBI",
     {"kind": "debit", "amount_paise": 200000, "counterparty": None, "txn_date": date(2025, 12, 27), "balance_paise": 35015284}),
    ("IM-SBIUPI", "Dear SBI UPI User, ur A/cX7605 credited by Rs11.0 on 08Jan26 by  (Ref no 600820836486)",
     {"kind": "credit", "amount_paise": 1100, "account_last4": "7605", "counterparty": None, "ref_no": "600820836486"}),
    ("VK-AXISBK-T", "INR 224.00 debited\nA/c no. XX9553\n29-09-26, 20:55:56\nUPI/P2A/627220451431/RITU CHOUDHARY\n"
     "Not you? SMS BLOCKUPI Cust ID to 919951860002\nAxis Bank",
     {"kind": "debit", "amount_paise": 22400, "account_last4": "9553", "counterparty": "RITU CHOUDHARY",
      "ref_no": "627220451431", "txn_date": date(2026, 9, 29)}),
    ("TM-AXISBK-T", "Spent\nCard no. XX1500\nINR 3,838.73\n30-07-26 11:30:57\nBHARAT PETROLEUM COR\nAvl Lmt INR 3,96,002.63\n"
     "SMS BLOCK 1500 to 919951860002, if not you - Axis Bank",
     {"kind": "debit", "amount_paise": 383873, "account_last4": "1500", "counterparty": "BHARAT PETROLEUM COR",
      "balance_paise": None, "is_card": True}),
    ("DM-AXISBK", "INR 1,327.17 credited to A/c no. XX5149 on 15-08-26, 22:36:05 IST. Info- IMPS/622722821650/"
     "ROPPEN TRANSPORTATION CAP. Avl Bal-INR 1,377.38 - Axis Bank",
     {"kind": "credit", "amount_paise": 132717, "counterparty": "ROPPEN TRANSPORTATION CAP", "ref_no": "622722821650",
      "balance_paise": 137738}),
    ("DM-BOBTXN", "Rs.208.00 Dr. from A/C XXXXXX7878 and Cr. to paytmqr33544652399525@paytm. Ref:611918345230. "
     "AvlBal:Rs32376.86(2026:04:29 18:02:01). Not you? Call 18005700-BOB",
     {"kind": "debit", "amount_paise": 20800, "account_last4": "7878", "counterparty": None,
      "vpa": "paytmqr33544652399525@paytm", "ref_no": "611918345230", "txn_date": date(2026, 4, 29), "balance_paise": 3237686}),
    ("QP-BOBTXN-S", "Rs.1277.97 Credited to A/c ...6140 thru IMPS 600822647810 by SWIGGY LTD DE PAYOUT. "
     "Total Bal:Rs.15275.88CR. (08-01-2026) - Bank of Baroda",
     {"kind": "credit", "amount_paise": 127797, "account_last4": "6140", "counterparty": "SWIGGY LTD DE PAYOUT",
      "ref_no": "600822647810", "txn_date": date(2026, 1, 8), "balance_paise": 1527588}),
    ("AX-CANBNK", "An amount of INR 1,155.00 has been DEBITED to your account XXX6183 on 19/05/2026 towards UPI/613901861843. "
     "Total Avail.bal INR 4,463.47. - Canara Bank",
     {"kind": "debit", "amount_paise": 115500, "account_last4": "6183", "counterparty": None, "ref_no": "613901861843",
      "balance_paise": 446347}),
    ("QP-KOTAKB-T", "Sent Rs.180.00 from Kotak Bank A/c X3502 to sapna2002@ybl on 16-03-26.UPI Ref 607515395588. "
     "Not you, https://kotak.com/KBANKT/Fraud",
     {"kind": "debit", "amount_paise": 18000, "account_last4": "3502", "counterparty": None, "vpa": "sapna2002@ybl",
      "ref_no": "607515395588", "txn_date": date(2026, 3, 16), "balance_paise": None}),
    ("CP-KOTAKB-S", "Rs.3000.00 debited from Kotak Bank A/c X6069 on 10-03-26 by NACH to INDIAN CLEARING CORP LTD. Bal:Rs.15601.17",
     {"kind": "debit", "amount_paise": 300000, "counterparty": "INDIAN CLEARING CORP LTD", "balance_paise": 1560117, "mode": "nach"}),
]


@pytest.mark.parametrize(("sender", "body", "want"), CASES, ids=[c[0] + " " + c[1][:28].replace("\n", " ") for c in CASES])
def test_known_wordings(sender: str, body: str, want: dict[str, object]) -> None:
    got = parse_sms(sender, body, RECEIVED, known_last4={"3219", "4602", "9168"})
    for field, value in want.items():
        assert getattr(got, field) == value, field


def test_a_wording_never_seen_before_falls_back_to_the_generic_rules() -> None:
    # no bank family, an unknown sender, and phrasing none of the family rules were written from
    got = parse_sms("VM-NEWBNK", "Your Credit Card XX4602 has been used for a transaction of INR 2,160.00 on Nov 11, 2025 "
                    "at 02:22:26. Info: TRENT LTD ZUDIO.", RECEIVED)
    assert (got.kind, got.amount_paise, got.account_last4, got.counterparty) == ("debit", 216000, "4602", "TRENT LTD ZUDIO")
    assert got.txn_date == date(2025, 11, 11)
    assert got.matched == "generic" and got.bank is None and got.is_card


@pytest.mark.parametrize(("sender", "body", "reason"), [
    ("AX-HDFCBK-T", "104850 is OTP for txn of INR 849.00 at FLIPKART INTERNET PVT LTD on card ending 3757. Valid till 14:16. "
     "Do not share OTP for security reasons.", "otp"),
    ("AX-HDFCBK", "Your HDFC Bank Credit Card XX3757 statement is generated. Total Amt Due: Rs 23,448.00; "
     "Min Amt Due: Rs 1,172.00; Due by 15-Dec-25. Pay via app.", "statement_notice"),
    ("DM-ICICIT-P", "Pre-approved Personal Loan of up to Rs 2,00,000 is waiting for you! Instant disbursal. T&C. "
     "Apply: https://bit.ly/x7244", "promo"),
    ("CP-SBIUPI-P", "Your A/c XX7605 balance is low? Get instant overdraft up to Rs 50,000. Visit app. T&C.", "promo"),
    ("VK-HDFCBK", "Dear Customer, update your KYC to continue uninterrupted services. Visit branch with Aadhaar & PAN.",
     "not_a_transaction"),
])
def test_messages_that_are_not_transactions_are_skipped(sender: str, body: str, reason: str) -> None:
    got = parse_sms(sender, body, RECEIVED)
    assert (got.kind, got.reason, got.amount_paise) == ("ignore", reason, None)


def test_the_first_direction_word_decides() -> None:
    assert parse_sms("X-ICICIT", "Acct XX219 debited for Rs 50.00; RAVI credited.", RECEIVED).kind == "debit"
    assert parse_sms("X-HDFCBK", "Refund of Rs.658.00 from SWIGGY credited to HDFC Bank Card 0484 on 20-10-26.", RECEIVED).kind == "credit"


def test_a_message_with_no_date_takes_the_day_it_arrived_in_india() -> None:
    late = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)  # 01:30 on the 11th in India
    assert parse_sms("X-HDFCBK", "Rs.10.00 debited from A/c XX9168 to RAVI", late).txn_date == date(2026, 11, 11)


def test_three_digit_account_needs_exactly_one_linked_account() -> None:
    assert resolve_last4("219", {"3219", "4602"}) == "3219"
    assert resolve_last4("219", {"3219", "8219"}) is None  # two accounts end the same way
    assert resolve_last4("219", set()) is None
    assert resolve_last4("XX9168"[-4:], set()) == "9168"
    assert resolve_last4(None, {"3219"}) is None


def test_sender_headers() -> None:
    assert sender_bank("DM-HDFCBK-S") == ("hdfc", False)
    assert sender_bank("AX-ICICIT-P") == ("icici", True)
    assert sender_bank("QP-ATMSBI") == ("sbi", False)
    assert sender_bank("VM-NEWBNK-T") == (None, False)


def test_money_is_exact() -> None:
    assert to_paise("1,25,580.98") == 12558098
    assert to_paise("420.0") == 42000
    assert to_paise("0.07") == 7
    assert to_paise("19,760") == 1976000
    assert to_paise("12.345") is None  # more precision than paise: refuse rather than round
    assert to_paise("abc") is None


@given(st.integers(min_value=1, max_value=10**12), st.sampled_from(["Rs.", "Rs ", "INR ", "Rs. ", "₹"]))
def test_any_amount_survives_formatting_and_parsing(paise: int, mark: str) -> None:
    printed = f"{group_indian(paise // 100)}.{paise % 100:02d}"
    got = parse_sms("DM-HDFCBK", f"{mark}{printed} debited from A/c XX9168 on 01-11-25 to RAVI KUMAR. Avl Bal Rs.1,00,000.00")
    assert got.amount_paise == paise
    assert got.balance_paise == 1_00_000_00
