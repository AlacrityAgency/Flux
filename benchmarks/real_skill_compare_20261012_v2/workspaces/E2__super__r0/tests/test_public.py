import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'intervals': [[1, 3], [3, 5], [2, 4], [8, 8]]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'intervals': [[1, 5]]})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'intervals': [[2, 1]]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'reversed'})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'intervals': []}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'intervals': []})
        self.assertEqual(facts,before)
