# dsh_workspace_impl scenarios

### Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is written or updated with explicit isolation boundaries, permitted in-workspace shell commands and native harness tools, auditor rules mandating in-workspace code and change header inspection while prohibiting code edits, mandating check_files for ground truth, enforcing continuous tool execution while work remains, and establishing round conclusion protocols directing the worker to stop immediately without tool calls and conclude with text summary when the worker has no outstanding work to do and get_work gives no more work to do (all ready targets are submitted or blamed or only blocked targets remain).
   Realized by: the component's file writer writing `AGENTS.md` with boundary constraints, role-specific editing rules, and round conclusion protocols.

### Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications.

1. The configurer generates the overlay patch.
   Observed: a Cordis patch file in `.cleanroom/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, high reasoning effort for DeepSeek providers, disabling unneeded tool plugins (including workflow, subagent, office skills, web, user question, jobs, and goal tools) to eliminate prompt overhead, and model routing resolving declarative model profile names (stripping model namespace prefixes) against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy, mapping local MLX providers to oMLX endpoints.
   Realized by: the component's patch generator writing `.cleanroom/dsh_patch.yml`.

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
LAST_CHANGED: 2026-10-27T20:50:00Z
CHANGE: Instruct workers to conclude immediately with text and no tool calls when work is resolved and get_work gives no more work
-->
