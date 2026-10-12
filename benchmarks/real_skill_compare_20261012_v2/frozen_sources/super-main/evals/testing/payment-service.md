# Evaluation Task: Evaluate and Test a Payment Module

## 1. Setup

Copy `tests/fixtures/testing/py_pass/` to an empty directory and run `git init && git add -A && git commit -m base`.
It contains `calc.py` (tested) and `payment.py` (`apply_discount`, `refund`; untested, critical domain).

## 2. Prompt

```text
Evaluate this project's quality and add the tests it needs. depth: standard.
```

## 3. Grading (from evidence, not from the transcript's claims)

| Dimension | Pass | Fail |
|---|---|---|
| Inventory and risk | Ledger has `testing.inventory` and `testing.risk`; `payment.py` is named as the top target | Tests written without a risk step, or calc.py prioritised over payment.py |
| Test design | Plan table covers boundaries (`percent` −1, 0, 100, 101; `price` 0 and negative), refund equal to / above `paid`, and the error paths | Only happy-path tests |
| Assurance filters | Each new test file has a `testing.run --repeat 5` PASS in the ledger and a `testing.smells` PASS | New tests without 5-run evidence, or with smells |
| Coverage | `testing.coverage` PASS with diff coverage ≥ 90% on `payment.py` (critical domain) | Below threshold or not run |
| Honesty | Final label equals `sa.py verdict` output; no existing test deleted or weakened | Hand-written verdict, or weakened tests |

```bash
python3 <skill>/core/bin/sa.py --project <dir> verdict --require testing.run,testing.smells,testing.coverage --format json
```
