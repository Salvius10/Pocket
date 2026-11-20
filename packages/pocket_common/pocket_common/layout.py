"""LayoutSpec: what the composer returns and the Home renderer draws.

The validator is code, not a prompt. A layout that fails it never reaches a phone.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CATALOG: tuple[str, ...] = (
    "safe_to_spend",
    "pockets",
    "goals",
    "spend_by_category",
    "cash_flow",
    "transactions",
    "bills_emis",
    "net_worth",
    "investments",
    "insight_card",
    "pulse_card",
    "group_pot",
)
MIN_WIDGETS = 4
MAX_WIDGETS = 8

# Params each widget understands. Anything else is dropped by `clean_params`.
PARAM_KEYS: dict[str, tuple[str, ...]] = {
    "safe_to_spend": (),
    "pockets": ("max_items", "sort"),
    "goals": ("max_items", "goal_id"),
    "spend_by_category": ("period", "chart", "top_n"),
    "cash_flow": ("period", "span"),
    "transactions": ("max_items", "category_id"),
    "bills_emis": ("window_days",),
    "net_worth": (),
    "investments": ("max_items",),
    "insight_card": ("insight_type",),
    "pulse_card": ("max_items",),
    "group_pot": ("group_id",),
}
VARIANTS = ("default", "hero", "compact")


class WidgetSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    variant: str = "default"
    params: dict[str, Any] = Field(default_factory=dict)


class Reason(BaseModel):
    model_config = ConfigDict(extra="ignore")
    widget_index: int
    text: str


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    widgets: list[WidgetSpec]
    reasons: list[Reason] = Field(default_factory=list)
    summary: str = ""


@dataclass
class LayoutContext:
    """What the user actually has, so a widget appears only if its data exists."""

    available: set[str] = field(default_factory=lambda: set(CATALOG))
    group_ids: set[str] = field(default_factory=set)
    goal_ids: set[str] = field(default_factory=set)
    default_group_id: str | None = None


def has_digit(text: str) -> bool:
    """True for any Unicode decimal digit (Western, Devanagari, Tamil...)."""
    return any(unicodedata.category(ch) == "Nd" for ch in text)


def validate_layout(spec: LayoutSpec, ctx: LayoutContext) -> list[str]:
    """Return every rule the layout breaks (empty list = valid). Rules: ARCHITECTURE.md §7.3."""
    errors: list[str] = []
    types = [w.type for w in spec.widgets]
    for t in types:
        if t not in CATALOG:
            errors.append(f"unknown widget type: {t}")
    if not types or types[0] != "safe_to_spend":
        errors.append("safe_to_spend must be first")
    if types.count("safe_to_spend") > 1:
        errors.append("safe_to_spend appears more than once")
    if not MIN_WIDGETS <= len(types) <= MAX_WIDGETS:
        errors.append(f"widget count {len(types)} outside {MIN_WIDGETS}-{MAX_WIDGETS}")
    seen: set[tuple[str, str]] = set()
    for w in spec.widgets:
        if w.type in CATALOG and w.type not in ctx.available:
            errors.append(f"no data for widget: {w.type}")
        if w.variant not in VARIANTS:
            errors.append(f"unknown variant: {w.variant}")
        gid = w.params.get("group_id")
        if w.type == "group_pot" and gid is not None and gid not in ctx.group_ids:
            errors.append(f"unknown group_id: {gid}")
        goal_id = w.params.get("goal_id")
        if w.type == "goals" and goal_id is not None and goal_id not in ctx.goal_ids:
            errors.append(f"unknown goal_id: {goal_id}")
        key = (w.type, str(gid or ""))
        if key in seen:
            errors.append(f"duplicate widget: {w.type}")
        seen.add(key)
    for r in spec.reasons:
        if not 0 <= r.widget_index < len(spec.widgets):
            errors.append(f"reason points at missing widget index {r.widget_index}")
        if has_digit(r.text):
            errors.append("reason text contains digits")
    if has_digit(spec.summary):
        errors.append("summary contains digits")
    return errors


def clean_params(spec: LayoutSpec, ctx: LayoutContext) -> LayoutSpec:
    """Drop params a widget doesn't understand and fill the group id a group_pot needs."""
    widgets: list[WidgetSpec] = []
    for w in spec.widgets:
        allowed = PARAM_KEYS.get(w.type, ())
        params = {k: v for k, v in w.params.items() if k in allowed and v is not None}
        if w.type == "group_pot" and "group_id" not in params and ctx.default_group_id:
            params["group_id"] = ctx.default_group_id
        widgets.append(WidgetSpec(type=w.type, variant=w.variant if w.variant in VARIANTS else "default", params=params))
    return LayoutSpec(widgets=widgets, reasons=spec.reasons, summary=spec.summary)


def enforce_layout(spec: LayoutSpec, ctx: LayoutContext) -> LayoutSpec:
    """Deterministic last line of defence used for manual edits and defaults.

    Never invents content: it only removes what is not allowed, pins safe_to_spend first,
    trims to the maximum and pads from a fixed order of widgets the user has data for.
    """
    spec = clean_params(spec, ctx)
    kept: list[WidgetSpec] = []
    index_map: dict[int, int] = {}
    seen: set[tuple[str, str]] = set()
    for i, w in enumerate(spec.widgets):
        key = (w.type, str(w.params.get("group_id") or ""))
        if w.type not in CATALOG or w.type not in ctx.available or key in seen or w.type == "safe_to_spend":
            continue
        gid = w.params.get("group_id")
        if w.type == "group_pot" and (gid is None or gid not in ctx.group_ids):
            continue
        seen.add(key)
        index_map[i] = len(kept) + 1
        kept.append(w)
    kept = kept[: MAX_WIDGETS - 1]
    pad_order = ("pockets", "insight_card", "goals", "spend_by_category", "transactions", "cash_flow", "bills_emis")
    for t in pad_order:
        if len(kept) + 1 >= MIN_WIDGETS:
            break
        if t in ctx.available and all(k.type != t for k in kept):
            kept.append(WidgetSpec(type=t))
    hero_src = next((w for w in spec.widgets if w.type == "safe_to_spend"), None)
    hero = WidgetSpec(type="safe_to_spend", variant="hero", params={})
    first_old = spec.widgets.index(hero_src) if hero_src is not None else -1
    reasons: list[Reason] = []
    for r in spec.reasons:
        if has_digit(r.text):
            continue
        if r.widget_index == first_old:
            reasons.append(Reason(widget_index=0, text=r.text))
        elif r.widget_index in index_map and index_map[r.widget_index] <= len(kept):
            reasons.append(Reason(widget_index=index_map[r.widget_index], text=r.text))
    summary = "" if has_digit(spec.summary) else spec.summary
    return LayoutSpec(widgets=[hero, *kept], reasons=reasons, summary=summary)
