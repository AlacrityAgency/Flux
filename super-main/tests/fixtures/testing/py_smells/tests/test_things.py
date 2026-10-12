import time
import unittest


class ThingTests(unittest.TestCase):
    def test_empty(self):
        pass

    def test_sleeps(self):
        time.sleep(0.01)
        self.assertTrue(True)

    def test_no_assert(self):
        value = 1 + 1

    @unittest.skip("later")
    def test_skipped(self):
        self.assertEqual(1, 1)

    def test_good(self):
        self.assertEqual(sorted([3, 1]), [1, 3])
