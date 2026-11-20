"""GEMINI_MODE=fake: a rule-based stand-in for the live model (BUILD_PLAN H2).

It reads typed text, picks a tool by keywords in English, Hindi, Tamil and Tanglish, and speaks
only the `say` text core-api returned. No audio. It lets the whole app run before a key exists
and gives the chat evals a deterministic baseline.
"""

from __future__ import annotations

import re
from typing import Any

from pocket_common import guard

from agent.live.session import LiveSession
from agent.prompts.lines import line

ADVICE = re.compile(
    r"should i (?:buy|sell|invest|switch|redeem|exit|hold)|shall i (?:buy|sell|invest)|can i (?:buy|invest in)|which (?:fund|stock|sip|share|etf|mutual)|"
    r"best (?:fund|stock|sip|share|mutual)|good (?:fund|stock|time to (?:buy|invest|sell))|recommend .{0,20}(?:fund|stock|sip)|"
    r"(?:buy|sell) (?:this|that|some|more|gold|shares?|stocks?|bitcoin|crypto)|is it (?:a )?(?:good|right) time|start (?:a |an )?sip in|"
    r"खरीद लूँ|खरीदूँ|खरीदना चाहिए|बेच दूँ|बेचना चाहिए|कौन सा फंड|कौन सा शेयर|निवेश करूँ|निवेश करना चाहिए|"
    r"வாங்கலாமா|விற்கலாமா|வாங்கட்டுமா|எந்த ஃபண்ட்|எந்த பங்கு|முதலீடு செய்யலாமா|முதலீடு பண்ணலாமா|"
    r"vaangalama|vaangalaama|vikkalama|podalama|invest pannalama|kharid lun|kharidna chahiye|bech dun|konsa fund|kaun sa fund",
    re.IGNORECASE,
)
PREDICT = re.compile(r"(?:market|nifty|sensex|gold|बाज़ार|बाजार|சந்தை).{0,30}(?:will|going to|badhega|girega|बढ़ेगा|गिरेगा|ஏறுமா|இறங்குமா|yeruma|go up|crash|fall|rise)", re.IGNORECASE)
YES = re.compile(r"^\s*(?:yes|yeah|yep|ok|okay|sure|do it|go ahead|confirm|haan|हाँ|हां|ठीक है|कर दो|சரி|ஆம்|ஆமா|pannu|seri|sari)\b[\s.!]*$", re.IGNORECASE)

INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("layout", re.compile(r"(?:put|move|bring|show|keep|pin).{0,40}(?:first|top|above|upar|पहले|ऊपर|முதலில்|மேலே)|(?:hide|remove|take off|eduthudu|हटा|நீக்கு|மறை).{0,40}|"
                          r"(?:home|layout|screen|होम|முகப்பு).{0,30}(?:change|rebuild|redo|reset|बदल|மாற்று)|rebuild my home", re.IGNORECASE)),
    ("afford", re.compile(r"afford|can i (?:buy|get|spend)|kharid sakt|खरीद सकत|ले सकत|வாங்க முடியுமா|mudiyuma|vaanga mudiyum", re.IGNORECASE)),
    ("move", re.compile(r"(?:move|shift|transfer|डाल|भेज|மாற்று|maathu).{0,60}(?:from|to|से|में|இலிருந்து|க்கு)", re.IGNORECASE)),
    ("goal_new", re.compile(r"(?:new goal|create (?:a )?goal|set (?:a )?goal|save up for|start saving for|नया लक्ष्य|புதிய இலக்கு)", re.IGNORECASE)),
    ("pocket_new", re.compile(r"(?:new pocket|create (?:a )?pocket|add (?:a )?pocket|set (?:a )?budget|नया पॉकेट|புதிய பாக்கெட்)", re.IGNORECASE)),
    ("cash", re.compile(r"(?:spent|paid|gave|खर्च किए|दिए|செலவு பண்ணினேன்|கொடுத்தேன்).{0,40}(?:cash|नकद|ரொக்க)|add (?:a )?(?:cash|transaction|expense)", re.IGNORECASE)),
    ("compare", re.compile(r"compare|compared|than last|vs\.? last|more than (?:usual|before)|पिछले महीने से|போன மாதத்தை விட|pona maasam", re.IGNORECASE)),
    ("insights", re.compile(r"notice|noticed|anything (?:new|odd|wrong)|leak|wast|save more|tips?|pattern|what should i know|क्या देखा|कुछ खास|என்ன கவனித்|ethavathu|enna kavanich", re.IGNORECASE)),
    ("pulse", re.compile(r"market|nifty|sensex|news|pulse|repo|rbi|inflation|world|बाज़ार|बाजार|खबर|சந்தை|செய்தி", re.IGNORECASE)),
    ("groups", re.compile(r"trip|group|flat|flatmate|owe|owes|split|settle|pot\b|ट्रिप|ग्रुप|हिसाब|ட்ரிப்|குழு|கணக்கு", re.IGNORECASE)),
    ("bills", re.compile(r"\bbills?\b|\bemis?\b|due|rent|recharge|बिल|ईएमआई|किराया|பில்|இஎம்ஐ|வாடகை", re.IGNORECASE)),
    ("net_worth", re.compile(r"net worth|worth|total (?:money|wealth)|how much do i have|कुल संपत्ति|நிகர சொத்து|motham evlo", re.IGNORECASE)),
    ("investments", re.compile(r"invest|mutual|\bsip\b|portfolio|funds?|holdings?|निवेश|फंड|முதலீடு|ஃபண்ட்", re.IGNORECASE)),
    ("where", re.compile(r"where.{0,20}(?:money|going|spend)|most of my money|biggest|top (?:spend|categor)|कहाँ जा रहा|kahan ja|எங்கே போகுது|எங்கே போகிறது|enga poguthu", re.IGNORECASE)),
    ("goals", re.compile(r"goal|saving for|savings|बचत|लक्ष्य|இலக்கு|சேமிப்பு", re.IGNORECASE)),
    ("cash_flow", re.compile(r"cash ?flow|income|earn|came in|आय|कमाई|வருமானம்", re.IGNORECASE)),
    ("safe", re.compile(r"how much can i spend|safe|left (?:for )?today|today|spend today|daily|aaj kitna|आज कितना|இன்று எவ்வளவு|innaikku evlo", re.IGNORECASE)),
    ("pockets", re.compile(r"pocket|budget|spent on|spend on|how much (?:have i|did i)|पॉकेट|बजट|कितना खर्च|பாக்கெட்|பட்ஜெட்|எவ்வளவு செலவு", re.IGNORECASE)),
    ("greeting", re.compile(r"^\s*(?:hi|hello|hey|namaste|vanakkam|नमस्ते|வணக்கம்)\b", re.IGNORECASE)),
]

CATEGORY_WORDS = {
    "food_delivery": r"food delivery|swiggy|zomato|delivery|फूड डिलीवरी|உணவு டெலிவரி", "eating_out": r"eating out|restaurant|dinner|lunch|बाहर खाना|வெளியே சாப்பாடு",
    "groceries": r"grocer|kirana|किराना|மளிகை", "shopping": r"shopping|amazon|flipkart|खरीदारी|ஷாப்பிங்", "transport": r"cab|uber|ola|auto|travel|सफर|பயணம்",
    "fuel": r"fuel|petrol|diesel|पेट्रोल|பெட்ரோல்", "entertainment": r"movie|entertainment|fun|मनोरंजन|பொழுதுபோக்கு", "subscriptions": r"subscription|netflix|spotify|सब्सक्रिप्शन|சந்தா",
    "rent": r"\brent\b|किराया|வாடகை", "health": r"health|medicine|doctor|दवा|மருந்து",
}
WIDGET_WORDS = {
    "bills_emis": r"emi|bill|ईएमआई|बिल|இஎம்ஐ|பில்", "goals": r"goal|लक्ष्य|இலக்கு|laptop|bike", "investments": r"invest|fund|निवेश|முதலீடு",
    "net_worth": r"net worth|संपत्ति|சொத்து", "cash_flow": r"cash ?flow|income", "spend_by_category": r"categor|where.*money|spend", "pockets": r"pocket|budget|पॉकेट|பாக்கெட்",
    "transactions": r"transaction|लेन-देन|பரிவர்த்தனை", "group_pot": r"group|trip|pot|ग्रुप|குழு|ட்ரிப்", "pulse_card": r"pulse|news|market", "insight_card": r"insight|notice",
}

