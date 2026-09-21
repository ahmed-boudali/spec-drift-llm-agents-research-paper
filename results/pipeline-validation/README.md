# pipeline-validation/

**These are NOT experimental results.** They are real model outputs from two
tiny runs used to verify that the runner, validator and attribution logic work
end to end before any experiment was contemplated.

| File | n | Purpose |
|---|---|---|
| `pipeline-check-tours-n8.jsonl` | 8 | tour-seeded items; confirms the happy path scores |
| `pipeline-check-probes-n10.jsonl` | 10 | drift probes; confirms attribution fires |

## Why they are not results

- **n = 18 total**, drawn in file order, not sampled.
- Model: `nvidia/nemotron-3-ultra-550b-a55b:free`, not the deployed
  `gpt-4o-mini` (which needs paid credits).
- No control stratum, no C3 comparison, no seeds, no statistics.

They establish only that *the instrument runs*. Nothing in the paper is derived
from them, and no figure in the paper was computed from these files.

## What they showed

The probe check returned 6 `F_drift`, 2 `F_gap`, 2 correct. The `F_drift` cases
were the agent walking a `CANDIDATE` through timesheet pages that
`timesheetGuard` refuses — because Σ₀ never mentions the `CANDIDATE` role.

That is the mechanism H2 predicts, observed once, at n=10. It is a reason to run
the experiment, not a substitute for running it.
