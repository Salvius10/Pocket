"""The 14 mascot tools (ARCHITECTURE.md §8). One description list feeds both the live model and the fake.

Amounts go in as rupees exactly as the user said them; core-api converts to paise. The model
never converts, adds or splits.
"""

from __future__ import annotations

from typing import Any

SECTIONS = ["safe_to_spend", "pockets", "goals", "spend_by_category", "cash_flow", "bills", "net_worth", "investments"]
PERIODS = ["this_month", "last_month", "last_month_to_date", "this_week", "last_week", "last_7_days", "last_30_days", "last_3_months"]
WIDGETS = ["safe_to_spend", "pockets", "goals", "spend_by_category", "cash_flow", "transactions", "bills_emis", "net_worth",
           "investments", "insight_card", "pulse_card", "group_pot"]
WRITE_TOOLS = ("set_goal", "create_pocket", "move_between_pockets", "add_transaction")


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or []}


_STR = {"type": "string"}
_NUM = {"type": "number"}

TOOL_SPECS: list[dict[str, Any]] = [
    {"name": "get_summary", "description": "The user's current numbers. Sections: safe_to_spend (what they can spend today), pockets (budgets), goals, spend_by_category (where money goes), cash_flow, bills (upcoming bills and EMIs), net_worth, investments (their own holdings and how they moved).",
     "parameters": _obj({"sections": {"type": "array", "items": {"type": "string", "enum": SECTIONS}}}, ["sections"])},
    {"name": "get_transactions", "description": "Find transactions. Returns matches plus a count and total computed by code.",
     "parameters": _obj({"category": _STR, "merchant": _STR, "period": {"type": "string", "enum": PERIODS},
                         "direction": {"type": "string", "enum": ["debit", "credit"]}, "min_rupees": _NUM, "max_rupees": _NUM})},
    {"name": "compare_spend", "description": "Compare spending between two periods, optionally for one category. Returns both totals, the difference and the percent.",
     "parameters": _obj({"category": _STR, "period_a": {"type": "string", "enum": PERIODS}, "period_b": {"type": "string", "enum": PERIODS}},
                        ["period_a", "period_b"])},
    {"name": "check_affordability", "description": "Whether an amount fits today and this month, and the new daily figure after it.",
     "parameters": _obj({"amount_rupees": _NUM}, ["amount_rupees"])},
    {"name": "get_insights", "description": "The top patterns found in the user's money (overspending, creeping costs, forgotten subscriptions, duplicate charges, idle cash, card interest).",
     "parameters": _obj({})},
    {"name": "get_pulse", "description": "Today's markets and world news with sources, and what each item means for this user's own loans and holdings.",
     "parameters": _obj({})},
    {"name": "get_groups", "description": "Shared groups (family, trip, flatmates): balances, who owes whom, pot progress.",
     "parameters": _obj({"group_id": _STR})},
    {"name": "save_profile", "description": "Store what the user said during onboarding. Keys: income (how money comes in), income_amount, saving_for, worries, occupation, household.",
     "parameters": _obj({"facts": {"type": "object", "properties": {k: _STR for k in ("income", "income_amount", "saving_for", "worries", "occupation", "household")}}},
                        ["facts"])},
    {"name": "compose_home", "description": "Rebuild the Home screen. Pass the user's request in their own words, e.g. 'put my EMIs first', 'hide investments'.",
     "parameters": _obj({"instruction": _STR})},
    {"name": "show_widget", "description": "Open one widget in a sheet on the phone so the user can see it while you talk.",
     "parameters": _obj({"type": {"type": "string", "enum": WIDGETS}}, ["type"])},
    {"name": "set_goal", "description": "WRITE. Propose creating or changing a savings goal. Shows a confirm card; nothing happens until the user taps it.",
     "parameters": _obj({"name": _STR, "target_rupees": _NUM, "deadline": {"type": "string", "description": "YYYY-MM-DD"}, "monthly_plan_rupees": _NUM},
                        ["name", "target_rupees"])},
    {"name": "create_pocket", "description": "WRITE. Propose a new monthly budget pocket. Shows a confirm card; nothing happens until the user taps it.",
     "parameters": _obj({"name": _STR, "monthly_limit_rupees": _NUM, "categories": {"type": "array", "items": _STR}}, ["name", "monthly_limit_rupees"])},
    {"name": "move_between_pockets", "description": "WRITE. Propose moving money from a pocket to another pocket or to a goal. Shows a confirm card; nothing happens until the user taps it.",
     "parameters": _obj({"from": {"type": "string", "description": "pocket name"}, "to": {"type": "string", "description": "pocket or goal name"},
                         "amount_rupees": _NUM}, ["from", "to", "amount_rupees"])},
    {"name": "add_transaction", "description": "WRITE. Propose adding a manual cash entry. Shows a confirm card; nothing happens until the user taps it.",
     "parameters": _obj({"amount_rupees": _NUM, "description": _STR, "category": _STR, "direction": {"type": "string", "enum": ["debit", "credit"]}},
                        ["amount_rupees"])},
]
TOOL_NAMES = [t["name"] for t in TOOL_SPECS]
