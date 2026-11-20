"""Pulse build: grounded news -> structured items in en/hi/ta -> guardrail -> core-api.

Personal "what it means for you" lines are NOT written here: core-api computes them from the
ledger. In fake mode the items are clearly labelled placeholders, never invented news.
"""

from __future__ import annotations

from typing import Any

from pocket_common import guard

from agent.config import get_settings
from agent.core_client import core

TAGS = ["mutual_funds", "rates", "fuel", "groceries", "gold", "fd", "general"]

ITEMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"items": {"type": "array", "maxItems": 8, "items": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "enum": ["markets", "rates", "prices", "world", "policy"]},
            "title": {"type": "object", "properties": {k: {"type": "string"} for k in ("en", "hi", "ta")}, "required": ["en", "hi", "ta"]},
            "summary": {"type": "object", "properties": {k: {"type": "string"} for k in ("en", "hi", "ta")}, "required": ["en", "hi", "ta"]},
            "source_name": {"type": "string"}, "source_url": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
        },
        "required": ["topic", "title", "summary", "source_name", "source_url", "tags"],
    }}},
    "required": ["items"],
}

SEARCH_PROMPT = """Today's news that affects household money in India. Cover, where there is real news today or this week:
Indian stock indices (Nifty 50, Sensex) and how they moved this week; RBI repo rate and home-loan or fixed-deposit rates;
petrol, diesel and LPG prices; food and vegetable prices or inflation; gold price; one major world event that affects Indian markets or prices.
State facts with dates and figures. Do not give any advice or predictions."""

STRUCTURE_PROMPT = """Turn the news notes below into at most 8 items for a personal finance app in India.

Rules:
- Facts only. No advice, no predictions, no "should", no call to buy, sell, invest or wait.
- Each item needs a title (under 9 words) and a summary (one or two plain sentences) in English, Hindi and Tamil.
- source_url must be copied exactly from the Sources list. If an item has no matching source, leave it out.
- tags say whose money it touches: mutual_funds (stock indices, markets), rates (repo, loans), fd (deposit rates), fuel, groceries, gold, general.

News notes:
{notes}

Sources:
{sources}"""

PLACEHOLDER_ITEMS: list[dict[str, Any]] = [
    {"topic": "markets", "tags": ["mutual_funds"], "source_name": "AMFI", "source_url": "https://www.amfiindia.com/net-asset-value/nav-download",
     "title": {"en": "Demo item: index funds this week", "hi": "डेमो आइटम: इस हफ्ते इंडेक्स फंड", "ta": "டெமோ உருப்படி: இந்த வாரம் இன்டெக்ஸ் ஃபண்டுகள்"},
     "summary": {"en": "Placeholder until the Gemini key is set. Live items come from Google Search with their sources.",
                 "hi": "जेमिनी की लगने तक यह प्लेसहोल्डर है। असली आइटम गूगल सर्च से स्रोत के साथ आते हैं।",
                 "ta": "ஜெமினி கீ அமைக்கும் வரை இது மாதிரி உருப்படி. உண்மையான உருப்படிகள் கூகுள் தேடலிலிருந்து ஆதாரத்துடன் வரும்."}},
    {"topic": "rates", "tags": ["rates"], "source_name": "Reserve Bank of India", "source_url": "https://www.rbi.org.in/",
     "title": {"en": "Demo item: interest rates", "hi": "डेमो आइटम: ब्याज दरें", "ta": "டெமோ உருப்படி: வட்டி விகிதங்கள்"},
     "summary": {"en": "Placeholder. The line below it is real: code works it out from your own loans.",
                 "hi": "प्लेसहोल्डर। इसके नीचे की पंक्ति असली है: कोड इसे आपके कर्ज़ से निकालता है।",
                 "ta": "மாதிரி உருப்படி. கீழே உள்ள வரி உண்மையானது: உங்கள் கடன்களிலிருந்து குறியீடு கணக்கிடுகிறது."}},
    {"topic": "prices", "tags": ["fuel", "groceries"], "source_name": "Ministry of Statistics", "source_url": "https://www.mospi.gov.in/",
     "title": {"en": "Demo item: prices", "hi": "डेमो आइटम: कीमतें", "ta": "டெமோ உருப்படி: விலைகள்"},
     "summary": {"en": "Placeholder. Your own fuel and grocery spend for the month appears below.",
                 "hi": "प्लेसहोल्डर। नीचे इस महीने का आपका ईंधन और किराने का खर्च दिखता है।",
                 "ta": "மாதிரி உருப்படி. இந்த மாத உங்கள் எரிபொருள், மளிகைச் செலவு கீழே தெரியும்."}},
]


async def build_pulse() -> dict[str, Any]:
    if not get_settings().is_live:
        out = await core().put_pulse(PLACEHOLDER_ITEMS)
        return {"mode": "fake", **out}

    from agent.llm.gemini import gemini

    notes, sources = await gemini().grounded(SEARCH_PROMPT)
    if not sources:
        return {"mode": "live", "kept": 0, "dropped": 0, "reason": "no sources returned"}
    listed = "\n".join(f"- {s['title'] or s['domain']}: {s['url']}" for s in sources[:20])
    raw = await gemini().generate_json(STRUCTURE_PROMPT.format(notes=notes[:8000], sources=listed), ITEMS_SCHEMA)
    allowed_urls = {s["url"] for s in sources}
    items, blocked = [], 0
    for it in (raw.get("items") or [])[:8]:
        if it.get("source_url") not in allowed_urls:
            continue  # no real source: drop
        text = " ".join(list((it.get("title") or {}).values()) + list((it.get("summary") or {}).values()))
        if not guard.check_advice(text).ok:
            blocked += 1
            continue
        items.append(it)
    out = await core().put_pulse(items)
    return {"mode": "live", "blocked_by_guard": blocked, **out}
