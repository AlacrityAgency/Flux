import os
import unittest

from calc import add

STATE = os.path.join(os.path.dirname(__file__), ".flaky_state")


class MixedTests(unittest.TestCase):
    def test_add_passes(self):
        self.assertEqual(add(1, 1), 2)

    def test_add_wrong_expectation(self):
        self.assertEqual(add(2, 2), 5)

    def test_alternates_between_runs(self):
        count = 0
        if os.path.exists(STATE):
            with open(STATE) as handle:
                count = int(handle.read())
        with open(STATE, "w") as handle:
            handle.write(str(count + 1))
        self.assertEqual(count % 2, 0)


if __name__ == "__main__":
    unittest.main()
