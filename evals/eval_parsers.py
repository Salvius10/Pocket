"""Gate 4: the SMS parser against the synthetic bank SMS.

Every SMS in the dataset carries the answer a perfect parser would give. An SMS is *fully
correct* when the parser agrees on all of: kind (debit, credit or ignore), amount, account last
four, counterparty, VPA, reference number, date and balance.

The gate is scored on the held-out wordings only (`holdout = true`, template ids ending `.v3`):
wordings that appear nowhere else in the data, which the bank families were not written from.
Pass: at least 95% fully correct.

`mode` and `is_card` are reported but not part of "fully correct": two banks word an IMPS
transfer and a card-bill payment identically, so the mode cannot always be read from the text.

Run: uv run python evals/eval_parsers.py [--set demo|eval|all] [--show N] [--template hdfc.upi_dr.v1]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from core_api.config import get_settings
from core_api.ingest.aa import parse_account
from core_api.ingest.sms import ParsedSms, parse_sms

GATE = 0.95
FIELDS = ("amount_paise", "account_last4", "counterparty", "vpa", "ref_no", "txn_date", "balance_paise")
EXTRA = ("mode", "is_card")


def messages(root: Path, which: str) -> Iterator[dict[str, Any]]:
    if which in ("demo", "all"):
        for path in sorted((root / "demo" / "sources").glob("*/sms.jsonl")):
            with path.open(encoding="utf-8") as f:
                for line in f:
                    yield json.loads(line)
    if which in ("eval", "all"):
        with gzip.open(root / "eval" / "sources" / "sms.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def linked_accounts(root: Path) -> dict[str, set[str]]:
    """user_id -> last four digits of each linked account (what the app knows from the account feed)."""
    out: dict[str, set[str]] = defaultdict(set)
    for name in ("demo", "eval"):
        with (root / name / "db" / "accounts.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                digits = "".join(ch for ch in row["masked_number"] if ch.isdigit())
                if len(digits) >= 4:
                    out[row["user_id"]].add(digits[-4:])
    return out


def wrong_fields(got: ParsedSms, want: dict[str, Any]) -> list[str]:
    if want["kind"] == "ignore" or got.kind == "ignore":
        return [] if got.kind == want["kind"] else ["kind"]
    bad = [] if got.kind == want["kind"] else ["kind"]
    for field in FIELDS:
        value = getattr(got, field)
        if field == "txn_date" and value is not None:
            value = value.isoformat()
        expected = want.get(field)
        if field == "counterparty" and isinstance(expected, str):
            expected = " ".join(expected.split()) or None  # a name cut to a fixed width can keep a trailing space
        if value != expected:
            bad.append(field)
    return bad


def statements(root: Path, which: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """(user_id, statement) for every account statement in the dataset."""
    if which in ("demo", "all"):
        users = {}
        with (root / "demo" / "db" / "accounts.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                users[row["masked_number"][-4:]] = row["user_id"]
        for path in sorted((root / "demo" / "sources").glob("*/account_aggregator/*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            account = doc["Account"]
            masked = str(account.get("maskedCardNumber") or account.get("maskedAccNumber") or "")
            yield users.get(masked[-4:], ""), doc
    if which in ("eval", "all"):
        with gzip.open(root / "eval" / "sources" / "account_aggregator.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                yield row["user_id"], row["statement"]


def norm(text: str | None) -> str:
    return " ".join((text or "").upper().split())


def aa_report(root: Path, which: str, sms_keys: Counter[tuple[str, str, str, str, int]] | None) -> None:
    """The account-feed parser against `transactions.csv`. The plan sets no gate for it: the numbers are reported."""
    truth: dict[str, tuple[str, ...]] = {}
    for name in (("demo", "eval") if which == "all" else (which,)):
        with (root / name / "db" / "transactions.csv").open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                truth[r["txn_id"]] = (r["amount_paise"], r["direction"], r["occurred_at"], r["balance_after_paise"], r["ref_no"],
                                      r["counterparty_vpa"], r["counterparty_name"], r["mode"])
    n = structured = 0
    field_ok: Counter[str] = Counter()
    name_exact = name_close = name_any = vpa_printed = vpa_right = 0
    mode_n: Counter[str] = Counter()
    mode_ok: Counter[str] = Counter()
    name_misses: dict[str, str] = {}
    aa_keys: Counter[tuple[str, str, str, str, int]] = Counter()
    t0 = time.perf_counter()
    for user_id, doc in statements(root, which):
        account = parse_account(doc)
        for t in account.transactions:
            want = truth.get(t.txn_id)
            if want is None:
                continue
            n += 1
            checks = {
                "amount": str(t.amount_paise) == want[0], "direction": t.direction == want[1],
                "time": t.occurred_at == datetime.fromisoformat(want[2]),
                "balance": account.kind == "credit_card" or str(t.balance_paise) == want[3],
                "ref_no": (t.ref_no or "") == want[4],
            }
            field_ok.update(k for k, ok in checks.items() if ok)
            structured += all(checks.values())
            if t.vpa:
                vpa_printed += 1
                vpa_right += t.vpa == want[5]
            got, real = norm(t.counterparty), norm(want[6])
            if real:
                name_any += 1
                name_exact += got == real
                shared = next((i for i, (a, b) in enumerate(zip(got, real, strict=False)) if a != b), min(len(got), len(real)))
                close = bool(got) and (real.startswith(got) or got.startswith(real) or shared >= 10)
                name_close += close
                if not close:
                    name_misses.setdefault(want[7], f"{t.narration[:70]!r} -> {t.counterparty!r}, real {want[6][:34]!r}")
            mode_n[want[7]] += 1
            mode_ok[want[7]] += t.mode == want[7]
            if t.ref_no:
                aa_keys[(user_id, account.last4, t.ref_no, t.direction, t.amount_paise)] += 1

    def pct(a: int, b: int) -> str:
        return f"{100 * a / b:.2f}%" if b else "n/a"

    print(f"\nAccount-feed parser vs transactions.csv: {n:,} rows in {time.perf_counter() - t0:.0f}s")
    print(f"structured fields all correct (amount, direction, time, balance, reference): {pct(structured, n)}")
    print("   " + "  ".join(f"{k} {pct(field_ok[k], n)}" for k in ("amount", "direction", "time", "balance", "ref_no")))
    print(f"VPA: printed in {vpa_printed:,} narrations, read correctly in {pct(vpa_right, vpa_printed)}")
    print(f"name of the other party: {pct(name_close, name_any)} are recognisably the real name (it, a cut-short form of it, or the same first ten letters) ({pct(name_exact, name_any)} exactly)")
    print("channel: " + "  ".join(f"{m} {pct(mode_ok[m], mode_n[m])}" for m in sorted(mode_n)))
    if name_misses:
        print(f"names that do not match ({name_any - name_close:,}), one per channel:")
        for channel, line in sorted(name_misses.items()):
            print(f"   {channel:<9} {line}")
    if sms_keys is not None:
        with_ref = sum(sms_keys.values())
        paired = sum(c for key, c in sms_keys.items() if aa_keys.get(key))
        print("SMS and account feed describing the same payment (same account, reference, direction, amount): "
              f"{pct(paired, with_ref)} of {with_ref:,} SMS that carry a reference find their account-feed row")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", choices=("demo", "eval", "all"), default="all")
    ap.add_argument("--show", type=int, default=0, help="print this many wrong messages")
    ap.add_argument("--template", default=None, help="only this template id (or prefix)")
    ap.add_argument("--seen-only", action="store_true", help="with --show: skip held-out wordings")
    ap.add_argument("--aa-only", action="store_true", help="only the account-feed parser (skips the SMS run and the gate)")
    args = ap.parse_args()
    if args.aa_only:
        aa_report(get_settings().data_path, args.set, None)
        return 0

    root = get_settings().data_path
    accounts = linked_accounts(root)
    total: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    generic_correct: Counter[str] = Counter()
    by_template: dict[str, Counter[str]] = defaultdict(Counter)
    field_misses: dict[str, Counter[str]] = defaultdict(Counter)
    extra_ok: Counter[str] = Counter()
    extra_n = 0
    sms_keys: Counter[tuple[str, str, str, str, int]] = Counter()  # for the same-payment join with the account feed
    shown = 0
    t0 = time.perf_counter()

    for sms in messages(root, args.set):
        template = sms["template_id"]
        if args.template and not template.startswith(args.template):
            continue
        want = sms["ground_truth"]
        known = accounts.get(sms["user_id"], set())
        received = datetime.fromisoformat(sms["received_at"])
        got = parse_sms(sms["sender_id"], sms["body"], received, known)
        if got.kind != "ignore" and got.ref_no and got.account_last4 and got.amount_paise:
            sms_keys[(sms["user_id"], got.account_last4, got.ref_no, got.kind, got.amount_paise)] += 1
        bad = wrong_fields(got, want)
        group = "holdout" if sms["holdout"] else "seen"
        total[group] += 1
        by_template[template]["n"] += 1
        if not bad:
            correct[group] += 1
            by_template[template]["ok"] += 1
        else:
            field_misses[template].update(bad)
            if shown < args.show and not (args.seen_only and sms["holdout"]):
                shown += 1
                print(f"[{template}] {sms['sender_id']} wrong: {bad}")
                print("   " + sms["body"].replace("\n", " ⏎ "))
                print("   got:  " + ", ".join(f"{f}={getattr(got, f)}" for f in ("kind", *FIELDS) if f in bad or f == "kind"))
                print("   want: " + ", ".join(f"{f}={want.get(f)}" for f in ("kind", *FIELDS) if f in bad or f == "kind"))
        # the generic rules on their own, as if no bank family existed
        fallback = parse_sms(sms["sender_id"], sms["body"], received, known, use_families=False)
        if not wrong_fields(fallback, want):
            generic_correct[group] += 1
        if want["kind"] != "ignore" and got.kind != "ignore":
            extra_n += 1
            for field in EXTRA:
                extra_ok[field] += getattr(got, field) == want.get(field)

    def pct(a: int, b: int) -> str:
        return f"{100 * a / b:6.2f}%" if b else "   n/a"

    print(f"\nSMS parser vs ground truth: {sum(total.values()):,} SMS in {time.perf_counter() - t0:.0f}s\n")
    print(f"{'template':<24}{'n':>8}{'fully correct':>15}   most-missed fields")
    for template in sorted(by_template):
        c = by_template[template]
        misses = ", ".join(f"{k} {v}" for k, v in field_misses[template].most_common(3))
        mark = "  (held out)" if template.endswith(".v3") else ""
        if c["ok"] != c["n"] or mark or args.template:
            print(f"{template:<24}{c['n']:>8}{pct(c['ok'], c['n']):>15}   {misses}{mark}")
    perfect = sum(1 for c in by_template.values() if c["ok"] == c["n"])
    print(f"({perfect} of {len(by_template)} templates are 100% and not listed unless held out)\n")
    for group, label in (("seen", "seen wordings"), ("holdout", "held-out wordings")):
        print(f"{label:<22}{total[group]:>8,}  fully correct {pct(correct[group], total[group])}"
              f"   generic rules alone {pct(generic_correct[group], total[group])}")
    if extra_n:
        print("not scored:           " + "  ".join(f"{f} {pct(extra_ok[f], extra_n).strip()}" for f in EXTRA))

    if not args.template:
        aa_report(root, args.set, sms_keys)
    if total["holdout"] == 0:
        print("\nGate 4: no held-out SMS in this selection, so the gate was not measured.")
        return 0
    rate = correct["holdout"] / total["holdout"]
    ok = rate >= GATE
    print(f"\nGate 4 (held-out wordings fully correct >= {GATE:.0%}): {'PASS' if ok else 'FAIL'} at {rate:.2%}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
