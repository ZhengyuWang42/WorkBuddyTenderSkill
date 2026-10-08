# XLSX Round9–12: historical reproduction vs current regression

Two questions are kept separate:

1. **HISTORICAL REPRODUCTION** — does a frozen intermediate successor still
   reproduce the verdict its own committed report records?
2. **CURRENT REGRESSION** — does the current final Round-12 successor still
   satisfy the invariant that round introduced?

- HISTORICAL_REPRODUCTION_ALL_MATCH = True
- ROUND12_FINAL_XLSX_DELIVERY_TEXT = PASS

| round | historical verdict | historical reproduction | current verdict |
| --- | --- | --- | --- |
| round9 | PASS | MATCHES_FROZEN_EXPECTATION | PASS |
| round10 | PASS | MATCHES_FROZEN_EXPECTATION | PASS |
| round11 | PASS | MATCHES_FROZEN_EXPECTATION | PASS |
| round12 | PASS | MATCHES_FROZEN_EXPECTATION | PASS |

The Round-12 banked-regression gate re-runs the round-5/6/7 fixtures against
the round-12 successor workbooks, so the current verdicts above are measured
on the current authoritative artifact rather than on a historical one.
