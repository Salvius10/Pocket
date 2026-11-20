"""Smoke test: link every demo persona and print the headline numbers and detected insights.

Run: uv run python evals/smoke_core.py   (needs migrations applied)
"""

from __future__ import annotations

import asyncio
import sys
import time

from core_api import models as m
from core_api.api.deps import get_or_create_user
from core_api.api.public import refresh
from core_api.db import dispose_engine, get_sessionmaker
from core_api.insights import engine
from core_api.ledger import summary
from core_api.seed import loader
from sqlalchemy import select


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    bad = 0
    async with get_sessionmaker()() as session:
        await loader.seed_reference(session)
        for persona in loader.PERSONAS:
            user = await get_or_create_user(session, f"dev:smoke-{persona}")
            user.language = "en"
            t0 = time.perf_counter()
            counts = await loader.link_persona(session, user, persona)
            await session.commit()
            ctx = await refresh(session, user)
            took = time.perf_counter() - t0
            s = summary.build_summary(ctx)
            sts = s["safe_to_spend"]
            print(f"\n=== {persona} ({user.first_name}) linked in {took:.2f}s {counts}")
            print(f"  safe-to-spend {sts['daily']['display']}/day, left today {sts['left_today']['display']}, "
                  f"income {sts['income']['display']}, committed {sts['committed']['display']}, "
                  f"goals {sts['goal_reserve']['display']}, flex spent {sts['flexible_spent']['display']} [{sts['status']}]")
            print("  pockets:", ", ".join(f"{p['name']} {p['spent']['display']}/{p['limit']['display']} {p['status']}" for p in s["pockets"]))
            print("  goals:", ", ".join(f"{g['name']} {g['pct']}% {g['status']}" for g in s["goals"]))
            print("  top cats:", ", ".join(f"{c['name']} {c['amount']['display']}" for c in s["spend_by_category"]["this_month"][:4]))
            print(f"  net worth {s['net_worth']['total']['display']}; investments {s['investments']['total']['display']} "
                  f"week {s['investments']['week_change']['display']}; bills due {s['bills']['count']} = {s['bills']['total_due']['display']}")
            found = {f.fingerprint: f for f in engine.detect_all(ctx, await engine.load_merchants(session))}
            planted = list((await session.execute(select(m.PlantedPattern).where(m.PlantedPattern.user_id == user.id))).scalars())
            keys = {p.natural_key for p in planted}
            hit = keys & set(found)
            missed = keys - set(found)
            extra = [fp for fp, f in found.items() if f.type in engine.PLANTED_TYPES and fp not in keys]
            print(f"  planted found {len(hit)}/{len(keys)}; missed {sorted(missed)}; extra planted-type {extra}")
            bad += len(missed) + len(extra)
            for row in (await engine.list_insights(session, ctx))[:14]:
                tag = " [+proposal: " + row["proposal"]["title"] + "]" if row["proposal"] else ""
                print(f"   - s{row['severity']} {row['type']}: {row['title']} — {row['body']}{tag}")
    await dispose_engine()
    print(f"\nplanted mismatches: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
