"""The loader: account statements in, ledger rows out. Each rule on a hand-built statement, then
the six demo personas against the ledger the dataset ships."""

from datetime import datetime
from typing import Any

import pytest
from core_api.config import get_settings
from core_api.ingest.feed import FeedError, GroupLinks, SettlementLink, _says, _vpa_spells, load_feed
from core_api.ingest.sms import parse_sms
from core_api.insights import engine
from core_api.ledger import summary
from core_api.reports.monthly import monthly_report
from core_api.seed import loader
from core_api.seed.offline import Dataset

Row = dict[str, str | None]


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return Dataset("demo")


# ---------- hand-built statements ----------
SAVINGS: Row = {"account_id": "acct-savings", "type": "savings", "masked_number": "XXXXXX9168", "role": "primary", "institution_code": "HDFC"}
SECOND: Row = {"account_id": "acct-second", "type": "savings", "masked_number": "XXXXXX2924", "role": "secondary", "institution_code": "SBI"}
CARD: Row = {"account_id": "acct-card", "type": "credit_card", "masked_number": "XXXXXXXXXXXX4602", "role": "card", "institution_code": "ICICI"}
ACCOUNTS = [SAVINGS, SECOND, CARD]


def row(txn_id: str, kind: str, rupees: str, when: str, narration: str, reference: str = "", mode: str = "UPI") -> dict[str, str]:
    return {"txnId": txn_id, "type": kind, "mode": mode, "amount": rupees, "currentBalance": "50000.00",
            "transactionTimestamp": f"{when}+05:30", "valueDate": when[:10], "narration": narration, "reference": reference}


def deposit(last4: str, *rows: dict[str, str]) -> dict[str, Any]:
    return {"Account": {"type": "deposit", "maskedAccNumber": f"XXXXXX{last4}", "Transactions": {"Transaction": list(rows)}}}


def card(*rows: dict[str, str]) -> dict[str, Any]:
    shaped = [{"txnId": r["txnId"], "txnType": r["type"], "amount": r["amount"], "txnDate": r["transactionTimestamp"],
               "valueDate": r["valueDate"], "narration": r["narration"], "reference": r["reference"]} for r in rows]
    return {"Account": {"type": "credit_card", "maskedCardNumber": "46XXXXXXXXXX4602", "Transactions": {"Transaction": shaped}}}


def item(key: str, category: str, rupees: int, *, payee: str = "", merchant: str = "", channel: str = "upi_p2p", kind: str = "bill",
         variable: bool = False, day: int = 5) -> Row:
    return {"key": key, "kind": kind, "category": category, "channel": channel, "merchant_key": merchant or None, "payee": payee or None,
            "amount_paise": str(rupees * 100), "amount_is_variable": str(variable), "account_role": "primary", "start_date": None,
            "end_date": None, "day": str(day), "cadence": "monthly"}


def load(ds: Dataset, *statements: dict[str, Any], recurring: tuple[Row, ...] = (), income_pattern: str = "salaried",
         **more: Any) -> dict[str, Row]:
    rows = load_feed(statements, accounts=ACCOUNTS, recurring=recurring, merchants=ds.merchant_index, categories=ds.data.category_map,
                     owner_name="Ananya Srinivasan", income_pattern=income_pattern, **more)
    return {str(r["txn_id"]): r for r in rows}


def test_a_statement_for_an_account_the_user_has_not_linked_is_refused(ds: Dataset) -> None:
    with pytest.raises(FeedError):
        load(ds, deposit("0000", row("t1", "DEBIT", "10.00", "2026-11-01T10:00:00", "UPI/SWIGGY/632313123456/UPI")))


