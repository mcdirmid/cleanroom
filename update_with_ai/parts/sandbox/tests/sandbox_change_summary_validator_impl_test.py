"""Unit tests for sandbox_change_summary_validator_impl aligned with grounding specifications."""

import unittest
from update_with_ai.parts.dag.lib.dag_storage import Node
from update_with_ai.parts.agent.lib.agent_file_alias import ReadWriteFile, WorkspacePath
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.sandbox.lib.sandbox_change_summary_validator import (
    ChangeSummaryValidator,
    DiffSummary,
    NetChange,
)
from update_with_ai.parts.sandbox.lib.sandbox_change_summary_validator_impl import (
    ChangeSummaryValidator as ChangeSummaryValidatorImpl,
    __initialize__,
)
from update_with_ai.parts.agent.lib.agent_node_config import VerificationCheck


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class SandboxChangeSummaryValidatorImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_net_change_and_diff_summary_dataclasses(self) -> None:
        """CUJ: Instantiating NetChange and DiffSummary records."""
        node = Node(unit_address="//pkg:target")
        rw_file = ReadWriteFile(
            short_name="module.py",
            workspace_path=_make_workspace_path("pkg/module.py"),
            owning_node=node,
        )
        change = NetChange(
            file=rw_file,
            initial_content="def old(): pass",
            current_content="def new(): pass",
        )
        self.assertEqual(change.file, rw_file)
        self.assertEqual(change.initial_content, "def old(): pass")
        self.assertEqual(change.current_content, "def new(): pass")

        diff = DiffSummary(summary_text="- old\n+ new")
        self.assertEqual(diff.summary_text, "- old\n+ new")

    def test_verify_and_lifecycle_retrieval(self) -> None:
        """CUJ: Resolving validator and performing change verification."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            validator = scope.get_singleton(ChangeSummaryValidator)
            self.assertIsInstance(validator, ChangeSummaryValidatorImpl)

            # VerificationCheck interface compatibility
            check = scope.get_singleton(VerificationCheck)
            self.assertIs(check, validator)

            # Requirement: The change summary validator compares initial baseline file content with current content to identify net changes.
            is_valid, msg = validator.verify()
            self.assertTrue(is_valid)
            self.assertIn("valid", msg.lower())


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - The change summary validator rejects change summaries exceeding the soft length bound up to a grace limit before rejecting at the hard bound.
# - A diff summary truncates line diffs exceeding the configured diff size limit.
# - If a change summary fails to describe all files with net changes, verification fails with diagnostic feedback.
# - If a change summary claims changes for unchanged files, verification fails with diagnostic feedback.
# - [ChangeSummaryValidator] The change summary validator verifies that a change summary describes all net changes across workspace files.
# - [ChangeSummaryValidator] The change summary validator rejects a change summary that claims changes for files with no net change.
# - [ChangeSummaryValidator] The change summary validator produces a diff summary of modified files.
# - [ChangeSummaryValidator] The change summary validator rejects a change summary exceeding configured length bounds with shortening guidance.
