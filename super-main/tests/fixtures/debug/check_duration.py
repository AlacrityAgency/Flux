"""Independent regression oracle for an isolated project-owned duration validator."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
from duration_app import valid_duration


control = "--control" in sys.argv
checks = []
if control:
    probes = [("valid-duration-accepted", 120, True), ("negative-duration-rejected", -1, False)]
else:
    probes = [("invalid-duration-rejected", "banana", False)]
for name, value, expected in probes:
    checks.append({"name": name, "status": "PASS" if valid_duration(value) is expected else "FAIL", "executed": 1})
print(json.dumps({"checks": checks}))
raise SystemExit(1 if any(row["status"] == "FAIL" for row in checks) else 0)
