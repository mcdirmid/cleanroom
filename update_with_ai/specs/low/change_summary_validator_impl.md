<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
  - change_summary_validator.md
-->

# Implementation LLS: change_summary_validator_impl

## Data Types
```python
from change_summary_validator import ChangeValidator

class ChangeValidatorImpl(ChangeValidator):
    def __init__(self, max_diff_chars: int = 4000) -> None: ...
```

## Behavioral Description

- Compares initial baseline file content with current content to identify net changes.
- Formats unified diffs comparing initial file content against current file content, truncating line diffs exceeding `max_diff_chars`.
- Verifies that all net-changed files are described in the change summary.
- Rejects change summaries exceeding the soft length bound (2,000 characters) up to a grace limit (3,000 characters) before rejecting at the hard bound (4,000 characters).

## Invariants

- Rejects change summaries claiming changes on files with net-zero modifications.
- Rejects change summaries that omit net-modified files or exceed length bounds.
