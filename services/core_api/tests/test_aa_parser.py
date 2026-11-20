"""The account-feed (Account Aggregator) parser: structured fields exactly, and each bank's narration style."""

from datetime import date, datetime

import pytest
from core_api.config import IST
from core_api.ingest.aa import parse_account, read_narration, rupees_to_paise
from core_api.seed.offline import Dataset
from hypothesis import given
from hypothesis import strategies as st

# (narration, AA mode, direction) -> (channel, name the bank printed, VPA). Narrations are from the synthetic dataset.
NARRATIONS: list[tuple[str, str, str, tuple[str, str | None, str | None]]] = [
    ("TO TRANSFER-UPI/DR/530719713120/R BALU/UTIB/rbalu980@okaxis/UPI--", "UPI", "debit", ("upi", "R BALU", "rbalu980@okaxis")),
    ("TO TRANSFER-UPI/DR/531205367681/BHARTI AIRTEL XSTREA/AIRP/airtelxstream@airtel/AUTOPAY--", "UPI", "debit",
     ("autopay", "BHARTI AIRTEL XSTREA", "airtelxstream@airtel")),
    ("BY TRANSFER-IMPS/P2A/530618340752/RAMESH NARAYANAN/UTIB/Household--", "FT", "credit", ("imps", "RAMESH NARAYANAN", None)),
    ("BY TRANSFER-NEFT*HDFC0000846*HDFCN25307402695*KAVERI AUTO COMP--", "FT", "credit", ("neft", "KAVERI AUTO COMP", None)),
    ("DEBIT-ACHDr 724741258604 SBI HOME LOAN", "OTHERS", "debit", ("nach", "SBI HOME LOAN", None)),
    ("ATM WDL-ATM CASH 2172 MADIPAKKAM CHENNAI", "ATM", "debit", ("atm", "ATM MADIPAKKAM CHENNAI", None)),
    ("UPI-LAKSHMAMMA-lakshmamma86@okaxis-UTIB0000284-530509919924-MAID SALARY – NOV", "UPI", "debit",
     ("upi", "LAKSHMAMMA", "lakshmamma86@okaxis")),
    ("UPI-AKHIL KUMAR-gpay-36034732876@okbizaxis-UTIB0000983-530518663866-UPI", "UPI", "debit",
     ("upi", "AKHIL KUMAR", "gpay-36034732876@okbizaxis")),
    ("UPI-SPOTIFY INDIA-spotify.rzp@icici-ICIC0000320-530904687697-AUTOPAY", "UPI", "debit", ("autopay", "SPOTIFY INDIA", "spotify.rzp@icici")),
    ("NEFT CR-ICIC0000508-BLUEWAVE TECHNOLOGIES-ANANYA SRINIVASAN-ICICN25332434198", "FT", "credit", ("neft", "BLUEWAVE TECHNOLOGIES", None)),
    ("NEFT DR-YESB0000245-SHREE SAI HEIGHTS CHS-NETBANK, MUM-HDFCN25314427612-PAYMENT", "FT", "debit", ("neft", "SHREE SAI HEIGHTS CHS", None)),
    ("ACH D- LIFE INSURANCE CORPORA-607796542629", "OTHERS", "debit", ("nach", "LIFE INSURANCE CORPORA", None)),
    ("NWD-XXXXXXXXXXXX9168-NWDCH9973-HSR LAYOUT BENGALU", "ATM", "debit", ("atm", "ATM HSR LAYOUT BENGALU", None)),
    ("NETBANKING TRF-SRI VIDYA MANDIR MATRI-IB9886794298", "OTHERS", "debit", ("other", "SRI VIDYA MANDIR MATRI", None)),
    ("UPI/P2M/530517934292/STYLE POINT SALON/Payment from Ph/Yes Bank", "UPI", "debit", ("upi", "STYLE POINT SALON", None)),
    ("ACH-DR-LIFE INSURANCE CORPO-776856561410", "OTHERS", "debit", ("nach", "LIFE INSURANCE CORPO", None)),
    ("ATM-CASH/MALVIYA NAGAR JAIP/AXHY2184", "ATM", "debit", ("atm", "ATM MALVIYA NAGAR JAIP", None)),
    ("UPI/VIKAS KUMAR/531422269186/For you", "UPI", "credit", ("upi", "VIKAS KUMAR", None)),
    ("ACH DR HERO FINCORP LTD 200772183610", "OTHERS", "debit", ("nach", "HERO FINCORP LTD", None)),
    ("ATL/KMBL1716/530610025297/LAXMI NAGAR DELHI", "ATM", "debit", ("atm", "ATM LAXMI NAGAR DELHI", None)),
    ("UPI/532216091668/DR/JAIPUR VIDYUT VITRAN/SBIN/jvvnl.bbps@sbi", "UPI", "debit", ("upi", "JAIPUR VIDYUT VITRAN", "jvvnl.bbps@sbi")),
    ("NEFT-YESBN25306992450-PHONEPE PVT LTD-SETTLEMENT 011125", "FT", "credit", ("neft", "PHONEPE PVT LTD", None)),
    ("NACH DR INDIAN CLEARING CORP L 438659672905", "OTHERS", "debit", ("nach", "INDIAN CLEARING CORP L", None)),
    ("MMT/IMPS/530718714762/Household/SOWMYA NATARAJA/ICIC", "FT", "credit", ("imps", "SOWMYA NATARAJA", None)),
    # this bank prints the payer's note and the payee's bank, but not the payee: no name, the VPA identifies them
    ("UPI/530517995677/Payment from Ph/q664579246@ybl/Yes Bank/ICI1555564350", "UPI", "debit", ("upi", None, "q664579246@ybl")),
    ("BY CASH MALVIYA NAGAR", "CASH", "credit", ("cash", "CASH DEPOSIT", None)),
    ("INTEREST PAID TILL 31-12-2025", "OTHERS", "credit", ("interest", "INTEREST", None)),
    ("SB:XX9553:Int.Pd:01-10-2025:31-12-2025", "OTHERS", "credit", ("interest", "INTEREST", None)),
    ("TRF TO FD NO 82328820746", "OTHERS", "debit", ("other", "FD 82328820746", None)),
    ("TD CLOSURE PROCEEDS 32018061067", "OTHERS", "credit", ("other", "FD CLOSURE PROCEEDS", None)),
    ("TO TRANSFER-INB BILLDESK CC 3757--", "OTHERS", "debit", ("other", "BILLDESK", None)),
]


