#!/usr/bin/env python3
"""
subset.py -- draw a stratified subset of BI4YOU-Nav for a shorter run.

Keeps EVERY drift probe (the strata carrying the H2/H3 signal, and too few to
sample) and every tour-seeded item, then samples the controls. Reporting a
subset is honest; silently sampling the probes would not be, since that is
where the effect lives.

Usage:
    python subset.py --items items.jsonl --out items_150.jsonl --controls 90
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

SEED = 20260921


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items", type=Path, default=Path("items.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("items_150.jsonl"))
    ap.add_argument("--controls", type=int, default=90)
    ap.add_argument("--tours", type=int, default=26,
                    help="tour-seeded items to keep (0 = all)")
    args = ap.parse_args()

    rng = random.Random(SEED)
    items = [json.loads(l) for l in args.items.open(encoding="utf-8")]

    probes = [i for i in items if i["provenance"] == "drift_probe"]
    tours = [i for i in items if i["provenance"] == "tour_seeded"]
    ctls = [i for i in items if i["provenance"] == "control"]

    # One item per distinct tour, so all 26 gold sequences are represented
    # rather than five paraphrases of the same five tours.
    by_tour: dict[str, list[dict]] = defaultdict(list)
    for t in tours:
        by_tour[t["id"].rsplit("-", 1)[0]].append(t)
    keep_tours = [rng.choice(v) for v in by_tour.values()]
    if args.tours:
        keep_tours = keep_tours[:args.tours]

    # Stratify controls by language so the multilingual axis survives sampling.
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for c in ctls:
        by_lang[c["language"]].append(c)
    keep_ctls: list[dict] = []
    total = sum(len(v) for v in by_lang.values())
    for lang, pool in by_lang.items():
        share = max(1, round(args.controls * len(pool) / total))
        keep_ctls += rng.sample(pool, min(share, len(pool)))
    keep_ctls = keep_ctls[:args.controls]

    out = probes + keep_tours + keep_ctls
    rng.shuffle(out)
    with args.out.open("w", encoding="utf-8") as fh:
        for it in out:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    prov: dict[str, int] = defaultdict(int)
    layer: dict[str, int] = defaultdict(int)
    lang: dict[str, int] = defaultdict(int)
    for it in out:
        prov[it["provenance"]] += 1
        layer[it["layer"]] += 1
        lang[it["language"]] += 1

    print(f"{len(out)} items -> {args.out}")
    print("  provenance:", dict(sorted(prov.items())))
    print("  layer     :", dict(sorted(layer.items())))
    print("  language  :", dict(sorted(lang.items())))
    print(f"\n  all {len(probes)} drift probes retained (not sampled)")
    print(f"  est. runtime at 34 s/item: {len(out) * 34 / 60:.0f} min per condition")


if __name__ == "__main__":
    main()
