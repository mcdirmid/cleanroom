# Guide: High-Level to Scenario Alignment

## Summary

The artifact is a scenario file (`scenarios/<name>.md`) restating the caller-observable behaviour of a component as concrete interaction sequences, submitted via `submit(target="<target_file>", change_summary="...")`. In-band metadata blocks (`<!-- CLEANROOM METADATA`) are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Seed files materialize as bootstrap templates that must be completely replaced. In multi-node sessions, multiple scenario files are processed together by package-relative alias path.

A scenario pairs a numbered title with a `Given:` state and numbered steps. The state holds only what is true before the first step; every step is one interaction with the component. An interface step records the observation that must hold afterwards (`Observed: ...`). An implementation step records that observation immediately followed by its realization beside it as part of the same numbered step (`Observed: ...`, `Realized by: ...`). Interface scenarios cover only the component's specification, naming no collaborators or code symbols. Implementation scenarios restate only the interface(s) the component implements under `## Reused from the interface` (token-for-token identical to the interface scenario file with an immediate `Realized by:` line per step), placing additional scenarios under `## Implementation-only`. When an operation is absent from a thin specification, unstated preconditions are supplied in `Given:` and marked as inferred; an absent capability or contradictory requirement is blamed on `high/<name>.md`.

> META: "Scenario files witness a high-level specification at concrete instances so its translation into the low-level specification can be evaluated one action at a time; the mechanism, its two evaluations, and its uncovered boundary conditions are described in design-docs/concrete_scenario_validation.md."

## Lint checks

- [ ] Header matches `# Concrete scenarios for `<stem>` (interface|implementation)`
- [ ] In interface files, scenario headings match `## Scenario <number> — <title>` with an exact em dash (`—`) and contiguous numbering from one
- [ ] In implementation files, sections are closed strictly to `## Reused from the interface` followed by `## Implementation-only`
- [ ] In implementation files, scenario headings under section headers match `### Scenario <number> — <title>` with an exact em dash (`—`) and contiguous numbering from one
- [ ] In implementation files, blocks under `## Reused from the interface` match the implemented interface file token-for-token with an immediate `Realized by:` sub-clause attached to each step
- [ ] Every scenario contains a `Given:` paragraph followed by one or more numbered steps starting from `1.`
- [ ] Every interface step contains an `Observed:` clause stating caller-observable outcome
- [ ] Every implementation step contains an `Observed:` clause followed immediately by a `Realized by:` clause as part of the same numbered step
- [ ] In interface files, backticked identifiers are restricted strictly to terms defined within the component's specification vocabulary
- [ ] In implementation files, every backticked collaborator component is declared under `imports:` or `implements:` in the high-level specification
- [ ] Template residue, including `<component type>`, `<title>`, `Bootstrap:`, and template instruction comments, is absent from the file
- [ ] Code fences (```), markdown tables (`|`), and specification line-number citations are strictly absent from the file

## Scenario structure and headings

- [ ] Every scenario opens with a `Given:` paragraph defining state existing prior to the first interaction
- [ ] Steps within a scenario are numbered sequentially (`1.`, `2.`, `3.`) representing distinct chronological interactions
- [ ] In implementation scenarios, each numbered step pairs its observation and realization immediately: `1. Action description.` followed on the next line by `Observed: Outcome.` and on the next line by `Realized by: Mechanism.`
- [ ] Effects appear in the observation of the step causing them and are never separated into trailing consequence steps
- [ ] No step restates conditions established in the `Given:` paragraph or preceding steps
- [ ] An unstated precondition in a thin specification is declared in the `Given:` state and marked as inferred
- [ ] Template instruction comments and placeholder tokens are completely deleted before submission

## Concreteness and positive tests

- [ ] Every `Observed:` clause contains at least one concrete literal (number, timestamp, path, identifier) not present in the specification sentence it exercises
- [ ] No `Observed:` clause copies or paraphrases the high-level specification sentence
- [ ] Schematically open phrases (`the declared attributes`, `the configured patterns`) are absent from states and observations
- [ ] Every `Given:` assertion is decidable from concrete state facts alone, avoiding vacuous negative assertions
- [ ] When a capability is absent from a thin specification, defect attribution is delivered to `high/<name>.md` via `blame` rather than inventing speculative operations

## Synthetic vocabulary and carrier names

- [ ] Concrete instances use standardized synthetic carrier identifiers across scenarios (roles: `role_a`, `worker`; packages: `scope_x`, `package_a`; units: `unit_m`; timestamps: ISO format literals starting at `2026-01-01T00:00:00Z`; filesystem roots: `/repo_root`, `/workspace_dir`)
- [ ] Host operating system paths, real repository directory trees, and external package names are strictly avoided

## Visibility and thin specifications

- [ ] An interface scenario file is authored with visibility limited to the component's specification and its declared imports
- [ ] Python module names, class names, member functions, AST types, and code keywords are absent from interface scenario files
- [ ] For specifications defining only passive data types or configuration without callable operations, scenarios verify structural creation, and negative partition requirements are omitted
- [ ] Implementation scenarios name only collaborator components declared in front-matter `imports:`

## Implementation scenarios and restatement

- [ ] An implementation scenario file restates the scenarios of the interface(s) the component implements under `## Reused from the interface` with identical titles, states, steps, and observations
- [ ] Realizations under `Realized by:` resolve to an imported collaborator capability, a delegated interface capability, or an internal private mechanism
- [ ] A realization that reads internal state explicitly names the operation that writes that state
- [ ] Scenarios covering internal realization behavior unobservable through the interface appear under `## Implementation-only`
- [ ] Interface scenario files are written before implementation scenario files; edits to interface scenarios cascade re-stamping to implementation scenarios

## Coverage and negative partitions

- [ ] Every caller interaction is exercised across applicable negative partitions (collections at 0, 1, and multiple items; graphs with loops or disconnected nodes; empty/malformed inputs; uninitialized/dirty states)
- [ ] Components without inputs, state, or branches are exempt from negative partition coverage
