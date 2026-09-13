from typing import Protocol, Tuple
from dataclasses import dataclass
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config

@dataclass(frozen=True)
class NetChange:
    file: agent_file_alias.ReadWriteFile
    initial_content: agent_file_alias.FileContent
    current_content: agent_file_alias.FileContent

@dataclass(frozen=True)
class DiffSummary:
    summary_text: str

class ChangeSummaryValidator(agent_node_config.VerificationCheck, Protocol):
    def verify(self) -> Tuple[bool, str]:
        ...
