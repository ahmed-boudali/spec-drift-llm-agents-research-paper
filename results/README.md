# results/

**This directory contains no experimental results, because the inference
experiments described in the paper were not run.**

What is here:

- `analyse.py` — aggregates scored run files into console summaries and LaTeX
  macros. It has no input yet.
- `pipeline-validation/` — 18 real model outputs from two tiny runs that verified
  the runner works end to end. **Not results**: n=18, unsampled, wrong model, no
  control stratum. Nothing in the paper derives from them. See the README there.
- `discarded/` — a 13-record partial file produced while two runner instances
  wrote concurrently to one output. Interleaved and untrustworthy; retained for
  provenance only and used in nothing.

## To produce results

See `../RUN_ME.md`. Running `run.py` writes `C1.jsonl` / `C3.jsonl` here, then:

```bash
python analyse.py --runs C1.jsonl C3.jsonl --latex ../paper/tables.tex
```

`analyse.py` emits LaTeX macros (`\CoNeDriftShare` and similar) that the paper
can consume directly, so reported numbers are generated from run files rather
than transcribed by hand.

## What the paper says in the meantime

Section 7.2 reports *illustrative projections* — clearly labelled as such, in a
distinct colour, with every table captioned `[ILLUSTRATIVE — NOT MEASURED]`.
They are not measurements and must not be cited as results.
