from typing import List, Optional
from . import file_alias
from . import node_config
from . import sandbox_guide_delivery
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class GuideDelivery(sandbox_guide_delivery.GuideDelivery, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._guide: Optional[sandbox_guide_delivery.Guide] = None
        self._initial_delivered: bool = False
        self._step_index: int = 0

    def initialize(self) -> None:
        # Requirement: Initializing the guide delivery obtains its guide from the node config.
        cfg = get_singleton(node_config.NodeConfig)
        self._guide = cfg.guide
        self._initial_delivered = False
        self._step_index = 0

    @property
    def has_steps_remaining(self) -> bool:
        # Requirement: [GuideDelivery] Steps remaining indicates whether further step sections remain to be completed.
        if self._guide is None:
            return False
        if not self._initial_delivered:
            return True
        return self._step_index < len(self._guide.sections)

    def parse_guide(self, content: file_alias.FileContent) -> sandbox_guide_delivery.Guide:
        # Requirement: Guide parsing extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.
        raw = str(content)
        lines = raw.splitlines()
        summary_lines: List[str] = []
        sections: List[sandbox_guide_delivery.StepSection] = []

        current_title: Optional[str] = None
        current_section_lines: List[str] = []

        for line in lines:
            if line.startswith("## "):
                if current_title is None:
                    summary_lines = list(current_section_lines)
                else:
                    if not current_title.startswith("Lint checks"):
                        sections.append(
                            sandbox_guide_delivery.StepSection(
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
            if not current_title.startswith("Lint checks"):
                sections.append(
                    sandbox_guide_delivery.StepSection(
                        index=len(sections),
                        title=current_title,
                        content="\n".join(current_section_lines).strip(),
                    )
                )

        elif not summary_lines:
            summary_lines = current_section_lines

        return sandbox_guide_delivery.Guide(
            summary="\n".join(summary_lines).strip(),
            sections=sections,
        )

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.Response]:
        # Requirement: When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.
        if self._guide is None or not self.has_steps_remaining:
            return None

        if not verification_passed:
            diag_text = failure_diagnostics or ""
            if self._step_index == 0:
                # Requirement: When advancing a step with failed verification, if no step section has been delivered yet, the guide delivery retains its index and emits a response combining the guide summary and failure diagnostics.
                content = f"{self._guide.summary}\n\nVerification failed:\n{diag_text}".strip()
            else:
                # Requirement: When advancing a step with failed verification, if a step section is currently active, the guide delivery retains the current step index without advancement and emits a response combining the guide summary, the current step section content, and the failure diagnostics.
                section = self._guide.sections[self._step_index - 1]
                content = f"{self._guide.summary}\n\n## {section.title}\n{section.content}\n\nVerification failed:\n{diag_text}".strip()
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=content,
            )

        if not self._initial_delivered:
            # Requirement: When advancing a step with passed verification, if no steps have been delivered yet, the guide delivery emits a response containing the guide summary alone without delivering a step section.
            self._initial_delivered = True
            return tool_provider.Response(
                is_failed=False,
                is_terminated=False,
                content=self._guide.summary,
            )

        # Requirement: When advancing a step with passed verification, if steps have already been delivered and further step sections remain, the guide delivery emits a response presenting the guide summary above the next step section content and advances its index to that section.
        section = self._guide.sections[self._step_index]
        self._step_index += 1
        content = f"{self._guide.summary}\n\n## {section.title}\n{section.content}".strip()
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=content,
        )

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        GuideDelivery,
        keys=[GuideDelivery, sandbox_guide_delivery.GuideDelivery],
        tier="agent_session",
    )
