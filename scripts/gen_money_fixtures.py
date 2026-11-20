"""Writes data/fixtures/money_format.json: 100 shared cases checked by both the Python and Dart tests.

The expected strings come from pocket_common.money, so this file is the parity contract for the
Dart port. The hand-written anchors in test_money.py are what pin the Python side itself.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from pocket_common import money

EDGES = [
    0, 1, 49, 50, 99, 100, 150, 2714, 99949, 99950, 99999, 100000, 100049, 100050, 1234567, 9994999, 9995000, 9999999,
    10000000, 10049999, 10050000, 12000000, 12345650, 99949999, 99950000, 99999999, 100000000, 999499999, 999500000,
    1000000000, 1050000000, 1234567890, 99999999999, -1, -50, -150, -99999, -1234567, -12000000, -1050000000,
]


def main() -> None:
    rng = random.Random(20261120)
    values = list(EDGES)
    while len(values) < 100:
        magnitude = rng.choice([3, 4, 5, 6, 7, 8, 9, 10, 11])
        v = rng.randrange(10 ** (magnitude - 1), 10**magnitude)
        values.append(-v if rng.random() < 0.1 else v)
    cases = [
        {"paise": v, "display": money.display(v), "exact": money.exact(v),
         "spoken": {lang: money.spoken(v, lang) for lang in money.LANGS}}
        for v in values[:100]
    ]
    out = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "money_format.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    main()
