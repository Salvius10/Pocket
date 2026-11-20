"""Bank-style narrations, bank SMS (with ground truth) and Account Aggregator-style JSON.

Wording approximates the public formats Indian banks use. It is synthetic: calibrate against a few real,
redacted samples before trusting a parser on real data.
"""
from __future__ import annotations

import random
from datetime import timedelta

from . import refdata as R

HANDLE_BANK = {
    "axisbank": ("UTIB", "Axis Bank"), "axisb": ("UTIB", "Axis Bank"), "axl": ("UTIB", "Axis Bank"), "okaxis": ("UTIB", "Axis Bank"),
    "okbizaxis": ("UTIB", "Axis Bank"), "naviaxis": ("UTIB", "Axis Bank"), "apl": ("UTIB", "Axis Bank"), "ptaxis": ("UTIB", "Axis Bank"),
    "hdfcbank": ("HDFC", "HDFC Bank"), "okhdfcbank": ("HDFC", "HDFC Bank"), "pthdfc": ("HDFC", "HDFC Bank"),
    "icici": ("ICIC", "ICICI Bank"), "okicici": ("ICIC", "ICICI Bank"), "ibl": ("ICIC", "ICICI Bank"),
    "ybl": ("YESB", "Yes Bank"), "ptyes": ("YESB", "Yes Bank"), "ptys": ("YESB", "Yes Bank"),
    "sbi": ("SBIN", "State Bank Of India"), "oksbi": ("SBIN", "State Bank Of India"), "ptsbi": ("SBIN", "State Bank Of India"),
    "upi": ("BARB", "Bank of Baroda"), "barodampay": ("BARB", "Bank of Baroda"), "paytm": ("PYTM", "Paytm Payments Bank"),
    "cnrb": ("CNRB", "Canara Bank"), "kotak": ("KKBK", "Kotak Mahindra Bank"), "kmbl": ("KKBK", "Kotak Mahindra Bank"),
    "airtel": ("AIRP", "Airtel Payments Bank"), "fbpe": ("FDRL", "Federal Bank"), "pocketdemo": ("DEMO", "Demo Bank"),
}
MCC = {"food_delivery": 5814, "groceries": 5411, "eating_out": 5812, "fuel": 5541, "transport": 4121, "travel": 4722,
       "shopping": 5311, "entertainment": 7832, "subscriptions": 5815, "utilities": 4900, "mobile_internet": 4814,
       "health": 5912, "insurance": 6300, "education": 8299, "personal_care": 7230, "home_services": 7349,
       "gifts_donations": 5947, "business_supplies": 5300, "emi": 6012}
CARD_CITY = {"swiggy": "BANGALORE", "zomato": "GURGAON", "flipkart": "BANGALORE", "amazon": "BANGALORE", "blinkit": "GURGAON",
             "zepto": "MUMBAI", "uber": "GURGAON", "ola": "BANGALORE", "myntra": "BANGALORE", "netflix": "MUMBAI",
             "spotify": "MUMBAI", "bookmyshow": "MUMBAI", "makemytrip": "GURGAON", "indigo": "GURGAON", "irctc": "NEW DELHI",
             "nykaa": "MUMBAI", "bigbasket": "BANGALORE", "openai": "SAN FRANCISCO", "linkedin": "BANGALORE",
             "googleone": "MUMBAI", "youtubepremium": "MUMBAI", "applemedia": "MUMBAI"}


def bank_of_vpa(vpa: str | None) -> tuple[str, str]:
    if not vpa or "@" not in vpa:
        return ("HDFC", "HDFC Bank")
    return HANDLE_BANK.get(vpa.split("@")[-1].lower(), ("YESB", "Yes Bank"))


