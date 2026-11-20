"""Writes data/fixtures/a2ui_home.json: the A2UI v1.0 messages the backend emits for one layout.

This file is the contract between the two sides. The Python test checks the builder still
produces exactly this; the Dart test feeds it to the pinned `a2ui_core` MessageProcessor and to
the app's Home renderer. If the agent side and the renderer side ever drift, one of them fails.

Run: uv run python scripts/gen_a2ui_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pocket_common.a2ui import A2UI_VERSION, CATALOG_ID, COMPONENT_NAMES, ROOT_COMPONENT, build_messages
from pocket_common.layout import CATALOG, LayoutContext, LayoutSpec, enforce_layout

ROOT = Path(__file__).resolve().parents[1]

# One widget of every catalog type, with every param the composer may set.
CONTRACT_SPEC = {
    "widgets": [
        {"type": "safe_to_spend", "variant": "hero", "params": {}},
        {"type": "bills_emis", "variant": "compact", "params": {"window_days": 14}},
        {"type": "pockets", "variant": "default", "params": {"max_items": 4, "sort": "risk"}},
        {"type": "insight_card", "variant": "default", "params": {}},
        {"type": "goals", "variant": "default", "params": {"max_items": 2}},
        {"type": "spend_by_category", "variant": "default", "params": {"period": "this_month", "chart": "donut", "top_n": 5}},
        {"type": "group_pot", "variant": "default", "params": {"group_id": "00000000-0000-4000-8000-000000000001"}},
        {"type": "investments", "variant": "default", "params": {"max_items": 3}},
    ],
    "reasons": [
        {"widget_index": 0, "text": "Safe-to-spend always comes first."},
        {"widget_index": 1, "text": "You have EMIs due soon."},
    ],
    "summary": "I put your EMIs right under Safe-to-spend.",
}


GROUP_ID = "00000000-0000-4000-8000-000000000001"


def ideal_layouts() -> list[dict[str, object]]:
    """The six default persona layouts (data/content/ideal_layouts.json) as core-api stores them:
    fitted to a user who has data for every widget, which drops the params no widget understands
    and gives the group widget a group id. Then the messages built for each."""
    fits_all = LayoutContext(available=set(CATALOG), group_ids={GROUP_ID}, goal_ids=set(), default_group_id=GROUP_ID)
    out: list[dict[str, object]] = []
    for row in json.loads((ROOT / "data" / "content" / "ideal_layouts.json").read_text(encoding="utf-8")):
        spec = enforce_layout(LayoutSpec.model_validate(row["spec"]), fits_all)
        out.append({"persona_id": row["persona_id"], "spec": spec.model_dump(), "messages": build_messages(spec)})
    return out


def contract() -> dict[str, object]:
    spec = LayoutSpec.model_validate(CONTRACT_SPEC)
    return {
        "protocol_version": A2UI_VERSION,
        "catalog_id": CATALOG_ID,
        "root_component": ROOT_COMPONENT,
        "component_names": COMPONENT_NAMES,
        "spec": spec.model_dump(),
        "messages": build_messages(spec),
        "ideal_layouts": ideal_layouts(),
    }


def main() -> None:
    out = ROOT / "data" / "fixtures" / "a2ui_home.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(contract(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
