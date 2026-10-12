import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'amount_cents': 105, 'percent': '50'}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'cents': 53})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'amount_cents': 0, 'percent': '12.5'}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'cents': 0})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'amount_cents': 101, 'percent': '100'}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'cents': 0})
        self.assertEqual(facts,before)
