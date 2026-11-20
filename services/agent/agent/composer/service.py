"""UI composer: what a person needs -> a LayoutSpec. Anything outside the catalog is rejected.

The model sees features and names, never amounts. Its output goes through the code validator;
one repair retry; then the deterministic default. GEMINI_MODE=fake uses fixed rules instead.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pocket_common.layout import (
    CATALOG,
    MAX_WIDGETS,
    MIN_WIDGETS,
    LayoutContext,
    LayoutSpec,
    Reason,
    WidgetSpec,
    clean_params,
    enforce_layout,
    validate_layout,
)

from agent.config import get_settings

log = logging.getLogger("agent.composer")

LAYOUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "widgets": {"type": "array", "minItems": MIN_WIDGETS, "maxItems": MAX_WIDGETS, "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": list(CATALOG)},
                "variant": {"type": "string", "enum": ["default", "hero", "compact"]},
                "params": {"type": "object", "properties": {
                    "max_items": {"type": "integer"}, "sort": {"type": "string", "enum": ["risk", "name"]},
                    "period": {"type": "string", "enum": ["this_month", "last_month"]}, "chart": {"type": "string", "enum": ["donut", "bars"]},
                    "top_n": {"type": "integer"}, "window_days": {"type": "integer"}, "group_id": {"type": "string"}, "span": {"type": "string", "enum": ["months", "weeks"]},
                }},
            },
            "required": ["type", "variant", "params"],
        }},
        "reasons": {"type": "array", "items": {"type": "object", "properties": {"widget_index": {"type": "integer"}, "text": {"type": "string"}},
                                               "required": ["widget_index", "text"]}},
        "summary": {"type": "string"},
    },
    "required": ["widgets", "reasons", "summary"],
}

SYSTEM = """You design the Home screen of Pocket, a personal finance app in India. Reply with JSON only.

