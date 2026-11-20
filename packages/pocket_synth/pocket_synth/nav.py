"""NAV history for the 16 real schemes: a seeded random walk that ENDS at each scheme's real latest NAV.

Only the latest NAV is real. Use AMFI history at runtime for true past prices.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

from . import refdata as R

MARKET_HOLIDAYS = {d for d in R.BANK_HOLIDAYS if d.weekday() < 5}


def trading_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in MARKET_HOLIDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out


def build_nav(seed: int = 20261120) -> dict[int, dict[date, float]]:
    g = np.random.default_rng(seed)
    days = trading_days(R.START - timedelta(days=45), R.END)
    n = len(days)
    mkt_mu, mkt_sig = 0.10 / 250, 0.13 / math.sqrt(250)
    market = g.normal(mkt_mu, mkt_sig, n)
    gold = g.normal(0.16 / 250, 0.15 / math.sqrt(250), n)
    out: dict[int, dict[date, float]] = {}
    for code, name, cat, latest, anchor, drift, vol, beta in R.FUNDS:
        if cat == "liquid":
            r = np.full(n, drift / 250) + g.normal(0, 0.0002, n)
        elif cat == "gold":
            r = gold + g.normal(0, 0.003, n)
        else:
            idio_sig = math.sqrt(max(vol ** 2 - (beta * 0.13) ** 2, 0.0004)) / math.sqrt(250)
            r = beta * market + (drift - beta * 0.10) / 250 + g.normal(0, idio_sig, n)
        idx = max(i for i, d in enumerate(days) if d <= anchor)
        navs = np.empty(n)
        navs[idx] = latest
        for i in range(idx - 1, -1, -1):
            navs[i] = navs[i + 1] / math.exp(r[i + 1])
        for i in range(idx + 1, n):
            navs[i] = navs[i - 1] * math.exp(r[i])
        out[code] = {d: round(float(v), 4) for d, v in zip(days, navs)}
    return out
