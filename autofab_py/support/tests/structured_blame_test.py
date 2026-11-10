"""Unit tests for support.lib.structured_blame."""

from __future__ import annotations

import unittest
from support.lib import experiments, structured_blame


class StructuredBlameTest(unittest.TestCase):
    def setUp(self) -> None:
        experiments.clear_active_experiments()

    def tearDown(self) -> None:
        experiments.clear_active_experiments()

    def test_active_check(self) -> None:
        self.assertFalse(structured_blame.is_structured_blame_active())
        experiments.set_active_experiments("structured_blame")
        self.assertTrue(structured_blame.is_structured_blame_active())

    def test_parse_valid_bnf_string(self) -> None:
        text = (
            "[slug:semver.range.whitespace] [viol:post.wrong_return] "
            "Facet: embedded operator whitespace Witness: input='>= 1.0.0'"
        )
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.slug, "[slug:semver.range.whitespace]")
        self.assertEqual(blame.violation, "[viol:post.wrong_return]")
        self.assertEqual(blame.facet, "embedded operator whitespace")
        self.assertEqual(blame.witness, "input='>= 1.0.0'")

    def test_parse_without_witness(self) -> None:
        text = "[slug:semver.range.caret] [viol:cov.missing_boundary_endpoint] Facet: zero major caret boundary"
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertIsNone(blame.witness)

    def test_parse_from_cli_options(self) -> None:
        blame, errs = structured_blame.parse_structured_blame(
            text="",
            slug="semver.range.whitespace",
            viol="post.wrong_return",
            facet="embedded operator whitespace",
            witness="val=1",
        )
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.slug, "[slug:semver.range.whitespace]")
        self.assertEqual(blame.violation, "[viol:post.wrong_return]")

    def test_parse_malformed_string_fails(self) -> None:
        bad_texts = [
            "Just a free-form critique explaining why this failed.",
            "[slug:only.slug]",
            "[slug:foo] [viol:bar]",  # Missing Facet:
        ]
        for bad in bad_texts:
            blame, errs = structured_blame.parse_structured_blame(bad)
            self.assertIsNone(blame)
            self.assertTrue(len(errs) >= 1)

    def test_validate_action_token_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="[viol:post.wrong_return]",
            facet="fix the return value",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(any("forbidden imperative action token" in e for e in errs))

    def test_validate_facet_length_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="[viol:post.wrong_return]",
            facet="this facet description has way more than eight individual words inside it",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(any("exceeds maximum word count" in e for e in errs))

    def test_validate_test_symbol_leak_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="[viol:post.wrong_return]",
            facet="empty input error",
            witness="assert test_helper() == True",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(any("Information leakage detected" in e for e in errs))

    def test_validate_valid_blame_passes(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="[viol:post.wrong_return]",
            facet="empty input delimiter",
            witness="input='', exp=None",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertEqual(errs, [])

    def test_parse_and_validate_generalized_noun_phrase_violation(self) -> None:
        text = (
            "[slug:dag_lite.dag.get_node.node_must_exist] Violation: precondition error omission "
            "Facet: unregistered node identifier Witness: op=get_node, node='ghost', exp=NodeNotFoundError, obs=AssertionError"
        )
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.slug, "[slug:dag_lite.dag.get_node.node_must_exist]")
        self.assertEqual(blame.violation, "Violation: precondition error omission")
        self.assertEqual(blame.facet, "unregistered node identifier")
        self.assertEqual(
            blame.witness,
            "op=get_node, node='ghost', exp=NodeNotFoundError, obs=AssertionError",
        )

        val_errs = structured_blame.validate_structured_blame(blame, "lib/dag.py")
        self.assertEqual(val_errs, [])

    def test_validate_violation_action_token_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: fix the error handling",
            facet="unregistered node identifier",
            witness="node='ghost'",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(
            any(
                "Violation contains forbidden imperative action token" in e
                for e in errs
            )
        )

    def test_validate_witness_line_number_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: precondition error omission",
            facet="unregistered node identifier",
            witness="line=102, node='ghost'",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(any("dedicated 'Lines:' component" in e for e in errs))

    def test_parse_and_validate_lines_component(self) -> None:
        text = (
            "[slug:semver.range.whitespace] Violation: postcondition divergence "
            "Facet: embedded operator whitespace Lines: 84-88 Witness: input='>= 1.0.0', exp='>=1.0.0'"
        )
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.lines, "84-88")
        self.assertEqual(blame.to_critique_string(), text)

        val_errs = structured_blame.validate_structured_blame(blame, "lib/semver.py")
        self.assertEqual(val_errs, [])

    def test_validate_lines_range_ordering_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: postcondition divergence",
            facet="embedded operator whitespace",
            lines="50-40",
            witness="input='>= 1.0.0'",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(any("cannot precede start line" in e for e in errs))

    def test_validate_foreign_file_reference_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: postcondition divergence",
            facet="embedded operator whitespace",
            lines="42",
            witness="input='foo', companion_test='test_suite.py'",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(
            any(
                "Information leakage: critique references foreign file" in e
                for e in errs
            )
        )

    def test_validate_witness_prose_without_key_value_rejection(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: precondition error omission",
            facet="unregistered node identifier",
            witness="require_arg uses Domain in set blocking tests",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertTrue(
            any("Witness must contain literal key-value pairs" in e for e in errs)
        )

    def test_validate_witness_permits_action_tokens_in_values(self) -> None:
        blame = structured_blame.StructuredBlame(
            slug="[slug:valid.slug]",
            violation="Violation: precondition error omission",
            facet="unregistered node identifier",
            witness="op='add_node', node_id='n1', action='delete'",
        )
        errs = structured_blame.validate_structured_blame(blame, "lib/foo.py")
        self.assertEqual(errs, [])

    def test_parse_bracketed_witness_and_lines(self) -> None:
        text = (
            "[slug:semver.range.whitespace] Violation: postcondition divergence "
            "Facet: embedded operator whitespace [Lines: 84-88] [Witness: input='>= 1.0.0']"
        )
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.lines, "84-88")
        self.assertEqual(blame.witness, "input='>= 1.0.0'")

    def test_parse_from_cli_flag_formatted_string(self) -> None:
        text = (
            "--slug semver.range.whitespace --viol 'postcondition divergence' "
            "--facet 'embedded operator whitespace' --lines '84-88' --witness 'input=\">= 1.0.0\"'"
        )
        blame, errs = structured_blame.parse_structured_blame(text)
        self.assertEqual(errs, [])
        self.assertIsNotNone(blame)
        assert blame is not None
        self.assertEqual(blame.slug, "[slug:semver.range.whitespace]")
        self.assertEqual(blame.violation, "Violation: postcondition divergence")
        self.assertEqual(blame.facet, "embedded operator whitespace")
        self.assertEqual(blame.lines, "84-88")
        self.assertEqual(blame.witness, 'input=">= 1.0.0"')


if __name__ == "__main__":
    unittest.main()
