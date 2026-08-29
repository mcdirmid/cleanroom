<!-- Dependencies (md files to read alongside this one):
  - change_summary_validator.md
  - file_editor.md
  - tool_provider.md
-->

# Implementation LLS: change_summary_validator_impl

## Data Types
```python
from change_summary_validator import ChangeSummaryValidator
from file_editor import FileEditor

class ChangeSummaryValidatorImpl(ChangeSummaryValidator):
    def __init__(self, file_editor: FileEditor, diff_size_limit: int = 1000) -> None: ...
```

## Behavioral Description

Implements `ChangeSummaryValidator` over a collaborator `FileEditor` and configured diff size limit.
Checks that claimed change summaries name each net-changed file and no net-unchanged files.
Rejects missing, malformed, or fabricated change summaries with tool failures.
Maintains a grace counter per session for change summaries exceeding bounds.
Formats diff summaries with line-by-line differences up to the configured limit.

## Invariants

- Soft length bound is 300 characters, hard length bound is 500 characters, grace count is 4.
- Diff summaries are truncated at diff_size_limit.
