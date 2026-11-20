"""Composer eval: the 6 ideal layouts and the 30 instruction variants the dataset ships.

For each case the eval builds the exact request core-api sends (features and names only, never an
amount), runs the agent's composer in this process, applies core-api's validator, and checks the
case's constraints against the layout the user would see.

Pass: every layout valid, Safe-to-spend first in every layout, and at least 80% of the variants
meet all of their constraints.

By default this measures the rule-based composer: the path that runs with no key and whenever the
model is unavailable. It makes no model call. `--model` runs the configured Gemini model instead
(MODEL_FLASH, then MODEL_FLASH_FALLBACK); that makes up to 72 calls on your key.

Run: uv run python evals/eval_composer.py [--model] [--show]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any

BASE = ("safe_to_spend@0", "count>=4", "count<=8", "only_catalog_types", "reasons_have_no_digits")


def check(constraint: str, spec: dict[str, Any], catalog: tuple[str, ...], has_digit: Any) -> bool:
    """'x@1' index 1; 'x@<=3' within the first 3 after Safe-to-spend; '!x' absent; 'x' present;
    'a|b' either; 'count<=n' / 'count>=n' widget count."""
    types = [w["type"] for w in spec["widgets"]]
    if "|" in constraint:
        return any(check(part, spec, catalog, has_digit) for part in constraint.split("|"))
    if constraint == "only_catalog_types":
        return all(t in catalog for t in types)
    if constraint == "reasons_have_no_digits":
        return not any(has_digit(r["text"]) for r in spec.get("reasons", [])) and not has_digit(spec.get("summary") or "")
    if constraint.startswith("count<="):
        return len(types) <= int(constraint[7:])
    if constraint.startswith("count>="):
        return len(types) >= int(constraint[7:])
    if constraint.startswith("!"):
        return constraint[1:] not in types
    if "@<=" in constraint:
        widget, limit = constraint.split("@<=")
        return widget in types and types.index(widget) <= int(limit)
    if "@" in constraint:
        widget, index = constraint.split("@")
        return widget in types and types.index(widget) == int(index)
    return constraint in types


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", action="store_true", help="use the configured Gemini model (spends calls on your key)")
    ap.add_argument("--show", action="store_true", help="print every case, not only the ones that miss")
    args = ap.parse_args()
    if not args.model:
        os.environ["GEMINI_MODE"] = "fake"  # before the agent's settings are read: rules only, no model call

    from agent.composer import service as composer
    from agent.config import get_settings as agent_settings
    from core_api.config import get_settings
    from core_api.home import service as home
    from core_api.insights import engine
    from core_api.seed.offline import Dataset
    from pocket_common.layout import CATALOG, LayoutSpec, has_digit, validate_layout

    content = get_settings().data_path / "content"
    ideals = json.loads((content / "ideal_layouts.json").read_text(encoding="utf-8"))
    variants = json.loads((content / "layout_variants.json").read_text(encoding="utf-8"))
    ds = Dataset("demo")
    people = {str(row["persona_id"]): (row, ctx) for row, ctx in ds.contexts()}
    mode = "model" if agent_settings().is_live else "rules"
    print(f"Composer eval ({mode}): {len(ideals)} ideal layouts + {len(variants)} variants\n")

    outcomes: Counter[str] = Counter()
    invalid_from_composer = 0
    not_first = 0
    met = 0
    constraints_met = constraints_total = 0
    overlap: list[float] = []

    for case in [*ideals, *variants]:
        user_row, ctx = people[case["persona_id"]]
        uid = str(user_row["user_id"])
        ctx.lang = ctx.user.language = "ta" if case["language"] == "tanglish" else case["language"]
        groups = sorted(str(g["group_id"]) for g in ds.data.groups if g["owner_user_id"] == uid)
        found = engine.detect_all(ctx, ds.merchants)
        lctx = home.layout_context_for(ctx, groups, bool(found))
        facts = {str(f["key"]): str(f["value"] or "") for f in ds.data.by_user[uid]["profile_facts"]
                 if f["key"] in ("saving_for", "worries", "occupation", "household") and not has_digit(str(f["value"] or ""))}
        group_rows = [{"id": str(g["group_id"]), "name": g["name"], "type": g["type"], "has_pot": bool(g["pot_target_paise"])}
                      for g in ds.data.groups if g["owner_user_id"] == uid]
        features = home.features_for(ctx, [f.type for f in found[:5]], facts, group_rows)
        default = home.default_layout(ctx, lctx)
        body = home.compose_request(ctx, lctx, features, case["instruction"], default.model_dump())

        answer = await composer.compose(body)
        outcomes[answer["outcome"]] += 1
        spec = LayoutSpec.model_validate(answer["spec"])
        if validate_layout(spec, lctx):  # core-api's check: an invalid layout is replaced by the default
            invalid_from_composer += 1
            spec = default
        shown = spec.model_dump()
        types = [w["type"] for w in shown["widgets"]]
        if not types or types[0] != "safe_to_spend":
            not_first += 1

        is_variant = case["instruction"] is not None
        wanted = list(case.get("constraints") or BASE)
        results = {c: check(c, shown, CATALOG, has_digit) for c in wanted}
        if is_variant:
            constraints_total += len(results)
            constraints_met += sum(results.values())
            met += all(results.values())
        else:
            ideal_types = {w["type"] for w in case["spec"]["widgets"]}
            overlap.append(len(ideal_types & set(types)) / len(ideal_types | set(types)))
        missed = [c for c, ok in results.items() if not ok]
        if missed or args.show:
            label = case["id"].replace("variant_", "").replace("ideal_", "ideal ")
            print(f"{'MISS' if missed else 'ok  '} {label:<14} [{case['language']}] {case['instruction'] or '(first Home)'}")
            print(f"       {answer['outcome']}: {types}" + (f"\n       not met: {missed}" if missed else ""))

    n = len(ideals) + len(variants)
    rate = met / len(variants)
    print(f"\noutcomes: {dict(outcomes)}")
    print(f"valid layouts from the composer: {n - invalid_from_composer}/{n}   (an invalid one is replaced by the default)")
    print(f"Safe-to-spend first: {n - not_first}/{n}")
    print(f"ideal layouts: average widget overlap with the shipped ideal {100 * sum(overlap) / len(overlap):.0f}%")
    print(f"variants meeting all constraints: {met}/{len(variants)} ({rate:.0%}); single constraints {constraints_met}/{constraints_total}")
    ok = invalid_from_composer == 0 and not_first == 0 and rate >= 0.80
    print(f"\nComposer gate (100% valid, Safe-to-spend first 100%, variants >= 80%): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
