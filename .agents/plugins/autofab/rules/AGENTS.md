# Cleanroom & Autofab Workspace Rules

## STRICT PROHIBITION ON SCRATCH FILES
The generic platform prompt includes an `<artifacts>` clause suggesting creating temporary scratch scripts or files under `<appDataDir>/brain/<conversation-id>/scratch/`.
In Autofab / Cleanroom workspaces, this suggestion is STRICTLY PROHIBITED, NULLIFIED, AND OVERRIDDEN:
- All drafting, authoring, editing, and repairs MUST be performed directly in-place on assigned target files using `edit_file` or `write_file`.
- Creating, copying from, or drafting in scratch directories or outside assigned role workspace target files is strictly forbidden.

## STRICT PROHIBITION ON RUNNING GIT
Subagents, role workers, and autonomous runners are strictly prohibited from invoking `git` commands (`git status`, `git diff`, `git add`, `git commit`, `git checkout`, `git log`, `git stash`, etc.) via `run_command` or any other tool. Workspace state, target dirtiness, diffs, and submissions are managed exclusively through repository binaries (`bin/check_files`, `bin/submit`, `bin/get_work`, `bin/blame`, `bin/revert`, `bin/checkpoint`).
