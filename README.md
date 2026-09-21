# Specification–Implementation Drift in LLM Agents

When an LLM agent drives enterprise software, it is usually told what the
application contains by a hand-written system prompt. That prompt is a *second*
description of a system whose authoritative description is its source code — and
nothing keeps the two in sync.

This repository measures the gap, on a real deployed system.

**The finding in one line:** the agent's specification describes a subsystem that
was never built, omits two of six user roles, and states a business rule that
binds a different entity than the code enforces — and no test, compiler, or
conventional agent evaluation would catch any of it.

---

## Why this is hard to study, and why this system is unusual

To measure drift you need two independent descriptions of one system. Agent
benchmarks like WebArena and Mind2Web build their environments *for* the
benchmark, so the description and the environment are the same artefact — there
is nothing to drift *from*.

BI4YOU has both:

| | Artefact | Size |
|---|---|---|
| **Σ** (informal) | A hand-authored system prompt inside `FinanceAIService.java` | 638 lines, 37,701 chars |
| **I** (formal) | Angular templates, router, guards, Spring controllers | 94 selectors, 44 routes, 119 auth rules |

Neither was written to verify the other. That is what makes the comparison
informative.

---

## What was measured

Run it yourself in about five seconds — no database, no server, no API key:

```bash
cd extractor
python extract.py    --root /path/to/MyBi4you   # recover I from source
python parse_spec.py --root /path/to/MyBi4you   # recover Σ from the prompt
python drift.py                                 # set-difference the two
python validator.py                             # self-test on 26 gold tours
```

### Results

| Layer | Agreement | What diverges |
|---|---|---|
| **L1** lexical | **93 / 94** | 0 phantom selectors; 1 dark (`leaves`) |
| **L2** reachability | **14 / 14** URLs | …but bare `/timesheet` is *not* a declared route, while `/finance` is |
| **L3** authorisation | **4 / 6** roles | `FINANCE` and `CANDIDATE` absent from Σ; 3 guards admit roles Σ never mentions |
| **L4** procedural | — | 3 confirmed instances ↓ |

**The pattern is the point.** The layers whose violations fail *loudly* (a bad
selector breaks visibly) are clean. The layers whose violations fail *silently*
are where the drift lives. Most agent evaluation implicitly hunts for invented
affordances — L1 — which is precisely where this system has none.

### The three procedural defects

**L4-01 — phantom subsystem.** Σ documents finance accounting periods with
`OPEN`/`LOCKED` states that block invoice creation, names the roles that may
lock them, and describes the workflow. **No such entity, repository, service or
check exists anywhere in `finance-service`.** The mechanism is real in
`timesheet-service`; the specification generalised it to a module that never had
it.

An agent asked to lock a finance period will explain how — faithfully, in
detail, from its premises. Scored conventionally that is a hallucination. It
isn't. The model reasoned correctly over a false premise, and had no way to know.

**L4-02 — over-constraint.** Σ says a receipt is mandatory when *creating* a
supplier invoice. Extracting every business-rule exception in the finance
service layer shows the rule exists only for *cash operations at validation*.

**L4-03 — incomplete procedure.** The tour `"exporter les factures"` is the only
one of 26 with no navigation step, so its remaining steps cannot execute from
any route but `/finance/invoices`. **This one was found by `validator.py`, not
by the manual audit** — which is the property the instrument needed to have.

---

## Repository layout

```
extractor/
  extract.py        recover I from Angular + Spring sources (static analysis)
  parse_spec.py     recover Σ from the agent's system prompt
  drift.py          compute the four-layer drift table
  validator.py      four-dimensional action validator + gold-tour self-test
  routes.py         shared affordance / route / guard tables
  *.json            extractor output (committed so the audit is inspectable)

benchmark/
  generate.py       build the 500-item benchmark from measured drift
  subset.py         stratified 151-item subset (keeps all 35 probes)
  repair.py         derive Σ_R from Σ₀ by six pre-specified repairs
  run.py            agent runner + scorer   ← the only part needing an API key
  sigma_0.txt       the deployed specification, verbatim
  sigma_R.txt       the repaired specification (+851 chars, 6 edits)
  items*.jsonl      generated benchmark items

results/
  analyse.py        aggregate run files into LaTeX tables
  pipeline-validation/  18 real outputs proving the runner works — NOT results
  discarded/        a corrupted partial run, kept for provenance
```

---

## How the validator works

Given an action the agent emitted, it answers two questions independently:

**Is the action valid under the implementation?**