def test_the_facts_are_read_as_stated_and_the_merchant_decides_the_category(ds: Dataset) -> None:
    got = load(ds, deposit("9168", row("t1", "DEBIT", "1,234.50", "2026-11-01T21:15:07",
                                       "UPI-SWIGGY-swiggyorders@axisbank-UTIB0000100-632313123456-UPI", "632313123456")))["t1"]
    assert (got["account_id"], got["amount_paise"], got["direction"], got["ref_no"], got["balance_after_paise"]) == (
        "acct-savings", "123450", "debit", "632313123456", "5000000")
    assert (got["merchant_key"], got["category_id"], got["status"], got["kind"], got["source"]) == ("swiggy", "food_delivery", "success", "upi_p2m", "aa")


def test_money_back_under_the_same_reference_on_the_same_account_is_a_reversal(ds: Dataset) -> None:
    got = load(ds, deposit(
        "9168",
        row("pay", "DEBIT", "320.00", "2026-11-01T13:00:00", "UPI-ZOMATO LTD-zomato.payu@hdfcbank-HDFC0000102-632322840992-UPI", "632322840992"),
        row("back", "CREDIT", "320.00", "2026-11-01T13:02:00", "UPI REV/632322840992/ZOMATO LTD", "632322840992"),
    ))
    assert (got["pay"]["status"], got["back"]["status"], got["back"]["reversal_of_id"], got["back"]["kind"]) == ("reversed", "reversed", "pay", "upi_reversal")
    assert got["back"]["category_id"] == got["pay"]["category_id"] == "food_delivery"  # filed with the payment it undoes


def test_the_same_movement_on_two_own_accounts_is_a_transfer_and_on_a_card_a_bill_payment(ds: Dataset) -> None:
    got = load(
        ds,
        deposit("9168",
                row("out", "DEBIT", "5000.00", "2026-11-02T09:00:00", "IMPS-530617639666-ANANYA SRINIVASAN-XXXXXXXX2924-SELF", "530617639666", "FT"),
                row("bill", "DEBIT", "8000.00", "2026-11-03T09:00:00", "IB BILLPAY DR-BILLDESK-XXXXXXXXXXXX4602", "530700000001", "OTHERS")),
        deposit("2924", row("in", "CREDIT", "5000.00", "2026-11-02T09:00:05", "BY TRANSFER-IMPS/P2A/530617639666/ANANYA SRINIVASAN/SBIN/SELF--", "530617639666", "FT")),
        card(row("paid", "CREDIT", "8000.00", "2026-11-03T09:01:00", "PAYMENT RECEIVED - THANK YOU", "530700000001")),
    )
    assert (got["out"]["transfer_pair_id"], got["in"]["transfer_pair_id"]) == ("in", "out")
    assert (got["out"]["category_id"], got["in"]["category_id"], got["out"]["kind"], got["in"]["kind"]) == ("self_transfer", "self_transfer", "self_out", "self_in")
    assert (got["bill"]["transfer_pair_id"], got["paid"]["transfer_pair_id"]) == ("paid", "bill")
    assert (got["bill"]["category_id"], got["paid"]["category_id"], got["bill"]["kind"]) == ("card_payment", "card_payment", "card_bill_pay")


def test_a_payment_is_tied_to_the_recurring_item_it_pays(ds: Dataset) -> None:
    rent = item("rent", "rent", 16_800, payee="K NAGARAJ", kind="rent")
    spotify = item("spotify", "subscriptions", 139, merchant="spotify", channel="autopay", kind="subscription")
    got = load(ds, deposit(
        "9168",
        row("rent-old", "DEBIT", "16000.00", "2026-01-05T10:00:00", "UPI-K NAGARAJ-knagaraj@okaxis-UTIB0000284-600500000001-UPI", "600500000001"),
        row("rent-new", "DEBIT", "16800.00", "2026-11-05T10:00:00", "UPI-K NAGARAJ-knagaraj@okaxis-UTIB0000284-630900000002-UPI", "630900000002"),
        row("loan", "DEBIT", "2000.00", "2026-11-09T10:00:00", "UPI-K NAGARAJ-knagaraj@okaxis-UTIB0000284-631300000003-UPI", "631300000003"),
        row("mandate", "DEBIT", "1.00", "2026-10-01T10:00:00", "UPI-SPOTIFY INDIA-spotify.rzp@icici-ICIC0000320-627400000004-MANDATE REG", "627400000004"),
        row("song", "DEBIT", "139.00", "2026-11-01T10:00:00", "UPI-SPOTIFY INDIA-spotify.rzp@icici-ICIC0000320-630500000005-AUTOPAY", "630500000005"),
    ), recurring=(rent, spotify))
    assert (got["rent-old"]["recurring_key"], got["rent-new"]["recurring_key"]) == ("rent", "rent")  # the rent before and after it went up
    assert (got["rent-new"]["category_id"], got["song"]["recurring_key"]) == ("rent", "spotify")
    assert got["loan"]["recurring_key"] is None  # a much smaller payment to the landlord is not the rent
    assert got["loan"]["category_id"] == "rent"  # but it is still the landlord
    assert got["mandate"]["recurring_key"] is None  # the one-rupee mandate set-up is not a month of the subscription


