#!/usr/bin/env python3
"""
run.py -- run the agent over BI4YOU-Nav and score each emitted action.

Conditions (paper Table 5):
    C1  Sigma_0 + gpt-4o-mini      deployed baseline
    C2  Sigma_0 + stronger model   model scaling
    C3  Sigma_R + gpt-4o-mini      specification repair
    C4  Sigma_R + stronger model   both

Sigma_0 is the deployed prompt, extracted verbatim from FinanceAIService.java.
Sigma_R is Sigma_0 repaired against source-extracted ground truth by repair.py.

The API key is read from ../.env (gitignored). Never pass it on the command
line: it would be recorded in shell history.

Usage:
    python run.py --condition C1 --items items.jsonl --out ../results/C1.jsonl
    python run.py --condition C1 --limit 25          # smoke test first
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "extractor"))

from validator import Validator  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# The deployed system uses openai/gpt-4o-mini. That model requires paid
# credits, and the account used for these runs is free-tier, so the baseline
# below is a free model of comparable class rather than the deployed one.
# This is a deviation from the deployed configuration and is reported as a
# threat to validity (paper Sec. 9.2): absolute rates are NOT directly
# comparable to production, though the C1-vs-C3 contrast, which holds the
# model fixed, remains valid.
MODELS = {
    "baseline": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "strong": "nvidia/nemotron-3-ultra-550b-a55b:free",
    # Available if credits are purchased -- restores the deployed configuration.
    "deployed": "openai/gpt-4o-mini",
    "paid_strong": "anthropic/claude-3.5-sonnet",
}

CONDITIONS = {
    "C1": ("sigma_0", "baseline"),
    "C2": ("sigma_0", "strong"),
    "C3": ("sigma_R", "baseline"),
    "C4": ("sigma_R", "strong"),
}

# On a free-tier account "baseline" and "strong" resolve to the SAME model, so
# C2 and C4 cannot test H3 (model scaling). Running them anyway would produce
# a difference attributable only to sampling noise and would be reported as if
# it measured capability. run.py therefore refuses C2/C4 unless the models
# actually differ. H3 stays untested; see results/README.md.


def load_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("no API key: create .env from .env.example, or export OPENROUTER_API_KEY")
    return key


def load_prompt(which: str) -> str:
    p = ROOT / "benchmark" / ("sigma_0.txt" if which == "sigma_0" else "sigma_R.txt")
    if not p.exists():
        sys.exit(f"{p.name} missing -- run extract_prompt.py (sigma_0) or repair.py (sigma_R)")
    return p.read_text(encoding="utf-8")


def strip_sel(s: str) -> str:
    return s.replace("[data-nav='", "").replace("']", "").strip()


def call_model(key: str, model: str, system: str, item: dict,
               retries: int = 3) -> tuple[dict | None, str | None]:
    """One agent turn. Returns (parsed_json, error)."""
    user = f"[Page actuelle: {item['context']['route']}]\n{item['query']}"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            # The deployed system injects the role via gateway headers; the
            # benchmark states it explicitly so the condition is controlled.
            {"role": "system", "content": f"[Role de l'utilisateur: {item['context']['role']}]"},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=90)
            if r.status_code == 429:
                time.sleep(2 ** attempt * 3)
                continue
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}: {r.text[:180]}"
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content), None
        except json.JSONDecodeError as e:
            return None, f"model returned non-JSON: {e}"
        except Exception as e:  # network, timeout, malformed envelope
            if attempt == retries - 1:
                return None, f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt * 2)
    return None, "exhausted retries"


def score(v: Validator, item: dict, parsed: dict | None, err: str | None) -> dict:
    """Validate the emitted sequence and attribute every failure."""
    rec = {
        "id": item["id"], "layer": item["layer"], "language": item["language"],
        "provenance": item["provenance"], "role": item["context"]["role"],
        "route": item["context"]["route"], "gold": item["gold_sequence"],
    }
    if err or parsed is None:
        rec.update({"error": err, "emitted": None, "outcome": "api_error"})
        return rec

    steps = [strip_sel(s.get("selector", ""))
             for s in (parsed.get("steps") or []) if s.get("selector")]
    rec["emitted"] = steps
    rec["reply_len"] = len(parsed.get("reply") or "")

    gold = item["gold_sequence"]

    # An item whose gold is empty expects the agent to DECLINE (the action is
    # unavailable or the role is not admitted). Emitting steps there is a
    # failure of exactly the kind drift produces.
    if not gold:
        if not steps:
            rec.update({"outcome": "correct", "attribution": "correct",
                        "n_invalid": 0, "failures": []})
        else:
            rec.update({"outcome": "should_have_declined",
                        "attribution": "F_drift", "n_invalid": len(steps),
                        "failures": ["emitted steps where the correct answer "
                                     "is that the action is unavailable"]})
        return rec

    if not steps:
        rec.update({"outcome": "no_steps", "attribution": "F_gap",
                    "n_invalid": 0, "failures": ["emitted no executable steps"]})
        return rec

    verdicts = v.validate_sequence(steps, item["context"]["route"],
                                   item["context"]["role"])
    invalid = [x for x in verdicts if not x.valid]
    rec["n_invalid"] = len(invalid)
    rec["failures"] = [f"{x.selector}: {'; '.join(x.reasons)}" for x in invalid]
    rec["per_step"] = [x.as_dict() for x in verdicts]

    # Per-layer validity
    for k, attr in ((1, "v1_exists"), (2, "v2_reachable"),
                    (3, "v3_permitted"), (4, "v4_ordered")):
        rec[f"V{k}"] = all(getattr(x, attr) for x in verdicts)

    # Sequence agreement with gold
    sg, ss = set(gold), set(steps)
    inter = len(sg & ss)
    rec["precision"] = inter / len(ss) if ss else 0.0
    rec["recall"] = inter / len(sg) if sg else 0.0
    rec["exact_match"] = steps == gold

    if not invalid:
        rec.update({"outcome": "correct", "attribution": "correct"})
    else:
        attrs = [v.attribute(x) for x in invalid]
        rec["outcome"] = "invalid"
        rec["attribution"] = ("F_drift" if "F_drift" in attrs
                              else "F_gap" if "F_gap" in attrs else "F_model")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--items", type=Path, default=HERE / "items.jsonl")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0, help="0 = all items")
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--resume", action="store_true",
                    help="skip items already present in --out and append")
    args = ap.parse_args()

    sigma_which, model_key = CONDITIONS[args.condition]
    model = MODELS[model_key]

    if args.condition in ("C2", "C4") and MODELS["strong"] == MODELS["baseline"]:
        sys.exit(
            f"{args.condition} compares model capability, but 'strong' and "
            f"'baseline' resolve to the same model ({model}).\n"
            "Running it would measure sampling noise, not capability.\n"
            "Purchase OpenRouter credits and set MODELS['strong'] to a "
            "genuinely stronger model first. H3 remains untested until then."
        )
    system = load_prompt(sigma_which)
    key = load_key()

    items = [json.loads(l) for l in args.items.open(encoding="utf-8")]
    if args.limit:
        items = items[:args.limit]

    out = args.out or (ROOT / "results" / f"{args.condition}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    # A lock file prevents two instances writing the same output concurrently,
    # which silently interleaves records and corrupts the run.
    lock = out.with_suffix(out.suffix + ".lock")
    if lock.exists():
        sys.exit(
            f"{lock.name} exists -- another run may be writing {out.name}.\n"
            "If you are sure no other run is active, delete the lock file."
        )

    # --resume skips items already scored, so a long run survives a restart.
    done: set[str] = set()
    if args.resume and out.exists():
        for line in out.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue  # tolerate a truncated final line
        items = [it for it in items if it["id"] not in done]
        print(f"resuming: {len(done)} already scored, {len(items)} remaining")
    elif out.exists() and out.stat().st_size > 0:
        sys.exit(
            f"{out.name} already exists and is non-empty.\n"
            "Pass --resume to continue it, or choose a different --out."
        )

    v = Validator(
        json.loads((ROOT / "extractor" / "impl.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "extractor" / "spec.json").read_text(encoding="utf-8")),
    )

    print(f"condition {args.condition}: {sigma_which} + {model}")
    print(f"items {len(items)}  ->  {out}\n")

    counts: dict[str, int] = {}
    started = time.time()
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        # Append when resuming so earlier records survive.
        with out.open("a" if done else "w", encoding="utf-8") as fh:
            for i, item in enumerate(items, 1):
                parsed, err = call_model(key, model, system, item)
                rec = score(v, item, parsed, err)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                a = rec.get("attribution", rec["outcome"])
                counts[a] = counts.get(a, 0) + 1
                if i % 10 == 0 or i == len(items):
                    rate = (time.time() - started) / i
                    eta = rate * (len(items) - i) / 60
                    print(f"  {i}/{len(items)}  {rate:.0f}s/item  "
                          f"eta {eta:.0f}min  {counts}")
                time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("\ninterrupted -- rerun the same command with --resume to continue")
    finally:
        lock.unlink(missing_ok=True)

    print(f"\ndone -> {out}")
    print("attribution:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
