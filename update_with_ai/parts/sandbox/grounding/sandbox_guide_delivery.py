# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 6df0c9de2efd
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Sandbox guide delivery grounding specification module."""

from __future__ import annotations
from typing import NewType, Optional, Protocol
from support.lib.grounding_support import InTier, AgentSessionTier
from parts.agent.grounding import agent_file_alias, agent_node_config
from parts.sandbox.grounding import tool_provider

InitialPrimer = NewType("InitialPrimer", str)


class GuideDelivery(InTier[AgentSessionTier], Protocol):
    """Delivers sequential task guidance and gates progression behind verification checks."""

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """
        DEFERRED:
        - MUST return the configured node guide when present.
        """
        raise NotImplementedError

    @property
    def has_steps_remaining(self) -> bool:
        """
        DEFERRED:
        - MUST return whether progressive steps remain to be completed.
        """
        raise NotImplementedError

    def parse_guide(
        self, content: agent_file_alias.FileContent
    ) -> agent_node_config.NodeGuide:
        """
        COVERED:
        - MUST parse file content into a structured node guide.
          - Consequent knowledge: construct NodeGuide record.

        DEFERRED:
        - Markdown heading parsing and section extraction deferred to sandbox_guide_delivery_impl.py.
        """
        sample_section = agent_node_config.StepSection(
            index=agent_node_config.StepIndex(1),
            title=agent_node_config.StepTitle("Initial Step"),
            content=agent_node_config.StepContent("Follow instructions"),
        )
        _guide = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Overview"),
            sections=[sample_section],
        )
        raise NotImplementedError

    def record_initial_primer(self, primer: InitialPrimer) -> None:
        """
        DEFERRED:
        - MUST record the initial primer text.
        - Deferred to sandbox_guide_delivery_impl.py.
        """
        raise NotImplementedError

    def advance_step(
        self,
        verification_passed: bool,
        failure_diagnostics: agent_node_config.VerificationDiagnostic,
    ) -> Optional[tool_provider.ToolResponse]:
        """
        COVERED:
        - WHEN verification passes, MUST deliver instructional text.
          - Condition knowledge: test verification_passed.
          - Consequent knowledge: construct ToolResponse carrying next step contents.
        - WHEN verification fails, MUST retain current milestone and report failure diagnostics alongside verification failure instructions.
          - Condition knowledge: test not verification_passed.
          - Consequent knowledge: construct failed ToolResponse carrying failure_diagnostics.

        DEFERRED:
        - Step index pointer advancement deferred to sandbox_guide_delivery_impl.py."""
        _passed: bool = verification_passed
        _failure_resp: tool_provider.ToolResponse = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Verification failed: {failure_diagnostics}",
        )
        _success_resp: tool_provider.ToolResponse = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Next milestone instructions",
        )
        raise NotImplementedError
