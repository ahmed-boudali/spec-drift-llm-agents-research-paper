# Discarded runs

`C1-interleaved-DISCARD.jsonl` — 13 records produced while two `run.py`
instances were writing to the same output file concurrently. Interleaved writes
from independent processes, so item ordering and completeness are not
trustworthy. Retained only for provenance; **not** used in any reported result.