PERSONA_HINTS = [
    ("student", r"student|college|pocket money|parents|छात्र|कॉलेज|மாணவ|கல்லூரி|அப்பா"),
    ("shop", r"shop|store|my business|dukaan|दुकान|कारोबार|கடை|வியாபார"),
    ("gig", r"gig|delivery (?:partner|job|work|boy)|i deliver|driver|rider|daily (?:pay|earning)|डिलीवरी का काम|गिग|டெலிவரி வேலை"),
    ("investor", r"invest|mutual|stocks|portfolio|निवेश|முதலீடு"),
    ("family", r"family|kids|children|home loan|husband|wife|परिवार|बच्चे|குடும்ப|பிள்ளை"),
    ("first_job", r"salary|job|engineer|office|वेतन|नौकरी|சம்பள|வேலை"),
]


def first_amount(text: str) -> float | None:
    nums = [n for n in guard.extract_numbers(text) if n > 31]
    return nums[0] if nums else None


def match_name(text: str, names: list[str]) -> str | None:
    low = text.lower()
    hits = [n for n in names if n.lower() in low]
    if hits:
        return max(hits, key=len)
    for n in names:  # any distinctive word of the name
        if any(len(w) > 3 and w in low for w in n.lower().split()):
            return n
    return None


def category_in(text: str) -> str | None:
    return next((cid for cid, pat in CATEGORY_WORDS.items() if re.search(pat, text, re.IGNORECASE)), None)


