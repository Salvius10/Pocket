from pocket_common import guard
from pocket_common.a2ui import build_messages, messages_to_spec
from pocket_common.layout import LayoutContext, LayoutSpec, enforce_layout, validate_layout


def spec(*types: str, **kw: object) -> LayoutSpec:
    return LayoutSpec.model_validate({"widgets": [{"type": t} for t in types], **kw})


CTX = LayoutContext(group_ids={"g1"}, default_group_id="g1")


# ---------- layout ----------
def test_valid_layout_passes() -> None:
    assert validate_layout(spec("safe_to_spend", "pockets", "goals", "insight_card"), CTX) == []


def test_unknown_widget_is_rejected() -> None:
    errors = validate_layout(spec("safe_to_spend", "pockets", "goals", "crypto_ticker"), CTX)
    assert any("unknown widget type" in e for e in errors)


def test_safe_to_spend_must_be_first() -> None:
    assert any("first" in e for e in validate_layout(spec("pockets", "safe_to_spend", "goals", "insight_card"), CTX))


def test_widget_count_bounds() -> None:
    assert any("count" in e for e in validate_layout(spec("safe_to_spend", "pockets"), CTX))
    too_many = spec("safe_to_spend", "pockets", "goals", "insight_card", "cash_flow", "transactions", "bills_emis", "net_worth", "investments")
    assert any("count" in e for e in validate_layout(too_many, CTX))


def test_widget_needs_its_data() -> None:
    ctx = LayoutContext(available={"safe_to_spend", "pockets", "goals", "transactions"})
    assert any("no data" in e for e in validate_layout(spec("safe_to_spend", "pockets", "goals", "investments"), ctx))


def test_reasons_and_summary_have_no_digits() -> None:
    with_digit = spec("safe_to_spend", "pockets", "goals", "insight_card", reasons=[{"widget_index": 1, "text": "You overspent by 500."}])
    assert any("digits" in e for e in validate_layout(with_digit, CTX))
    tamil_digit = spec("safe_to_spend", "pockets", "goals", "insight_card", summary="௫ நாட்கள்")
    assert any("digits" in e for e in validate_layout(tamil_digit, CTX))


def test_unknown_group_id_is_rejected() -> None:
    bad = LayoutSpec.model_validate({"widgets": [{"type": "safe_to_spend"}, {"type": "pockets"}, {"type": "goals"}, {"type": "group_pot", "params": {"group_id": "nope"}}]})
    assert any("unknown group_id" in e for e in validate_layout(bad, CTX))


def test_enforce_pins_safe_to_spend_and_drops_unknowns() -> None:
    fixed = enforce_layout(spec("goals", "made_up", "pockets", "safe_to_spend", "goals"), CTX)
    assert [w.type for w in fixed.widgets][:3] == ["safe_to_spend", "goals", "pockets"]
    assert validate_layout(fixed, CTX) == []


def test_enforce_cannot_remove_safe_to_spend() -> None:
    fixed = enforce_layout(spec("pockets", "goals", "transactions"), CTX)
    assert fixed.widgets[0].type == "safe_to_spend"


# ---------- A2UI ----------
def test_a2ui_round_trip_and_carries_no_money() -> None:
    s = LayoutSpec.model_validate({
        "widgets": [{"type": "safe_to_spend", "variant": "hero", "params": {}},
                    {"type": "bills_emis", "variant": "compact", "params": {"window_days": 14, "amount_paise": 999}},
                    {"type": "pockets", "variant": "default", "params": {"max_items": 4}},
                    {"type": "group_pot", "variant": "default", "params": {"group_id": "g1"}}],
        "reasons": [{"widget_index": 1, "text": "You have EMIs due soon."}],
        "summary": "I put your EMIs right under Safe-to-spend.",
    })
    messages = build_messages(s)
    assert messages[0]["version"] == "1.0" and "createSurface" in messages[0]
    components = messages[1]["updateComponents"]["components"]
    assert components[0]["component"] == "PocketHomeColumn"
    bills = next(c for c in components if c["component"] == "BillsEmis")
    assert bills["windowDays"] == 14  # camelCase on the wire
    assert "amountPaise" not in bills  # layout only: money values never travel in A2UI
    back = messages_to_spec(messages)
    assert [w["type"] for w in back["widgets"]] == ["safe_to_spend", "bills_emis", "pockets", "group_pot"]
    assert back["widgets"][1]["params"] == {"window_days": 14}
    assert back["reasons"] == [{"widget_index": 1, "text": "You have EMIs due soon."}]


# ---------- guard: numbers ----------
def test_extract_numbers_indian_formats() -> None:
    assert guard.extract_numbers("Food delivery is ₹8,400 this month") == [8400.0]
    assert guard.extract_numbers("about ₹1.2 lakh and ₹1.05 crore") == [120000.0, 10500000.0]
    assert guard.extract_numbers("eight thousand four hundred rupees") == [8400.0]
    assert guard.extract_numbers("₹1.2 लाख") == [120000.0]
    assert guard.extract_numbers("३४९ रुपये") == [349.0]  # Devanagari digits


def test_allowed_numbers_from_tool_result() -> None:
    result = {"daily": {"paise": 141000, "display": "₹1,410", "exact": "₹1,410.00", "spoken": "₹1,400"}, "days_left": 11, "pct": 38}
    allowed = guard.numbers_in(result)
    assert guard.unknown_numbers("You can spend ₹1,400 a day for the next 11 days.", allowed) == []
    assert guard.unknown_numbers("You can spend ₹1,410 a day.", allowed) == []
    assert guard.unknown_numbers("You can spend ₹2,000 a day.", allowed) == [2000.0]


def test_small_integers_and_years_are_fine() -> None:
    assert guard.unknown_numbers("It is due on the 5th, in 3 days, in 2027.", set()) == []


def test_a_year_shaped_amount_is_still_checked() -> None:
    assert guard.unknown_numbers("You can spend ₹2,000 a day.", set()) == [2000.0]
    assert guard.unknown_numbers("That is 2000 rupees.", set()) == [2000.0]


# ---------- guard: advice ----------
def test_allowed_sentences_pass() -> None:
    for s in [
        "Food delivery is ₹8,400 this month, twice your plan.",
        "Move ₹3,000 from Eating out to your Bike goal?",
        "Nifty 50 index funds fell 3% this week; your funds are down ₹2,100.",
        "I can't tell you what to buy or sell.",
        "Your mutual funds moved up by ₹651 this week.",
        "எதை வாங்க வேண்டும், விற்க வேண்டும் என்று என்னால் சொல்ல முடியாது.",
    ]:
        assert guard.check_advice(s).ok, s


def test_banned_sentences_are_caught() -> None:
    cases = {
        "You should buy this fund.": "personal_security_pick",
        "I recommend you switch your SIP to this one.": "personal_security_pick",
        "Markets will rise, invest now.": "market_prediction_call_to_action",
        "This fund gives guaranteed returns.": "guaranteed_returns",
        "आपको यह फंड खरीदना चाहिए।": "personal_security_pick",
    }
    for sentence, banned in cases.items():
        result = guard.check_advice(sentence)
        assert not result.ok, sentence
        assert result.banned == banned, sentence


def test_written_text_rejects_digits() -> None:
    assert guard.check_written("You have EMIs due soon.").ok
    assert not guard.check_written("You spent 500 more.").ok


def test_split_sentences_keeps_the_tail() -> None:
    done, tail = guard.split_sentences("You can spend ₹650. Food is ₹8,4")
    assert done == ["You can spend ₹650."]
    assert tail == "Food is ₹8,4"
