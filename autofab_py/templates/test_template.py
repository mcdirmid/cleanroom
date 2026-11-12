from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase, fake

# Cleanroom test module.
# Derive your test suite directly from the low-level specification (.pyi)
# following your Companion Guide (guides/low_to_test.md).
# Target implementations MUST be imported with their full package-qualified path:
#   from <package>.lib.<unit_name>_impl import <TargetClass>
# (where <package> is the Python package name containing lib/, e.g. from my_part.lib.my_part_impl import ...)
# Organize test cases inheriting from LifecycleTestCase with test methods (test_*).
# Target singletons under test are registered automatically and accessible via self.sut.
# Collaborator fakes are declared using @fake within the test class.
# Never cite specification slugs in test comments or docstrings (prohibited by slug_lint).
# Never import or call __initialize__; never manually create LifecycleRegistry or enter_phase.
#
# Example:
#   class ExampleTest(LifecycleTestCase):
#       @fake
#       class FakeCollaborator(CollaboratorProtocol):
#           tier = "system"
#           ...
#
#       def test_basic_operation(self) -> None:
#           """Verify basic operation completes successfully."""
#           result = self.sut.do_something()
#           self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()


