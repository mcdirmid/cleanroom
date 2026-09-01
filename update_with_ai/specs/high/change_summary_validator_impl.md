# change_summary_validator_impl

imports: virtual_file_name, change_summary_validator
types from virtual_file_name: virtual file name
types from change_summary_validator: change validator, diff summary, net change, change summary
implements: change validator

## Behavior

- A *change validator* compares initial baseline file content with current content to identify *net changes*.
- A *change validator* rejects *change summaries* exceeding the soft length bound up to a grace limit before rejecting at the hard bound.
- A *diff summary* truncates line diffs exceeding the configured diff size limit.