Rules you must follow:
- Use only these widget types: {catalog}.
- The first widget is always safe_to_spend with variant "hero". Never remove or move it.
- Between {min_w} and {max_w} widgets in total. No duplicates.
- Only use widgets from this user's available list. For group_pot, params.group_id must be one of the given group ids.
- "Put X first" means X goes at index 1, right after safe_to_spend.
- If the user asks to hide or remove something, leave it out.
- Give one short reason per widget (widget_index, text) and a one-sentence summary, written in {language}, spoken to the user as "you".
- Reasons and summary must contain NO digits and no amounts. Never mention buying, selling or investing in anything.
- Order by what matters to this person: their worries, goals, EMIs, insights. Different people get different Homes."""

WIDGET_WORDS: dict[str, str] = {
    "bills_emis": r"emi|bill|loan|due|rent|ईएमआई|बिल|कर्ज़|किराया|இஎம்ஐ|பில்|கடன்|வாடகை",
    "goals": r"goal|saving|laptop|bike|trip fund|education|लक्ष्य|बचत|இலக்கு|சேமிப்பு",
    "investments": r"invest|fund|sip|portfolio|निवेश|फंड|முதலீடு|ஃபண்ட்",
    "net_worth": r"net worth|worth|wealth|संपत्ति|नेट ?वर्थ|சொத்து|நெட் ?வொர்த்",
    "cash_flow": r"cash ?flow|income|earning|आय|कमाई|வருமானம்",
    "spend_by_category": r"categor|where.{0,12}money|money goes|breakdown|spending|कहाँ जा|खर्च|எங்கே போ|செலவு",
    "pockets": r"pocket|budget|पॉकेट|बजट|பாக்கெட்|பட்ஜெட்",
    "transactions": r"transaction|recent|history|लेन-देन|பரிவர்த்தனை",
    "group_pot": r"group|trip|pot|flat|family budget|ग्रुप|ट्रिप|குழு|ட்ரிப்|pondy",
    "pulse_card": r"pulse|news|market|बाज़ार|खबर|சந்தை|செய்தி",
    "insight_card": r"insight|notice|tip|सुझाव|கவனி",
}
FIRST = re.compile(r"first|top|above|start|upar|mudhal|पहले|ऊपर|सबसे|முதலில்|மேலே", re.IGNORECASE)
HIDE = re.compile(r"hide|remove|take (?:it )?(?:off|out|away)|don't show|no more|get rid|eduthudu|vendam|हटा|मत दिखा|நீக்கு|மறை|வேண்டாம்", re.IGNORECASE)
RESET = re.compile(r"reset|start over|default|rebuild|फिर से|மீண்டும்", re.IGNORECASE)
# "keep it simple", "too many cards", "only the essentials": cut Home down to the minimum
SIMPLE = re.compile(r"simpl|too many|clutter|minimal|essential|fewer|सिंपल|सरल|ज़रूरी|जरूरी|कम कर|சிம்பிள|எளிமை|குறை", re.IGNORECASE)
# "I only want net worth and goals": keep just the things named
ONLY = re.compile(r"\bonly\b|सिर्फ़|सिर्फ|केवल|மட்டும்", re.IGNORECASE)

FAKE_TEXT = {
    "first": {"en": "You asked for this near the top.", "hi": "आपने इसे ऊपर रखने को कहा था।", "ta": "இதை மேலே வைக்கச் சொன்னீர்கள்."},
    "added": {"en": "You asked to see this.", "hi": "आपने इसे देखना चाहा था।", "ta": "இதைப் பார்க்க விரும்பினீர்கள்."},
    "pinned": {"en": "Safe-to-spend always comes first.", "hi": "आज कितना खर्च कर सकते हैं, यह हमेशा सबसे ऊपर रहता है।", "ta": "இன்று எவ்வளவு செலவழிக்கலாம் என்பது எப்போதும் முதலில்."},
    "summary_first": {"en": "I moved that right under Safe-to-spend.", "hi": "मैंने उसे सेफ़-टू-स्पेंड के ठीक नीचे रख दिया।", "ta": "அதை செலவு வரம்புக்கு அடுத்ததாக வைத்தேன்."},
    "summary_hide": {"en": "I took that off your Home.", "hi": "मैंने उसे आपके होम से हटा दिया।", "ta": "அதை உங்கள் முகப்பிலிருந்து நீக்கினேன்."},
    "summary_add": {"en": "I added that to your Home.", "hi": "मैंने उसे आपके होम में जोड़ दिया।", "ta": "அதை உங்கள் முகப்பில் சேர்த்தேன்."},
    "kept": {"en": "You asked to keep this.", "hi": "आपने इसे रखने को कहा था।", "ta": "இதை வைத்திருக்கச் சொன்னீர்கள்."},
    "summary_simple": {"en": "I kept only the essentials on your Home.", "hi": "मैंने आपके होम पर सिर्फ़ ज़रूरी चीज़ें रखीं।", "ta": "உங்கள் முகப்பில் முக்கியமானவற்றை மட்டும் வைத்தேன்."},
    "summary_only": {"en": "Your Home now shows just what you asked for.", "hi": "अब आपके होम पर वही है जो आपने माँगा।", "ta": "நீங்கள் கேட்டவை மட்டும் இப்போது உங்கள் முகப்பில் உள்ளன."},
    "summary_default": {"en": "I rebuilt your Home around what matters most to you.", "hi": "मैंने आपका होम आपकी ज़रूरत के हिसाब से फिर बनाया।", "ta": "உங்களுக்கு முக்கியமானவற்றைச் சுற்றி முகப்பை மீண்டும் அமைத்தேன்."},
}


def _ctx(context: dict[str, Any]) -> LayoutContext:
    return LayoutContext(available=set(context.get("available") or CATALOG), group_ids=set(context.get("group_ids") or []),
                         goal_ids=set(context.get("goal_ids") or []), default_group_id=context.get("default_group_id"))


CLAUSE_SPLIT = re.compile(r"\s*(?:,|;|\band then\b|\bthen\b|\band\b|\bbut\b|\balso\b|और|फिर|மற்றும்|பிறகு)\s*", re.IGNORECASE)


def rule_compose(body: dict[str, Any]) -> LayoutSpec:
    """Deterministic rules: move to first, hide, add, or reset. Used in fake mode, and in live mode
    when the model is unavailable (a code fallback: no other model is ever substituted).

    A request is read clause by clause, so "put my bills first and hide the group" does both."""
    lang = (body.get("features") or {}).get("language") or "en"
    lctx = _ctx(body.get("context") or {})
    default = LayoutSpec.model_validate(body["default"])
    instruction = (body.get("instruction") or "").strip()
    if not instruction or RESET.search(instruction):
        return default if default.summary else LayoutSpec(widgets=default.widgets, reasons=default.reasons, summary=FAKE_TEXT["summary_default"][lang])
    base = LayoutSpec.model_validate(body.get("current") or body["default"])
    widgets = [WidgetSpec(type=w.type, variant=w.variant, params=dict(w.params)) for w in base.widgets if w.type != "safe_to_spend"]
    reasons: dict[str, str] = {}
    actions: list[str] = []

    def finish(kept: list[WidgetSpec], why: dict[str, str], summary_key: str) -> LayoutSpec:
        spec = enforce_layout(LayoutSpec(widgets=[WidgetSpec(type="safe_to_spend", variant="hero"), *kept], summary=""), lctx)
        out = [Reason(widget_index=0, text=FAKE_TEXT["pinned"][lang])]
        out += [Reason(widget_index=i, text=why[w.type]) for i, w in enumerate(spec.widgets) if w.type in why]
        return LayoutSpec(widgets=spec.widgets, reasons=out, summary=FAKE_TEXT[summary_key][lang])

    named = {w: m.start() for w, pat in WIDGET_WORDS.items()
             if w in lctx.available and (m := re.search(pat, instruction, re.IGNORECASE)) is not None}
    if named and ONLY.search(instruction) and not FIRST.search(instruction) and not HIDE.search(instruction):
        # the things named, in the order they were said, filled up to the smallest Home allowed
        kept = [next((w for w in widgets if w.type == t), WidgetSpec(type=t)) for t in sorted(named, key=lambda t: named[t])]
        fill = sorted((w for w in widgets if w.type not in named), key=lambda w: w.type != "insight_card")
        kept += fill[: max(0, MIN_WIDGETS - 1 - len(kept))]
        return finish(kept, dict.fromkeys(named, FAKE_TEXT["kept"][lang]), "summary_only")
    if not named and SIMPLE.search(instruction):
        return finish(widgets[: MIN_WIDGETS - 1], {}, "summary_simple")

    for clause in [c for c in CLAUSE_SPLIT.split(instruction) if c and c.strip()]:
        targets = [w for w, pat in WIDGET_WORDS.items() if re.search(pat, clause, re.IGNORECASE) and w in lctx.available]
        if not targets:
            continue
        hide = bool(HIDE.search(clause))
        first = bool(FIRST.search(clause)) and not hide
        for t in targets:
            existing = next((w for w in widgets if w.type == t), None)
            widgets = [w for w in widgets if w.type != t]
            if hide:
                reasons.pop(t, None)
                continue
            # asked for by name: it goes right under Safe-to-spend, whether or not they said "first"
            widgets.insert(0, existing or WidgetSpec(type=t))
            reasons[t] = FAKE_TEXT["first" if first or existing is not None else "added"][lang]
        actions.append("hide" if hide else "first" if first else "add")
    if not actions:
        return default
    kind = "first" if "first" in actions else "add" if "add" in actions else "hide"
    return finish(widgets, reasons, f"summary_{kind}")


def _prompt(body: dict[str, Any]) -> str:
    import json

    f = body.get("features") or {}
    c = body.get("context") or {}
    return (
        f"User features: {json.dumps(f, ensure_ascii=False)}\n"
        f"Widgets this user has data for: {json.dumps(c.get('available'))}\n"
        f"Group ids: {json.dumps(c.get('group_ids'))}\n"
        f"Current Home: {json.dumps([w['type'] for w in (body.get('current') or {}).get('widgets', [])])}\n"
        f"User request: {body.get('instruction') or 'Build the best Home for this person.'}"
    )


async def compose(body: dict[str, Any]) -> dict[str, Any]:
    lctx = _ctx(body.get("context") or {})
    default = LayoutSpec.model_validate(body["default"])
    def by_rules(outcome: str, why: list[str]) -> dict[str, Any]:
        spec = rule_compose(body)
        ok = not validate_layout(spec, lctx)
        return {"spec": (spec if ok else default).model_dump(), "outcome": outcome if ok else "default", "errors": why}

    if not get_settings().is_live:
        return by_rules("fake", [])

    from agent.llm.gemini import GeminiError, gemini

    lang_name = {"en": "English", "hi": "Hindi", "ta": "Tamil"}.get((body.get("features") or {}).get("language", "en"), "English")
    system = SYSTEM.format(catalog=", ".join(CATALOG), min_w=MIN_WIDGETS, max_w=MAX_WIDGETS, language=lang_name)
    prompt = _prompt(body)
    errors: list[str] = []
    for attempt in (1, 2):  # one repair retry, then the fixed default
        ask = prompt if attempt == 1 else f"{prompt}\n\nYour last layout broke these rules: {errors}. Return a corrected layout."
        try:
            raw = await gemini().generate_json(ask, LAYOUT_SCHEMA, system)
        except GeminiError as exc:  # MODEL_FLASH and any configured fallback model are both unavailable
            log.warning("composer has no model to ask (%s): using the rule-based composer", exc)
            return by_rules("rules", ["model unavailable"])
        try:
            spec = clean_params(LayoutSpec.model_validate(raw), lctx)
        except ValueError as exc:
            errors = [f"not a LayoutSpec: {exc}"[:200]]
            continue
        errors = validate_layout(spec, lctx)
        if not errors:
            # composer = MODEL_FLASH answered; composer_fb = the configured fallback model did
            outcome = ("composer_fb" if gemini().used_fallback else "composer") if attempt == 1 else "repaired"
            return {"spec": spec.model_dump(), "outcome": outcome, "errors": []}
    return {"spec": default.model_dump(), "outcome": "default", "errors": errors}
