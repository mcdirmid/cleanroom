from typing import List, Optional, Protocol
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import file_alias
import tool_provider

@dataclass(frozen=True)
@data_type
class StepSection:
    """
PURPOSE:
Discrete milestone section within a guide
"""

    def __init__(self, index: int, title: str, content: str) -> None:
        ...

    @property
    def index(self) -> int:
        """
PURPOSE:
Established as the sequential index of the step section
"""
        ...

    @property
    def title(self) -> str:
        """
PURPOSE:
Established as the heading or title of the step section
"""
        ...

    @property
    def content(self) -> str:
        """
PURPOSE:
Established as the instructional content of the step section
"""
        ...

@dataclass(frozen=True)
@data_type
class Guide:
    """
PURPOSE:
Structured instructional text containing a summary and sequential step sections
"""

    def __init__(self, summary: str, sections: List[StepSection]) -> None:
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Established as the high-level overview of the guide
"""
        ...

    @property
    def sections(self) -> List[StepSection]:
        """
PURPOSE:
Established as the sequential milestone sections of the guide
"""
        ...

@singleton_type('agent_session')
class GuideDelivery(Protocol):
    """
PURPOSE:
Defined as an agent session service that delivers step-by-step instructions from a guide

FRESH_REQUIREMENTS:
- Steps remaining indicates whether further step sections remain to be completed.
"""

    @property
    def has_steps_remaining(self) -> bool:
        """
PURPOSE:
Exposes whether progressive step sections remain to be completed
"""
        ...

    @operation
    def parse_guide(self, content: file_alias.FileContent) -> Guide:
        """
PURPOSE:
Parses file content into a task guide, extracting summary and step sections

FRESH_REQUIREMENTS:
- Parsing file content extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.
"""
        ...

    @operation
    def advance_step(self, verification_passed: bool, failure_diagnostics: Optional[str]=None) -> Optional[tool_provider.Response]:
        """
PURPOSE:
Advances to the next step section if verification passed, or retains the current step and reports failure diagnostics

FRESH_REQUIREMENTS:
- When advancing a step with passed verification on initial delivery, the response contains the guide summary alone.
- When advancing a step with passed verification on subsequent steps and steps remain, the response presents the guide summary above the next step section content.
- When advancing a step with failed verification, advancing retains the current step section and reports the failure diagnostics.
"""
        ...
