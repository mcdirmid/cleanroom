"""Unit tests for support.lib.slug_lint."""

from __future__ import annotations

import unittest
from autofab_py.support.lib import slug_lint


class SlugLintTest(unittest.TestCase):
    def test_valid_slugs(self) -> None:
        content = (
            '"""Interface spec."""\n'
            "def foo() -> None:\n"
            '    """[slug:my_module.func.postcond] MUST return 1."""\n'
            "    ...\n"
            "def bar() -> None:\n"
            '    """[slug:my_module.func.err] MUST raise ValueError."""\n'
            "    ...\n"
        )
        errors = slug_lint.validate_spec_slugs(content, "test.pyi")
        self.assertEqual(errors, [])

    def test_duplicate_slug_detected(self) -> None:
        content = (
            '"""Interface spec."""\n'
            "def foo() -> None:\n"
            '    """[slug:dup.tag] MUST return 1."""\n'
            "    ...\n"
            "def bar() -> None:\n"
            '    """[slug:dup.tag] MUST raise ValueError."""\n'
            "    ...\n"
        )
        errors = slug_lint.validate_spec_slugs(content, "test.pyi")
        self.assertEqual(len(errors), 1)
        self.assertIn("duplicate specification slug", errors[0])

    def test_malformed_slug_detected(self) -> None:
        bad_cases = [
            '"""[slug:UPPERCASE.TAG]"""',
            '"""[slug:has spaces.tag]"""',
            '"""[slug:special$char]"""',
        ]
        for bad in bad_cases:
            errors = slug_lint.validate_spec_slugs(bad, "test.pyi")
            self.assertTrue(len(errors) >= 1, f"Expected error for: {bad}")
            self.assertIn("malformed specification slug", errors[0])

    def test_no_slug_references_clean(self) -> None:
        content = (
            "def test_foo():\n    slug = 'arbitrary_variable'\n    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(errors, [])

    def test_inband_metadata_feedback_permitted(self) -> None:
        content = (
            "# --- AUTOFAB METADATA ---\n"
            "# FEEDBACK:\n"
            "# - [slug:my_module.func.postcond] [viol:test.unmandated_behavior] Facet: Error in test\n"
            "# --- END AUTOFAB METADATA ---\n"
            "def test_foo():\n"
            "    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(errors, [])

    def test_inband_metadata_preserves_code_line_numbers(self) -> None:
        content = (
            "# --- AUTOFAB METADATA ---\n"
            "# FEEDBACK:\n"
            "# - [slug:my_module.func.postcond] In-band metadata feedback\n"
            "# --- END AUTOFAB METADATA ---\n"
            "# Line 5: Real prohibited reference to [slug:my_module.func.postcond]\n"
            "def test_foo():\n"
            "    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("test_foo.py:5:", errors[0])

    def test_declared_contract_references_prohibited_in_code(self) -> None:
        content = (
            "# Testing against [slug:my_module.func.postcond]\n"
            "def test_foo():\n"
            "    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "reference to declared specification contract 'my_module.func.postcond'",
            errors[0],
        )

    def test_unbracketed_contract_in_docstring_prohibited(self) -> None:
        content = (
            "def test_foo():\n"
            '    """POSTCONDITION my_module.func.postcond: returns 1."""\n'
            "    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "reference to declared specification contract 'my_module.func.postcond'",
            errors[0],
        )

    def test_boilerplate_and_hallucinated_slugs_ignored(self) -> None:
        content = (
            "# Just boilerplate: [slug:nonexistent.contract.clause]\n"
            "def test_foo():\n"
            '    """Some other [slug:fake.id] comment."""\n'
            "    assert foo() == 1\n"
        )
        errors = slug_lint.check_no_slug_references(
            content,
            "test_foo.py",
            declared_contract_ids={"my_module.func.postcond"},
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
