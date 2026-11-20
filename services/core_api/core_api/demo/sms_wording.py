"""Writes a synthetic bank SMS in the wording that bank uses, for the demo presets.

The demo adds a transaction the way a real one would arrive: as an SMS that goes through the
parser. These wordings are the ones in the synthetic dataset. Nothing here reads a real SMS.
"""

from __future__ import annotations

from datetime import datetime

from pocket_common.money import group_indian

_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _plain(paise: int) -> str:
    return f"{paise // 100}.{paise % 100:02d}"


def _commas(paise: int) -> str:
    return f"{group_indian(paise // 100)}.{paise % 100:02d}"


def bank_of(institution_code: str | None, institution: str | None) -> str:
    text = f"{institution_code or ''} {institution or ''}".lower()
    for bank, words in (("hdfc", ("hdfc",)), ("icici", ("icici",)), ("sbi", ("sbi", "state bank")), ("axis", ("axis",)),
                        ("kotak", ("kotak",)), ("bob", ("bob", "baroda")), ("canara", ("canara",))):
        if any(w in text for w in words):
            return bank
    return "other"


def upi_debit(bank: str, *, paise: int, last4: str, when: datetime, ref: str, name: str, vpa: str, balance_paise: int) -> tuple[str, str]:
    """(sender_id, body) for a UPI payment out of the account."""
    d = when
    if bank == "hdfc":
        return "VM-HDFCBK-S", (f"Money Sent! Rs.{_plain(paise)} from HDFC Bank A/c XX{last4} on {d:%d-%m-%y} to {vpa} "
                               f"(UPI Ref No {ref}). Not you? Call 18002586161")
    if bank == "sbi":
        amount = f"{paise // 100}.0" if paise % 100 == 0 else _plain(paise)
        return "VM-SBIUPI", (f"Dear UPI user A/C X{last4} debited by {amount} on date {d:%d}{_MON[d.month - 1]}{d:%y} trf to "
                             f"{name.upper()} Refno {ref} If not u? call-1800111109 for other services-18001234-SBI")
    if bank == "icici":
        return "JM-ICICIT", (f"ICICI Bank Acct XX{last4[-3:]} debited for Rs {_commas(paise)} on {d:%d}-{_MON[d.month - 1]}-{d:%y}; "
                             f"{name.upper()} credited. UPI:{ref}. Call 18002662 for dispute. SMS BLOCK {last4[-3:]} to 9215676766.")
    if bank == "axis":
        return "VK-AXISBK-T", (f"INR {_plain(paise)} debited\nA/c no. XX{last4}\n{d:%d-%m-%y}, {d:%H:%M:%S}\nUPI/P2M/{ref}/{name.upper()}\n"
                               "Not you? SMS BLOCKUPI Cust ID to 919951860002\nAxis Bank")
    if bank == "kotak":
        return "QP-KOTAKB-T", (f"Sent Rs.{_plain(paise)} from Kotak Bank A/c X{last4} to {vpa} on {d:%d-%m-%y}.UPI Ref {ref}. "
                               "Not you, https://kotak.com/KBANKT/Fraud")
    if bank == "bob":
        return "DM-BOBTXN", (f"Rs.{_plain(paise)} Dr. from A/C XXXXXX{last4} and Cr. to {vpa}. Ref:{ref}. "
                             f"AvlBal:Rs{_plain(balance_paise)}({d:%Y:%m:%d %H:%M:%S}). Not you? Call 18005700-BOB")
    return "VM-POCKET", f"Rs.{_plain(paise)} debited from A/c XX{last4} on {d:%d-%m-%y} to {vpa} (UPI Ref No {ref})."


def imps_credit(bank: str, *, paise: int, last4: str, when: datetime, ref: str, name: str, balance_paise: int) -> tuple[str, str]:
    """(sender_id, body) for money arriving by IMPS."""
    d, who = when, name.upper()
    if bank == "hdfc":
        return "VK-HDFCBK-S", f"Rs.{_plain(paise)} credited to HDFC Bank A/c XX{last4} on {d:%d-%m-%y} by IMPS Ref No {ref} from {who}."
    if bank == "sbi":
        return "BZ-CBSSBI-S", (f"Dear Customer, Your A/c XX{last4} has been credited with INR {_commas(paise)} on {d:%d/%m/%Y} "
                               f"by IMPS Ref {ref} from {who}. -SBI")
    if bank == "icici":
        return "CP-ICICIT", (f"ICICI Bank Account XX{last4[-3:]} credited:Rs. {_commas(paise)} on {d:%d}-{_MON[d.month - 1]}-{d:%y}. "
                             f"Info IMPS-{ref}-{who}. Available Balance is Rs. {_commas(balance_paise)}.")
    if bank == "axis":
        return "DM-AXISBK", (f"INR {_commas(paise)} credited to A/c no. XX{last4} on {d:%d-%m-%y}, {d:%H:%M:%S} IST. "
                             f"Info- IMPS/{ref}/{who}. Avl Bal-INR {_commas(balance_paise)} - Axis Bank")
    if bank == "kotak":
        return "DM-KOTAKB-S", (f"Rs {_commas(paise)} is credited in your Kotak Bank A/c XX{last4} by IMPS {ref} from {who} "
                               f"on {d:%d-%m-%y}. Updated Bal:Rs {_commas(balance_paise)}")
    if bank == "bob":
        return "QP-BOBTXN-S", (f"Rs.{_plain(paise)} Credited to A/c ...{last4} thru IMPS {ref} by {who}. "
                               f"Total Bal:Rs.{_plain(balance_paise)}CR. ({d:%d-%m-%Y}) - Bank of Baroda")
    return "VM-POCKET", f"Rs.{_plain(paise)} credited to A/c XX{last4} on {d:%d-%m-%y} by IMPS Ref No {ref} from {who}."


