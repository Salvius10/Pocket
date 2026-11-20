"""Ledger contexts built straight from the dataset files: in memory, no database.

Used by the evals and the tests. The demo set (6 personas) fits in memory. The eval set
(200 users, about 2.3 lakh transactions) does not on a small laptop, so its transactions are
streamed one user at a time.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from typing import Any

from core_api import models as m
from core_api.config import get_settings
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

    def __init__(self, name: str) -> None:
        self.name = name
        self.streamed = name != "demo"
        self.data = loader.DemoData(data_root(), name, skip=("transactions",) if self.streamed else ())
        self.categories = {c.id: c for c in loader.category_models(self.data)}
        self.merchants = {x.key: x for x in loader.merchant_models(self.data)}
        nav: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        for r in self.data.nav:
            nav[int(str(r["scheme_code"]))].append((date.fromisoformat(str(r["nav_date"])[:10]), Decimal(str(r["nav"]))))
        self.nav = {code: sorted(points) for code, points in nav.items()}
        self.users = {str(u["user_id"]): u for u in self.data.all_users}

    def planted(self, user_id: str) -> set[tuple[str, str]]:
        """The answer key for one user: (pattern_type, natural_key)."""
        return {(str(p["pattern_type"]), str(p["natural_key"])) for p in self.data.by_user[user_id]["planted_patterns"]}

    def contexts(self, today: date | None = None, limit: int | None = None) -> Iterator[tuple[Row, Ctx]]:
        """Each user with a ledger context as of `today` (default: the last day of that user's data)."""
        if self.streamed:
            pairs: Iterator[tuple[str, list[Row] | None]] = stream_by_user(self.data.db_dir / "transactions.csv")
        else:
            pairs = iter([(uid, None) for uid in self.users])
        done = 0
        for uid, txn_rows in pairs:
            if limit is not None and done >= limit:
                return
            user_row = self.users[uid]
            if txn_rows is not None:
                self.data.by_user[uid]["transactions"] = txn_rows
            yield user_row, self._ctx(user_row, today or date.fromisoformat(str(user_row["data_end"])))
            if txn_rows is not None:
                del self.data.by_user[uid]["transactions"]
            done += 1
        if self.streamed and limit is None and done != len(self.users):
            raise SystemExit(f"{self.name}: {len(self.users)} users but transactions for {done}")

    def _ctx(self, user_row: Row, today: date) -> Ctx:
        uid = str(user_row["user_id"])
        built = loader.build_user_rows(self.data, uid, uid, today, lambda old: old)  # keep the dataset's ids
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
