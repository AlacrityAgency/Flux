# Test Smells

Patterns that make a test suite slow, flaky or blind. `testing.smells` detects the ones below; names follow the test-smell literature (tsDetect / the open test smell catalogs).

| Smell | Detected as | Confidence | Why it matters | Fix |
|---|---|---|---|---|
| Focused test | `it.only`, `test.only`, `describe.only`, `fit`, `fdescribe` | verified → **fails** | Only part of the suite runs; the rest is silently skipped | Remove the focus marker |
| Empty Test | test body with no statements (or only `pass`) | verified → **fails** | Always passes, checks nothing | Write assertions or delete |
| Ignored / skipped test | `.skip`, `xit`, `@unittest.skip`, `@pytest.mark.skip`, `t.Skip` | suspected | Gives no protection, rots | Fix and re-enable, or delete with a tracked reason |
| Sleepy Test | `sleep`, `waitForTimeout(n)`, `setTimeout(…, ≥100ms)` | suspected | Slow and timing-dependent (flaky) | Wait for a condition, inject a fake clock |
| Assertion-free test | no `expect`/`assert`/`assert*` in the body | suspected | Only fails on exceptions; wrong results pass | Assert on the outcome |
| Conditional Test Logic | `if`/`for`/`while`/`switch` in a test | suspected | Hides which path was checked | Parametrise (`test.each`, `pytest.mark.parametrize`, `subTest`) |
| Mystery Guest / external dependency | real external URL in a test | suspected | Network makes tests slow and flaky | Mock the boundary, use a local double |
| Snapshot-only | only `toMatchSnapshot` | suspected | Snapshots get updated blindly | Add explicit behavioural assertions |

Suspected smells are reported but do not fail the gate: confirm them by reading the test before acting. New tests written by the agent must have **no** smells (filter F4).

Further reading: https://test-smell-catalog.readthedocs.io/ · https://testsmells.org/