@pytest.mark.parametrize(("narration", "aa_mode", "direction", "want"), NARRATIONS, ids=[n[0][:44] for n in NARRATIONS])
def test_narrations(narration: str, aa_mode: str, direction: str, want: tuple[str, str | None, str | None]) -> None:
    mode, name, vpa, _, _ = read_narration(narration, reference=None, aa_mode=aa_mode, direction=direction, on_card=False)
    assert (mode, name, vpa) == want


@pytest.mark.parametrize(("narration", "want"), [
    ("BATA INDIA LTD CHENNAI IN", ("card", "BATA INDIA LTD")),
    ("INDIAN OIL CORPORATION NEW DELHI IN", ("card", "INDIAN OIL CORPORATION")),
    ("REFUND ZEPTO KIRANAKART", ("card", "ZEPTO KIRANAKART")),
    ("PAYMENT RECEIVED - THANK YOU", ("other", "PAYMENT RECEIVED")),
    ("CC PAYMENT RECEIVED NETBANKING", ("other", "PAYMENT RECEIVED")),
    ("IGST ON FINANCE CHARGES", ("other", "IGST ON FINANCE CHARGES")),
])
def test_card_narrations(narration: str, want: tuple[str, str]) -> None:
    mode, name, vpa, _, _ = read_narration(narration, reference=None, aa_mode=None, direction="debit", on_card=True)
    assert (mode, name, vpa) == (*want, None)


def test_reversals_and_own_account_transfers_are_marked() -> None:
    _, name, _, reversal, own = read_narration("BY TRANSFER-UPI/REV/535110446029/VELACHERY FRESH VEGE/YESB/q202172359@ybl--",
                                               reference="535110446029", aa_mode="UPI", direction="credit", on_card=False)
    assert (name, reversal, own) == ("VELACHERY FRESH VEGE", True, False)
    _, name, _, reversal, own = read_narration("IMPS-530617639666-ANANYA SRINIVASAN-XXXXXXXX2924-SELF", reference="530617639666",
                                               aa_mode="FT", direction="debit", on_card=False)
    assert (name, reversal, own) == ("ANANYA SRINIVASAN", False, True)


