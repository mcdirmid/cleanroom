"""Tests for grounding_support infrastructure."""

import unittest
from update_with_ai.support.lib.grounding_support import (
    AgentSessionTier,
    InTier,
    SystemTier,
    key,
    only_elem,
    value,
)


class DummySystemService(InTier[SystemTier]):
    pass


class DummySessionService(InTier[AgentSessionTier]):
    pass


class GroundingSupportTest(unittest.TestCase):
    def test_single_element_collection_utilities(self):
        m = {"hello": "world"}
        self.assertEqual(key(m), "hello")
        self.assertEqual(value(m), "world")

        seq = [42]
        self.assertEqual(only_elem(seq), 42)

    def test_in_tier_types(self):
        sys_svc = DummySystemService()
        sess_svc = DummySessionService()
        self.assertIsInstance(sys_svc, InTier)
        self.assertIsInstance(sess_svc, InTier)


if __name__ == "__main__":
    unittest.main()
