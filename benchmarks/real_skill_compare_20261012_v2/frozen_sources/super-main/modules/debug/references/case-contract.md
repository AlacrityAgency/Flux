# Experiment Case Contract (Version 1)

Save under `<project>/debug-cases/<id>.json` as versioned input. No shell interpolation: `command`
is argv. `{tmp}` and `{report}` are replaced with fresh temporary paths. Expected names must match
the independent runner's assertions. Preconditions are recorded for human review, not automatically
proven; the runner should assert machine-checkable ones. No implicit production permission exists.
The [JSON Schema](../case.schema.json) is available for editor/tool validation. Runtime uses the
stdlib validator in `core/lib/debugger.py`, with no extra package required. Unknown fields are errors.

```json
{
  "version": 1,
  "id": "reject-invalid-duration",
  "hypothesis": "Duration validation accepts nonnumeric input",
  "preconditions": ["Local validator and isolated fixtures; no live data"],
  "input": "duration = banana",
  "oracle": {
    "source": "Project requirement: motion duration is a finite nonnegative number",
    "reason": "Independent assertion checks rejection and unchanged output, not implementation truthiness"
  },
  "environment": "local",
  "command": ["python3", "tests/reproduce_duration.py", "--invalid", "--report", "{report}", "--data", "{tmp}"],
  "expected": ["invalid-duration-rejected", "no-invalid-output"],
  "timeout": 30,
  "cleanup": "temporary-data",
  "controls": [
    {
      "command": ["python3", "tests/reproduce_duration.py", "--valid", "--report", "{report}", "--data", "{tmp}"],
      "expected": ["valid-duration-accepted"]
    }
  ]
}
```

Each command writes JSON to `{report}` (or prints only that JSON):

```json
{"checks": [{"name": "invalid-duration-rejected", "status": "FAIL", "executed": 1}]}
```

Use PASS/FAIL/SKIP. PASS/FAIL require a positive integer number of actual executed assertions;
booleans and zero are invalid. Exit 0 for healthy assertions, 1 for a failed assertion. Dependency
errors must not be encoded as failing product assertions: use a non-0/1 exit or mark SKIP.
Every expected assertion must appear; missing or skipped coverage prevents confirmation/refutation.
The JSON contract is not proof that assertions are honest: inspect the runner independently.

Records are stored via the shared evidence ledger under `.superagent/runs/` with SHA-256 hashes.
Fix verification keeps the exact case/oracle hash, prior failing run id, source fingerprints and
healthy control observations. Local hashes detect accidental change; they are not signatures or a
tamper-proof ledger against someone able to rewrite both reports and the ledger.