def test_two_items_alike_in_payee_and_amount_are_told_apart_by_their_day(ds: Dataset) -> None:
    first = item("sip_0", "investment", 5000, merchant="iccl", channel="ach", kind="sip", day=5)
    second = item("sip_1", "investment", 5000, merchant="iccl", channel="ach", kind="sip", day=20)
    got = load(ds, deposit(
        "9168",
        row("a", "DEBIT", "5000.00", "2026-11-05T06:00:00", "ACH D- INDIAN CLEARING CORP L-922884233303", "922884233303", "OTHERS"),
        row("b", "DEBIT", "5000.00", "2026-11-20T06:00:00", "ACH D- INDIAN CLEARING CORP L-647096595490", "647096595490", "OTHERS"),
    ), recurring=(first, second))
    assert (got["a"]["recurring_key"], got["b"]["recurring_key"]) == ("sip_0", "sip_1")


def test_a_bank_that_prints_only_the_vpa_still_finds_the_item(ds: Dataset) -> None:
    maid = item("maid", "home_services", 3500, payee="ANITA SAINI")
    got = load(ds, deposit("9168", row("t1", "DEBIT", "3500.00", "2026-11-07T08:00:00",
                                       "UPI/600717931856/UPI/anitas93@upi/Bank of Baroda/ICI66204100", "600717931856")), recurring=(maid,))
    assert (got["t1"]["counterparty_name"], got["t1"]["recurring_key"], got["t1"]["category_id"]) == (None, "maid", "home_services")


def test_refunds_cashback_and_what_cannot_be_known(ds: Dataset) -> None:
    got = load(ds, deposit(
        "9168",
        row("order-1", "DEBIT", "191.00", "2026-11-02T20:00:00", "UPI/SWIGGY/600501418463/UPI", "600501418463"),
        row("order-2", "DEBIT", "491.00", "2026-11-04T22:00:00", "UPI/SWIGGY/600501418464/UPI", "600501418464"),
        row("refund", "CREDIT", "191.00", "2026-11-05T01:00:00", "UPI/SWIGGY/600501418465/REFUND", "600501418465"),
        row("cashback", "CREDIT", "25.00", "2026-11-06T01:00:00", "UPI/AMAZON PAY CASHBACK/600501418466/Cashback", "600501418466"),
        row("friend", "DEBIT", "170.00", "2026-11-06T09:00:00", "UPI/SNEHA SUBRAMANIAN/600501418467/UPI", "600501418467"),
        row("pump", "DEBIT", "1600.00", "2026-11-06T10:00:00", "TO TRANSFER-UPI/DR/534011383916/SAI KRUPA SERVICE ST/YESB/q563528537@ybl/UPI--", "534011383916"),
        row("atm", "DEBIT", "2000.00", "2026-11-07T10:00:00", "ATM WDL-ATM CASH 2172 MADIPAKKAM CHENNAI", "", "ATM"),
        row("fee", "DEBIT", "17.70", "2026-11-08T10:00:00", "SMS ALERT CHARGES SMS CHGS OCT-DEC26", "", "OTHERS"),
        row("fd", "DEBIT", "10000.00", "2026-11-09T10:00:00", "TRF TO FD 61212698040", "", "OTHERS"),
    ))
    assert (got["refund"]["category_id"], got["refund"]["refund_of_id"]) == ("refund", "order-1")  # the order of exactly that amount, not the latest
    assert got["cashback"]["category_id"] == "other_income"
    assert got["friend"]["category_id"] == "uncategorised"  # what a payment to a person was for is not in the feed
    assert (got["pump"]["category_id"], got["atm"]["category_id"], got["fee"]["category_id"], got["fd"]["category_id"]) == (
        "fuel", "cash_withdrawal", "fees_charges", "self_transfer")


