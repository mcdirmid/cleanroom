# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T02:24:25Z
# CHANGE: Implement GuideDelivery in sandbox_guide_delivery_impl.py
# CODE_HASH: b2fe8dd869eb
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

from typing import List, Optional
from support.lib.lifecycle import (
    InTier,
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
from . import sandbox_guide_delivery
from . import tool_provider

# Requirements specified in sandbox_guide_delivery_impl.pyi


def _parse_guide_markdown(content: str) -> agent_node_config.NodeGuide:
    lines = content.splitlines()
    preamble_lines: List[str] = []
    summary_lines: List[str] = []
    sections: List[agent_node_config.StepSection] = []
    vf_lines: Optional[List[str]] = None
    curr_title: Optional[str] = None
    curr_sec: List[str] = []

    def flush(title: Optional[str], sec: List[str]) -> None:
        nonlocal vf_lines
        if title is None:
            preamble_lines.extend(sec)
            return
        t = title.strip().lower()
        if t == "summary" or t.startswith("summary"):
            summary_lines.extend(sec)
        elif t.startswith("verification failure"):
            vf_lines = list(sec)
        elif not t.startswith("lint checks"):
            sections.append(agent_node_config.StepSection(
                index=agent_node_config.StepIndex(len(sections)),
                title=agent_node_config.StepTitle(title),
                content=agent_node_config.StepContent("\n".join(sec).strip()),
            ))

    for line in lines:
        if line.startswith("## "):
            flush(curr_title, curr_sec)
            curr_title, curr_sec = line[3:].strip(), []
        else:
            curr_sec.append(line)
    flush(curr_title, curr_sec)

    clean_preamble = [l for l in preamble_lines if not l.startswith("# ")]
    combined = (clean_preamble if any(l.strip() for l in clean_preamble) else []) + summary_lines
    summary = "\n".join(combined or preamble_lines).strip()
    vf = agent_node_config.VerificationFailureInstructions("\n".join(vf_lines).strip()) if vf_lines is not None else None
    return agent_node_config.NodeGuide(
        summary=agent_node_config.GuideSummary(summary),
        sections=sections,
        verification_failure=vf,
    )


class GuideDelivery(sandbox_guide_delivery.GuideDelivery, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._guide: Optional[agent_node_config.NodeGuide] = None
        self._current_step: int = 0
        self._primer: Optional[sandbox_guide_delivery.InitialPrimer] = None

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        return self._guide

    @property
    def has_steps_remaining(self) -> bool:
        if self._guide is None:
            return False
        return self._current_step < len(self._guide.sections)

    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        guide = _parse_guide_markdown(str(content))
        self._guide = guide
        self._current_step = 0
        return guide

    def record_initial_primer(self, primer: sandbox_guide_delivery.InitialPrimer) -> None:
        self._primer = primer

    def advance_step(
        self,
        verification_passed: bool,
        failure_diagnostics: agent_node_config.VerificationDiagnostic,
    ) -> Optional[tool_provider.ToolResponse]:
        if verification_passed:
            if self._guide is not None and self._current_step < len(self._guide.sections):
                sec = self._guide.sections[self._current_step]
                self._current_step += 1
                content = f"## {sec.title}\n\n{sec.content}"
                return tool_provider.ToolResponse(
                    is_failed=False,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(content),
                )
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent("All milestone steps completed."),
            )
        else:
            parts: List[str] = []
            if self._current_step == 0:
                if self._primer:
                    parts.append(str(self._primer))
                if self._guide and self._guide.summary:
                    parts.append(str(self._guide.summary))
            vf_inst = str(self._guide.verification_failure) if self._guide and self._guide.verification_failure else ""
            if vf_inst:
                parts.append(vf_inst)
            diag = str(failure_diagnostics).strip()
            if diag:
                parts.append(diag)
            msg = "\n\n".join(parts) if parts else "Verification failed."
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(msg),
            )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        GuideDelivery,
        keys=[GuideDelivery, sandbox_guide_delivery.GuideDelivery, InTier[AgentSessionTier]],
        tier=agent_session,
    )

_initialize_ = __initialize__
