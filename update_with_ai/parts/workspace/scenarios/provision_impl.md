<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:45:00Z
CHANGE: align AGENTS.md scenarios with in-workspace file inspection and terminal command restrictions
CODE_HASH: 48150813effc
-->

# Concrete scenarios for `provision_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Commissioning an isolated role workspace

Given: role alpha is commissioned for scope_a at workspace directory `/ws/alpha_scope_a` with main
repository root `/repo`; alpha declares source pattern `alpha/{unit}.md` and upstream contract
dependencies `beta/high/beta_contract.md` and `guides/alpha_guide.md`, and declares no stub role
dependencies; the alpha source for the unit widget is absent from disk, the alpha source for the
unit gadget is present, and the persistent workspaces registry is empty.

1. The provisioner commissions the alpha workspace for scope_a.
   Observed: the tree exists at `/ws/alpha_scope_a`; `alpha/widget.md` exists with read-write
   permissions as a starter skeleton; `alpha/gadget.md` exists with read-write permissions, projected metadata exposing an ephemeral code hash, and the
   content of the gadget source; `beta/high/beta_contract.md` and `guides/alpha_guide.md` exist
   with read-only permissions; and the persistent registry holds exactly one descriptor for
   `/ws/alpha_scope_a`.
   Realized by: role definition resolution and the workspace directory computation of
   `role_registry`, which also persists the descriptor, and the component's own tree
   creation, pattern inspection, writable-file copying, contract copying, and starter skeleton
   synthesis delegated to `scaffold`.

2. The provisioner commissions the alpha workspace for scope_a a second time.
   Observed: the tree still holds one copy of each file, the read-only files stay read-only, and
   the persistent registry still holds exactly one descriptor for `/ws/alpha_scope_a`.
   Realized by: the component's own repeated copying and skeleton synthesis delegated to
   `scaffold`, which overwrite rather than duplicate, and the register-or-update path
   of `role_registry`.

### Scenario 2 — Workspaces for two scopes stay separate

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a` and for scope_b at
`/ws/alpha_scope_b`, both declaring source pattern `alpha/{unit}.md`.

1. The provisioner commissions the alpha workspace for scope_a.
   Observed: `/ws/alpha_scope_a/alpha/widget.md` exists and is read-write.
   Realized by: the workspace directory computation of `role_registry`, which combines the
   repository root, the role name, and the directory scope, and the component's own writable-file
   copying.

2. The provisioner commissions the alpha workspace for scope_b.
   Observed: `/ws/alpha_scope_b/alpha/widget.md` exists as a distinct file, and writing to it
   leaves the scope_a target unchanged.
   Realized by: the workspace directory computation of `role_registry`, which confines the
   scope name to a single path component, and the component's own copying into the newly created
   tree.

### Scenario 3 — The deployed runner tools

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace `bin/` directory holds the runner tools for the work, check files,
   submit, blame, fail, and coverage subcommands, each executable, and each runs without any
   tooling installed outside the workspace.
   Realized by: runner zipapp deployment delegated to `scaffold`, which embeds a
   self-contained executable wrapper for each subcommand and gives it execution permissions.

### Scenario 4 — The synthesized role guide

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a` with main repository root
`/repo`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace guide states that the agent acts only inside `/ws/alpha_scope_a`, that
   version control operations are forbidden, that `/repo` is read-only and reachable only through
   the workspace runner tools, that terminal commands are restricted to prescribed `bin/` tools,
   that reading a file outside the workspace aborts the session at once, that inspecting in-workspace
   specifications and code using file-reading tools is explicitly permitted, and that passing static
   checks does not mean feedback is resolved, requiring runtime defects to be addressed before submit
   and requiring target change headers to be inspected before auditor blame delivery.
   Realized by: role guide synthesis delegated to `scaffold`, which writes the boundary
   rules, the contamination tripwire, the blame and feedback resolution instructions, and the
   fail-stop reporting protocol into the guide file.

2. The agent runs the work runner tool from the workspace `bin/` directory.
   Observed: the tool runs from the workspace alone and reports alpha work.
   Realized by: runner deployment delegated to `scaffold`, whose wrappers carry their
   dependencies inside the workspace.

### Scenario 5 — Stub role dependencies are synthesized rather than copied

Given: role alpha is commissioned for scope_a and declares the stub role dependency beta, whose
companion specification `beta/high/beta.md` exists and whose canonical implementation
`beta/lib/beta.py` exists with the content `def beta(): return 7`.

1. The provisioner commissions the alpha workspace.
   Observed: the beta entry in the workspace is a read-only test stub raising
   `NotImplementedError`, built from `beta/high/beta.md`, and `def beta(): return 7` appears
   nowhere in the workspace.
   Realized by: role definition resolution through `role_registry`, which supplies the stub
   role dependencies, and the component's own stub synthesis from the companion specification.

### Scenario 6 — Commissioning against a missing target directory

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`, and `/ws/alpha_scope_a`
does not exist.

1. The provisioner commissions the alpha workspace.
   Observed: commissioning fails explicitly naming `/ws/alpha_scope_a`, no workspace tree is
   created, and the persistent registry holds no descriptor for it.
   Realized by: the component's own validation of the workspace directory, which precedes every
   write and reports the missing directory.

### Scenario 7 — Commissioning an undeclared role

Given: no role configuration declares role zeta, and the directory `/ws/zeta_scope_a` exists and
is empty.

1. The provisioner commissions the zeta workspace for scope_a.
   Observed: commissioning fails explicitly naming zeta, no file is written under
   `/ws/zeta_scope_a`, and the persistent registry holds no descriptor for it.
   Realized by: role definition resolution through `role_registry`, whose resolution of an
   undeclared role fails fast, and the component's own propagation of that failure without
   substituting a synthetic role.

## Implementation-only

### Scenario 8 — Build definitions and package initializers are copied verbatim

Given: role alpha is commissioned for scope_a, its directory scope holds the project
configuration and the build definition for the part, and the stub role dependency beta supplies
`beta/lib/beta.py` whose canonical content is `def beta(): return 7`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace holds the project configuration and the part build definition with the
   same content as the main repository, and the stub for beta raises `NotImplementedError` instead
   of carrying `def beta(): return 7`.
   Realized by: the component's own selective copying, which passes build definitions, project
   configuration, and package initializers through while routing stub role dependencies to stub
   synthesis.

### Scenario 9 — Type checking covers the workspace without exclusions

Given: role alpha is commissioned for scope_a, and the main repository project configuration
excludes a directory that exists inside the workspace.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace project configuration retains the workspace directory in its
   type-checking coverage and excludes no workspace directory.
   Realized by: the component's own configuration rewriting, which adjusts type-checking coverage
   as it copies the project configuration.

### Scenario 10 — The workspace role descriptor

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace role descriptor records the role address alpha, the role name alpha,
   and the directory scope scope_a, omitting host repository roots to preserve double-blind isolation.
   Realized by: the component's own descriptor writing, and the role definition resolved through
   `role_registry`.
