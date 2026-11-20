"""AMFI NAVAll.txt ingest (real data). Only the schemes users hold are stored."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.ledger import context

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def parse_navall(text: str, wanted: set[int]) -> dict[int, tuple[Any, Decimal]]:
    """Lines look like: 120716;INF...;INF...;UTI Nifty 50 Index Fund - Direct Plan - Growth;179.7634;19-Nov-2026"""
    out: dict[int, tuple[Any, Decimal]] = {}
    for line in text.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        code = int(parts[0])
        if code not in wanted:
            continue
        try:
            nav = Decimal(parts[4])
            day = datetime.strptime(parts[5].strip(), "%d-%b-%Y").date()
        except (InvalidOperation, ValueError):
            continue
        out[code] = (day, nav)
    return out


async def ingest_latest(session: AsyncSession) -> dict[str, Any]:
    wanted = {int(c) for c in (await session.execute(select(m.NavPrice.scheme_code).distinct())).scalars()}
    try:
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
            r = await client.get(AMFI_URL)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"AMFI unreachable: {type(exc).__name__}"}
    latest = parse_navall(r.text, wanted)
    added = 0
    for code, (day, nav) in latest.items():
        if await session.get(m.NavPrice, (code, day)) is None:
            session.add(m.NavPrice(scheme_code=code, nav_date=day, nav=nav, source="amfi"))
            added += 1
    await session.commit()
    context._ref_cache.pop("nav", None)
    context._ctx_cache.clear()
    return {"ok": True, "schemes": len(latest), "added": added}
