import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'rows': [{'id': 2, 'name': 'B'}, {'id': 1, 'name': 'A'}]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'rows': [{'id': 1, 'display_name': 'A'}, {'id': 2, 'display_name': 'B'}]})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'rows': [{'id': 1, 'name': 'X'}, {'id': 1, 'name': 'Y'}]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'duplicate'})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'rows': [{'id': 2}]}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'error': 'missing_name'})
        self.assertEqual(facts,before)
