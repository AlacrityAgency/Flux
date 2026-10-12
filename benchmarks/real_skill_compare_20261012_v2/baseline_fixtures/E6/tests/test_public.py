import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'version': 2, 'payload': {'title': 'legacy', 'display_name': 'new'}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'label': 'new'})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'version': 3, 'payload': {'title': 'A'}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'version'})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'version': 1, 'payload': {}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'missing'})
        self.assertEqual(facts,before)