| | Check |
|---|---|
| `V1` existence | the selector appears in some template |
| `V2` reachability | the target is reachable from the current route |
| `V3` permission | the acting role is admitted by the guard |
| `V4` procedure | step ordering respects extracted preconditions |

**Is the action entailed by the specification?** — `entailed` / `contradicted` /
`unspecified`.

Crossing them attributes every failure:

| Valid under I? | Entailed by Σ? | Verdict |
|---|---|---|
| ✗ | contradicted | `F_model` — the model violated a correct spec |
| ✗ | **entailed** | **`F_drift`** — the model was faithful to a false premise |
| ✗ | unspecified | `F_gap` — the spec was silent, the model guessed |

That middle row is the whole point. Conventional evaluation reports one number
and cannot separate it from the row above.

---

## Status: what ran and what didn't

| | Status |
|---|---|
| **E1 — drift audit** | ✅ **Executed.** Every figure above, reproducible in seconds |
| E2–E5 — inference experiments | ⬜ **Not executed.** Runner ships; needs an inference budget |

**There are no execution logs in this repository.** The inference experiments
were not run, and nothing here pretends otherwise. The paper reports projections
for them, rendered in a distinct colour with every table captioned
`[ILLUSTRATIVE — NOT MEASURED]`.

`results/pipeline-validation/` holds 18 genuine model outputs from two small
runs that verified the runner works end to end. They are labelled, explained,
and no figure anywhere derives from them.

### Running the experiments

See **[RUN_ME.md](RUN_ME.md)**. `run.py` calls the agent over HTTP —
**BI4YOU does not need to be running.**

```bash
cp .env.example .env        # add your OpenRouter key
pip install -r requirements.txt
cd benchmark
python run.py --condition C1 --items items_150.jsonl --out ../results/C1.jsonl --resume
python run.py --condition C3 --items items_150.jsonl --out ../results/C3.jsonl --resume
cd ../results && python analyse.py --runs C1.jsonl C3.jsonl
```

Roughly 86 minutes per condition on a free-tier model.

**C2 and C4 deliberately refuse to run.** They isolate model capability, and on
a free-tier account the strong and baseline slots resolve to the same model — so
any difference would be sampling noise presented as a capability effect. The
runner exits with an explanation instead. Hypothesis H3 is consequently
untested, and the paper says so.

---

## Design decisions worth knowing

**Σ_R is mechanical, not hand-tuned.** `repair.py` applies six pre-specified
edits derived from the measured drift, asserts each applies exactly once, and
aborts otherwise. A specification tuned against the benchmark would make the
repaired condition win by construction.

**One schema artefact is excluded, on purpose.** Naive extraction finds a
selector named `selector` — an artefact of the JSON example in the prompt. We
exclude it and say so, because an unaudited drift pipeline would have reported a
defect that does not exist.

**The probe strata are small (35, not 250).** Probes are generated from
*measured* divergences, and this system has few. Padding with synthetic drift
would restore the count and destroy its meaning. It is a real limit on
statistical power, recorded as such.

**No aggregate drift score.** The layers are counted in incommensurable units —
selectors, routes, roles, rules. Averaging them would manufacture precision the
measurement doesn't have.

---

## Limitations

- **n = 1.** One system. The layer ordering (L1 ≻ L2 ≻ L3 ≻ L4) is a
  detection-pressure hypothesis consistent with one observation, not a
  regularity.
- **Drift is not shown to cause failures.** E1 compares two documents. Nothing
  here measures model behaviour. That is what E2–E5 are for.
- **L4 extraction is partly manual**, and the audit is not exhaustive — hence
  "at least three" instances, not "three".
- **The extractor is framework-specific** (Angular + Spring Boot). The
  formalisation generalises; this code does not.
- **Author bias:** the author wrote the system whose defects are reported,
  including Σ₀. L1–L3 are mechanical set differences anyone can recompute; L4
  depends on judgement and is flagged.

---

## Requirements

Python 3.10+. The extractor, drift computation, validator, generator and repair
tool use only the standard library. `run.py` needs `requests`
(`pip install -r requirements.txt`) and an OpenRouter API key in `.env`.

**Never commit `.env`.** It is gitignored; `.env.example` is the template.

---

## The paper

The accompanying working paper is **not yet in this repository** — it is being
finalised and will be added here (English and French) once ready. This
repository currently holds the instrument and the measured drift audit, which
stand on their own: everything reported above is reproducible from the code
here, without the paper.

## Citation

Working paper; see `CITATION.md`. The study system is BI4YOU, a final-year
engineering project at ESPRIT, Tunis.
