import copy, unittest
from solution import solve

class PublicTests(unittest.TestCase):
    def test_case_0(self):
        facts={'actor': {'id': 'a', 'tenant': 'T', 'role': 'user', 'active': True}, 'resource': {'owner': 'a', 'tenant': 'T'}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'allowed': True})
        self.assertEqual(facts,before)
    def test_case_1(self):
        facts={'actor': {'id': 'a', 'tenant': 'T', 'role': 'admin', 'active': True}, 'resource': {'owner': 'b', 'tenant': 'U'}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'allowed': False})
        self.assertEqual(facts,before)
    def test_case_2(self):
        facts={'actor': {'id': 'a', 'tenant': 'T', 'role': 'user', 'active': False}, 'resource': {'owner': 'a', 'tenant': 'T'}}
        before=copy.deepcopy(facts)
        self.assertEqual(solve(facts),{'allowed': False})
        self.assertEqual(facts,before)
