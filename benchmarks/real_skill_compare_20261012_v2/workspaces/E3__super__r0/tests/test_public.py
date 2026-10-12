import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'initial': 10, 'events': [{'id': 'a', 'kind': 'credit', 'amount': 7}, {'id': 'a', 'kind': 'credit', 'amount': 7}]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'balance': 17, 'applied': 1})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'initial': 0, 'events': [{'id': 'a', 'kind': 'credit', 'amount': 7}, {'id': 'a', 'kind': 'credit', 'amount': 8}]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'conflict'})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'initial': 2, 'events': []}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'balance': 2, 'applied': 0})
        self.assertEqual(facts,before)
