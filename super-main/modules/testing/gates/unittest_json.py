#!/usr/bin/env python3
"""Run unittest discovery in the current directory and write per-test outcomes as JSON.

Used by testing.run for projects without pytest: parsing unittest's text output is fragile
(warnings and prints interleave with result lines), so outcomes are captured from the result object.
"""

import argparse
import json
import sys
import unittest


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def _record(self, test, outcome):
        test_id = test.id()
        module_class, _, name = test_id.rpartition(".")
        self.outcomes[f"{module_class}::{name}" if module_class else test_id] = outcome

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "failed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--start", default=".")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("paths", nargs="*", help="Optional test files to run instead of discovering all tests")
    args, _ = parser.parse_known_args()
    sys.path.insert(0, ".")
    if args.paths:
        import os
        suite = unittest.TestSuite()
        for path in args.paths:
            suite.addTests(unittest.defaultTestLoader.discover(os.path.dirname(path) or ".", pattern=os.path.basename(path), top_level_dir="."))
    else:
        suite = unittest.defaultTestLoader.discover(args.start, pattern=args.pattern, top_level_dir=".")
    runner = unittest.TextTestRunner(verbosity=1, resultclass=RecordingResult)
    result = runner.run(suite)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result.outcomes, handle, indent=2)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
