"""Unit tests for support.lib.markdown_preprocessor."""

from __future__ import annotations

import unittest
from support.lib import experiments, markdown_preprocessor


class MarkdownPreprocessorTest(unittest.TestCase):
    def test_passthrough_plain_text(self) -> None:
        source = (
            "# Hello\n\nThis is a standard markdown document.\n- Item 1\n- Item 2\n"
        )
        out = markdown_preprocessor.preprocess_markdown(
            source, active_experiments={"feat_a"}
        )
        self.assertEqual(out, source)

    def test_if_true_branch(self) -> None:
        source = (
            "Header\n"
            "<!-- if experiment:feat_a -->\n"
            "Feature A is enabled.\n"
            "<!-- endif -->\n"
            "Footer\n"
        )
        out = markdown_preprocessor.preprocess_markdown(
            source, active_experiments={"feat_a"}
        )
        self.assertEqual(out, "Header\nFeature A is enabled.\nFooter\n")

    def test_if_false_branch(self) -> None:
        source = (
            "Header\n"
            "<!-- if experiment:feat_a -->\n"
            "Feature A is enabled.\n"
            "<!-- endif -->\n"
            "Footer\n"
        )
        out = markdown_preprocessor.preprocess_markdown(
            source, active_experiments=set()
        )
        self.assertEqual(out, "Header\nFooter\n")

    def test_if_else_branch(self) -> None:
        source = (
            "<!-- if experiment:feat_a -->\n"
            "Alpha Active\n"
            "<!-- else -->\n"
            "Alpha Inactive\n"
            "<!-- endif -->\n"
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"feat_a"}
            ),
            "Alpha Active\n",
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(source, active_experiments=set()),
            "Alpha Inactive\n",
        )

    def test_if_elif_else(self) -> None:
        source = (
            "<!-- if experiment:mode_x -->\n"
            "Mode X\n"
            "<!-- elif experiment:mode_y -->\n"
            "Mode Y\n"
            "<!-- else -->\n"
            "Default Mode\n"
            "<!-- endif -->\n"
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"mode_x"}
            ),
            "Mode X\n",
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"mode_y"}
            ),
            "Mode Y\n",
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(source, active_experiments=set()),
            "Default Mode\n",
        )

    def test_line_suffix_conditional(self) -> None:
        source = (
            "- Base instruction\n"
            "- Feature instruction <!-- if experiment:feat_a -->\n"
            "- Alternative instruction <!-- if not experiment:feat_a -->\n"
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"feat_a"}
            ),
            "- Base instruction\n- Feature instruction\n",
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(source, active_experiments=set()),
            "- Base instruction\n- Alternative instruction\n",
        )

    def test_complex_boolean_expression(self) -> None:
        source = (
            "<!-- if experiment:feat_a and not experiment:feat_b -->\n"
            "Only A\n"
            "<!-- endif -->\n"
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"feat_a"}
            ),
            "Only A\n",
        )
        self.assertEqual(
            markdown_preprocessor.preprocess_markdown(
                source, active_experiments={"feat_a", "feat_b"}
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