def test_one_vpa_is_one_payee_whatever_name_the_bank_prints(ds: Dataset) -> None:
    got = load(ds, deposit(
        "9168",
        row("a", "DEBIT", "291.00", "2026-11-02T10:00:00", "TO TRANSFER-UPI/DR/535811583172/SELVAM STORES/YESB/q466177183@ybl/UPI--", "535811583172"),
        row("b", "DEBIT", "480.00", "2026-11-03T10:00:00", "TO TRANSFER-UPI/DR/601521438610/R SELVAM/YESB/q466177183@ybl/Pay--", "601521438610"),
        row("c", "DEBIT", "480.00", "2026-11-04T10:00:00", "TO TRANSFER-UPI/DR/601521438611/R SELVAM/YESB/rselvam77@okaxis/Pay--", "601521438611"),
    ))
    assert (got["a"]["category_id"], got["b"]["category_id"]) == ("groceries", "groceries")
    assert got["c"]["category_id"] == "uncategorised"  # the same name on another VPA is someone else


def test_salary_and_regular_income(ds: Dataset) -> None:
    months = ("2026-07", "2026-08", "2026-09")
    salaried = load(ds, deposit(
        "9168",
        row("said", "CREDIT", "51010.00", "2026-10-30T10:00:00", "NEFT HDFCN25332621729 MERIDIAN HEALTHCARE LT SALARY OCT 2026", "HDFCN25332621729", "FT"),
        *(row(f"pay-{mo}", "CREDIT", "61842.00", f"{mo}-28T10:00:00", f"NEFT CR-ICIC0000508-BLUEWAVE TECHNOLOGIES-ANANYA SRINIVASAN-ICICN253{i}", f"ICICN253{i}", "FT")
          for i, mo in enumerate(months)),
        row("tax", "CREDIT", "4200.00", "2026-09-12T10:00:00", "NEFT CR-SBIN0000001-CBDT INCOME TAX REFUND-ANANYA SRINIVASAN-SBINN2539", "SBINN2539", "FT"),
    ))
    assert salaried["said"]["category_id"] == "salary"  # the narration says so
    assert {salaried[f"pay-{mo}"]["category_id"] for mo in months} == {"salary"}  # the same amount from the same payer, three months running
    assert salaried["tax"]["category_id"] == "other_income"
    student = load(ds, deposit("9168", *(row(f"home-{mo}", "CREDIT", "6000.00", f"{mo}-02T10:00:00", f"UPI/R RAMASAMY/5305190713{i}/Pocket money",
                                           f"5305190713{i}") for i, mo in enumerate(months))), income_pattern="student")
    assert {r["category_id"] for r in student.values()} == {"allowance"}


