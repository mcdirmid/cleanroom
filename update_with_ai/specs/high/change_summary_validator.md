# change_summary_validator

imports: virtual_file_name
types from virtual_file_name: virtual file name

## Purpose

Enforces change summary accuracy and conciseness against actual workspace file modifications, preventing inaccurate completion claims.

Language models often write change descriptions that do not match actual modifications, fail to describe altered files, or write excessively verbose change essays. Change summary validator verifies claimed changes against net-modified files, rejects net-unchanged claims, and bounds summary length within configured limits.

## Types

- A *change summary* is a description of modifications made to workspace files
- A *change validator* is a service that verifies *change summaries* against net file modifications
- A *diff summary* is a formatted representation of line changes across modified files
- A *net change* is an observable difference between a file's initial content and its current content

## Behavior

- A *change validator* verifies that a *change summary* describes all *net changes* across workspace files.
- A *change validator* rejects a *change summary* that claims changes for files with no *net change*.
- A *change validator* produces a *diff summary* of modified files.
- A *change validator* rejects a *change summary* exceeding configured length bounds with shortening guidance.
