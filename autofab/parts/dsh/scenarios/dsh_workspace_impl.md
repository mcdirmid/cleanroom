# dsh_workspace_impl scenarios

### Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a as an author role with writable targets, and for role_b as an auditor role with zero writable targets.

1. The configurer customizes role agent documentation for role_a.
   Observed: `AGENTS.md` is written or updated with explicit isolation boundaries, permitted in-workspace read-only inspection shell utilities (`cat`, `grep`, `find`, `head`, `tail`, `sed`) and native harness tools while strictly prohibiting ad-hoc runtime tests, test runners, or inline Python scripts (including `python3 -c` and stdin heredocs) against targets or implementation code, workspace undo and rollback instructions (`bin/revert [target]`, `git restore <target>`, `git diff <target>`), mandating check_files for ground truth, enforcing continuous tool execution while work remains, and establishing round conclusion protocols directing the worker to stop immediately without tool calls and conclude with text summary when the worker has no outstanding work to do and get_work gives no more work to do (all ready targets are submitted or blamed or only blocked targets remain).
   Realized by: the component's file writer writing `AGENTS.md` with boundary constraints, rollback instructions, role-specific editing rules, and round conclusion protocols.

2. The configurer customizes role agent documentation for role_b.
   Observed: `AGENTS.md` omits rollback guidance and strictly prohibits file edits and git commands.
   Realized by: the component's file writer tailoring `AGENTS.md` for auditor roles.

### Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications as an author role with writable targets, and for role_b as an auditor role with zero writable targets.

1. The configurer generates the overlay patch for role_a.
   Observed: a Cordis patch file in `.autofab/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, high reasoning effort for DeepSeek providers, pre-tool lifecycle hooks on edit and write tools triggering `bin/checkpoint pre-edit`, disabling unneeded tool plugins (including workflow, subagent, office skills, web, user question, jobs, and goal tools) to eliminate prompt overhead, and model routing resolving declarative model profile names (stripping model namespace prefixes) against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy, mapping local MLX providers to oMLX endpoints.
   Realized by: the component's patch generator writing `.autofab/dsh_patch.yml` with pre-tool hooks and provider configs.

2. The configurer generates the overlay patch for role_b.
   Observed: a Cordis patch file in `.autofab/dsh_patch.yml` is generated disabling `edit` and `write` tools, setting `file_policy: read-only`, and omitting pre-tool checkpoint hooks.
   Realized by: the component's patch generator detecting auditor roles and disabling file-editing tools.

### Scenario 3 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
   Realized by: the component's report constructor checking created files and building the report.

### Scenario 4 — Customizing role agent documentation with model-contingent directives

Given: a provisioned role workspace directory with a local or output-constrained model specification.

1. The configurer customizes role agent documentation for a local or constrained model.
   Observed: `AGENTS.md` contains incremental authoring and payload ceiling protection directives instructing the worker to avoid monolithic tool calls.
   Realized by: the component's file writer writing `AGENTS.md` with model-contingent staged writing instructions.

2. The configurer customizes role agent documentation for a cloud model.
   Observed: `AGENTS.md` omits incremental authoring advice.
   Realized by: the component's file writer omitting payload ceiling instructions for cloud models.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-02T20:38:00Z
CHANGE: Prohibit ad-hoc runtime testing and inline python scripts in customized AGENTS.md
-->
-->
