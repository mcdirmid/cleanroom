# provision_impl implementation component

imports: session, cleanroom_files_ext, role_registry, scaffold, stub, src_metadata
implements: provision

## Purpose

The provision_impl implementation component realizes role workspace filesystem initialization, permission-isolated copying, executable runner script deployment, and configuration synthesis.

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in `bin/`, and writes the hidden role descriptor configuration file.

**Out of scope:** The provision_impl implementation component does not parse git commits, evaluate forward dirty node propagation, or schedule multi-node builds; these are handled by other components.

**Delegated:** Role definition resolution, target directory computation, and workspace registry persistence are delegated to role_registry. File naming conventions for the role descriptor configuration are delegated to cleanroom_files_ext. Test stub generation and synchronization are delegated to stub. Runner zipapp deployment, role metadata serialization, AGENTS.md guide synthesis, and missing target skeleton generation are delegated to scaffold. In-band metadata extraction, projection, and ephemeral code hash generation are delegated to src_metadata.

## Types and Behavior

The workspace provisioner commissions a role workspace at the resolved workspace directory path.

The workspace provisioner:

- Validates that the target directory exists and resolves the role definition.

- Creates the role workspace working tree, copying workspace roots, project configurations (.python-version, pyproject.toml, uv.lock, model_configs.toml), and build definitions while configuring type-checking to cover the workspace without directory exclusions.

- Inspects the declared role patterns to identify writable target files, upstream contract dependencies, and stub role dependencies.

- Synthesizes read-only test stubs raising `NotImplementedError` from companion specification files into the workspace for stub role dependencies, delegating stub generation and synchronization to the workspace stub synthesizer.

- Copies writable target files into the workspace with write permissions, projecting in-band metadata to expose only change, feedback, and ephemeral code hash attributes, and creating a missing target skeleton when a declared file does not yet exist on disk.

- Copies and writes files across role workspaces, applying explicit read-only, writable, or executable permissions.

- Synchronizes read-only test stubs for stub role dependencies across role workspaces, delegating stub updates and purging to the workspace stub synthesizer.

- Copies upstream contract dependencies and guides into the workspace with read-only permissions, ensuring agents cannot alter an upstream specification in place.

- Copies user-facing runtime libraries and type stubs (`lifecycle.py`, `lifecycle.pyi`, `framework.py`, `framework.pyi`) into support directories with read-only permissions, projecting constituent runtime support libraries directly into `./support/lib` and the role's assigned companion guide into `./guides` (copying all companion guides across all constituent roles when provisioning a fused role), strictly avoiding copying templates, unneeded methodology configurations (`cleanroom_roles.toml`, `pyright_spec.json`), redundant package directories, or unbound repository root directories into the role workspace root, while strictly excluding internal methodology oracles, AST linters, and role runners (`build_lint_common.py`, `*_lint.py`, `cleanroom_role_tool.py`, `cleanroom_uv_runner.py`) from role workspace filesystems.

- Deploys self-contained executable zipapps into the `bin/` directory of the workspace, packaging compiled Python bytecode (`.pyc`) and source modules for cleanroom_role_tool, build_lint_common, and role verification linters inside the archive so that runners execute in-memory across Python runtime versions without exposing loose oracle files in the role workspace filesystem, and deploying use-based micro-binaries (`bin/verify_lib`, `bin/verify_test`, `bin/verify_pretense`, `bin/verify_coverage`) for fused roles.


- Writes the role descriptor configuration file recording the role address, role name, and directory scope, omitting host repository paths to preserve isolation, with optional model profile attributes.

- Synthesizes an `AGENTS.md` guide containing the behavioral constraints, role instructions, and tool usage sequences tailored to the commissioned role, formatting fused authoring and arbiter self-audit directives for fused roles.

- Writes boundary rules into the guide that confine the agent to the workspace, forbid git operations, and declare the main repository read-only, and writes a contamination tripwire that mandates an immediate abort upon reading an out-of-bounds file outside the workspace directory, while explicitly permitting and instructing file inspection of in-workspace specifications, tests, code implementations, and commit change metadata headers.

- Writes execution guidance into the guide that permits shell commands and native harness tools within the workspace directory, while mandating that Cleanroom target verification and round resolution proceed through prescribed `bin/` executables (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`).

- Writes a fail-stop and reporting protocol into the guide that prohibits self-healing on an infrastructure traceback, error, or missing dependency, while distinguishing ordinary verification test failures and establishing an unresolvable impasse protocol where failures are recorded via `bin/fail` and escalated to the coordinator.

- Writes instructions for acting on blame and feedback into the guide, warning authoring agents that static checks do not execute tests or verify runtime logic, clarifying that passing `bin/check_files` does not mean feedback is resolved, directing authors to resolve runtime defects against contracts and tests before submitting, and mandating that auditor agents inspect target `# CHANGE:` commit headers before delivering blame to tailor feedback to what remains unaddressed without recycling identical critiques.

- Registers the new workspace descriptor in the workspace registry.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:38:00Z
LAST_CHANGED: 2026-10-26T20:38:00Z
CHANGE: Provision all companion guides and use-based micro-binaries for fused roles
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
