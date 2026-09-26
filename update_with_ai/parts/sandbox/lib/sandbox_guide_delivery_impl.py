# Requirements specified in sandbox_guide_delivery_impl.pyi
from typing import List, Optional
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from . import sandbox_guide_delivery
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)


class GuideDelivery(sandbox_guide_delivery.GuideDelivery, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._guide: Optional[agent_node_config.NodeGuide] = None
        self._initial_primer: Optional[str] = None
        self._step_index: int = 0

    def initialize(self) -> None:
        # Requirement: Initializing the guide delivery obtains its guide from the node config.
        cfg = get_singleton(agent_node_config.NodeConfig)
        self._guide = cfg.guide
        self._initial_primer = None
        self._step_index = 0

    def set_initial_primer(self, primer: str) -> None:
        # Requirement: Can record an initial primer.
        self._initial_primer = primer

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        if self._guide is None:
            try:
                cfg = get_singleton(agent_node_config.NodeConfig)
                self._guide = cfg.guide
            except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton NodeConfig resolvable)
                pass  # pragma: no cover
        return self._guide

    @property
    def has_steps_remaining(self) -> bool:
        # Requirement: [GuideDelivery] Steps remaining indicates whether further step sections remain to be completed.
        g = self.guide
        if g is None:
            return False
        return self._step_index < len(g.sections)

    def parse_guide(
        self, content: agent_file_alias.FileContent
    ) -> agent_node_config.NodeGuide:
        # Requirement: Guide parsing extracts the summary from content preceding the first section heading and under any heading titled `Summary`, captures verification failure instructions when a section heading begins with `Verification failure`, and creates sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Summary`, `Lint checks`, or `Verification failure`.
        raw = str(content)
        lines = raw.splitlines()
        summary_lines: List[str] = []
        sections: List[agent_node_config.StepSection] = []
        verification_failure_lines: Optional[List[str]] = None

        current_title: Optional[str] = None
        current_section_lines: List[str] = []

        for line in lines:
            if line.startswith("## "):
                if current_title is None:
                    summary_lines = list(current_section_lines)
                else:
                    if current_title.startswith("Summary"):
                        summary_lines.extend(current_section_lines)
                    elif current_title.startswith("Verification failure"):
                        verification_failure_lines = list(current_section_lines)
                    elif not current_title.startswith("Lint checks"):
                        sections.append(
                            agent_node_config.StepSection(
                                index=len(sections),
                                title=current_title,
                                content="\n".join(current_section_lines).strip(),
                            )
                        )
                current_title = line[3:].strip()
                current_section_lines = []
            else:
                current_section_lines.append(line)

        if current_title is not None:
            if current_title.startswith("Summary"):
                summary_lines.extend(current_section_lines)
            elif current_title.startswith("Verification failure"):
                verification_failure_lines = list(current_section_lines)
            elif not current_title.startswith("Lint checks"):
                sections.append(
                    agent_node_config.StepSection(
                        index=len(sections),
                        title=current_title,
                        content="\n".join(current_section_lines).strip(),
                    )
                )

        elif not summary_lines:
            summary_lines = current_section_lines

        vf_text = (
            "\n".join(verification_failure_lines).strip()
            if verification_failure_lines is not None
            else None
        )

        return agent_node_config.NodeGuide(
            summary="\n".join(summary_lines).strip(),
            sections=sections,
            verification_failure=vf_text,
        )

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.ToolResponse]:
        # Requirement: When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.
        g = self.guide
        if g is None or not self.has_steps_remaining:
            return None

        if not verification_passed:
            diag_text = failure_diagnostics or ""
            vf_block = ""
            if g.verification_failure:
                vf_block = (
                    f"\n\n## Verification failure\n{g.verification_failure}"
                )
            if self._step_index == 0:
                # Requirement: Advancing a step when verification fails emits a response combining the initial primer content (or guide summary when an initial primer is omitted), any configured verification failure instructions, and failure diagnostics without activating a step section when no step section has been delivered yet.
                base_text = self._initial_primer if self._initial_primer else g.summary
                content = f"{base_text}{vf_block}\n\nVerification failed:\n{diag_text}".strip()
            else:
                # Requirement: Advancing a step when verification fails emits a response combining the current step section content introduced by Now check carefully:, any configured verification failure instructions, and failure diagnostics without advancing to subsequent sections when a step section is currently active.
                section = g.sections[self._step_index - 1]
                content = f"## {section.title}\nNow check carefully:\n{section.content}{vf_block}\n\nVerification failed:\n{diag_text}".strip()
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=content,
            )

        # Requirement: Advancing a step when verification passes emits a response presenting the next step section content introduced by Now check carefully: alongside instructions to check carefully, make edits if the source file does not conform to any checklist item, and call advance() only when conforming, transitioning to that step section when further step sections remain.
        section = g.sections[self._step_index]
        self._step_index += 1
        content = (
            f"## {section.title}\nNow check carefully:\n{section.content}\n\n"
            "Check carefully and make edits if the source file does not conform to any checklist item, calling advance() only when the source file conforms to all checklist items."
        ).strip()
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=content,
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        GuideDelivery,
        keys=[GuideDelivery, sandbox_guide_delivery.GuideDelivery],
        tier=agent_session,
    )