class FakeBridge:
    def __init__(self, session: LiveSession) -> None:
        self.s = session
        self._onb_step = 0
        self._answers: list[str] = []
        self._pending_proposal = False

    async def start(self) -> None:
        if self.s.mode == "onboarding":
            await self.s.say(line(self.s.lang, "onb.q1"))
        else:
            await self.s.mood("idle")

    async def on_audio(self, pcm: bytes) -> None:  # fake mode has no ears
        return

    async def on_audio_end(self) -> None:
        return

    async def correct(self, instruction: str) -> None:
        await self.s.send("transcript", role="mascot", text=line(self.s.lang, "correction"), final=True)

    async def close(self) -> None:
        return

    async def _tool_say(self, name: str, args: dict[str, Any], prefix: str = "", mood: str = "talking") -> dict[str, Any]:
        await self.s.mood("thinking")
        out = await self.s.call_tool(name, args)
        if out.get("error") and name in ("set_goal", "create_pocket", "move_between_pockets", "add_transaction"):
            await self.s.say(line(self.s.lang, "write_failed", reason=out["error"]), "concerned")
            return out
        say = " ".join(p for p in (prefix, out.get("say") or "") if p) or line(self.s.lang, "tool_failed")
        await self.s.say(say, mood)
        return out

    async def on_text(self, text: str) -> None:
        s, lang = self.s, self.s.lang
        await s.user_said(text)
        if s.mode == "onboarding":
            await self._onboarding(text)
            return
        if not s.linked:
            await s.say(line(lang, "not_linked"), "concerned")
            return
        if YES.match(text) and self._pending_proposal:
            await s.say(line(lang, "yes_needs_tap"))  # a spoken yes never executes anything
            return
        if ADVICE.search(text):
            await self._tool_say("get_summary", {"sections": ["investments"]}, line(lang, "refusal"), "concerned")
            return
        if PREDICT.search(text):
            await self._tool_say("get_pulse", {}, line(lang, "prediction_refusal"), "concerned")
            return
        amount = first_amount(text)
        needs_amount = ("afford", "move", "goal_new", "pocket_new", "cash")
        intent = next((name for name, pat in INTENTS if pat.search(text) and (amount or name not in needs_amount)), None)
        if intent == "layout":
            await self._tool_say("compose_home", {"instruction": text}, mood="happy")
        elif intent == "afford" and amount:
            await self._tool_say("check_affordability", {"amount_rupees": amount})
        elif intent == "move" and amount:
            src, dst = match_name(text, s.names.get("pockets", [])), match_name(text, s.names.get("goals", []))
            if dst is None:
                others = [n for n in s.names.get("pockets", []) if n != src]
                dst = match_name(text.replace(src or "", ""), others)
            out = await self._tool_say("move_between_pockets", {"from": src or "", "to": dst or "", "amount_rupees": amount})
            self._pending_proposal = bool(out.get("ok"))
        elif intent == "goal_new" and amount:
            name = re.sub(r"(?i).*?(?:for|goal)\s+(?:a |an |my |the )?", "", re.sub(r"[₹\d,]+.*", "", text)).strip(" .?") or "New goal"
            out = await self._tool_say("set_goal", {"name": name[:40].title(), "target_rupees": amount})
            self._pending_proposal = bool(out.get("ok"))
        elif intent == "pocket_new" and amount:
            cat = category_in(text) or "other_expense"
            out = await self._tool_say("create_pocket", {"name": cat.replace("_", " ").title(), "monthly_limit_rupees": amount, "categories": [cat]})
            self._pending_proposal = bool(out.get("ok"))
        elif intent == "cash" and amount:
            out = await self._tool_say("add_transaction", {"amount_rupees": amount, "category": category_in(text) or "other_expense", "description": "Cash"})
            self._pending_proposal = bool(out.get("ok"))
        elif intent == "compare":
            await self._tool_say("compare_spend", {"category": category_in(text), "period_a": "last_month_to_date", "period_b": "this_month"})
        elif intent == "insights":
            out = await self._tool_say("get_insights", {}, mood="concerned")
            self._pending_proposal = bool(out.get("client"))
        elif intent == "pulse":
            await self._tool_say("get_pulse", {})
        elif intent == "groups":
            await self._tool_say("get_groups", {})
            await s.call_tool("show_widget", {"type": "group_pot"})
        elif intent in ("bills", "net_worth", "investments", "goals", "cash_flow"):
            await self._tool_say("get_summary", {"sections": [intent]})
        elif intent == "where":
            await s.call_tool("show_widget", {"type": "spend_by_category"})
            await self._tool_say("get_summary", {"sections": ["spend_by_category"]})
        elif intent == "safe":
            await self._tool_say("get_summary", {"sections": ["safe_to_spend"]})
        elif intent == "pockets" or category_in(text):
            await self._pocket_answer(text)
        elif intent == "greeting":
            await s.say(line(lang, "greeting", name=s.first_name or ""), "happy")
        elif re.search(r"show|open|dikha|दिखा|காட்டு|kaatu", text, re.IGNORECASE):
            wtype = next((w for w, pat in WIDGET_WORDS.items() if re.search(pat, text, re.IGNORECASE)), None)
            await (self._tool_say("show_widget", {"type": wtype}) if wtype else s.say(line(lang, "fallback"), "concerned"))
        else:
            await s.say(line(lang, "fallback"), "concerned")

    async def _pocket_answer(self, text: str) -> None:
        s = self.s
        await s.mood("thinking")
        out = await s.call_tool("get_summary", {"sections": ["pockets"]})
        pockets = (out.get("result") or {}).get("pockets") or []
        cat = category_in(text)
        name = match_name(text, [p["name"] for p in pockets])
        hit = next((p for p in pockets if p["name"] == name), None) or next((p for p in pockets if cat and cat in p["category_ids"]), None)
        if hit is not None:
            await s.say(hit["say"], "concerned" if hit["status"] == "over" else "talking")
        elif cat:
            await self._tool_say("get_transactions", {"category": cat, "period": "this_month"})
        else:
            await s.say(out.get("say") or line(s.lang, "tool_failed"))

    async def _onboarding(self, text: str) -> None:
        s = self.s
        self._answers.append(text)
        self._onb_step += 1
        if self._onb_step < 4:
            await s.say(line(s.lang, f"onb.q{self._onb_step + 1}"))
            return
        keys = ("income", "income_amount", "saving_for", "worries")
        await s.mood("thinking")
        await s.call_tool("save_profile", {"facts": dict(zip(keys, self._answers[:4], strict=False))})
        joined = " ".join(self._answers)
        persona = next((p for p, pat in PERSONA_HINTS if re.search(pat, joined, re.IGNORECASE)), "first_job")
        await s.send("onboarding_done", suggested_persona=persona)
        await s.say(line(s.lang, "onb.done"), "happy")