def rs(paise: int, comma: bool = False, decimals: int = 2) -> str:
    v = paise / 100
    if comma:
        whole = int(abs(paise) // 100)
        s = str(whole)
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            parts = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            s = ",".join(parts) + "," + tail
        return f"{s}.{abs(paise) % 100:02d}" if decimals == 2 else s
    return f"{v:.{decimals}f}"


def sbi_amt(paise: int) -> str:
    v = paise / 100
    return f"{v:.1f}" if paise % 10 == 0 else f"{v:.2f}"


class Renderer:
    def __init__(self, builder, seed: int):
        self.b = builder
        self.r = random.Random(seed + 7)
        self.sms: list[dict] = []
        self.sms_seq = 0

    # ------------------------------------------------------------------ narration
    def narrate(self, t, acc) -> str:
        if acc.type == "credit_card":
            return self._card_narr(t)
        name = (t.cp_name or "").upper()[:22].strip()
        vpa = t.cp_vpa or ""
        b4, bname = bank_of_vpa(vpa)
        ifsc = f"{b4}0000{self.r.randrange(100, 999)}"
        note = (t.note or ("PAYMENT" if t.kind in ("neft_out", "netbanking") else "UPI"))[:20]
        bank = acc.bank
        k = t.kind
        if k in ("upi_p2m", "upi_p2p_out", "autopay", "billpay", "card_bill_pay") and t.mode in ("upi", "autopay"):
            if k == "autopay":
                note = "MANDATE REG" if "Mandate" in (t.note or "") else "AUTOPAY"
            if k == "billpay":
                note = "BBPS BILLPAY"
            return {
                "HDFC": f"UPI-{name}-{vpa}-{ifsc}-{t.ref}-{note.upper()}",
                "SBI": f"TO TRANSFER-UPI/DR/{t.ref}/{name[:20]}/{b4}/{vpa}/{note}--",
                "ICICI": f"UPI/{t.ref}/{note}/{vpa}/{bname}/{'ICI' + str(self.r.randrange(10**9, 10**10))}",
                "AXIS": (f"UPI/P2M/{t.ref}/{name[:20]}/{note}/{bname}" if k != "upi_p2p_out" else f"UPI/P2A/{t.ref}/{name[:20]}/{bname}/{note}"),
                "KOTAK": f"UPI/{name[:20]}/{t.ref}/{note}",
                "CANARA": f"UPI/DR/{t.ref}/{name[:20]}/{b4}/{vpa}/{note}",
                "BOB": f"UPI/{t.ref}/DR/{name[:20]}/{b4}/{vpa}",
            }[bank]
        if k == "card_bill_pay":          # via BillDesk / netbanking
            card = t.meta.get("card_masked", "XXXXXXXXXXXX0000")
            return {"HDFC": f"IB BILLPAY DR-BILLDESK-{card}", "SBI": f"TO TRANSFER-INB BILLDESK CC {card[-4:]}--",
                    "ICICI": f"BIL/ONL/{t.ref}/BILLDESK/CC{card[-4:]}", "AXIS": f"IB/BILLPAY/BILLDESK/{card[-4:]}",
                    "KOTAK": f"BILLDESK CC PAYMENT {card[-4:]}", "CANARA": f"BILLDESK CC {card[-4:]}",
                    "BOB": f"BILLDESK/CC/{card[-4:]}"}[bank]
        if k in ("upi_in",):
            return {
                "HDFC": f"UPI-{name}-{vpa}-{ifsc}-{t.ref}-{note.upper()}",
                "SBI": f"BY TRANSFER-UPI/CR/{t.ref}/{name[:20]}/{b4}/{vpa}/{note}--",
                "ICICI": f"UPI/{t.ref}/{note}/{vpa}/{bname}/{'ICI' + str(self.r.randrange(10**9, 10**10))}",
                "AXIS": f"UPI/P2A/{t.ref}/{name[:20]}/{bname}/{note}",
                "KOTAK": f"UPI/{name[:20]}/{t.ref}/{note}",
                "CANARA": f"UPI/CR/{t.ref}/{name[:20]}/{b4}/{vpa}/{note}",
                "BOB": f"UPI/{t.ref}/CR/{name[:20]}/{b4}/{vpa}",
            }[bank]
        if k == "upi_reversal":
            return {"HDFC": f"REV-UPI-{t.ref}-{name}", "SBI": f"BY TRANSFER-UPI/REV/{t.ref}/{name[:20]}/{b4}/{vpa}--",
                    "ICICI": f"UPI/REV/{t.ref}/{vpa}", "AXIS": f"UPI/REV/{t.ref}/{name[:20]}", "KOTAK": f"UPI REV/{t.ref}/{name[:20]}",
                    "CANARA": f"UPI/REV/{t.ref}/{name[:20]}", "BOB": f"UPI/{t.ref}/REV/{name[:20]}"}[bank]
        if k == "neft_in":
            pb = t.meta.get("payer_bank", "ICIC")
            pifsc = f"{pb}0000{self.r.randrange(100, 999)}"
            ben = self.b.s.full_name.upper()
            purpose = (t.note or "").upper()
            return {
                "HDFC": f"NEFT CR-{pifsc}-{name}-{ben}-{t.ref}",
                "SBI": f"BY TRANSFER-NEFT*{pifsc}*{t.ref}*{name[:16]}--",
                "ICICI": f"NEFT-{t.ref}-{name}-{purpose}-XXXXXXXX{self.r.randrange(1000, 9999)}-{pifsc}",
                "AXIS": f"NEFT/{t.ref}/{name}/{purpose}",
                "KOTAK": f"NEFT {t.ref} {name} {purpose}".strip(),
                "CANARA": f"NEFT CR {t.ref} {name}",
                "BOB": f"NEFT-{t.ref}-{name}-{purpose}".rstrip("-"),
            }[bank]
        if k == "neft_out":
            return {"HDFC": f"NEFT DR-{ifsc}-{name}-NETBANK, MUM-{t.ref}-{note.upper()}", "SBI": f"TO TRANSFER-INB NEFT {t.ref} {name[:20]}--",
                    "ICICI": f"NEFT-{t.ref}-{name}-{note}", "AXIS": f"NEFT/{t.ref}/{name}", "KOTAK": f"NEFT {t.ref} {name}",
                    "CANARA": f"NEFT DR {t.ref} {name}", "BOB": f"NEFT-{t.ref}-{name}"}[bank]
        if k in ("imps_in", "self_in"):
            ob = self.r.choice(["SBIN", "HDFC", "ICIC", "UTIB", "KKBK"]) if k == "imps_in" else R.BANKS[bank]["ifsc"][:4]
            n = "SELF" if k == "self_in" else note
            return {"HDFC": f"IMPS-{t.ref}-{name}-{ob}-XXXXXXXX{self.r.randrange(1000, 9999)}-{n}",
                    "SBI": f"BY TRANSFER-IMPS/P2A/{t.ref}/{name[:20]}/{ob}/{n}--", "ICICI": f"MMT/IMPS/{t.ref}/{n}/{name[:15]}/{ob}",
                    "AXIS": f"IMPS/P2A/{t.ref}/{name[:20]}/{ob}/{n}", "KOTAK": f"IMPS-{t.ref}-{name}-{n}",
                    "CANARA": f"IMPS/{t.ref}/{name}", "BOB": f"IMPS/{t.ref}/{name}/{n}"}[bank]
        if k in ("imps_out", "self_out"):
            n = "SELF" if k == "self_out" else note
            tom = t.meta.get("to_masked", "")[-4:]
            return {"HDFC": f"IMPS-{t.ref}-{name}-XXXXXXXX{tom}-{n}", "SBI": f"TO TRANSFER-IMPS/{t.ref}/{name[:20]}/{n}--",
                    "ICICI": f"MMT/IMPS/{t.ref}/{n}/{name[:15]}", "AXIS": f"IMPS/P2A/{t.ref}/{name[:20]}/{n}",
                    "KOTAK": f"IMPS-{t.ref}-{name}-{n}", "CANARA": f"IMPS/{t.ref}/{name}", "BOB": f"IMPS/{t.ref}/{name}/{n}"}[bank]
        if k == "ach_dr":
            ref = (t.ref or "")[-12:]
            return {"HDFC": f"ACH D- {name}-{ref}", "SBI": f"DEBIT-ACHDr {ref} {name[:20]}", "ICICI": f"ACH/{name[:20]}/{ref}",
                    "AXIS": f"ACH-DR-{name[:20]}-{ref}", "KOTAK": f"ACH DR {name} {ref}", "CANARA": f"NACH DR {name} {ref}",
                    "BOB": f"ACH DR {name} {ref}"}[bank]
        if k == "atm_wd":
            atm = t.meta.get("atm_id", "ATM0001")
            loc = name.replace("ATM ", "")
            return {"HDFC": f"NWD-XXXXXXXXXXXX{acc.last4}-{atm}-{loc}", "SBI": f"ATM WDL-ATM CASH {atm[-4:]} {loc}",
                    "ICICI": f"ATM/CASH WDL/{atm}/{loc}", "AXIS": f"ATM-CASH/{loc}/{atm}", "KOTAK": f"ATL/{atm}/{t.ref}/{loc}",
                    "CANARA": f"ATM WDL {atm} {loc}", "BOB": f"ATM/{atm}/{loc}"}[bank]
        if k == "pos_dr":
            return {"HDFC": f"POS XXXXXXXXXXXX{acc.last4} {name}", "SBI": f"POS PRCH {name}--", "ICICI": f"POS/{name}/{self.b.s.city.upper()}",
                    "AXIS": f"POS/{name}/{self.b.s.city.upper()}", "KOTAK": f"PCD/{acc.last4}/{name}/{self.b.s.city.upper()}",
                    "CANARA": f"POS {name}", "BOB": f"POS/{name}"}[bank]
        if k == "charge":
            return {"SBI": f"{name} {t.note}--".strip(), "ICICI": f"{name}:{t.note}"}.get(bank, f"{name} {t.note}".strip())
        if k == "interest":
            frm, to = (t.note or " to ").split(" to ")
            return {"HDFC": f"INTEREST PAID TILL {to}", "SBI": "CREDIT INTEREST--", "ICICI": f"{acc.masked[-12:]}:Int.Pd:{frm} to {to}",
                    "AXIS": f"SB:{acc.masked[-6:]}:Int.Pd:{frm}:{to}", "KOTAK": f"Int.Pd:{acc.masked[-6:]}:{frm}-{to}",
                    "CANARA": "SB INT", "BOB": "INT. CREDIT"}[bank]
        if k == "cash_dep":
            return {"HDFC": f"CASH DEP {self.b.s.area.upper()}", "SBI": "CASH DEPOSIT SELF--", "ICICI": f"CASH DEP/{self.b.s.area.upper()}",
                    "AXIS": "CASH DEPOSIT", "KOTAK": "CASH DEPOSIT", "CANARA": "BY CASH", "BOB": f"BY CASH {self.b.s.area.upper()}"}[bank]
        if k == "fd_book":
            fd = name.replace("FD ", "")
            return {"HDFC": f"TRF TO FD NO {fd}", "SBI": f"TO TRANSFER-TRANSFER TO {fd}--", "ICICI": f"TO FD {fd}",
                    "AXIS": f"TRF TO FD {fd}", "KOTAK": f"FD BOOKED {fd}", "CANARA": f"TO FD {fd}", "BOB": f"TRF TO FD {fd}"}[bank]
        if k == "fd_maturity":
            fd = f"{self.r.randrange(10**10, 10**11)}"
            return {"HDFC": f"FD CLOSURE PROCEEDS {fd}", "SBI": f"BY TRANSFER-FD CLOSURE {fd}--", "ICICI": f"FD MATURITY/{fd}",
                    "AXIS": f"TD CLOSURE PROCEEDS {fd}", "KOTAK": f"FD MATURITY PROCEEDS {fd}", "CANARA": f"FD CLOSURE {fd}",
                    "BOB": f"BY TRF FD CLOSURE {fd}"}[bank]
        if k == "netbanking":
            return {"HDFC": f"NETBANKING TRF-{name}-{t.ref}", "SBI": f"TO TRANSFER-INB {name[:20]}--", "ICICI": f"BIL/INFT/{t.ref}/{name[:20]}",
                    "AXIS": f"IB/TPFT/{name[:20]}/{t.ref}", "KOTAK": f"IB {name} {t.ref}", "CANARA": f"INB {name}", "BOB": f"INB/{name}"}[bank]
        return f"{name} {t.note}".strip()

    def _card_narr(self, t) -> str:
        name = (t.cp_name or "").upper()
        if t.kind == "card_spend":
            city = CARD_CITY.get(t.merchant_key or "", self.b.s.city.upper())
            return f"{name[:22].strip()} {city[:13]} IN"
        if t.kind == "card_refund":
            return f"REFUND {name[:22]}"
        if t.kind == "card_payment_in":
            return self.r.choice(["PAYMENT RECEIVED - THANK YOU", "BBPS PAYMENT RECEIVED", "CC PAYMENT RECEIVED NETBANKING"])
        if t.kind == "fin_charge":
            return "FINANCE CHARGES"
        if t.kind == "fin_charge_gst":
            return "IGST ON FINANCE CHARGES"
        return name

    # ------------------------------------------------------------------ SMS
    def header(self, code: str) -> str:
        return f"{self.r.choice(R.SMS_HEADER_PREFIXES)}-{code}{self.r.choice(R.SMS_SUFFIXES)}"

    def add_sms(self, t, sender, body, tpl, gt, delay_s=(2, 90), holdout=False):
        self.sms_seq += 1
        sid = f"{self.b.s.user_id[:8]}-{self.sms_seq:06d}"   # user-scoped; never reveals the linked transaction
        received = (t.ts if t else gt.pop("_ts")) + timedelta(seconds=self.r.randint(*delay_s))
        self.sms.append(dict(sms_id=sid, user_id=self.b.s.user_id, sender_id=sender, body=body, received_at=received.isoformat(),
                             template_id=tpl, holdout=holdout, transaction_id=t.id if t else None, ground_truth=gt))
        if t:
            t.sms_ids.append(sid)

    def sms_for(self, t, acc):
        k = t.kind
        if t.status == "reversed" and t.direction == "debit":
            k2 = "upi_dr"
        elif k == "upi_reversal":
            k2 = "rev_cr"
        elif acc.type == "credit_card":
            k2 = {"card_spend": "card_spend", "card_payment_in": "card_payment", "card_refund": "card_refund"}.get(k)
        else:
            k2 = {"upi_p2m": "upi_dr", "upi_p2p_out": "upi_dr", "autopay": "upi_dr", "billpay": "upi_dr", "upi_in": "upi_cr",
                  "neft_in": "neft_cr", "imps_in": "imps_cr", "self_in": "imps_cr", "imps_out": "imps_dr", "self_out": "imps_dr",
                  "neft_out": "neft_dr", "atm_wd": "atm", "pos_dr": "pos", "ach_dr": "ach_dr", "cash_dep": "cash_dep",
                  "card_bill_pay": "upi_dr" if t.mode == "upi" else "neft_dr", "netbanking": "neft_dr", "fd_book": None,
                  "interest": None, "charge": None}.get(k)
        if not k2:
            return
        fn = getattr(self, f"_sms_{acc.bank.lower()}", None)
        if not fn:
            return
        out = fn(k2, t, acc)
        if not out:
            return
        tpl, body, acct_ref, cp_shown = out
        gt = dict(kind="credit" if t.direction == "credit" else "debit", amount_paise=t.amount, account_ref=acct_ref,
                  account_last4=acc.last4, counterparty=cp_shown, vpa=t.cp_vpa if t.cp_vpa and t.cp_vpa in body else None,
                  ref_no=t.ref if t.ref and t.ref in body else None, txn_date=t.ts.date().isoformat(),
                  balance_paise=t.balance_after if "Bal" in body or "bal" in body else None,
                  mode=t.mode, is_card=acc.type == "credit_card")
        codes = R.BANKS[acc.bank]["card_sms" if acc.type == "credit_card" else "sms"]
        code = codes[0]
        if acc.bank == "SBI" and acc.type != "credit_card":
            code = {"upi_dr": "SBIUPI", "upi_cr": "SBIUPI", "rev_cr": "SBIUPI", "atm": "ATMSBI"}.get(k2, "CBSSBI")
        delay = (60, 1800) if k2 in ("neft_cr", "ach_dr") else (2, 90)
        holdout = tpl.endswith(".v3")
        self.add_sms(t, self.header(code), body, tpl, gt, delay, holdout)

    def _dt(self, t, fmt):
        return t.ts.strftime(fmt)

    def _sms_hdfc(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        v = self.r.randint(1, 3)
        if k == "upi_dr":
            if v == 1:
                return ("hdfc.upi_dr.v1", f"Sent Rs.{rs(t.amount)}\nFrom HDFC Bank A/C *{a4}\nTo {cp}\nOn {self._dt(t, '%d/%m/%y')}\nRef {t.ref}\nNot You?\nCall 18002586161/SMS BLOCK UPI to 7308080808", a4, cp)
            if v == 2:
                return ("hdfc.upi_dr.v2", f"Money Sent! Rs.{rs(t.amount)} from HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%m-%y')} to {t.cp_vpa} (UPI Ref No {t.ref}). Not you? Call 18002586161", a4, None)
            return ("hdfc.upi_dr.v3", f"Rs {rs(t.amount)} debited from HDFC Bank A/c **{a4} on {self._dt(t, '%d-%m-%y')} to VPA {t.cp_vpa} (UPI Ref No {t.ref}). If not done by you, call 18002586161.", a4, None)
        if k == "upi_cr":
            if v <= 2:
                return ("hdfc.upi_cr.v1", f"Rs.{rs(t.amount)} credited to HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%m-%y')} by a/c linked to VPA {t.cp_vpa} (UPI Ref No  {t.ref}).", a4, None)
            return ("hdfc.upi_cr.v3", f"Received Rs.{rs(t.amount)} in your HDFC Bank A/c *{a4} from {cp} on {self._dt(t, '%d/%m/%y')}. UPI Ref {t.ref}", a4, cp)
        if k == "rev_cr":
            return ("hdfc.rev_cr.v1", f"Rs.{rs(t.amount)} reversed to HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%m-%y')} for UPI Ref No {t.ref}.", a4, None)
        if k == "neft_cr":
            return ("hdfc.neft_cr.v1", f"Update! INR {rs(t.amount, True)} deposited in HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%b-%y').upper()} for NEFT Cr-{t.ref}-{cp}.Avl bal INR {rs(t.balance_after, True)}. Cheque deposits in A/C are subject to clearing", a4, cp)
        if k == "imps_cr":
            return ("hdfc.imps_cr.v1", f"Rs.{rs(t.amount)} credited to HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%m-%y')} by IMPS Ref No {t.ref} from {cp}.", a4, cp)
        if k in ("imps_dr", "neft_dr"):
            return (f"hdfc.{k}.v1", f"Rs.{rs(t.amount)} debited from A/c XX{a4} on {self._dt(t, '%d-%m-%y')} to {cp} via {'IMPS' if k == 'imps_dr' else 'NEFT'}. Ref {t.ref}. Not you? Call 18002586161", a4, cp)
        if k == "atm":
            return ("hdfc.atm.v1", f"Rs.{rs(t.amount)} withdrawn from HDFC Bank Card x{a4} at {cp} on {self._dt(t, '%d-%m-%y %H:%M')}. Avl bal: Rs {rs(t.balance_after, True)}. Not you? Call 18002586161", a4, cp)
        if k == "pos":
            return ("hdfc.pos.v1", f"Spent Rs.{rs(t.amount)} From HDFC Bank Debit Card x{a4} At {cp} On {self._dt(t, '%Y-%m-%d:%H:%M:%S')}. Not You? Call 18002586161", a4, cp)
        if k == "ach_dr":
            return ("hdfc.ach_dr.v1", f"Rs.{rs(t.amount)} debited from A/c XX{a4} on {self._dt(t, '%d-%m-%y')} towards ACH {cp}. Avl Bal Rs.{rs(t.balance_after, True)}", a4, cp)
        if k == "cash_dep":
            return ("hdfc.cash_dep.v1", f"INR {rs(t.amount, True)} deposited in HDFC Bank A/c XX{a4} on {self._dt(t, '%d-%b-%y').upper()} by CASH. Avl bal INR {rs(t.balance_after, True)}", a4, None)
        if k == "card_spend":
            if v <= 2:
                return ("hdfc.card_spend.v1", f"Spent Rs.{rs(t.amount)} On HDFC Bank Card {a4} At {cp} On {self._dt(t, '%Y-%m-%d:%H:%M:%S')}.Not You? To Block+Reissue Call 18002586161/SMS BLOCK CC {a4} to 7308080808", a4, cp)
            return ("hdfc.card_spend.v3", f"Rs.{rs(t.amount)} spent on HDFC Bank Card ending {a4} at {cp} on {self._dt(t, '%d-%m-%Y')}. Avl Lmt: Rs.{rs(acc.card_limit - t.balance_after, True)}", a4, cp)
        if k == "card_payment":
            return ("hdfc.card_payment.v1", f"DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. {rs(t.amount, True)} RECEIVED TOWARDS YOUR CREDIT CARD ENDING WITH {a4} ON {self._dt(t, '%d-%m-%Y')}.YOUR AVAILABLE LIMIT IS Rs. {rs(acc.card_limit - t.balance_after, True)}", a4, None)
        if k == "card_refund":
            return ("hdfc.card_refund.v1", f"Refund of Rs.{rs(t.amount)} from {cp} credited to HDFC Bank Card {a4} on {self._dt(t, '%d-%m-%y')}.", a4, cp)

    def _sms_sbi(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        v = self.r.randint(1, 3)
        if k == "upi_dr":
            if v <= 2:
                return ("sbi.upi_dr.v1", f"Dear UPI user A/C X{a4} debited by {sbi_amt(t.amount)} on date {self._dt(t, '%d%b%y')} trf to {cp} Refno {t.ref} If not u? call-1800111109 for other services-18001234-SBI", a4, cp)
            return ("sbi.upi_dr.v3", f"Dear SBI User, your A/c X{a4}-debited by Rs{sbi_amt(t.amount)} on {self._dt(t, '%d%b%y')} transfer to {cp} Ref No {t.ref}. If not done by you, call 1800111109 -SBI", a4, cp)
        if k == "upi_cr":
            return ("sbi.upi_cr.v1", f"Dear SBI UPI User, ur A/cX{a4} credited by Rs{sbi_amt(t.amount)} on {self._dt(t, '%d%b%y')} by  (Ref no {t.ref})", a4, None)
        if k == "rev_cr":
            return ("sbi.rev_cr.v1", f"Dear SBI UPI User, Rs{sbi_amt(t.amount)} reversed to your A/c X{a4} on {self._dt(t, '%d%b%y')} (Ref no {t.ref}) -SBI", a4, None)
        if k == "neft_cr":
            return ("sbi.neft_cr.v1", f"Dear Customer, INR {rs(t.amount, True)} credited to your A/c No XX{a4} on {self._dt(t, '%d/%m/%Y')} through NEFT with UTR {t.ref} by {cp}, INFO: {(t.note or '').upper()}. -SBI", a4, cp)
        if k == "imps_cr":
            return ("sbi.imps_cr.v1", f"Dear Customer, Your A/c XX{a4} has been credited with INR {rs(t.amount, True)} on {self._dt(t, '%d/%m/%Y')} by IMPS Ref {t.ref} from {cp}. -SBI", a4, cp)
        if k in ("imps_dr", "neft_dr"):
            return (f"sbi.{k}.v1", f"Your A/C XXXXX{a4} Debited INR {rs(t.amount, True)} on {self._dt(t, '%d/%m/%y')} -Transferred to {cp}. Avl Balance INR {rs(t.balance_after, True)}-SBI", a4, cp)
        if k == "atm":
            return ("sbi.atm.v1", f"Dear Customer, Your A/C XXXXX{a4} has a debit by ATM withdrawal of Rs {rs(t.amount, True)} on {self._dt(t, '%d%b%y')}. Avl Bal Rs {rs(t.balance_after, True)}.If not done by you, forward this SMS to 7400165218/ call 1800111109 to block card. -SBI", a4, None)
        if k == "pos":
            return ("sbi.pos.v1", f"Your A/C XXXXX{a4} Debited INR {rs(t.amount, True)} on {self._dt(t, '%d/%m/%y')} -Purchase at {cp}. Avl Balance INR {rs(t.balance_after, True)}-SBI", a4, cp)
        if k == "ach_dr":
            return ("sbi.ach_dr.v1", f"Your A/C XXXXX{a4} Debited INR {rs(t.amount, True)} on {self._dt(t, '%d/%m/%y')} -ACH-{cp}. Avl Balance INR {rs(t.balance_after, True)}-SBI", a4, cp)
        if k == "cash_dep":
            return ("sbi.cash_dep.v1", f"Your A/C XXXXX{a4} Credited INR {rs(t.amount, True)} on {self._dt(t, '%d/%m/%y')} -Deposit by Cash. Avl Balance INR {rs(t.balance_after, True)}-SBI", a4, None)
        if k == "card_spend":
            return ("sbi.card_spend.v1", f"Rs.{rs(t.amount)} spent on your SBI Credit Card ending {a4} at {cp} on {self._dt(t, '%d/%m/%y')}. Trxn. not done by you? Report at https://sbicard.com/Dispute", a4, cp)
        if k == "card_payment":
            return ("sbi.card_payment.v1", f"We have received payment of Rs.{rs(t.amount, True)} via BBPS towards your SBI Credit Card ending with {a4} on {self._dt(t, '%d/%m/%y')}. Your available limit is Rs.{rs(acc.card_limit - t.balance_after, True)}.", a4, None)
        if k == "card_refund":
            return ("sbi.card_refund.v1", f"Refund of Rs.{rs(t.amount)} from {cp} credited to your SBI Credit Card ending {a4} on {self._dt(t, '%d/%m/%y')}.", a4, cp)

    def _sms_icici(self, k, t, acc):
        a3 = acc.last4[-3:]
        cp = (t.cp_name or "").upper()[:25]
        v = self.r.randint(1, 3)
        if k == "upi_dr":
            if v <= 2:
                return ("icici.upi_dr.v1", f"ICICI Bank Acct XX{a3} debited for Rs {rs(t.amount)} on {self._dt(t, '%d-%b-%y')}; {cp} credited. UPI:{t.ref}. Call 18002662 for dispute. SMS BLOCK {a3} to 9215676766.", a3, cp)
            return ("icici.upi_dr.v3", f"Dear Customer, Acct XX{a3} is debited with INR {rs(t.amount)} on {self._dt(t, '%d-%b-%y')} towards {t.cp_vpa}. UPI Ref {t.ref}. Not you? SMS BLOCK {a3} to 9215676766", a3, None)
        if k == "upi_cr":
            return ("icici.upi_cr.v1", f"Dear Customer, Acct XX{a3} is credited with Rs {rs(t.amount)} on {self._dt(t, '%d-%b-%y')} from {cp}. UPI:{t.ref}-ICICI Bank.", a3, cp)
        if k == "rev_cr":
            return ("icici.rev_cr.v1", f"Dear Customer, Rs {rs(t.amount)} has been reversed to Acct XX{a3} on {self._dt(t, '%d-%b-%y')}. UPI:{t.ref}-ICICI Bank.", a3, None)
        if k == "neft_cr":
            return ("icici.neft_cr.v1", f"ICICI Bank Account XX{a3} credited:Rs. {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')}. Info NEFT-{t.ref}-{cp}. Available Balance is Rs. {rs(t.balance_after, True)}.", a3, cp)
        if k == "imps_cr":
            return ("icici.imps_cr.v1", f"ICICI Bank Account XX{a3} credited:Rs. {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')}. Info IMPS-{t.ref}-{cp}. Available Balance is Rs. {rs(t.balance_after, True)}.", a3, cp)
        if k in ("imps_dr", "neft_dr"):
            return (f"icici.{k}.v1", f"ICICI Bank Acct XX{a3} debited with Rs {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')} & Acct of {cp} credited. {'IMPS' if k == 'imps_dr' else 'NEFT'}:{t.ref}. Call 18002662 for dispute.", a3, cp)
        if k == "atm":
            return ("icici.atm.v1", f"ICICI Bank Acct XX{a3} debited with INR {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')} at ATM {cp}. Avl Bal INR {rs(t.balance_after, True)}.", a3, None)
        if k == "pos":
            return ("icici.pos.v1", f"INR {rs(t.amount, True)} spent using ICICI Bank Debit Card XX{acc.last4} on {self._dt(t, '%d-%b-%y')} at {cp}. Avl Bal: INR {rs(t.balance_after, True)}.", acc.last4, cp)
        if k == "ach_dr":
            return ("icici.ach_dr.v1", f"ICICI Bank Acct XX{a3} debited with Rs {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')} towards {cp} (NACH). Avl Bal Rs {rs(t.balance_after, True)}.", a3, cp)
        if k == "cash_dep":
            return ("icici.cash_dep.v1", f"ICICI Bank Account XX{a3} credited:Rs. {rs(t.amount, True)} on {self._dt(t, '%d-%b-%y')}. Info CASH DEP. Available Balance is Rs. {rs(t.balance_after, True)}.", a3, None)
        if k == "card_spend":
            if v <= 2:
                return ("icici.card_spend.v1", f"INR {rs(t.amount, True)} spent using ICICI Bank Card XX{acc.last4} on {self._dt(t, '%d-%b-%y')} on {cp}. Avl Limit: INR {rs(acc.card_limit - t.balance_after, True)}. If not you, call 1800 2662/SMS BLOCK {acc.last4} to 9215676766.", acc.last4, cp)
            return ("icici.card_spend.v3", f"Your ICICI Bank Credit Card XX{acc.last4} has been used for a transaction of INR {rs(t.amount, True)} on {self._dt(t, '%b %d, %Y at %I:%M:%S')}. Info: {cp}.", acc.last4, cp)
        if k == "card_payment":
            return ("icici.card_payment.v1", f"Dear Customer, Payment of INR {rs(t.amount, True)} has been received on your ICICI Bank Credit Card Account {acc.last4[:2]}XX...XX{acc.last4} on {self._dt(t, '%d-%b-%y')}.Thank you.", acc.last4, None)
        if k == "card_refund":
            return ("icici.card_refund.v1", f"Dear Customer, a refund of INR {rs(t.amount, True)} from {cp} has been credited to your ICICI Bank Credit Card XX{acc.last4} on {self._dt(t, '%d-%b-%y')}.", acc.last4, cp)

    def _sms_axis(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        if k == "upi_dr":
            kind = "P2A" if t.kind == "upi_p2p_out" else "P2M"
            return ("axis.upi_dr.v1", f"INR {rs(t.amount)} debited\nA/c no. XX{a4}\n{self._dt(t, '%d-%m-%y, %H:%M:%S')}\nUPI/{kind}/{t.ref}/{cp[:20]}\nNot you? SMS BLOCKUPI Cust ID to 919951860002\nAxis Bank", a4, cp[:20])
        if k == "upi_cr":
            return ("axis.upi_cr.v1", f"INR {rs(t.amount)} credited\nA/c no. XX{a4}\n{self._dt(t, '%d-%m-%y, %H:%M:%S')} IST\nUPI/P2A/{t.ref}/{cp[:20]}\n- Axis Bank", a4, cp[:20])
        if k == "rev_cr":
            return ("axis.rev_cr.v1", f"INR {rs(t.amount)} credited (reversal)\nA/c no. XX{a4}\n{self._dt(t, '%d-%m-%y, %H:%M:%S')}\nUPI/REV/{t.ref}\n- Axis Bank", a4, None)
        if k in ("neft_cr", "imps_cr"):
            return (f"axis.{k}.v1", f"INR {rs(t.amount, True)} credited to A/c no. XX{a4} on {self._dt(t, '%d-%m-%y, %H:%M:%S')} IST. Info- {'NEFT' if k == 'neft_cr' else 'IMPS'}/{t.ref}/{cp}. Avl Bal-INR {rs(t.balance_after, True)} - Axis Bank", a4, cp)
        if k in ("imps_dr", "neft_dr", "ach_dr", "pos"):
            info = {"imps_dr": "IMPS", "neft_dr": "NEFT", "ach_dr": "ACH-DR", "pos": "POS"}[k]
            return (f"axis.{k}.v1", f"INR {rs(t.amount, True)} debited from A/c no. XX{a4} on {self._dt(t, '%d-%m-%y, %H:%M:%S')} IST. Info- {info}/{cp}. Avl Bal-INR {rs(t.balance_after, True)} - Axis Bank", a4, cp)
        if k == "atm":
            return ("axis.atm.v1", f"INR {rs(t.amount, True)} withdrawn from A/c no. XX{a4} on {self._dt(t, '%d-%m-%y, %H:%M:%S')} IST at ATM. Avl Bal-INR {rs(t.balance_after, True)} - Axis Bank", a4, None)
        if k == "cash_dep":
            return ("axis.cash_dep.v1", f"INR {rs(t.amount, True)} credited to A/c no. XX{a4} on {self._dt(t, '%d-%m-%y, %H:%M:%S')} IST. Info- CASH DEPOSIT. Avl Bal-INR {rs(t.balance_after, True)} - Axis Bank", a4, None)
        if k == "card_spend":
            return ("axis.card_spend.v1", f"Spent\nCard no. XX{a4}\nINR {rs(t.amount, True)}\n{self._dt(t, '%d-%m-%y %H:%M:%S')}\n{cp[:20]}\nAvl Lmt INR {rs(acc.card_limit - t.balance_after, True)}\nSMS BLOCK {a4} to 919951860002, if not you - Axis Bank", a4, cp[:20])
        if k == "card_payment":
            return ("axis.card_payment.v1", f"Payment of INR {rs(t.amount, True)} received towards your Axis Bank Credit Card no. XX{a4} on {self._dt(t, '%d-%m-%y')}. Available limit: INR {rs(acc.card_limit - t.balance_after, True)}", a4, None)
        if k == "card_refund":
            return ("axis.card_refund.v1", f"Refund of INR {rs(t.amount, True)} from {cp} credited to Axis Bank Credit Card no. XX{a4} on {self._dt(t, '%d-%m-%y')}.", a4, cp)

    def _sms_kotak(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        if k == "upi_dr":
            return ("kotak.upi_dr.v1", f"Sent Rs.{rs(t.amount)} from Kotak Bank A/c X{a4} to {t.cp_vpa} on {self._dt(t, '%d-%m-%y')}.UPI Ref {t.ref}. Not you, https://kotak.com/KBANKT/Fraud", a4, None)
        if k == "upi_cr":
            return ("kotak.upi_cr.v1", f"Received Rs.{rs(t.amount)} in your Kotak Bank A/c X{a4} from {t.cp_vpa} on {self._dt(t, '%d-%m-%y')}.UPI Ref:{t.ref}.", a4, None)
        if k == "rev_cr":
            return ("kotak.rev_cr.v1", f"Rs.{rs(t.amount)} reversed to your Kotak Bank A/c X{a4} on {self._dt(t, '%d-%m-%y')}.UPI Ref:{t.ref}.", a4, None)
        if k in ("neft_cr", "imps_cr", "cash_dep"):
            via = {"neft_cr": "NEFT", "imps_cr": "IMPS", "cash_dep": "CASH"}[k]
            return (f"kotak.{k}.v1", f"Rs {rs(t.amount, True)} is credited in your Kotak Bank A/c XX{a4} by {via} {t.ref or ''} from {cp} on {self._dt(t, '%d-%m-%y')}. Updated Bal:Rs {rs(t.balance_after, True)}", a4, cp if k != "cash_dep" else None)
        if k in ("imps_dr", "neft_dr", "ach_dr", "pos", "atm"):
            via = {"imps_dr": "IMPS", "neft_dr": "NEFT", "ach_dr": "NACH", "pos": "Debit Card", "atm": "ATM"}[k]
            return (f"kotak.{k}.v1", f"Rs.{rs(t.amount)} debited from Kotak Bank A/c X{a4} on {self._dt(t, '%d-%m-%y')} by {via}{(' to ' + cp) if k != 'atm' else ''}. Bal:Rs.{rs(t.balance_after)}", a4, cp if k != "atm" else None)
        if k == "card_spend":
            return ("kotak.card_spend.v1", f"Rs.{rs(t.amount)} spent on Kotak Credit Card x{a4} at {cp} on {self._dt(t, '%d/%m/%Y')}. Avl limit Rs.{rs(acc.card_limit - t.balance_after)}. Not you? Call 18602662666", a4, cp)
        if k == "card_payment":
            return ("kotak.card_payment.v1", f"Payment of Rs.{rs(t.amount)} received on your Kotak Credit Card x{a4} on {self._dt(t, '%d/%m/%Y')}. Thank you.", a4, None)
        if k == "card_refund":
            return ("kotak.card_refund.v1", f"Refund of Rs.{rs(t.amount)} from {cp} credited to your Kotak Credit Card x{a4} on {self._dt(t, '%d/%m/%Y')}.", a4, cp)

    def _sms_canara(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        if k in ("upi_dr", "imps_dr", "neft_dr", "ach_dr", "pos", "atm"):
            return (f"canara.{k}.v1", f"An amount of INR {rs(t.amount, True)} has been DEBITED to your account XXX{a4} on {self._dt(t, '%d/%m/%Y')} towards {('UPI/' + str(t.ref)) if k == 'upi_dr' else cp}. Total Avail.bal INR {rs(t.balance_after, True)}. - Canara Bank", a4, None if k == "upi_dr" else cp)
        if k in ("upi_cr", "imps_cr", "neft_cr", "cash_dep", "rev_cr"):
            return (f"canara.{k}.v1", f"An amount of INR {rs(t.amount, True)} has been CREDITED to your account XXX{a4} on {self._dt(t, '%d/%m/%Y')} {('UPI Ref ' + str(t.ref)) if t.ref else ''}. Total Avail.bal INR {rs(t.balance_after, True)}. - Canara Bank", a4, None)

    def _sms_bob(self, k, t, acc):
        a4 = acc.last4
        cp = (t.cp_name or "").upper()[:25]
        if k == "upi_dr":
            return ("bob.upi_dr.v1", f"Rs.{rs(t.amount)} Dr. from A/C XXXXXX{a4} and Cr. to {t.cp_vpa}. Ref:{t.ref}. AvlBal:Rs{rs(t.balance_after)}({self._dt(t, '%Y:%m:%d %H:%M:%S')}). Not you? Call 18005700-BOB", a4, None)
        if k in ("upi_cr", "rev_cr"):
            return (f"bob.{k}.v1", f"Rs.{rs(t.amount)} Credited to A/c ...{a4} thru UPI/{t.ref} by {t.cp_vpa}. Total Bal:Rs.{rs(t.balance_after)}CR. Avlbl Amt:Rs.{rs(t.balance_after)}({self._dt(t, '%d-%m-%Y')}) - Bank of Baroda", a4, None)
        if k in ("neft_cr", "imps_cr", "cash_dep"):
            return (f"bob.{k}.v1", f"Rs.{rs(t.amount)} Credited to A/c ...{a4} thru {'NEFT' if k == 'neft_cr' else 'IMPS' if k == 'imps_cr' else 'CASH'} {t.ref or ''} by {cp}. Total Bal:Rs.{rs(t.balance_after)}CR. ({self._dt(t, '%d-%m-%Y')}) - Bank of Baroda", a4, cp)
        if k in ("imps_dr", "neft_dr", "ach_dr", "pos", "atm"):
            return (f"bob.{k}.v1", f"Rs.{rs(t.amount)} Dr. from A/C XXXXXX{a4} towards {cp}. Ref:{t.ref or 'NA'}. AvlBal:Rs{rs(t.balance_after)}({self._dt(t, '%Y:%m:%d %H:%M:%S')}) - BOB", a4, cp)

    # ------------------------------------------------------------------ noise SMS the parser must ignore
    def noise_sms(self):
        s = self.b.s
        accs = list(self.b.accounts.values())
        for t in self.b.accepted:
            acc = self.b.by_id[t.account_id]
            if acc.type == "credit_card" and t.kind == "card_spend" and t.merchant_key in ("amazon", "flipkart", "myntra", "makemytrip", "nykaa") and self.r.random() < 0.7:
                otp = self.r.randrange(100000, 999999)
                body = (f"{otp} is OTP for txn of INR {rs(t.amount, True)} at {t.cp_name} on card ending {acc.last4}. "
                        f"Valid till {(t.ts + timedelta(minutes=5)).strftime('%H:%M')}. Do not share OTP for security reasons.")
                gt = dict(kind="ignore", reason="otp", _ts=t.ts - timedelta(seconds=40))
                self.add_sms(None, self.header(R.BANKS[acc.bank]["card_sms"][0]), body, f"{acc.bank.lower()}.otp.v1", gt, (0, 5))
        from datetime import date as _date, datetime as _dt
        from .engine import IST
        for ms_i in range(13):
            acc = self.r.choice(accs)
            d = R.START + timedelta(days=30 * ms_i + self.r.randrange(25))
            if d > R.END:
                continue
            ts = _dt(d.year, d.month, d.day, self.r.randint(9, 20), self.r.randrange(60), tzinfo=IST)
            promos = [
                f"Pre-approved Personal Loan of up to Rs {self.r.choice(['2,00,000', '5,00,000', '8,50,000'])} is waiting for you! Instant disbursal. T&C. Apply: https://bit.ly/x{self.r.randrange(1000, 9999)}",
                f"Upgrade your {R.BANKS[acc.bank]['name']} Debit Card to Platinum and get 5% cashback on dining. Reply YES to 5676766. T&C apply.",
                f"Your A/c XX{acc.last4} balance is low? Get instant overdraft up to Rs 50,000. Visit app. T&C.",
                f"Dear Customer, update your KYC to continue uninterrupted services. Visit branch with Aadhaar & PAN. Ignore if already done. -{R.BANKS[acc.bank]['name']}",
            ]
            gt = dict(kind="ignore", reason="promo", _ts=ts)
            self.add_sms(None, f"{self.r.choice(R.SMS_HEADER_PREFIXES)}-{R.BANKS[acc.bank]['sms'][0]}-P", self.r.choice(promos),
                         f"{acc.bank.lower()}.promo.v1", gt, (0, 1))
        for acc in accs:
            if acc.type == "credit_card":
                for st in acc.statements:
                    if st["total_due_paise"] <= 0:
                        continue
                    sd = _date.fromisoformat(st["statement_date"])
                    ts = _dt(sd.year, sd.month, sd.day, 21, 30, tzinfo=IST)
                    body = (f"Your {R.BANKS[acc.bank]['name']} Credit Card XX{acc.last4} statement is generated. Total Amt Due: Rs {rs(st['total_due_paise'], True)}; "
                            f"Min Amt Due: Rs {rs(st['min_due_paise'], True)}; Due by {_date.fromisoformat(st['due_date']).strftime('%d-%b-%y')}. Pay via app.")
                    gt = dict(kind="ignore", reason="statement_notice", _ts=ts, total_due_paise=st["total_due_paise"], min_due_paise=st["min_due_paise"])
                    self.add_sms(None, self.header(R.BANKS[acc.bank]["card_sms"][0]), body, f"{acc.bank.lower()}.statement.v1", gt, (0, 60))

    # ------------------------------------------------------------------ AA JSON
    def aa_json(self, acc, txns: list) -> dict:
        s = self.b.s
        holder = dict(name=s.full_name.upper(), dob=f"{2026 - s.age}-{self.r.randint(1, 12):02d}-{self.r.randint(1, 28):02d}",
                      mobile="XXXXXX" + f"{self.r.randrange(10000):04d}", nominee="REGISTERED",
                      email=f"{s.first_name.lower()}.{self.r.randrange(100, 999)}@example.com",
                      pan="XXXXX" + f"{self.r.randrange(10000):04d}" + "X", ckycCompliance=True)
        mode_map = {"upi": "UPI", "autopay": "UPI", "neft": "FT", "imps": "FT", "rtgs": "FT", "atm": "ATM", "card": "CARD",
                    "cash": "CASH", "nach": "OTHERS", "interest": "OTHERS", "other": "OTHERS"}
        if acc.type == "credit_card":
            last = acc.statements[-1] if acc.statements else {}
            fc = sum(t.amount for t in txns if t.kind in ("fin_charge", "fin_charge_gst"))
            return {"Account": {
                "type": "credit_card", "maskedCardNumber": acc.masked, "version": "1.1", "linkedAccRef": acc.id,
                "Profile": {"Holders": {"type": "SINGLE", "Holder": [holder]}},
                "Summary": {"issuerName": R.BANKS[acc.bank]["name"], "cardType": self.r.choice(["VISA", "MASTERCARD", "RUPAY"]),
                            "primary": "YES", "creditLimit": rs(acc.card_limit), "cashLimit": rs(acc.card_limit * 2 // 10),
                            "availableCredit": rs(acc.card_limit - max(0, acc.balance)), "currentDue": rs(max(0, acc.balance)),
                            "lastStatementDate": last.get("statement_date"), "dueDate": last.get("due_date"),
                            "totalDueAmount": rs(last.get("total_due_paise", 0)), "minDueAmount": rs(last.get("min_due_paise", 0)),
                            "previousDueAmount": rs(acc.statements[-2]["total_due_paise"]) if len(acc.statements) > 1 else "0.00",
                            "financeCharges": rs(fc), "loyaltyPoints": str(self.r.randrange(200, 9000)),
                            "annualInterestRatePercent": f"{acc.card_rate_bps / 100:.2f}"},
                "Statements": acc.statements,
                "Transactions": {"startDate": R.START.isoformat(), "endDate": R.END.isoformat(), "Transaction": [
                    {"txnId": t.id, "txnType": "DEBIT" if t.direction == "debit" else "CREDIT", "mcc": MCC.get(t.category),
                     "amount": rs(t.amount), "txnDate": t.ts.isoformat(), "valueDate": t.ts.date().isoformat(),
                     "narration": t.narration, "reference": t.ref or ""} for t in txns]}}}
        bal_end = acc.balance
        return {"Account": {
            "type": "deposit", "maskedAccNumber": acc.masked, "version": "1.1", "linkedAccRef": acc.id,
            "Profile": {"Holders": {"type": "SINGLE", "Holder": [holder]}},
            "Summary": {"currentBalance": rs(bal_end), "currency": "INR", "exchgeRate": "", "balanceDateTime": f"{R.END.isoformat()}T23:59:59+05:30",
                        "type": "SAVINGS" if acc.type == "savings" else "CURRENT", "branch": f"{s.area.upper()}, {s.city.upper()}",
                        "facility": "OD" if acc.type == "current" else "", "ifscCode": acc.ifsc, "micrCode": f"{self.r.randrange(10**8, 10**9)}",
                        "openingDate": acc.opened.isoformat(), "currentODLimit": "0", "drawingLimit": "0", "status": "ACTIVE",
                        "Pending": {"transactionType": "DEBIT", "amount": "0.00"}},
            "Transactions": {"startDate": R.START.isoformat(), "endDate": R.END.isoformat(), "Transaction": [
                {"txnId": t.id, "type": "DEBIT" if t.direction == "debit" else "CREDIT", "mode": mode_map.get(t.mode, "OTHERS"),
                 "amount": rs(t.amount), "currentBalance": rs(t.balance_after), "transactionTimestamp": t.ts.isoformat(),
                 "valueDate": t.ts.date().isoformat(), "narration": t.narration, "reference": t.ref or ""} for t in txns]}}}
