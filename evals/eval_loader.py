"""The loader: a ledger worked out from account statements against the ledger the dataset ships.

For every user the account-feed statements go through the parser and the loader
(`core_api/ingest/feed.py`), and each row is compared with the same row in `transactions.csv`:
the merchant, the category, the spend class, the recurring item, and the links between rows
(own transfers, reversals, refunds, group expenses, settle-ups). Then the money figures the app
shows for the last month are compared between the two ledgers.

By default the loader is given each user's list of recurring items, as the app is. The dataset
marks that table as a label (it is what a recurring detector should find), so the recurring
links, the spend class and the money figures are not an independent result in that mode.
`--without-bills` withholds the table and shows what the loader does from the feed alone.

The plan sets no gate for the loader; the numbers are reported. Runs in memory: no database and
no model call.

Run: uv run python evals/eval_loader.py [--set demo|eval|all] [--limit N] [--show N] [--without-bills]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, defaultdict
from datetime import date

from core_api.ledger import summary
from core_api.reports.monthly import monthly_report
from core_api.seed.offline import Dataset

EXACT = ("account_id", "amount_paise", "direction", "occurred_at", "status", "budget_month", "personal_amount_paise")
DERIVED = ("merchant", "category", "spend_class", "recurring_item_id", "kind", "mode")
LINKS = ("transfer_pair_id", "reversal_of_id", "refund_of_id", "group_expense_id", "settlement_id")
FIGURES = ("income", "spend", "committed", "flexible", "saved")


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.2f}%" if b else "n/a"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", choices=("demo", "eval", "all"), default="all")
    ap.add_argument("--limit", type=int, default=None, help="only the first N users of each set")
    ap.add_argument("--show", type=int, default=12, help="how many kinds of mismatch to list per field")
    ap.add_argument("--without-bills", action="store_true",
                    help="do not give the loader the user's recurring items (the dataset marks that table as a label)")
    args = ap.parse_args()

    rows = users = 0
    ok: Counter[str] = Counter()
    link_want: Counter[str] = Counter()
    link_hit: Counter[str] = Counter()
    link_extra: Counter[str] = Counter()
    misses: dict[str, Counter[str]] = defaultdict(Counter)
    figure_same: Counter[str] = Counter()
    safe_same = 0
    months = 0
    t0 = time.perf_counter()

    for name in (("demo", "eval") if args.set == "all" else (args.set,)):
        ds = Dataset(name)
        pairs = zip(ds.processed_by_user(), ds.feed_by_user(given_bills=not args.without_bills), strict=True)
        for done, ((uid, processed), (feed_uid, feed)) in enumerate(pairs):
            if args.limit is not None and done >= args.limit:
                break
            if uid != feed_uid:
                raise SystemExit(f"{name}: transactions.csv and the account feed list users in a different order ({uid} / {feed_uid})")
            user_row = ds.users[uid]
            today = date.fromisoformat(str(user_row["data_end"]))
            want_ctx, got_ctx = ds.ctx(user_row, today, processed), ds.ctx(user_row, today, feed)
            got_by_id = {t.id: t for t in got_ctx.txns}
            if len(got_by_id) != len(want_ctx.txns):
                raise SystemExit(f"{name} {uid[:8]}: {len(want_ctx.txns)} rows in transactions.csv, {len(got_by_id)} from the feed")
            users += 1
            for want in want_ctx.txns:
                got = got_by_id[want.id]
                rows += 1
                for f in EXACT + DERIVED:
                    same = getattr(want, f) == getattr(got, f)
                    ok[f] += same
                    if not same and f in ("category", "spend_class", "recurring_item_id", "merchant", "status"):
                        misses[f][f"{getattr(want, f)} -> {getattr(got, f)}  [{want.kind}]"] += 1
                if want.balance_after_paise is not None and got.balance_after_paise is not None:
                    ok["balance"] += want.balance_after_paise == got.balance_after_paise
                    ok["balance_n"] += 1
                for f in LINKS:
                    w, g = getattr(want, f), getattr(got, f)
                    link_want[f] += w is not None
                    link_hit[f] += w is not None and w == g
                    link_extra[f] += g is not None and w != g
            # the figures the app shows, for the last full month and the one before it (the report lists newest first)
            for month in [x["month"] for x in monthly_report(want_ctx)["months"]][:2]:
                a, b = monthly_report(want_ctx, month), monthly_report(got_ctx, month)
                months += 1
                for f in FIGURES:
                    figure_same[f] += a[f]["paise"] == b[f]["paise"]
            safe_same += summary.sts_calc(want_ctx) == summary.sts_calc(got_ctx)

    def line(label: str, fields: tuple[str, ...]) -> None:
        print(f"{label}: " + "  ".join(f"{f} {pct(ok[f], rows)}" for f in fields))

    print(f"Loader vs transactions.csv: {rows:,} rows, {users} users, {time.perf_counter() - t0:.0f}s")
    if args.without_bills:
        print("The loader was NOT given the user's recurring items: everything below comes from the feed, the SMS, the merchant list and the groups.\n")
    else:
        print("The loader was GIVEN the user's recurring items, which the dataset marks as a label table. The recurring links, and the\n"
              "spend class and money figures that follow from them, are therefore not an independent result. --without-bills shows the feed alone.\n")
    line("read from the feed as stated", EXACT)
    print(f"   balance after the payment {pct(ok['balance'], ok['balance_n'])} of {ok['balance_n']:,} rows on deposit accounts (card statements carry none)")
    line("worked out by rule", DERIVED)
    print("links between rows (found / in the dataset, and links the dataset does not have):")
    for f in LINKS:
        print(f"   {f:<18} {link_hit[f]:>6,} / {link_want[f]:<6,} {pct(link_hit[f], link_want[f]):>8}   extra {link_extra[f]:,}")
    print(f"figures for the last two months ({months} user-months identical out of): "
          + "  ".join(f"{f} {pct(figure_same[f], months)}" for f in FIGURES))
    print(f"Safe-to-spend on the last day identical for {safe_same} of {users} users ({pct(safe_same, users)})")
    for f in ("category", "spend_class", "recurring_item_id", "merchant", "status"):
        if misses[f]:
            print(f"\n{f}: {sum(misses[f].values()):,} rows differ (dataset -> loader [kind]):")
            for what, n in misses[f].most_common(args.show):
                print(f"   {n:>6,}  {what}")
    return 0 if users else 1


if __name__ == "__main__":
    raise SystemExit(main())