SENDERS = {"hdfc": "VM-HDFCBK-S", "sbi": "VM-CBSSBI", "icici": "JM-ICICIT", "axis": "VK-AXISBK-T", "kotak": "QP-KOTAKB-T",
           "bob": "DM-BOBTXN", "canara": "AD-CANBNK-T"}
BANK_NAMES = {"hdfc": "HDFC Bank", "sbi": "SBI", "icici": "ICICI Bank", "axis": "Axis Bank", "kotak": "Kotak", "bob": "Bank of Baroda",
              "canara": "Canara Bank"}


def upi_debit_to_name(bank: str, *, paise: int, last4: str, when: datetime, ref: str, name: str, balance_paise: int) -> tuple[str, str]:
    """A UPI payment where only the payee's name is known. Banks that normally print the VPA use
    their name wording instead."""
    d, who = when, name.upper()
    if bank == "hdfc":
        return "DM-HDFCBK", (f"Sent Rs.{_plain(paise)}\nFrom HDFC Bank A/C *{last4}\nTo {who}\nOn {d:%d/%m/%y}\nRef {ref}\nNot You?\n"
                             "Call 18002586161/SMS BLOCK UPI to 7308080808")
    if bank == "kotak":
        return "QP-KOTAKB-T", (f"Sent Rs.{_plain(paise)} from Kotak Bank A/c X{last4} to {who} on {d:%d-%m-%y}.UPI Ref {ref}. "
                               "Not you, https://kotak.com/KBANKT/Fraud")
    if bank == "bob":
        return "DM-BOBTXN", (f"Rs.{_plain(paise)} Dr. from A/C XXXXXX{last4} and Cr. to {who}. Ref:{ref}. "
                             f"AvlBal:Rs{_plain(balance_paise)}({d:%Y:%m:%d %H:%M:%S}). Not you? Call 18005700-BOB")
    if bank in ("sbi", "icici", "axis"):  # these already print the name
        return upi_debit(bank, paise=paise, last4=last4, when=when, ref=ref, name=name, vpa="", balance_paise=balance_paise)
    return SENDERS.get(bank, "VM-POCKET"), f"Rs.{_plain(paise)} debited from A/c XX{last4} on {d:%d-%m-%y} to {who} (UPI Ref No {ref})."


def card_spend(bank: str, *, paise: int, last4: str, when: datetime, name: str, limit_paise: int) -> tuple[str, str]:
    """(sender_id, body) for a credit card purchase."""
    d, who = when, name.upper()
    if bank == "hdfc":
        return "AD-HDFCBK-T", (f"Spent Rs.{_plain(paise)} On HDFC Bank Card {last4} At {who} On {d:%Y-%m-%d:%H:%M:%S}.Not You? "
                               f"To Block+Reissue Call 18002586161/SMS BLOCK CC {last4} to 7308080808")
    if bank == "icici":
        return "VK-ICICIT", (f"INR {_commas(paise)} spent using ICICI Bank Card XX{last4} on {d:%d}-{_MON[d.month - 1]}-{d:%y} on {who}. "
                             f"Avl Limit: INR {_commas(limit_paise)}. If not you, call 1800 2662/SMS BLOCK {last4} to 9215676766.")
    if bank == "sbi":
        return "JD-SBICRD", (f"Rs.{_plain(paise)} spent on your SBI Credit Card ending {last4} at {who} on {d:%d/%m/%y}. "
                             "Trxn. not done by you? Report at https://sbicard.com/Dispute")
    if bank == "axis":
        return "TM-AXISBK-T", (f"Spent\nCard no. XX{last4}\nINR {_commas(paise)}\n{d:%d-%m-%y %H:%M:%S}\n{who}\n"
                               f"Avl Lmt INR {_commas(limit_paise)}\nSMS BLOCK {last4} to 919951860002, if not you - Axis Bank")
    if bank == "kotak":
        return "VM-KOTAKB-S", (f"Rs.{_plain(paise)} spent on Kotak Credit Card x{last4} at {who} on {d:%d/%m/%Y}. "
                               f"Avl limit Rs.{_plain(limit_paise)}. Not you? Call 18602662666")
    return SENDERS.get(bank, "VM-POCKET"), f"Rs.{_plain(paise)} spent on Credit Card XX{last4} at {who} on {d:%d-%m-%y}."


def card_payment(bank: str, *, paise: int, last4: str, when: datetime) -> tuple[str, str]:
    """(sender_id, body) for a bill payment arriving on a credit card."""
    name = BANK_NAMES.get(bank, "Bank")
    return SENDERS.get(bank, "VM-POCKET"), f"Payment of Rs.{_plain(paise)} received on your {name} Credit Card XX{last4} on {when:%d/%m/%Y}. Thank you."


def account_debit(bank: str, *, paise: int, last4: str, when: datetime, name: str, channel: str, balance_paise: int) -> tuple[str, str]:
    """(sender_id, body) for a mandate, NEFT or IMPS debit. `channel` is NACH, NEFT or IMPS."""
    bank_name = BANK_NAMES.get(bank, "Bank")
    return SENDERS.get(bank, "VM-POCKET"), (f"Rs.{_plain(paise)} debited from {bank_name} A/c X{last4} on {when:%d-%m-%y} by {channel} to "
                                            f"{name.upper()}. Bal:Rs.{_plain(balance_paise)}")
