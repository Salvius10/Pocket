"""The rule-based composer: what Home becomes when there is no model to ask."""

from typing import Any

import pytest
from agent.composer.service import rule_compose
from pocket_common.layout import CATALOG, LayoutContext, has_digit, validate_layout

CURRENT = ["safe_to_spend", "net_worth", "investments", "pulse_card", "cash_flow", "goals", "insight_card"]


def request(instruction: str | None, lang: str = "en", available: tuple[str, ...] = CATALOG, group_ids: tuple[str, ...] = ("g1",)) -> dict[str, Any]:
    spec = {"widgets": [{"type": t, "variant": "hero" if t == "safe_to_spend" else "default", "params": {}} for t in CURRENT],
            "reasons": [], "summary": ""}
    return {
        "features": {"language": lang}, "instruction": instruction, "current": spec, "default": spec,
        "context": {"available": sorted(available), "group_ids": list(group_ids), "goal_ids": [],
                    "default_group_id": group_ids[0] if group_ids else None},
    }


def types(body: dict[str, Any]) -> list[str]:
    spec = rule_compose(body)
    context = LayoutContext(available=set(body["context"]["available"]), group_ids=set(body["context"]["group_ids"]),
                            goal_ids=set(), default_group_id=body["context"]["default_group_id"])
    assert validate_layout(spec, context) == []
    assert not any(has_digit(r.text) for r in spec.reasons) and not has_digit(spec.summary)
    return [w.type for w in spec.widgets]


def test_no_instruction_keeps_the_default() -> None:
    assert types(request(None)) == CURRENT


def test_put_something_first_goes_right_under_safe_to_spend() -> None:
    assert types(request("Put the news first"))[:2] == ["safe_to_spend", "pulse_card"]
    assert types(request("EMI पहले दिखाओ", "hi"))[:2] == ["safe_to_spend", "bills_emis"]


def test_hide_removes_it() -> None:
    assert "investments" not in types(request("Remove investments from home"))


def test_a_compound_request_does_both_parts() -> None:
    got = types(request("Put my bills first and hide the news"))
    assert got[1] == "bills_emis" and "pulse_card" not in got


def test_only_keeps_what_was_named_in_the_order_it_was_said() -> None:
    got = types(request("I only want net worth and goals"))
    assert got[:3] == ["safe_to_spend", "net_worth", "goals"]
    assert len(got) == 4  # filled up to the smallest Home allowed, never more


def test_only_with_first_is_an_ordinary_move() -> None:
    got = types(request("only put my goals first"))
    assert got[1] == "goals" and len(got) == len(CURRENT)


@pytest.mark.parametrize(("instruction", "lang"), [
    ("Too many cards, simplify", "en"), ("ரொம்ப சிம்பிளா வை", "ta"), ("सिर्फ़ ज़रूरी चीज़ें", "hi"),
])
def test_simplify_cuts_home_to_the_minimum(instruction: str, lang: str) -> None:
    assert types(request(instruction, lang)) == CURRENT[:4]


def test_net_worth_is_understood_in_hindi() -> None:
    body = request("नेट वर्थ भी चाहिए", "hi")
    body["current"]["widgets"] = [w for w in body["current"]["widgets"] if w["type"] != "net_worth"]
    assert types(body)[1] == "net_worth"


def test_safe_to_spend_cannot_be_hidden_or_moved() -> None:
    assert types(request("hide safe to spend and remove everything"))[0] == "safe_to_spend"
    assert types(request("Put my goals first"))[0] == "safe_to_spend"


def test_a_widget_the_user_has_no_data_for_is_not_added() -> None:
    available = tuple(t for t in CATALOG if t != "group_pot")
    assert "group_pot" not in types(request("Add the college gang trip", available=available, group_ids=()))


def test_words_it_does_not_understand_change_nothing() -> None:
    assert types(request("make it more purple")) == CURRENT
