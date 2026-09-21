# Running everything

Two halves: a **static audit** that needs nothing but the BI4YOU sources, and
**inference experiments** that need an API key. The static half is the one that
produced the paper's measured results.

Nothing here requires BI4YOU to be running — no Spring, no Postgres, no Angular.
The agent is called directly over HTTP; the audit reads files.

---

## Part 1 — the static audit (free, ~5 seconds)

Reproduces every measured figure in the paper.

```bash
cd extractor
python extract.py    --root "C:\path\to\MyBi4you"
python parse_spec.py --root "C:\path\to\MyBi4you"
python drift.py
python validator.py
```

`--root` should point at a directory containing `MyBi4you_back-main` and
`MyBi4you_front-main`; the scripts locate the trees themselves.

### Expected output

```
extract.py     94 selectors · 44 routes (21 guarded) · 6 roles
               119 @PreAuthorize (15 distinct) · 245 endpoints
parse_spec.py  638 lines · 93 selectors · 26 tours (104 steps)
drift.py       L1 93/94 · L2 14/14 (+1 phantom) · L3 4/6 roles
validator.py   104 steps validated, 2 invalid  ← both in one tour (L4-03)
```

If your numbers differ, the BI4YOU sources have changed since the audit.

---

## Part 2 — inference experiments (needs an API key)

### Setup

```bash
cp .env.example .env     # then paste your OpenRouter key into it
pip install -r requirements.txt
```

### Smoke test first (~3 min)

```bash
cd benchmark
python run.py --condition C1 --limit 5 --out ../results/smoke.jsonl
```

Expect `{'correct': 5}`. If you see `api_error`, open the JSONL and read the
error — HTTP 402 means the account has no credits.

### The runs

**Stratified subset (~86 min each, recommended)** — 151 items: all 35 drift
probes, all 26 tours, 90 sampled controls.

```bash
python run.py --condition C1 --items items_150.jsonl --out ../results/C1.jsonl --resume
python run.py --condition C3 --items items_150.jsonl --out ../results/C3.jsonl --resume
```

**Full benchmark (~4.7 h each)** — all 500 items.

```bash
python run.py --condition C1 --out ../results/C1.jsonl --resume
python run.py --condition C3 --out ../results/C3.jsonl --resume
```

Always pass `--resume`. If a run dies, rerun the identical command and it picks
up where it stopped. Progress and an ETA print every 10 items.

### Analysis

```bash
cd ../results
python analyse.py --runs C1.jsonl C3.jsonl --latex tables.tex
```

Prints per-layer validity, failure attribution, Wilson intervals and a McNemar
test, and writes LaTeX macros so paper numbers come from run files rather than
being typed by hand.

---

## The conditions

| | Specification | Model | Tests |
|---|---|---|---|
| **C1** | Σ₀ (deployed) | baseline | H2 — how many failures are drift-entailed |
| **C3** | Σ_R (repaired) | *same* | RQ3 — does repairing Σ help, and in which layers |
| C2 / C4 | — | — | **refuse to run** ↓ |

C1 vs C3 holds the model fixed and varies only the specification, so any
difference is attributable to Σ alone. That is the study's primary comparison.

C2 and C4 isolate *model capability*. On a free-tier account the strong and
baseline slots resolve to the same model, so running them would measure
sampling noise and report it as a capability effect. `run.py` exits with an
explanation instead.

**To enable them:** buy OpenRouter credits, then in `run.py` set
`MODELS["strong"]` to a genuinely stronger model (`MODELS["deployed"]` and
`MODELS["paid_strong"]` are pre-filled). Hypothesis H3 is untestable until then.

---

## Safety guards in the runner

- **Lock file** — refuses to start if another run holds the same output. Two
  concurrent runs once corrupted a file; see `results/discarded/`.
- **No silent clobber** — refuses to overwrite a non-empty output without
  `--resume`.
- **No fake capability comparison** — the C2/C4 refusal above.

---

## Regenerating the benchmark

Only needed if the BI4YOU sources change.

```bash
cd extractor && python extract.py --root ... && python parse_spec.py --root ... && python drift.py
cd ../benchmark && python generate.py --target 500 && python subset.py --controls 90
python repair.py     # regenerate Σ_R from the new Σ₀
```

Generation is seeded (`SEED = 20260920`), so the same sources give the same
items.

---

## ⚠️ Before publishing this repository

1. **Confirm `.env` is absent.** `git status` must not list it. Only
   `.env.example` ships.
2. **Rotate any key** that has been pasted into a chat, a terminal transcript,
   or a screenshot.
3. **Verify `references.bib`** — every entry is marked `UNVERIFIED` and needs
   checking against the publisher record.
4. **Confirm co-authorship** with the supervisor before circulating (see
   `CITATION.md`).