def test_groups_say_what_their_payments_were(ds: Dataset) -> None:
    links = GroupLinks(
        expenses={"dinner": ("exp-1", "grp-1", "eating_out")},
        settlements=[SettlementLink("set-1", "grp-1", 176_800, "credit", "Riya Shetty", datetime.fromisoformat("2026-11-03T22:45:00+05:30"))],
    )
    got = load(ds, deposit(
        "9168",
        row("dinner", "DEBIT", "3252.00", "2026-11-01T21:00:00", "UPI/DR/626608105882/GOA EATING OUT/SBIN/goa92@oksbi/Dinner", "626608105882"),
        row("settled", "CREDIT", "1768.00", "2026-11-03T22:45:30", "UPI-RIYA SHETTY-riyas55@oksbi-SBIN0000284-630700000001-UPI", "630700000001"),
        row("gift", "CREDIT", "1768.00", "2026-11-12T10:00:00", "UPI-RIYA SHETTY-riyas55@oksbi-SBIN0000284-631600000002-UPI", "631600000002"),
    ), links=links)
    assert (got["dinner"]["group_expense_id"], got["dinner"]["group_id"], got["dinner"]["category_id"]) == ("exp-1", "grp-1", "eating_out")
    assert (got["settled"]["settlement_id"], got["settled"]["category_id"]) == ("set-1", "group_settlement")
    assert (got["gift"]["settlement_id"], got["gift"]["category_id"]) == (None, "other_income")  # the same amount nine days later is not that settle-up


def test_the_sms_for_a_payment_adds_to_its_row_and_never_a_second_row(ds: Dataset) -> None:
    statement = deposit("9168", row("t1", "DEBIT", "30.00", "2026-11-01T09:48:58", "UPI/SIVA S/530518663866/Pay to merchant", "530518663866"))
    when = datetime.fromisoformat("2026-11-01T09:48:58+05:30")
    sms = parse_sms("IM-HDFCBK-S", "Rs 30.00 debited from HDFC Bank A/c **9168 on 01-11-26 to VPA gpay-36034732876@okbizaxis "
                    "(UPI Ref No 530518663866). Not you? Call 18002586161", when, {"9168"})
    assert (sms.kind, sms.ref_no, sms.vpa) == ("debit", "530518663866", "gpay-36034732876@okbizaxis")
    alone, merged = load(ds, statement), load(ds, statement, sms=[sms])
    assert alone["t1"]["counterparty_vpa"] is None
    assert len(merged) == 1 and merged["t1"]["counterparty_vpa"] == "gpay-36034732876@okbizaxis"


def test_shop_words_cut_short_and_vpas_that_spell_a_name() -> None:
    assert _says("SAI KRUPA SERVICE ST", "SERVICE STATION") and _says("SRI KRISHNA BHOJANAL", "BHOJANALAYA")
    assert _says("SAI KRUPA PETROLEUMS", "PETROLEUM") and _says("NEW MEDICALS PORUR", "MEDICAL")
    assert not _says("SERVICE", "SERVICE STATION") and not _says("RESTORE POINT", "STORE") and not _says("ANITA S", "SALON")
    assert _vpa_spells("kunal.fernandes@ptaxis", "KUNAL FERNANDES") and _vpa_spells("anitas93@upi", "ANITA SAINI")
    assert not _vpa_spells("q563528537@ybl", "ANITA SAINI") and not _vpa_spells("sunita.devi@ybl", "ANITA SAINI") and not _vpa_spells(None, "ANITA SAINI")


def test_a_cut_short_name_shared_by_a_company_and_its_payout_account(ds: Dataset) -> None:
    find = ds.merchant_index.find
    assert find("ROPPEN TRANSPORTATIO", None, "debit", "upi").key == "rapido"  # type: ignore[union-attr]
    assert find("ROPPEN TRANSPORTATIO", None, "credit", "imps").key == "rapido_payout"  # type: ignore[union-attr]
    assert find("ROPPEN TRANSPORTATIO", None) is None  # with nothing to go on, no guess
    assert find("ZOMATO LTD DELIVERY PA WEEKLY PAYOUT", None, "credit", "neft").key == "zomato_payout"  # type: ignore[union-attr]
    assert find("BLINKIT COMMERCE PARTN", None, "credit", "imps").key == "blinkit_payout"  # type: ignore[union-attr]
    assert find("VIJAY N", None, "debit", "upi") is None  # a short name is a whole name, not the start of a shop's


