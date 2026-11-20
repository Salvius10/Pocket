"""Every sentence core-api produces, in en / hi / ta.

Code fills the numbers; the LLM never writes these. Hindi and Tamil are agent-written and
marked x-review until a native speaker checks them (BUILD_PLAN H4).
"""

from __future__ import annotations

X_REVIEW = ("hi", "ta")

_T: dict[str, dict[str, str]] = {
    # ---------- tool "say" lines ----------
    "sts.say": {
        "en": "You can spend {daily} a day for the next {days} days. {left} is left for today.",
        "hi": "अगले {days} दिन आप रोज़ {daily} खर्च कर सकते हैं। आज के लिए {left} बचा है।",
        "ta": "அடுத்த {days} நாட்களுக்கு தினமும் {daily} செலவு செய்யலாம். இன்றைக்கு {left} மீதம் உள்ளது.",
    },
    "sts.say_over": {
        "en": "You are {over} over today's limit. Your daily amount is {daily} for the next {days} days.",
        "hi": "आज की सीमा से {over} ज़्यादा खर्च हो चुका है। अगले {days} दिन रोज़ की रकम {daily} है।",
        "ta": "இன்றைய வரம்பை விட {over} அதிகம் செலவாகிவிட்டது. அடுத்த {days} நாட்களுக்கு தினசரி தொகை {daily}.",
    },
    "sts.say_zero": {
        "en": "There is nothing left to spend freely this month. Bills and goals already use your income.",
        "hi": "इस महीने खुलकर खर्च करने के लिए कुछ नहीं बचा। बिल और लक्ष्य आपकी आय ले चुके हैं।",
        "ta": "இந்த மாதம் தாராளமாக செலவு செய்ய எதுவும் மீதமில்லை. பில்களும் இலக்குகளும் வருமானத்தை எடுத்துவிட்டன.",
    },
    "cat.say_top": {
        "en": "Most of your money this month went to {a_name}: {a_amt}.",
        "hi": "इस महीने सबसे ज़्यादा पैसा {a_name} में गया: {a_amt}।",
        "ta": "இந்த மாதம் அதிக பணம் {a_name}-க்கு போனது: {a_amt}.",
    },
    "cat.say_next": {
        "en": "Then {b_name} at {b_amt} and {c_name} at {c_amt}.",
        "hi": "उसके बाद {b_name} {b_amt} और {c_name} {c_amt}।",
        "ta": "அடுத்து {b_name} {b_amt}, {c_name} {c_amt}.",
    },
    "cat.say_total": {
        "en": "In all you have spent {total} this month.",
        "hi": "कुल मिलाकर इस महीने {total} खर्च हुआ है।",
        "ta": "மொத்தமாக இந்த மாதம் {total} செலவாகியுள்ளது.",
    },
    "pocket.say": {
        "en": "{name}: {spent} spent of {limit}.",
        "hi": "{name}: {limit} में से {spent} खर्च।",
        "ta": "{name}: {limit}-இல் {spent} செலவு.",
    },
    "pocket.say_over": {
        "en": "{name} is over by {over}: {spent} spent of {limit}.",
        "hi": "{name} सीमा से {over} ऊपर है: {limit} में से {spent} खर्च।",
        "ta": "{name} வரம்பை விட {over} அதிகம்: {limit}-இல் {spent} செலவு.",
    },
    "goal.say": {
        "en": "{name}: {saved} saved of {target}.",
        "hi": "{name}: {target} में से {saved} जमा।",
        "ta": "{name}: {target}-இல் {saved} சேமிப்பு.",
    },
    "goal.say_need": {
        "en": "It needs {need} a month to stay on time.",
        "hi": "समय पर पूरा करने के लिए हर महीने {need} चाहिए।",
        "ta": "நேரத்தில் முடிக்க மாதம் {need} தேவை.",
    },
    "bills.say": {
        "en": "{count} payments are due in the next {days} days, {total} in all. Next is {name}, {amt}, on {date}.",
        "hi": "अगले {days} दिनों में {count} भुगतान आने हैं, कुल {total}। अगला {name} है, {amt}, {date} को।",
        "ta": "அடுத்த {days} நாட்களில் {count} கட்டணங்கள் உள்ளன, மொத்தம் {total}. அடுத்தது {name}, {amt}, {date} அன்று.",
    },
    "bills.say_none": {
        "en": "Nothing is due in the next {days} days.",
        "hi": "अगले {days} दिनों में कोई भुगतान नहीं है।",
        "ta": "அடுத்த {days} நாட்களில் கட்டணம் எதுவும் இல்லை.",
    },
    "networth.say": {
        "en": "Your net worth is {total}: {assets} in accounts and investments, minus {liab} owed.",
        "hi": "आपकी कुल संपत्ति {total} है: खातों और निवेश में {assets}, और {liab} बकाया।",
        "ta": "உங்கள் நிகர சொத்து {total}: கணக்குகளிலும் முதலீடுகளிலும் {assets}, கடன் {liab}.",
    },
    "inv.say": {
        "en": "Your investments are worth {total}. Your mutual funds moved {dir} by {week} this week.",
        "hi": "आपके निवेश की कीमत {total} है। इस हफ्ते आपके म्यूचुअल फंड {week} {dir} हुए।",
        "ta": "உங்கள் முதலீடுகளின் மதிப்பு {total}. இந்த வாரம் உங்கள் மியூச்சுவல் ஃபண்டுகள் {week} {dir}.",
    },
    "inv.say_none": {
        "en": "You have no investments linked.",
        "hi": "आपका कोई निवेश जुड़ा नहीं है।",
        "ta": "உங்களுக்கு முதலீடுகள் எதுவும் இணைக்கப்படவில்லை.",
    },
    "dir.up": {"en": "up", "hi": "ऊपर", "ta": "உயர்ந்தன"},
    "dir.down": {"en": "down", "hi": "नीचे", "ta": "குறைந்தன"},
    "cash.say": {
        "en": "This month {income} came in and {spend} went out.",
        "hi": "इस महीने {income} आया और {spend} गया।",
        "ta": "இந்த மாதம் {income} வந்தது, {spend} போனது.",
    },
    "txn.say": {
        "en": "I found {count} transactions, {total} in all.",
        "hi": "मुझे {count} लेन-देन मिले, कुल {total}।",
        "ta": "{count} பரிவர்த்தனைகள் கிடைத்தன, மொத்தம் {total}.",
    },
    "txn.say_none": {
        "en": "I found no transactions like that.",
        "hi": "ऐसा कोई लेन-देन नहीं मिला।",
        "ta": "அப்படி எந்த பரிவர்த்தனையும் இல்லை.",
    },
    "compare.say_up": {
        "en": "{what} is {b} this period against {a} before: up {delta}, {pct} percent more.",
        "hi": "{what} इस बार {b} है, पहले {a} था: {delta} ज़्यादा, {pct} प्रतिशत बढ़ा।",
        "ta": "{what} இப்போது {b}, முன்பு {a}: {delta} அதிகம், {pct} சதவீதம் உயர்வு.",
    },
    "compare.say_down": {
        "en": "{what} is {b} this period against {a} before: down {delta}, {pct} percent less.",
        "hi": "{what} इस बार {b} है, पहले {a} था: {delta} कम, {pct} प्रतिशत घटा।",
        "ta": "{what} இப்போது {b}, முன்பு {a}: {delta} குறைவு, {pct} சதவீதம் குறைவு.",
    },
    "compare.say_same": {
        "en": "{what} is {b}, the same as before.",
        "hi": "{what} {b} है, पहले जितना ही।",
        "ta": "{what} {b}, முன்பு போலவே.",
    },
    "spending": {"en": "Spending", "hi": "खर्च", "ta": "செலவு"},
    "afford.say_yes": {
        "en": "Yes. {amount} fits. After it you would have {left} of free money left this month, about {daily} a day.",
        "hi": "हाँ। {amount} हो सकता है। इसके बाद इस महीने {left} बचेगा, यानी रोज़ करीब {daily}।",
        "ta": "ஆம். {amount} முடியும். அதன் பிறகு இந்த மாதம் {left} மீதம் இருக்கும், தினமும் சுமார் {daily}.",
    },
    "afford.say_today_no": {
        "en": "It fits this month but not today's amount. After it you would have {left} left, about {daily} a day.",
        "hi": "इस महीने में हो जाएगा, पर आज की रकम से ज़्यादा है। इसके बाद {left} बचेगा, यानी रोज़ करीब {daily}।",
        "ta": "இந்த மாதத்தில் முடியும், ஆனால் இன்றைய தொகையை தாண்டும். அதன் பிறகு {left} மீதம், தினமும் சுமார் {daily}.",
    },
    "afford.say_no": {
        "en": "Not from this month's free money. You have {have} left and this costs {amount}: short by {short}.",
        "hi": "इस महीने के खुले पैसे से नहीं। आपके पास {have} बचा है और यह {amount} का है: {short} कम है।",
        "ta": "இந்த மாத தாராள பணத்தில் முடியாது. உங்களிடம் {have} உள்ளது, இது {amount}: {short} குறைவு.",
    },
    "groups.say_owed": {
        "en": "In {group} you are owed {amt}.",
        "hi": "{group} में आपको {amt} मिलने हैं।",
        "ta": "{group}-இல் உங்களுக்கு {amt} வர வேண்டும்.",
    },
    "groups.say_owe": {
        "en": "In {group} you owe {amt}.",
        "hi": "{group} में आपको {amt} देने हैं।",
        "ta": "{group}-இல் நீங்கள் {amt} தர வேண்டும்.",
    },
    "groups.say_even": {
        "en": "In {group} you are all settled.",
        "hi": "{group} में आपका हिसाब बराबर है।",
        "ta": "{group}-இல் கணக்கு சரியாக உள்ளது.",
    },
    "groups.say_pot": {
        "en": "The pot has {have} of {target}.",
        "hi": "पॉट में {target} में से {have} जमा है।",
        "ta": "பாட்டில் {target}-இல் {have} சேர்ந்துள்ளது.",
    },
    "groups.say_none": {
        "en": "You are not in any group yet.",
        "hi": "आप अभी किसी ग्रुप में नहीं हैं।",
        "ta": "நீங்கள் இன்னும் எந்த குழுவிலும் இல்லை.",
    },
    "pulse.say_none": {
        "en": "There is no Pulse for today yet.",
        "hi": "आज का पल्स अभी तैयार नहीं है।",
        "ta": "இன்றைய பல்ஸ் இன்னும் தயாராகவில்லை.",
    },
    "insights.say_none": {
        "en": "I have nothing new to flag right now.",
        "hi": "अभी बताने लायक कुछ नया नहीं है।",
        "ta": "இப்போது சொல்ல புதிதாக எதுவும் இல்லை.",
    },
    "profile.saved": {
        "en": "Saved. Thank you.",
        "hi": "सेव हो गया। धन्यवाद।",
        "ta": "சேமிக்கப்பட்டது. நன்றி.",
    },
    "home.unchanged": {
        "en": "I couldn't change your Home just now, so I left it as it was. Please try again in a moment.",
        "hi": "अभी मैं आपका होम नहीं बदल पाया, इसलिए उसे वैसा ही छोड़ दिया। थोड़ी देर में फिर कोशिश करें।",
        "ta": "இப்போது உங்கள் முகப்பை மாற்ற முடியவில்லை; அதை அப்படியே விட்டுவிட்டேன். சற்று நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.",
    },
    "home.updated": {
        "en": "Done. I changed your Home.",
        "hi": "हो गया। मैंने आपका होम बदल दिया।",
        "ta": "முடிந்தது. உங்கள் முகப்பை மாற்றினேன்.",
    },
    "proposal.ask_tap": {
        "en": "I have put a card on your screen. Tap Confirm if you want me to do it.",
        "hi": "मैंने स्क्रीन पर एक कार्ड रखा है। करना हो तो कन्फर्म पर टैप करें।",
        "ta": "திரையில் ஒரு கார்டு வைத்துள்ளேன். செய்ய வேண்டுமானால் உறுதிசெய் என்பதைத் தட்டுங்கள்.",
    },
    # ---------- proposal cards ----------
    "proposal.move.title": {
        "en": "Move {amt} from {src} to {dst}?",
        "hi": "{src} से {amt} {dst} में डालें?",
        "ta": "{src}-இலிருந்து {amt} {dst}-க்கு மாற்றவா?",
    },
    "proposal.move.body": {
        "en": "{src} will have {src_left} left this month. {dst} will reach {dst_after}.",
        "hi": "इस महीने {src} में {src_left} बचेगा। {dst} {dst_after} तक पहुँचेगा।",
        "ta": "இந்த மாதம் {src}-இல் {src_left} மீதம் இருக்கும். {dst} {dst_after} ஆகும்.",
    },
    "proposal.goal.title": {
        "en": "Create the goal {name}: {target}?",
        "hi": "लक्ष्य {name} बनाएँ: {target}?",
        "ta": "{name} இலக்கை உருவாக்கவா: {target}?",
    },
    "proposal.goal.body": {
        "en": "It needs {need} a month.",
        "hi": "इसके लिए हर महीने {need} चाहिए।",
        "ta": "இதற்கு மாதம் {need} தேவை.",
    },
    "proposal.goal.body_open": {
        "en": "No deadline. Add to it whenever you like.",
        "hi": "कोई समय-सीमा नहीं। जब चाहें जोड़ें।",
        "ta": "காலக்கெடு இல்லை. எப்போது வேண்டுமானாலும் சேர்க்கலாம்.",
    },
    "proposal.pocket.title": {
        "en": "Create the pocket {name}: {limit} a month?",
        "hi": "पॉकेट {name} बनाएँ: महीने का {limit}?",
        "ta": "{name} பாக்கெட்டை உருவாக்கவா: மாதம் {limit}?",
    },
    "proposal.pocket.body": {
        "en": "You have spent {spent} on this so far this month.",
        "hi": "इस महीने अब तक इस पर {spent} खर्च हुआ है।",
        "ta": "இந்த மாதம் இதுவரை இதில் {spent} செலவாகியுள்ளது.",
    },
    "proposal.txn.title": {
        "en": "Add a cash spend of {amt}?",
        "hi": "{amt} का नकद खर्च जोड़ें?",
        "ta": "{amt} ரொக்க செலவை சேர்க்கவா?",
    },
    "proposal.txn.title_in": {
        "en": "Add cash received: {amt}?",
        "hi": "नकद आय जोड़ें: {amt}?",
        "ta": "பெற்ற ரொக்கத்தை சேர்க்கவா: {amt}?",
    },
    "proposal.txn.body": {
        "en": "{what}, under {category}.",
        "hi": "{what}, श्रेणी {category}।",
        "ta": "{what}, வகை {category}.",
    },
    "proposal.done": {
        "en": "Done.",
        "hi": "हो गया।",
        "ta": "முடிந்தது.",
    },
    # ---------- insights ----------
    "insight.overspend_pocket.title": {
        "en": "{name} is over its limit",
        "hi": "{name} सीमा पार कर गया",
        "ta": "{name} வரம்பை தாண்டிவிட்டது",
    },
    "insight.overspend_pocket.body": {
        "en": "{spent} spent of {limit}, with {days} days still to go.",
        "hi": "{limit} में से {spent} खर्च, अभी {days} दिन बाकी हैं।",
        "ta": "{limit}-இல் {spent} செலவு, இன்னும் {days} நாட்கள் உள்ளன.",
    },
    "insight.pocket_at_risk.title": {
        "en": "{name} will run out early",
        "hi": "{name} जल्दी खत्म हो जाएगा",
        "ta": "{name} சீக்கிரம் தீர்ந்துவிடும்",
    },
    "insight.pocket_at_risk.body": {
        "en": "At this pace it reaches {projected} against a limit of {limit}.",
        "hi": "इस रफ़्तार से यह {projected} तक जाएगा, सीमा {limit} है।",
        "ta": "இந்த வேகத்தில் {projected} ஆகும், வரம்பு {limit}.",
    },
    "insight.category_creep.title": {
        "en": "{name} is creeping up",
        "hi": "{name} का खर्च बढ़ता जा रहा है",
        "ta": "{name} செலவு ஏறிக்கொண்டே போகிறது",
    },
    "insight.category_creep.body": {
        "en": "{recent} a month lately, up {pct}% from {earlier}. So far this month: {mtd}.",
        "hi": "हाल में महीने का {recent}, पहले के {earlier} से {pct}% ज़्यादा। इस महीने अब तक: {mtd}।",
        "ta": "சமீபத்தில் மாதம் {recent}, முன்பிருந்த {earlier}-ஐ விட {pct}% அதிகம். இந்த மாதம் இதுவரை: {mtd}.",
    },
    "insight.spike.title": {
        "en": "{name} jumped this month",
        "hi": "इस महीने {name} अचानक बढ़ा",
        "ta": "இந்த மாதம் {name} திடீரென உயர்ந்தது",
    },
    "insight.spike.body": {
        "en": "{now} so far, against a usual {usual} for a full month.",
        "hi": "अब तक {now}, जबकि पूरे महीने में आमतौर पर {usual}।",
        "ta": "இதுவரை {now}, வழக்கமாக முழு மாதத்துக்கு {usual}.",
    },
    "insight.forgotten_subscription.title": {
        "en": "Still paying for {name}?",
        "hi": "क्या {name} अब भी इस्तेमाल हो रहा है?",
        "ta": "{name}-க்கு இன்னும் பணம் கட்டுகிறீர்களா?",
    },
    "insight.forgotten_subscription.body": {
        "en": "{monthly} a month since a trial began. {count} charges so far: {total}.",
        "hi": "ट्रायल के बाद से हर महीने {monthly}। अब तक {count} बार कटा: {total}।",
        "ta": "ட்ரையல் தொடங்கியதிலிருந்து மாதம் {monthly}. இதுவரை {count} முறை: {total}.",
    },
    "insight.subscription_overlap.title": {
        "en": "{count} subscriptions of the same kind",
        "hi": "एक ही तरह के {count} सब्सक्रिप्शन",
        "ta": "ஒரே வகையில் {count} சந்தாக்கள்",
    },
    "insight.subscription_overlap.body": {
        "en": "{names} together cost {total} a month.",
        "hi": "{names} मिलकर महीने के {total} लेते हैं।",
        "ta": "{names} சேர்ந்து மாதம் {total} ஆகிறது.",
    },
    "insight.price_hike.title": {
        "en": "{name} went up",
        "hi": "{name} महँगा हुआ",
        "ta": "{name} விலை உயர்ந்தது",
    },
    "insight.price_hike.body": {
        "en": "From {old} to {new}: {pct}% more each time.",
        "hi": "{old} से {new}: हर बार {pct}% ज़्यादा।",
        "ta": "{old}-இலிருந்து {new}: ஒவ்வொரு முறையும் {pct}% அதிகம்.",
    },
    "insight.duplicate_charge.title": {
        "en": "{name} charged you twice",
        "hi": "{name} ने दो बार पैसे काटे",
        "ta": "{name} இரண்டு முறை பணம் எடுத்தது",
    },
    "insight.duplicate_charge.body": {
        "en": "{amt} twice within minutes on {date}. One of them may be refundable.",
        "hi": "{date} को कुछ ही मिनटों में {amt} दो बार। एक का रिफंड मिल सकता है।",
        "ta": "{date} அன்று சில நிமிடங்களில் {amt} இரண்டு முறை. ஒன்று திரும்பக் கிடைக்கலாம்.",
    },
    "insight.idle_cash.title": {
        "en": "{amt} is sitting idle",
        "hi": "{amt} यूँ ही पड़ा है",
        "ta": "{amt} சும்மா கிடக்கிறது",
    },
    "insight.idle_cash.body": {
        "en": "Your {bank} account {acct} has not dropped below {min} in two months.",
        "hi": "आपका {bank} खाता {acct} दो महीने में {min} से नीचे नहीं गया।",
        "ta": "உங்கள் {bank} கணக்கு {acct} இரண்டு மாதங்களாக {min}-க்கு கீழே போகவில்லை.",
    },
    "insight.expensive_card_balance.title": {
        "en": "Your card balance is costing you",
        "hi": "कार्ड का बकाया महँगा पड़ रहा है",
        "ta": "கார்டு நிலுவை உங்களுக்கு செலவாகிறது",
    },
    "insight.expensive_card_balance.body": {
        "en": "{charges} paid in interest and tax on {bank} card {acct}. {owed} is owed now.",
        "hi": "{bank} कार्ड {acct} पर ब्याज और टैक्स में {charges} गया। अभी {owed} बकाया है।",
        "ta": "{bank} கார்டு {acct}-இல் வட்டி, வரியாக {charges} போனது. இப்போது நிலுவை {owed}.",
    },
    "insight.emi_load.title": {
        "en": "EMIs take {pct}% of your income",
        "hi": "आय का {pct}% ईएमआई में जाता है",
        "ta": "வருமானத்தில் {pct}% இஎம்ஐ-க்கு போகிறது",
    },
    "insight.emi_load.body": {
        "en": "{emi} a month in EMIs against about {income} coming in.",
        "hi": "हर महीने ईएमआई में {emi}, जबकि आय करीब {income}।",
        "ta": "மாதம் இஎம்ஐ {emi}, வருமானம் சுமார் {income}.",
    },
    "insight.pocket_surplus.title": {
        "en": "{name} has room to spare",
        "hi": "{name} में पैसे बच रहे हैं",
        "ta": "{name}-இல் பணம் மீதமாகிறது",
    },
    "insight.pocket_surplus.body": {
        "en": "About {surplus} will be left over this month. It could go to {goal}.",
        "hi": "इस महीने करीब {surplus} बचेगा। यह {goal} में जा सकता है।",
        "ta": "இந்த மாதம் சுமார் {surplus} மீதமாகும். அதை {goal}-க்கு மாற்றலாம்.",
    },
    "insight.goal_off_track.title": {
        "en": "{name} is behind",
        "hi": "{name} पीछे चल रहा है",
        "ta": "{name} பின்தங்கியுள்ளது",
    },
    "insight.goal_off_track.body": {
        "en": "{saved} saved of {target}. It now needs {need} a month to finish on time.",
        "hi": "{target} में से {saved} जमा। समय पर पूरा करने के लिए अब हर महीने {need} चाहिए।",
        "ta": "{target}-இல் {saved} சேமிப்பு. நேரத்தில் முடிக்க இனி மாதம் {need} தேவை.",
    },
    "insight.income_drop.title": {
        "en": "Less money came in this month",
        "hi": "इस महीने कम पैसा आया",
        "ta": "இந்த மாதம் குறைவான பணம் வந்தது",
    },
    "insight.income_drop.body": {
        "en": "{now} so far, against {usual} by this day in earlier months.",
        "hi": "अब तक {now}, जबकि पिछले महीनों में इस दिन तक {usual}।",
        "ta": "இதுவரை {now}, முந்தைய மாதங்களில் இந்த நாள் வரை {usual}.",
    },
    # ---------- nudges ----------
    "nudge.bill_due.title": {"en": "{name} is due {when}", "hi": "{name} {when} देना है", "ta": "{name} {when} கட்ட வேண்டும்"},
    "nudge.bill_due.body": {"en": "{amt} will go out.", "hi": "{amt} जाएगा।", "ta": "{amt} போகும்."},
    "nudge.overspend.title": {"en": "{name} is over its limit", "hi": "{name} सीमा पार", "ta": "{name} வரம்பை தாண்டியது"},
    "nudge.overspend.body": {"en": "{spent} spent of {limit}.", "hi": "{limit} में से {spent} खर्च।", "ta": "{limit}-இல் {spent} செலவு."},
    "nudge.group_request.title": {"en": "{group}: you owe {amt}", "hi": "{group}: आपको {amt} देने हैं", "ta": "{group}: நீங்கள் {amt} தர வேண்டும்"},
    "nudge.group_request.body": {"en": "Settle up by UPI when you are ready.", "hi": "जब चाहें यूपीआई से चुकाएँ।", "ta": "தயாரானதும் யுபிஐ மூலம் செலுத்துங்கள்."},
    "nudge.goal_reached.title": {"en": "{name} is fully saved", "hi": "{name} पूरा हो गया", "ta": "{name} முழுமையாக சேர்ந்துவிட்டது"},
    "nudge.goal_reached.body": {"en": "{saved} of {target}. Well done.", "hi": "{target} में से {saved}। बहुत बढ़िया।", "ta": "{target}-இல் {saved}. அருமை."},
    "nudge.weekly_report.title": {"en": "Your week in review", "hi": "आपका हफ्ता", "ta": "உங்கள் வார மதிப்பாய்வு"},
    "nudge.weekly_report.body": {"en": "{spend} spent, {income} came in.", "hi": "{spend} खर्च, {income} आया।", "ta": "{spend} செலவு, {income} வரவு."},
    "when.today": {"en": "today", "hi": "आज", "ta": "இன்று"},
    "when.tomorrow": {"en": "tomorrow", "hi": "कल", "ta": "நாளை"},
    "when.in_days": {"en": "in {n} days", "hi": "{n} दिन में", "ta": "{n} நாட்களில்"},
    # ---------- pulse personal lines ----------
    "pulse.link.mf_week": {
        "en": "Your mutual funds are {dir} {amt} this week.",
        "hi": "इस हफ्ते आपके म्यूचुअल फंड {amt} {dir} हैं।",
        "ta": "இந்த வாரம் உங்கள் மியூச்சுவல் ஃபண்டுகள் {amt} {dir}.",
    },
    "pulse.link.nifty": {
        "en": "Nifty 50 index funds moved {pct}% this week.",
        "hi": "इस हफ्ते निफ्टी 50 इंडेक्स फंड {pct}% बदले।",
        "ta": "இந்த வாரம் நிஃப்டி 50 இன்டெக்ஸ் ஃபண்டுகள் {pct}% மாறின.",
    },
    "pulse.link.rate_move": {
        "en": "A 0.25% rate move would change your {lender} EMI by about {amt} a month.",
        "hi": "दर में 0.25% बदलाव से आपकी {lender} ईएमआई महीने में करीब {amt} बदलेगी।",
        "ta": "0.25% வட்டி மாற்றம் உங்கள் {lender} இஎம்ஐ-யை மாதம் சுமார் {amt} மாற்றும்.",
    },
    "pulse.link.fuel": {
        "en": "You have spent {amt} on fuel this month.",
        "hi": "इस महीने ईंधन पर {amt} खर्च हुआ है।",
        "ta": "இந்த மாதம் எரிபொருளுக்கு {amt} செலவாகியுள்ளது.",
    },
    "pulse.link.groceries": {
        "en": "Groceries have cost you {amt} this month.",
        "hi": "इस महीने किराने पर {amt} खर्च हुआ है।",
        "ta": "இந்த மாதம் மளிகைக்கு {amt} செலவாகியுள்ளது.",
    },
    "pulse.link.gold": {
        "en": "You hold {grams} grams of gold.",
        "hi": "आपके पास {grams} ग्राम सोना है।",
        "ta": "உங்களிடம் {grams} கிராம் தங்கம் உள்ளது.",
    },
    "pulse.link.fd": {
        "en": "You have {amt} in fixed deposits.",
        "hi": "आपके फिक्स्ड डिपॉज़िट में {amt} है।",
        "ta": "உங்கள் நிலையான வைப்பில் {amt} உள்ளது.",
    },
    # ---------- labels ----------
    "label.bank_accounts": {"en": "Bank accounts", "hi": "बैंक खाते", "ta": "வங்கி கணக்குகள்"},
    "label.mutual_funds": {"en": "Mutual funds", "hi": "म्यूचुअल फंड", "ta": "மியூச்சுவல் ஃபண்டுகள்"},
    "label.fd": {"en": "Fixed deposits", "hi": "फिक्स्ड डिपॉज़िट", "ta": "நிலையான வைப்பு"},
    "label.ppf_epf": {"en": "PPF and EPF", "hi": "पीपीएफ और ईपीएफ", "ta": "பிபிஎஃப் & இபிஎஃப்"},
    "label.gold": {"en": "Gold (approx.)", "hi": "सोना (लगभग)", "ta": "தங்கம் (தோராயம்)"},
    "label.cards": {"en": "Credit cards", "hi": "क्रेडिट कार्ड", "ta": "கிரெடிட் கார்டுகள்"},
    "label.loans": {"en": "Loans", "hi": "कर्ज़", "ta": "கடன்கள்"},
    "label.card_bill": {"en": "{bank} card bill", "hi": "{bank} कार्ड बिल", "ta": "{bank} கார்டு பில்"},
    "label.cash": {"en": "Cash", "hi": "नकद", "ta": "ரொக்கம்"},
}

_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुला", "अग", "सित", "अक्टू", "नव", "दिस"],
    "ta": ["ஜன", "பிப்", "மார்", "ஏப்", "மே", "ஜூன்", "ஜூலை", "ஆக", "செப்", "அக்", "நவ", "டிச"],
}


def t(lang: str, key: str, **kw: object) -> str:
    entry = _T.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry["en"]
    try:
        return template.format(**kw)
    except (KeyError, IndexError):
        return template


def month_label(lang: str, month: int) -> str:
    return _MONTHS.get(lang, _MONTHS["en"])[month - 1]


def date_label(lang: str, d: object) -> str:
    """'24 Nov' style, Western digits."""
    from datetime import date as _date

    assert isinstance(d, _date)
    return f"{d.day} {month_label(lang, d.month)}"


def category_name(cat: object, lang: str) -> str:
    name = getattr(cat, f"name_{lang}", "") or getattr(cat, "name_en", "")
    return str(name)
