"""LayoutSpec -> A2UI v1.0 messages. Code builds these; the LLM never writes A2UI.

A2UI carries layout only. No money value ever goes in: each widget reads its numbers from the
phone's local cache. Wire props are camelCase; component names are the Pocket catalog's.
"""

from __future__ import annotations

from typing import Any

from pocket_common.layout import LayoutSpec

A2UI_VERSION = "1.0"
CATALOG_ID = "https://pocket.in/a2ui/catalogs/home/v1"
SURFACE_ID = "home"
ROOT_COMPONENT = "PocketHomeColumn"

COMPONENT_NAMES: dict[str, str] = {
    "safe_to_spend": "SafeToSpend",
    "pockets": "Pockets",
    "goals": "Goals",
    "spend_by_category": "SpendByCategory",
    "cash_flow": "CashFlow",
    "transactions": "Transactions",
    "bills_emis": "BillsEmis",
    "net_worth": "NetWorth",
    "investments": "Investments",
    "insight_card": "InsightCard",
    "pulse_card": "PulseCard",
    "group_pot": "GroupPot",
}
WIDGET_TYPES = {v: k for k, v in COMPONENT_NAMES.items()}


def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def snake(camel_name: str) -> str:
    out = []
    for ch in camel_name:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _is_money_key(key: str) -> bool:
    k = key.lower()
    return k.endswith("paise") or "amount" in k or "rupee" in k or "balance" in k


def build_messages(spec: LayoutSpec, surface_id: str = SURFACE_ID) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    child_ids: list[str] = []
    reasons = {r.widget_index: r.text for r in spec.reasons}
    for i, w in enumerate(spec.widgets):
        cid = f"w{i}"
        child_ids.append(cid)
        comp: dict[str, Any] = {"id": cid, "component": COMPONENT_NAMES[w.type], "variant": w.variant}
        for key, value in w.params.items():
            if _is_money_key(key):
                continue  # layout only: never a money value
            comp[camel(key)] = value
        if i in reasons:
            comp["reason"] = reasons[i]
        components.append(comp)
    root = {"id": "root", "component": ROOT_COMPONENT, "children": child_ids, "summary": spec.summary}
    return [
        {"version": A2UI_VERSION, "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": A2UI_VERSION, "updateComponents": {"surfaceId": surface_id, "components": [root, *components]}},
    ]


def messages_to_spec(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Inverse of `build_messages`, used by tests to prove both renderers get the same layout."""
    comps: list[dict[str, Any]] = []
    for msg in messages:
        if "updateComponents" in msg:
            comps = msg["updateComponents"]["components"]
    by_id = {c["id"]: c for c in comps}
    root = by_id["root"]
    widgets, reasons = [], []
    for i, cid in enumerate(root["children"]):
        c = by_id[cid]
        params = {snake(k): v for k, v in c.items() if k not in ("id", "component", "variant", "reason")}
        widgets.append({"type": WIDGET_TYPES[c["component"]], "variant": c.get("variant", "default"), "params": params})
        if "reason" in c:
            reasons.append({"widget_index": i, "text": c["reason"]})
    return {"widgets": widgets, "reasons": reasons, "summary": root.get("summary", "")}
