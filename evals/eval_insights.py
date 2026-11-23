"""Gate 1: the insight engine against the dataset's answer key.

Runs the real engine (`detect_all`) on the 6 demo personas and the 200 evaluation users and
compares what it finds for the six planted types with `planted_patterns.csv`. Runs in memory;
no database and no model call.

Pass: recall >= 0.90 and precision >= 0.80 (overall, and reported per type).

Run: uv run python evals/eval_insights.py [--set demo|eval|all] [--limit N] [--show N]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, defaultdict
from datetime import date

from core_api.insights import engine
from core_api.seed.offline import Dataset

RECALL_GATE = 0.90
PRECISION_GATE = 0.80


def ratio(num: int, den: int) -> float:
    return num / den if den else 1.0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", choices=("demo", "eval", "all"), default="all")
    ap.add_argument("--limit", type=int, default=None, help="only the first N users of each set")
    ap.add_argument("--today", type=date.fromisoformat, default=None, help="score as of this day (default: last day of the data)")
    ap.add_argument("--show", type=int, default=10, help="how many misses and extras to list")
    ap.add_argument("--source", choices=("processed", "feed"), default="processed",
                    help="the ledger to run on: the dataset's ready-made transactions, or the ones the loader works out from the account feed")
    ap.add_argument("--without-bills", action="store_true",
                    help="with --source feed: do not give the loader the recurring items (the dataset marks that table as a label)")
    args = ap.parse_args()

    hit: Counter[str] = Counter()
    missed: Counter[str] = Counter()
    extra: Counter[str] = Counter()
    other: Counter[str] = Counter()  # the non-planted insight types, for information
    examples: dict[str, list[str]] = defaultdict(list)
    users = 0
    t0 = time.perf_counter()

    for name in (("demo", "eval") if args.set == "all" else (args.set,)):
        ds = Dataset(name, source=args.source, given_bills=not args.without_bills)
        for user_row, ctx in ds.contexts(today=args.today, limit=args.limit):
            users += 1
            uid = str(user_row["user_id"])
            want = ds.planted(uid)
            found = engine.detect_all(ctx, ds.merchants)
            got = {(f.type, f.fingerprint) for f in found if f.type in engine.PLANTED_TYPES}
            other.update(f.type for f in found if f.type not in engine.PLANTED_TYPES)
            hit.update(kind for kind, _ in want & got)
            for kind, key in sorted(want - got):
                missed[kind] += 1
                examples["missed"].append(f"{name} {user_row['archetype']} {uid[:8]}  {kind}  {key}")
            for kind, key in sorted(got - want):
                extra[kind] += 1
                examples["extra"].append(f"{name} {user_row['archetype']} {uid[:8]}  {kind}  {key}")

    print(f"Insight engine vs answer key: {users} users, {time.perf_counter() - t0:.1f}s, ledger from the {args.source} data"
          + (", recurring items withheld from the loader" if args.without_bills else "") + "\n")
    print(f"{'type':<26}{'planted':>8}{'found':>7}{'hit':>6}{'missed':>8}{'extra':>7}{'recall':>9}{'precision':>11}")
    for kind in engine.PLANTED_TYPES:
        planted, found_n = hit[kind] + missed[kind], hit[kind] + extra[kind]
        print(f"{kind:<26}{planted:>8}{found_n:>7}{hit[kind]:>6}{missed[kind]:>8}{extra[kind]:>7}"
              f"{ratio(hit[kind], planted):>9.3f}{ratio(hit[kind], found_n):>11.3f}")
    h, mi, ex = sum(hit.values()), sum(missed.values()), sum(extra.values())
    recall, precision = ratio(h, h + mi), ratio(h, h + ex)
    print(f"{'all six':<26}{h + mi:>8}{h + ex:>7}{h:>6}{mi:>8}{ex:>7}{recall:>9.3f}{precision:>11.3f}")

    for label in ("missed", "extra"):
        if examples[label]:
            print(f"\n{label} ({len(examples[label])}):")
            for line in examples[label][: args.show]:
                print("  " + line)
    if other:
        print("\nother insight types raised (not scored): " + ", ".join(f"{k} {v}" for k, v in sorted(other.items())))

    ok = recall >= RECALL_GATE and precision >= PRECISION_GATE and users > 0
    print(f"\nGate 1 (recall >= {RECALL_GATE:.2f}, precision >= {PRECISION_GATE:.2f}): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