# ---------- the six demo personas ----------
def test_demo_ledgers_from_the_feed_give_the_same_money_figures(ds: Dataset) -> None:
    """Every figure the app shows must be the same whether the ledger was shipped ready-made or worked out from the feed.

    The loader is given each persona's recurring items, as the app is (the dataset marks that table
    as a label). This guards the app's numbers; it is not a test of finding recurring payments."""
    seen = rows = same_category = 0
    for (uid, processed), (feed_uid, feed) in zip(ds.processed_by_user(), ds.feed_by_user(), strict=True):
        assert uid == feed_uid
        user_row = ds.users[uid]
        today = datetime.fromisoformat(str(user_row["data_end"])).date()
        want, got = ds.ctx(user_row, today, processed), ds.ctx(user_row, today, feed)
        got_by_id = {t.id: t for t in got.txns}
        assert len(got_by_id) == len(want.txns)
        for a in want.txns:
            b = got_by_id[a.id]
            assert (a.account_id, a.amount_paise, a.direction, a.occurred_at, a.status, a.budget_month, a.personal_amount_paise) == (
                b.account_id, b.amount_paise, b.direction, b.occurred_at, b.status, b.budget_month, b.personal_amount_paise), a.narration
            assert (a.spend_class, a.recurring_item_id, a.transfer_pair_id, a.reversal_of_id, a.group_expense_id, a.settlement_id) == (
                b.spend_class, b.recurring_item_id, b.transfer_pair_id, b.reversal_of_id, b.group_expense_id, b.settlement_id), a.narration
            rows += 1
            same_category += a.category == b.category
        for month in [x["month"] for x in monthly_report(want)["months"]]:
            a_month, b_month = monthly_report(want, month), monthly_report(got, month)
            for figure in ("income", "spend", "committed", "flexible", "saved", "net"):
                assert a_month[figure]["paise"] == b_month[figure]["paise"], (user_row["persona_id"], month, figure)
        assert summary.sts_calc(want) == summary.sts_calc(got), user_row["persona_id"]
        found = {(f.type, f.fingerprint) for f in engine.detect_all(got, ds.merchants) if f.type in engine.PLANTED_TYPES}
        assert found == ds.planted(uid), user_row["persona_id"]  # Gate 1's answer key, on the feed-loaded ledger
        seen += 1
    assert (seen, rows) == (6, 7379)
    assert same_category / rows >= 0.94  # the rest are payments to people, which the feed cannot explain


def test_without_the_list_of_recurring_items_nothing_is_tied_to_a_bill(ds: Dataset) -> None:
    """The loader links payments to recurring items it is given; it does not detect them."""
    uid = next(u for u, row in ds.users.items() if row["persona_id"] == "first_job")
    rows = loader.feed_transactions(ds.data, uid, loader.feed_statements(ds.data, "first_job"), ds.merchant_index, given_bills=False)
    assert rows and all(r["recurring_key"] is None for r in rows)
    spotify = [r for r in rows if r["merchant_key"] == "spotify" and r["direction"] == "debit"]
    assert spotify and all(r["category_id"] == "subscriptions" for r in spotify)  # the merchant still says what it is


def test_an_unknown_ledger_source_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ledger_source", "guess")
    with pytest.raises(ValueError, match="LEDGER_SOURCE"):
        loader.ledger_source()


def test_start_up_refuses_the_feed_source_when_the_statements_were_not_shipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    loader.check_ledger_source()  # the repository ships them

    class Elsewhere:
        db_dir = tmp_path / "demo" / "db"

    monkeypatch.setattr(loader, "demo_data", lambda: Elsewhere())
    with pytest.raises(RuntimeError, match="LEDGER_SOURCE=feed"):
        loader.check_ledger_source()
    monkeypatch.setattr(get_settings(), "ledger_source", "processed")
    loader.check_ledger_source()  # the processed ledger needs no statements
