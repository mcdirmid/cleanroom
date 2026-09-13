# sandbox_change_summary_validator_impl implementation component

imports: agent_node_config, agent_file_alias
implements: sandbox_change_summary_validator

## Purpose

The sandbox_change_summary_validator_impl implementation component realizes diff-based net change detection, soft-and-hard length boundary enforcement, and diff payload truncation for change summaries.

Enforcing concise and honest summaries requires comparing current file state against pristine session baselines while providing clear feedback when summaries drift or expand. The sandbox_change_summary_validator_impl implementation component compares initial and current file contents, applies grace thresholds to summary length limits, and truncates large unified diff snippets to safeguard context windows.

**Out of scope:** The sandbox_change_summary_validator_impl implementation component does not execute build steps, evaluate test assertions, or record transcript logs; these are handled by other components.

## Types and Behavior

The change summary validator compares initial baseline file content with current content to identify net changes across declared read-write files.

When validating a change summary as a verification check:

- The validator rejects change summaries exceeding a soft length bound up to a grace limit before failing at the hard bound.

- If the change summary is missing or fails to describe all files with net changes, verification fails with diagnostic guidance.

- If the change summary claims modifications for files without net changes, verification fails with diagnostic guidance.

A diff summary truncates line diffs exceeding the configured diff size limit. When verification passes, the validator reports that verification passed with a diff summary.
