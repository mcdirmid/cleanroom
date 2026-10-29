# Concrete scenarios for `scaffold` (interface)

## Scenario 1 — Deploying runner zipapps into the bin directory

Given: an empty or newly created workspace directory `/ws/alpha_scope_a` with a `bin` directory.

1. The scaffolder deploys runner zipapps into `/ws/alpha_scope_a/bin`.
   Observed: `/ws/alpha_scope_a/bin` contains standalone executable zipapps for `get_work`, `check_files`, `submit`, `blame`, `feedback`, and `fail`; each file begins with `#!/usr/bin/env python3` followed by a valid zip archive containing `__main__.py`, has permissions 0o755, and any preexisting `coverage` file is removed.

## Scenario 2 — Writing role configuration metadata

Given: role `alpha` commissioned for scope `scope_a`, with model profile `gpt-4o`, subagent batch size 2, and max feedback chars 4000.

1. The scaffolder writes role metadata into `/ws/alpha_scope_a`.
   Observed: `.cleanroom_role.json` exists in `/ws/alpha_scope_a` with permissions 0o644; it contains valid JSON with keys `role`, `role_name`, `parts_dir`, `dir_scope`, `model`, `batch_size`, and `max_feedback_chars`, and contains no host repository absolute paths.

## Scenario 3 — Synthesizing role AGENTS.md guide instructions for author role

Given: role `alpha` is a writable authoring role with companion guide `guides/alpha_guide.md` and scope `parts/alpha`.

1. The scaffolder writes the role agents guide into `/ws/alpha_scope_a`.
   Observed: `AGENTS.md` exists in `/ws/alpha_scope_a` with permissions 0o644; it contains boundary rules confining execution to the workspace, the contamination tripwire with permitted in-workspace code and spec reading, instructions permitting in-workspace shell commands and native harness tools while mandating turn resolution through prescribed `bin/` tools, instructions for acting on blame and feedback (explaining that static checks do not verify runtime behavior), and fail-stop protocols.

## Scenario 4 — Synthesizing role AGENTS.md guide instructions for auditor role

Given: role `spec_qa` is a read-only auditor role with companion guide `guides/spec_qa.md` and scope `parts/alpha`.

1. The scaffolder writes the role agents guide into `/ws/spec_qa_scope_a`.
   Observed: `AGENTS.md` exists with auditor requirements instructing inspection of `# CHANGE:` commit headers before delivering blame and prohibiting blind recycling of feedback without checking what the author attempted to fix.

## Scenario 5 — Generating starter skeletons for missing targets

Given: role `alpha` declares source pattern `parts/alpha/lib/{unit_name}.py` and writable file patterns `["parts/alpha/lib/*.py"]`; unit `widget` has companion specification `parts/alpha/low/widget.pyi` in the repository root, but `parts/alpha/lib/widget.py` does not yet exist.

1. The scaffolder creates missing target skeletons for the workspace.
   Observed: `parts/alpha/lib/widget.py` is generated in `/ws/alpha_scope_a` with starter skeleton content derived from `widget.pyi`, and has permissions 0o644.

## Scenario 6 — Synthesizing role AGENTS.md guide instructions for fused role

Given: role `baseline` is a fused role combining `lib`, `test`, `qa`, and `coverage` with companion guides in `guides/` and scope `parts/alpha`.

1. The scaffolder writes the role agents guide into `/ws/baseline_scope_a`.
   Observed: `AGENTS.md` exists with multi-phase workflow instructions incorporating use-based micro-binary verification (`bin/verify_lib`, `bin/verify_test`, `bin/verify_coverage`), QA arbiter contract fidelity self-audit directives, coverage arbiter semantic closure directives requiring pruning uncontracted dead defensive code upon coverage failure, and an atomic completion protocol omitting per-target submission.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T11:35:00Z
LAST_CHANGED: 2026-10-29T15:30:00Z
CHANGE: Derive fused role micro-binaries strictly and dynamically from constituent role names with zero hardcoded role names
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
