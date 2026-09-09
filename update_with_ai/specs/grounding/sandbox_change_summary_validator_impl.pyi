from typing import Tuple
from framework import operation, override, singleton_type
import file_alias
import sandbox_change_summary_validator
import sandbox_run_control

@singleton_type('agent_session')
class ChangeSummaryValidator(sandbox_change_summary_validator.ChangeSummaryValidator):
    """
PURPOSE:
Implements change summary validator comparing baseline and disk contents

GROUNDING_ARGUMENT:
- As an agent_session singleton, ChangeSummaryValidator inspects net file changes and validates descriptions within the active session, accessing collaborator types in the same lifecycle tier (sandbox_run_control.AdvanceTool) and external filesystem utilities.
"""

    @operation
    @override
    def verify(self) -> Tuple[bool, str]:
        """
PURPOSE:
Verifies net changes, bounds lengths, and produces diff summary

FRESH_REQUIREMENTS:
- The change summary validator compares initial baseline file content with current content to identify net changes.
- The change summary validator rejects change summaries exceeding the soft length bound up to a grace limit before rejecting at the hard bound.
- A diff summary truncates line diffs exceeding the configured diff size limit.
- If a change summary fails to describe all files with net changes, verification fails with diagnostic feedback.
- If a change summary claims changes for unchanged files, verification fails with diagnostic feedback.

INHERITED_REQUIREMENTS:
- [ChangeSummaryValidator] The change summary validator verifies that a change summary describes all net changes across workspace files.
- [ChangeSummaryValidator] The change summary validator rejects a change summary that claims changes for files with no net change.
- [ChangeSummaryValidator] The change summary validator produces a diff summary of modified files.
- [ChangeSummaryValidator] The change summary validator rejects a change summary exceeding configured length bounds with shortening guidance.

GROUNDING_ARGUMENT:
- Compares recorded initial baseline file content with current workspace file state via the filesystem, retrieves the candidate change summary from imported sandbox_run_control.AdvanceTool (in the same session lifecycle tier), validates change coverage against net modifications, and formats a bounded diff summary.
"""
        ...
