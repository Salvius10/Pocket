"""Ledger contexts built straight from the dataset files: in memory, no database.

Used by the evals and the tests. The demo set (6 personas) fits in memory. The eval set
(200 users, about 2.3 lakh transactions) does not on a small laptop, so its transactions and
its account statements are streamed one user at a time.

A dataset can be read two ways (`source`): "processed" takes the transactions the dataset ships
ready-made; "feed" works them out from the account statements with the loader (`ingest/feed.py`).
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from typing import Any

from core_api import models as m
from core_api.config import get_settings
from core_api.ingest.pipeline import MerchantIndex
from core_api.ledger.context import Ctx, make_ctx
from core_api.seed import loader

Row = dict[str, str | None]


def data_root() -> Path:
    return get_settings().data_path


def stream_by_user(path: Path) -> Iterator[tuple[str, list[Row]]]:
    """Rows of a CSV that is grouped by `user_id`, one user at a time. Fails loudly if it is not grouped."""
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for uid, rows in groupby(csv.DictReader(f), key=lambda r: r["user_id"]):
            if uid in seen:
                raise SystemExit(f"{path.name} is not grouped by user_id (saw {uid} twice)")
            seen.add(uid)
            yield uid, [{k: (v if v != "" else None) for k, v in row.items()} for row in rows]


class Dataset:
    """One dataset folder ("demo" or "eval") plus the reference tables."""

    def __init__(self, name: str, source: str = "processed", given_bills: bool = True) -> None:
        if source not in loader.LEDGER_SOURCES:
            raise ValueError(f"unknown ledger source: {source}")
        self.name = name
        self.source = source
        self.given_bills = given_bills  # False: the feed loader is not handed the recurring items
        self.streamed = name != "demo"
        self.data = loader.DemoData(data_root(), name, skip=("transactions",) if self.streamed else ())
        self.categories = {c.id: c for c in loader.category_models(self.data)}
        self.merchants = {x.key: x for x in loader.merchant_models(self.data)}
        self.merchant_index = MerchantIndex(self.merchants.values())
        nav: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        for r in self.data.nav:
            nav[int(str(r["scheme_code"]))].append((date.fromisoformat(str(r["nav_date"])[:10]), Decimal(str(r["nav"]))))
        self.nav = {code: sorted(points) for code, points in nav.items()}
        self.users = {str(u["user_id"]): u for u in self.data.all_users}

    def planted(self, user_id: str) -> set[tuple[str, str]]:
        """The answer key for one user: (pattern_type, natural_key)."""
        return {(str(p["pattern_type"]), str(p["natural_key"])) for p in self.data.by_user[user_id]["planted_patterns"]}

    def processed_by_user(self) -> Iterator[tuple[str, list[Row]]]:
        """Each user's ready-made transactions (the dataset's `transactions.csv`)."""
        if self.streamed:
            yield from stream_by_user(self.data.db_dir / "transactions.csv")
        else:
            for uid in self.users:
                yield uid, self.data.by_user[uid]["transactions"]

    def statements_by_user(self) -> Iterator[tuple[str, list[dict[str, Any]]]]:
        """Each user's account statements, as the Account Aggregator would return them."""
        if not self.streamed:
            for uid, row in self.users.items():
                yield uid, loader.feed_statements(self.data, str(row["persona_id"]))
            return
        seen: set[str] = set()
        with gzip.open(self.data.db_dir.parent / "sources" / "account_aggregator.jsonl.gz", "rt", encoding="utf-8") as f:
            for uid, lines in groupby((json.loads(line) for line in f), key=lambda r: str(r["user_id"])):
                if uid in seen:
                    raise SystemExit(f"account_aggregator.jsonl.gz is not grouped by user_id (saw {uid} twice)")
                seen.add(uid)
                yield uid, [r["statement"] for r in lines]

    def sms_by_user(self) -> Iterator[tuple[str, list[dict[str, Any]]]]:
        """Each user's bank SMS for the same period (`{sender_id, body, received_at, ...}`)."""
        if not self.streamed:
            for uid, row in self.users.items():
                yield uid, loader.feed_sms(self.data, str(row["persona_id"]))
            return
        seen: set[str] = set()
        with gzip.open(self.data.db_dir.parent / "sources" / "sms.jsonl.gz", "rt", encoding="utf-8") as f:
            for uid, lines in groupby((json.loads(line) for line in f), key=lambda r: str(r["user_id"])):
                if uid in seen:
                    raise SystemExit(f"sms.jsonl.gz is not grouped by user_id (saw {uid} twice)")
                seen.add(uid)
                yield uid, list(lines)

    def feed_by_user(self, given_bills: bool = True) -> Iterator[tuple[str, list[Row]]]:
        """Each user's transactions worked out from their statements and SMS by the loader.
        `given_bills=False` withholds the dataset's recurring items, which it marks as labels."""
        for (uid, statements), (sms_uid, sms) in zip(self.statements_by_user(), self.sms_by_user(), strict=True):
            if uid != sms_uid:
                raise SystemExit(f"{self.name}: the account feed and the SMS file list users in a different order ({uid} / {sms_uid})")
            yield uid, loader.feed_transactions(self.data, uid, statements, self.merchant_index, sms, given_bills=given_bills)

    def contexts(self, today: date | None = None, limit: int | None = None) -> Iterator[tuple[Row, Ctx]]:
        """Each user with a ledger context as of `today` (default: the last day of that user's data)."""
        done = 0
        for uid, txn_rows in (self.feed_by_user(self.given_bills) if self.source == "feed" else self.processed_by_user()):
            if limit is not None and done >= limit:
                return
            user_row = self.users[uid]
            yield user_row, self.ctx(user_row, today or date.fromisoformat(str(user_row["data_end"])), txn_rows)
            done += 1
        if limit is None and done != len(self.users):
            raise SystemExit(f"{self.name}: {len(self.users)} users but transactions for {done}")

    def ctx(self, user_row: Row, today: date, txn_rows: list[Row]) -> Ctx:
        """A ledger context for one user from the given transaction rows (in the shape of `transactions.csv`)."""
        uid = str(user_row["user_id"])
        built = loader.build_user_rows(self.data, uid, uid, today, lambda old: old, txn_rows)  # keep the dataset's ids
        user = m.User(
            id=uid, firebase_uid=f"eval:{uid}", language=user_row["language"] or "en",
            display_name=user_row["display_name"] or "", first_name=user_row["first_name"] or "",
            persona_id=user_row["persona_id"], income_pattern=user_row["income_pattern"], city=user_row["city"],
            occupation=user_row["occupation"], data_version=0,
        )

        def models(model: Any, rows: list[dict[str, Any]]) -> list[Any]:
            return [model(**r) for r in rows]

        return make_ctx(
            user, today, settings=None, categories=self.categories,
            accounts=models(m.Account, built.accounts),
            txns=sorted(models(m.Transaction, built.txns), key=lambda t: t.occurred_at),
            recurring=models(m.RecurringItem, built.recurring),
            loans=models(m.Loan, built.loans),
            holdings=models(m.Holding, built.holdings),
            pockets=sorted(models(m.Pocket, built.pockets), key=lambda p: p.sort_order),
            adjustments=[],
            goals=sorted(models(m.Goal, built.goals), key=lambda g: -g.priority),
            contributions=models(m.GoalContribution, built.contributions),
            statements=sorted(models(m.CardStatement, built.statements), key=lambda s: s.statement_date),
            nav=self.nav,
        )
