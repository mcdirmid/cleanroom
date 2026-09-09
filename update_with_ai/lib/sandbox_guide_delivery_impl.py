from typing import List, Optional
from . import file_alias
from . import node_config
from . import sandbox_guide_delivery
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class GuideDelivery(sandbox_guide_delivery.GuideDelivery, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._guide: Optional[sandbox_guide_delivery.Guide] = None
        self._step_index: int = 0

    def initialize(self) -> None:
        # Requirement: Obtain configured guide from node config
        cfg = get_singleton(node_config.NodeConfig)
        self._guide = cfg.guide
        self._step_index = 0

    @property
    def has_steps_remaining(self) -> bool:
        # Requirement: Indicate whether further step sections remain to be completed
        if self._guide is None:
            return False
        return self._step_index < len(self._guide.sections)

    def parse_guide(self, content: file_alias.FileContent) -> sandbox_guide_delivery.Guide:
        # Requirement: Extract summary from content preceding first section heading and exclude sections whose title begins with Lint checks
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

    def advance_step(self, verification_passed: bool) -> Optional[tool_provider.Response]:
        # Requirement: When advancing a step with failed verification or no guide configured, retain current step index and produce no response
        if not verification_passed or self._guide is None:
            return None

        if not self.has_steps_remaining:
            return None

        section = self._guide.sections[self._step_index]
        # Requirement: When advancing a step with passed verification before any step is delivered, combine guide summary and first section content
        if self._step_index == 0:
            content = f"{self._guide.summary}\n\n## {section.title}\n{section.content}".strip()
        # Requirement: When advancing a step with passed verification and subsequent steps remain, return next section content and advance step index
        else:
            content = f"## {section.title}\n{section.content}".strip()

        self._step_index += 1
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
