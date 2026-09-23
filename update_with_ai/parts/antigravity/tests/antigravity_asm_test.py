from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.antigravity.lib import antigravity_asm


class AntigravityAsmTest(unittest.TestCase):
    def test_initialize(self) -> None:
        reg = LifecycleRegistry()
        antigravity_asm.__initialize__(reg)
        self.assertTrue(len(antigravity_asm.CONSTITUENTS) > 0)


if __name__ == "__main__":
    unittest.main()
