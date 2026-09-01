"""Guide delivery implementation delivering progressive step sections."""

from typing import Optional
from .guide_delivery import (
    GuideDelivery,
    GuideDeliveryFactory,
    TaskGuide,
    Guide,
    StepSection,
    StepDelivery,
)


class GuideDeliveryFactoryImpl(GuideDeliveryFactory):
    def create_guide_delivery(self, guide: TaskGuide) -> GuideDelivery:
        return _GuideDeliveryImpl(guide)


class _GuideDeliveryImpl(GuideDelivery):
    def __init__(self, guide: TaskGuide) -> None:
        self._guide = guide
        self._sections = [s for s in guide.sections if not s.title.lower().startswith("lint checks")]
        self._current_index = 0

    def get_summary_delivery(self) -> StepDelivery:
        return StepDelivery(content=self._guide.summary)

    def advance_step(self, verification_passed: bool) -> Optional[StepDelivery]:
        if verification_passed and self.has_steps_remaining():
            section = self._sections[self._current_index]
            self._current_index += 1
            return StepDelivery(content=section.content)
        return None

    def has_steps_remaining(self) -> bool:
        return self._current_index < len(self._sections)


def parse_guide_markdown(markdown_text: str) -> Guide:
    lines = markdown_text.splitlines()
    summary_lines = []
    sections: list[StepSection] = []
    current_title = None
    current_lines = []
    index = 0
    in_summary = True

    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if in_summary:
                in_summary = False
            else:
                if current_title and not current_title.lower().startswith("lint checks"):
                    sections.append(StepSection(index=index, title=current_title, content="\n".join(current_lines).strip()))
                    index += 1
            current_title = heading
            current_lines = []
        elif in_summary:
            summary_lines.append(line)
        else:
            current_lines.append(line)

    if current_title and not current_title.lower().startswith("lint checks"):
        sections.append(StepSection(index=index, title=current_title, content="\n".join(current_lines).strip()))

    return Guide(summary="\n".join(summary_lines).strip(), sections=sections)