def test_a_deposit_statement() -> None:
    account = parse_account({"Account": {
        "type": "deposit", "maskedAccNumber": "XXXXXXX9168",
        "Transactions": {"Transaction": [
            {"txnId": "t1", "type": "DEBIT", "mode": "UPI", "amount": "1,234.50", "currentBalance": "98765.43",
             "transactionTimestamp": "2026-11-19T21:15:07+05:30", "valueDate": "2026-11-19",
             "narration": "UPI-SWIGGY-swiggyorders@axisbank-UTIB0000100-632313123456-UPI", "reference": "632313123456"},
            {"txnId": "t2", "type": "PENDING", "mode": "UPI", "amount": "10.00", "transactionTimestamp": "2026-11-19T21:16:00+05:30",
             "narration": "x", "reference": ""},
            {"txnId": "t3", "type": "CREDIT", "mode": "FT", "amount": "12.345", "transactionTimestamp": "2026-11-19T21:17:00+05:30",
             "narration": "x", "reference": ""},
        ]},
    }})
    assert (account.kind, account.last4, len(account.transactions)) == ("deposit", "9168", 1)  # the other two are not money that moved
    t = account.transactions[0]
    assert (t.txn_id, t.direction, t.amount_paise, t.balance_paise, t.ref_no) == ("t1", "debit", 123450, 9876543, "632313123456")
    assert t.occurred_at == datetime(2026, 11, 19, 21, 15, 7, tzinfo=IST) and t.value_date == date(2026, 11, 19)
    assert (t.mode, t.counterparty, t.vpa) == ("upi", "SWIGGY", "swiggyorders@axisbank")


def test_a_card_statement_has_no_balance() -> None:
    account = parse_account({"Account": {
        "type": "credit_card", "maskedCardNumber": "46XXXXXXXXXX4602",
        "Transactions": {"Transaction": [
            {"txnId": "c1", "txnType": "DEBIT", "mcc": 5812, "amount": "762.00", "txnDate": "2025-11-02T13:35:53+05:30",
             "valueDate": "2025-11-02", "narration": "GRAVISS BASKIN ROBBINS CHENNAI IN", "reference": ""},
        ]},
    }})
    t = account.transactions[0]
    assert (account.last4, t.direction, t.amount_paise, t.balance_paise, t.ref_no, t.mode, t.counterparty, t.mcc) == (
        "4602", "debit", 76200, None, None, "card", "GRAVISS BASKIN ROBBINS", 5812)


def test_money_is_exact() -> None:
    assert rupees_to_paise("23448.00") == 2344800
    assert rupees_to_paise("0.07") == 7
    assert rupees_to_paise("1,25,580.98") == 12558098
    assert rupees_to_paise("12.345") is None
    assert rupees_to_paise(None) is None


@given(st.integers(min_value=1, max_value=10**13))
def test_any_amount_reads_back_exactly(paise: int) -> None:
    assert rupees_to_paise(f"{paise // 100}.{paise % 100:02d}") == paise


def test_every_demo_statement_row_matches_the_ledger() -> None:
    """The feed's structured fields against the loaded ledger, for all six personas."""
    import json

    from core_api.config import get_settings

    by_id = {t.id: t for _, ctx in Dataset("demo").contexts() for t in ctx.txns}
    seen = 0
    for path in sorted((get_settings().data_path / "demo" / "sources").glob("*/account_aggregator/*.json")):
        for t in parse_account(json.loads(path.read_text(encoding="utf-8"))).transactions:
            row = by_id[t.txn_id]
            assert (t.amount_paise, t.direction, t.occurred_at) == (row.amount_paise, row.direction, row.occurred_at), t.narration
            assert (t.ref_no or None) == (row.ref_no or None)
            if t.balance_paise is not None:
                assert t.balance_paise == row.balance_after_paise
            if t.vpa:
                assert t.vpa == row.counterparty_vpa, t.narration
            seen += 1
    assert seen == len(by_id) == 7379
