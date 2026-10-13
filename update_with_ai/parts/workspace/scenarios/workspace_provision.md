<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T03:14:20Z
CHANGE: Author workspace workspace_provision concrete scenarios
CODE_HASH: 5bd17de4c43d
-->

# Concrete scenarios for `workspace_provision` (interface)

## Scenario 1 — Commissioning an isolated role workspace

Given: role alpha is commissioned for scope_a at workspace directory `/ws/alpha_scope_a` with main
repository root `/repo`; alpha declares source pattern `alpha/{unit}.md` and upstream contract
dependencies `beta/high/beta_contract.md` and `guides/alpha_guide.md`, and declares no stub role
dependencies; the alpha source for the unit widget is absent from disk, the alpha source for the
unit gadget is present, and the persistent workspaces registry is empty.

1. The provisioner commissions the alpha workspace for scope_a.
   Observed: the tree exists at `/ws/alpha_scope_a`; `alpha/widget.md` exists with read-write
   permissions as a starter skeleton; `alpha/gadget.md` exists with read-write permissions and the
   content of the gadget source; `beta/high/beta_contract.md` and `guides/alpha_guide.md` exist
   with read-only permissions; and the persistent registry holds exactly one descriptor for
   `/ws/alpha_scope_a`.

2. The provisioner commissions the alpha workspace for scope_a a second time.
   Observed: the tree still holds one copy of each file, the read-only files stay read-only, and
   the persistent registry still holds exactly one descriptor for `/ws/alpha_scope_a`.

## Scenario 2 — Workspaces for two scopes stay separate

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a` and for scope_b at
`/ws/alpha_scope_b`, both declaring source pattern `alpha/{unit}.md`.

1. The provisioner commissions the alpha workspace for scope_a.
   Observed: `/ws/alpha_scope_a/alpha/widget.md` exists and is read-write.

2. The provisioner commissions the alpha workspace for scope_b.
   Observed: `/ws/alpha_scope_b/alpha/widget.md` exists as a distinct file, and writing to it
   leaves the scope_a target unchanged.

## Scenario 3 — The deployed runner tools

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace `bin/` directory holds the runner tools for the work, check files,
   submit, blame, fail, and coverage subcommands, each executable, and each runs without any
   tooling installed outside the workspace.

## Scenario 4 — The synthesized role guide

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a` with main repository root
`/repo`.

1. The provisioner commissions the alpha workspace.
   Observed: the workspace guide states that the agent acts only inside `/ws/alpha_scope_a`, that
   version control operations are forbidden, that `/repo` is read-only and reachable only through
   the workspace runner tools, and that reading a file outside the workspace aborts the session at
   once.

2. The agent runs the work runner tool from the workspace `bin/` directory.
   Observed: the tool runs from the workspace alone and reports alpha work.

## Scenario 5 — Stub role dependencies are synthesized rather than copied

Given: role alpha is commissioned for scope_a and declares the stub role dependency beta, whose
companion specification `beta/high/beta.md` exists and whose canonical implementation
`beta/lib/beta.py` exists with the content `def beta(): return 7`.

1. The provisioner commissions the alpha workspace.
   Observed: the beta entry in the workspace is a read-only test stub raising
   `NotImplementedError`, built from `beta/high/beta.md`, and `def beta(): return 7` appears
   nowhere in the workspace.

## Scenario 6 — Commissioning against a missing target directory

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`, and `/ws/alpha_scope_a`
does not exist.

1. The provisioner commissions the alpha workspace.
   Observed: commissioning fails explicitly naming `/ws/alpha_scope_a`, no workspace tree is
   created, and the persistent registry holds no descriptor for it.

## Scenario 7 — Commissioning an undeclared role

Given: no role configuration declares role zeta, and the directory `/ws/zeta_scope_a` exists and
is empty.

1. The provisioner commissions the zeta workspace for scope_a.
   Observed: commissioning fails explicitly naming zeta, no file is written under
   `/ws/zeta_scope_a`, and the persistent registry holds no descriptor for it.
