# Concrete Scenario Validation for High-Level Specification Translation

## 1. Executive Summary & Problem Statement

The Cleanroom pipeline validates the translation from a High-Level Specification (HLS) to a Low-Level Specification (LLS) through the `spec_qa` arbiter, which reads both artifacts and judges whether the LLS semantically represents the HLS. That judgement is holistic: it has no ground witness, no per-action localization, and no record of which requirements were examined.

This document develops an alternative, complementary instrument. A **scenario** is a concrete sequence of interactions with a component: a fully specified starting state, then numbered steps, each step being one interaction. Scenarios are written from the specification alone, with visibility limited to the artifacts the component is entitled to see.

The same scenario is then used twice, because the interface and the implementation answer different questions.

- **Interface evaluation.** For each action, does the interface specification state a requirement that supports the observation the caller expects? A caller-visible effect with no requirement behind it is a gap in the bill of sale.
- **Implementation evaluation.** For each action, does the implementation specification provide a realization — a named collaborator capability or a private mechanism — that can produce it? A step whose realization is missing, or named but never grounded for that action, is an implementability gap.

Both evaluations are semantic. The instrument does not decide anything by matching keywords or counting clauses; it produces concrete, localized questions that a reader or an arbiter answers against the specifications, and it says which action each question came from.

The instrument also runs in reverse. A specification can pass every scenario while some of its requirements are never exercised. Section 5.3 makes that a decision rather than an assumption: either the scenarios are incomplete, or the unexercised requirement is uncontracted and should not be there.

The worked example in Section 6 uses three hand-written scenario files for `workspace_work`, `workspace_work_impl`, and `workspace_registry`, and evaluates the first two against their low-level specifications. It surfaces six findings, listed in Section 6.4: planning-to-low translation losses, missing realizations, an interface that had been carrying the implementation's wiring and mostly no longer does, grounding gaps in the canvases, requirements no scenario exercises, and an algorithm with no home.

---

## 2. Why the Existing Gate Is Insufficient

The `spec_qa` arbiter is the only semantic bridge between HLS and LLS. Its current contract is stated in [spec_qa.md](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/guides/spec_qa.md): the arbiter evaluates low against high "as if a hypothetical direct `high_to_low.md` guide governed the relationship", triages a missing requirement between `planning/<name>.md` and `low/<name>.pyi`, and delivers non-prescriptive blame to one culprit file per turn.

That gate is holistic in ways a scenario-based evaluation is not.

**2.1 Comparison without a witness.** The arbiter compares two universally quantified artifacts. A missing clause in a short stub is easy to absorb into a paraphrase of the same stub. The same omission is hard to overlook when a specific caller action and its expected observation are placed in front of the reader.

**2.2 No per-action localization.** Blame identifies a file and a coarse location. It cannot say that asking for work never states that a missing target is created, or that the refusal does not say what it says. A scenario attaches each question to an action a caller performs.

**2.3 Not repeatable.** Nothing in the gate records which requirements were examined, so two passes need not examine the same surface. A written scenario is a fixed input; re-running the evaluation over it is a control experiment.

**2.4 No coverage of the requirement set.** Nothing forces the arbiter to consider every requirement, and nothing notices when a requirement is never needed by any caller. This is the translation-level analog of the Code Coverage Illusion in [paper_submission_design_doc.md §2.6.2](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md): an audit of the requirements the arbiter happened to read says nothing about the ones it did not.

**2.5 Asymmetric verification strength.** The library and test roles receive concrete postconditions, and the coverage arbiter measures whether the tests exercise them. The translation step receives prose. Scenarios give the translation step the same kind of concrete, per-action surface the lower stages already have.

---

## 3. Scenarios and the Interpretation Problem

The Cleanroom thesis holds that specifications are untestable. [paper_submission_design_doc.md §1.3.1](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md) argues that natural language has no operational semantics, and it uses the scenario idiom as its foil: deciding whether a specification satisfies a scenario requires an interpreter, and interpreting the interpreter requires another interpretation.

A scenario-based evaluation answers that objection by changing what is being decided, and by being honest about what it cannot decide.

**3.1 The scenario is a witness, not a second description.** The HLS states capabilities declaratively. It never says which capabilities a caller would invoke together, in which order, for which role, against which buffer contents, or what "unless forced" means for a particular caller. A scenario supplies composition, order, and data — three things absent from the source. That is why a vague scenario is worthless: if it supplies none of the three it collapses into a second reading of the HLS and evaluates nothing.

**3.2 Two different questions, two different artifacts.** The interface evaluation asks whether a requirement supports an observation; the implementation evaluation asks whether a realization exists for an action. The implementation's contribution to the translation is precisely its interaction structure — where operation boundaries fall, what parameters exist, what comes back, how failure surfaces — and the HLS says nothing about any of it. Evaluating that structure against a concrete action is not a re-reading of the source.

**3.3 Soundness and completeness, stated honestly.** A scenario can refute a translation: if the specification does not support an observation the caller must receive, or provides no realization for an action the caller performs, the translation is defective under any reading. A scenario cannot prove one: passing every scenario is evidence on a finite sample. The mitigation is not more scenarios in general but two bounded checks — every requirement should be exercised by at least one scenario (Section 5.3), and every action in every scenario should receive a verdict in both evaluations.

---

## 4. Scenarios

### 4.1 Shape

A scenario is a heading, a `Given:` state, and numbered steps. The state holds only what is true before the first interaction and never restates anything a step establishes. Each step is exactly one interaction with the component, carries no premise already in the state, and records what follows.

What a step records depends on which component the file is about. An **interface** step records observations: what the caller sees afterwards. An **implementation** step records both: the same observation, and beside it the realization that produces it — the collaborator capabilities and private mechanisms the action depends on. Keeping the observation on an implementation step matters, because the implementation's job is to produce the caller-visible effect, and a realization that does not produce the observed effect is a mismatch rather than a coverage gap. Two conventions follow. Effects belong to the step that causes them, so materializing a file or writing a buffer is part of the observation of the action that caused it, not a later step. And a step that is merely a consequence of another step is not a step.

### 4.2 Concreteness

**A scenario must be a substitution instance of the requirement it exercises, and the substitution must be complete.** The requirement is schematic; the scenario replaces every schematic slot with a literal value. The tests are:

- **Instantiation.** No schematic slot survives. "The declared attributes", "the configured patterns", and "a sequence of reasons" are unresolved slots: deciding the scenario requires reopening the specification to learn what fills them.
- **Self-decidability.** A reader holding only the scenario can set up the state and decide whether the observation holds.
- **Novel literals.** The scenario contains concrete values the requirement sentence does not contain. A scenario whose only novelty is invented nouns is the requirement with names swapped.
- **No restatement.** A scenario whose observation paraphrases the requirement duplicates it and adds nothing. Either instantiate it or delete it.

An **uninstantiable requirement** — one whose observable is unbounded or implementation-defined — is a finding about the requirement rather than a licence to write a paraphrase. Marking it is a testability audit of the specification.

### 4.3 Visibility

The two tiers see different things, and the difference is what keeps each scenario honest.

An **interface** scenario is written with visibility limited to the component's own specification and the interface specifications of its `imports:` closure. It contains no Python module, class, type, or operation name, and no collaborator. Instances the specification leaves open are filled with synthetic names — roles, units, scopes, paths, timestamps — never names taken from role configuration, repository layout, or another component's files. A scenario that names a collaborator or a code symbol proves the author read something other than the interface, and it is how the earlier draft of this sample went wrong: it closed every interface scenario with a note about where the interface was thin, which could only have been written after reading the implementation.

An **implementation** scenario is written with visibility limited to the component's own specification, the interface it implements, and the interface specifications of its `imports:` closure. It may name imported collaborator components and the capabilities the specification delegates to them, because those are in its specification. It may not name classes, methods, or pseudo-code: `dag_storage` and "starter template materialization" belong in the scenario; a collaborator member name belongs in the LLS grounding.

**Who writes it.** Scenario authorship is isolated the way test authorship is: the author is blind to the translation the scenario will judge, and works in a separate turn from whoever wrote or revised the specification it is drawn from. A model that authors both a scenario and the stub it evaluates will produce scenarios its own stub satisfies, and the isolation that makes the evaluation evidence rather than restatement is gone. Operationally the rule reuses the isolation the other roles already have: a dedicated authoring role runs in its own confined workspace, whose manifest exposes the component's specification and the interface specifications of its import closure, so the planning canvas and the low-level stub are unreadable rather than merely off-limits. The samples in Section 6 were written by hand under the same rule.

### 4.4 Imports and Scenario Order

No specification exists in isolation. Front-matter `imports:` names the collaborators whose capabilities the component may use; an implementation's `implements:` names the interface whose obligations it inherits; and an interface's `**Delegated:**` paragraph declares which of its obligations are supplied by imports rather than by the component itself.

Scenarios are written upstream first, in the same topological order the cleaning DAG uses: a component's import closure before the component, and an interface before its implementation. The imported component's scenarios are then available as settled statements of what a collaborator guarantees, used three ways: as concrete referents for an importer's steps, as consistency constraints (an importer is entitled to the collaborator's guarantees and to nothing more), and as coverage donors (an obligation that merely passes an imported guarantee through needs no fresh mechanism).

### 4.5 Boundary Coverage

A scenario set that only walks the successful path reproduces the Critical User Journey trap one tier up: the set passes, the specification looks exercised, and nothing has probed the states the pipeline exists to get right. The paper's diagnosis applies verbatim at this level, and so does its defence. Each interaction a set exercises must also appear in its negative partitions, along the paper's four orthogonal dimensions: cardinality at zero, one, and many; topology with a square, a self-dependency, and a disconnected component; nullity with a missing, empty, or malformed input; and operational state uninitialized, dirty, and terminal.

The negative partition is a coverage obligation on the *set*, not a property of any one scenario. A set whose refusals, empty cases, and corrupt states are absent is a finding against the set rather than against the specification, and it is reported the same way a missing realization is: the interaction was exercised, and the boundary was not.

---

## 5. The Two Evaluations

### 5.1 Interface Evaluation — Requirement Support

For each action in an interface scenario, ask whether the interface specification states a requirement that supports the observation. Three verdicts are enough:

- **Supported.** A clause mandates the observation, and the clause is quoted.
- **Partial.** A clause mandates the shape of the observation and not its content — the ready and blocked partition exists, but nothing says what a blocked reason contains. The clause mandating the shape is quoted, and the missing content is named.
- **Unstated.** No clause addresses the observation. The verdict names the clauses examined, so absence is evidenced rather than asserted.

The interface is a bill of sale, so it owes *observable cause and effect* and nothing else. "A missing ready target is materialized before it is reported ready" is an obligation it owes. "Materializes starter templates via graph storage" is mechanism, and naming the collaborator there is also a format violation, since imported component names do not belong in `## Types and Behavior`. The same distinction applies to failures: that a request is refused is bill-of-sale; that the refusal names the offending target and directs recovery is also bill-of-sale, because it is what the caller receives; how the message is composed is not.

A separate question belongs here too: an interface operation or public member that no caller needs is an over-specified surface. That is judged against all known consumers, not just the scenarios at hand.

### 5.2 Implementation Evaluation — Realization

For each action in an implementation scenario, every realization entry must resolve to something the implementation specification provides:

- **Realized.** The collaborator is imported, or the mechanism is the component's own, and the capability is grounded for that action.
- **Floating realization.** The scenario names a collaborator capability the specification does not import at all. Nothing provides it.
- **Ungrounded realization.** The collaborator is imported but the capability is not grounded for that action: the wiring exists and the specification never says it is used that way.
- **Unhomed realization.** The action needs algorithmic or domain knowledge that the visible specification does not fix and no external component documents. Nothing provides it, and the implementer would be inventing it.

**The implementation set re-derives the interface set.** An implementation scenario is not a fresh situation; it is an interface scenario restated with a realization beside each observation. Restating rather than reinventing makes realizability structural: if an interface observation has no realization in the implementation's scenario, the defect is in the implementation rather than a gap between two disjoint sets that were never compared. Implementation-only scenarios are reserved for behaviours the interface does not expose to a caller, and each of them is a standing question about whether it belongs in the interface set instead.

**Private mechanisms need a writer.** Reading internal state is a realization like any other, and it is justified only by an operation that writes what is read. Reading the pending buffer is justified because operations set, clear, and remove entries in it. A read of state nothing writes is either a missing writer or a fabricated read. A scenario states both halves, which is what makes the justification visible rather than assumed.

**Knowledge that is not grounding-derivable has an external home.** Some realizations are neither an import nor the component's own state. Where an action needs an algorithm the specification does not fix — ordering, tie-breaking, cycle handling — that knowledge cannot come from grounding weights without the implementer inventing it. What such knowledge needs is a low-level specification that is **authored rather than inferred**, and the external plane owns that property. An external component may describe how to call a foreign API, and it may equally describe how to perform a computation: its specification is written by hand rather than generated, so an algorithm whose rules the specification does not fix is documented there rather than guessed. The precedent is already in the tree, since `json_ext` documents a bracket-balancing state machine alongside the standard library's API. Section 6.4 finding F is the live example.

The per-action qualifier matters. Materialization grounded in one operation does not ground it in another, and a collaborator imported once for one purpose does not account for the six other capabilities a scenario reads from it. This is where an implementation scenario earns its keep: it asks not "is this collaborator known" but "is this action's mechanism stated".

### 5.3 The Reverse Direction — Unexercised Requirements and the Triage

A specification can pass both evaluations while containing requirements no scenario ever needs. That is not a pass; it is a question:

- If a requirement is never exercised, either **the scenarios are lacking** — a real caller need has no scenario — or **the requirement is uncontracted** — nothing needs it, and it is over-specification to be removed or justified.
- The tiebreaker is other consumers. An operation no scenario touches may still be load-bearing for a different component, in which case the correct response is another scenario, not deletion; if no consumer needs it, it is an invented requirement.
- The same logic applies in the other direction at the seam between interface and implementation: a caller-visible observation with no requirement is a missing contract, and a requirement with no observable is a missing realization or an internal exposed by mistake.

This is why "the evaluation passed" can never be reported as completeness. Passing means every scenario that exists was satisfied; it says nothing about requirements no scenario reaches.

Not every finding needs the instrument, and saying so is part of keeping it honest. A contract whose slug appears nowhere in the stub is a pure drop, and a deterministic trace from canvas contracts to stub clauses catches that class in one pass without a model or a scenario; that floor is worth having. It is a floor and not the instrument, because presence is not realization. A clause can cite a slug and state a weaker obligation, and a trace cannot see a missing realization, an orphan read, an unhomed algorithm, or whether the caller's observation is actually supported.

---

## 6. Worked Example: `workspace_work` and `workspace_work_impl`

This section records a hand-executed investigation. It is a demonstration of the method, not a `spec_qa` verdict; each finding is a candidate a human or the arbiter would confirm.

### 6.1 The Samples

Three scenario files were written by hand: [scenarios/workspace_work.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/scenarios/workspace_work.md) with five interface scenarios, [scenarios/workspace_work_impl.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/scenarios/workspace_work_impl.md) with ten implementation scenarios, and [scenarios/workspace_registry.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/scenarios/workspace_registry.md) with six interface scenarios for the imported component. The implementation file restates the interface scenarios one through five with a realization beside each observation, and adds five scenarios for behaviours the interface does not expose.

### 6.2 Interface Evaluation

Run against [low/workspace_work.pyi](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work.pyi).

**Supported.** Asking for work yields a ready and blocked partition and a summary, because `evaluate_work` must partition tasks and return the summary. The refusal while a pending target is dirty is contracted, including the `force` condition. Strict removal of a submitted target is contracted by `remove_pending_target`. Resolving the contracts for a target is fully contracted by `resolve_contract_files`.

**Partial.** The dirty reason reported on an item has no clause behind it; the only clause tying missingness to dirtiness belongs to a different operation, `is_pending_target_dirty`. The blocked reason naming the responsible prerequisite has no clause, though `compute_role_work_queue` does require checking intra-unit upstream roles. Strict removal does not state that non-matching entries survive. The refusal does not state what the refusal says.

**Unstated.** Materializing a missing ready target. Recording the ready targets into the pending buffer. Clearing the buffer when the scope is clean. The contents of `dependency_files`, so the star-role and silent-cross-role rule is unobservable from the interface. The explicit failure for an undeclared role.

**Attribution gap.** The upstream blocking that Scenario 3 relies on is contracted by `compute_role_work_queue`, but the scenario asks for work, which is `evaluate_work`. Nothing states which operation decides upstream blocking, so a caller using the entry point cannot rely on getting it.

### 6.3 Implementation Evaluation

Run against [low/workspace_work_impl.pyi](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work_impl.pyi).

**Realized.** Scheduling through `control_work_scheduler`; in-band metadata checks through `src_metadata`; template materialization through `dag_storage`, at class level and in `compute_role_work_queue`; contract resolution through `workspace_registry`; and pending-buffer reading, writing, and filtering as private mechanics. Removal is realized better than the interface states it: the grounding adds "without wiping non-matching targets", which the interface postcondition omits. The buffer is also the read-after-write case that holds, since every read of pending state is paired with operations that set, clear, and remove entries in the same file.

**Ungrounded.** Role configuration lookups that supply source patterns, upstream roles, star-role dependencies, silent cross-role dependencies, feedback role dependencies, and audit tags. `workspace_registry` is imported and grounded for exactly one action, `resolve_contract_files`. The library reads nine distinct role-definition constituents across ten call sites, none of which the stub accounts for.

**Missing.** Clearing the buffer as an effect of evaluating work. Materialization for `evaluate_work` specifically, as opposed to the class and `compute_role_work_queue`. Star-role and silent-cross-role filtering in the queue computation. The explicit failure for an undeclared role. The diagnostic content of the refusal. And the ordering algorithm behind the topological sort the queue computation must produce, which is finding F.

### 6.4 Findings Where the Specifications Can Be Improved

**A. Planning-to-low translation losses in the interface.** `planning/workspace_work.md` carries thirteen contracts; the interface stub expresses about seven. Five have no expression at all and each corresponds to an unsupported observation in Section 6.2: `[filter_role_dependencies]`, `[enforce_strict_role_resolution]`, `[materialize_ready_target_templates]`, `[record_ready_targets_buffer]`, and `[format_work_queue_diagnostics]`. The requirement was written, and it never reached a postcondition. The fix belongs in the interface stub as observable statements: what appears, what is recorded, what is cleared, what is refused, and what a blocked reason carries.

**B. Missing realizations in the implementation.** The same five behaviours are absent from the implementation's `GROUNDING:`, so an implementer reading the stub would not know they are needed. The largest is role configuration: the implementation depends on `workspace_registry` for the constituents that drive precedence, star-role expansion, silent cross-role suppression, feedback targets, and regeneration, and grounds it once. The fix is to name the registry in the groundings of the operations that read it — queue computation, pending dirtiness, and unit discovery — not only in contract resolution.

**C. The interface was carrying the implementation's wiring, and most of it has been corrected.** `high/workspace_work.md` imported the same five components as its implementation while its own types referenced none of them, and its `**Delegated:**` paragraph named all four collaborators. The import list is now `agent_session` alone, the delegation states only session scoping, and the interface canvas no longer grounds `control_work_scheduler`, `src_metadata`, or `dag_storage`; its knowledge requirements are down to the deferred local one. What remains is stale mechanism language with no import behind it: `## Types and Behavior` still says "materializing starter templates via graph storage" in its evaluation bullet and in its pending-tracking bullet, and two canvas contracts still read "dynamically from workspace_registry" and "based on star_role_deps and silent_cross_role_deps from workspace_registry" although the canvas neither imports nor grounds that component. Those four sentences should be restated as observable effects — what appears, what is recorded, what is filtered — which is what the corrected import list already implies they are. The leaked-import class itself is closed: a repo-wide check finds no interface specification importing a component its stub never mentions.

**D. Grounding gaps in the planning canvases.** The implementation canvas cites `workspace_registry: [resolve_role_definition, list_all_role_definitions]` in its woven contracts but still carries no Knowledge Requirement for the registry, although the registry declares `[workspace_registry_service]` and `[workspace_path_resolution]`. The correct form already exists in `planning/workspace_tool_impl.md`, which grounds `[workspace_registry: [workspace_registry_service]]`. The previously dangling `list_roles` citation has been corrected to `[list_all_role_definitions]`. On the interface side the cross-component citation was removed rather than grounded, which leaves two of its contracts naming a provider the canvas no longer covers, as finding C describes.

**E. Requirements no scenario exercises.** `PENDING_WORK_FILE`, `get_pending_work`, `set_pending_work`, `clear_pending_work`, `is_pending_target_dirty`, and `compute_role_work_queue` are untouched by the five interface scenarios. The first five are used by [workspace_tool_impl.py](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/workspace_tool_impl.py), so the triage in Section 5.3 says the scenarios are lacking rather than the requirements uncontracted: the sample covers the agent's flow and not the tool's, and either tool-facing scenarios are added or the tool's coverage is acknowledged. `compute_role_work_queue` and `is_pending_target_dirty` remain candidates for the separate minimality question, since both read as internals that the interface exposes. Re-deriving the interface scenarios in the implementation set exposed a concreteness defect that the set had carried unnoticed: the removal step of interface scenario 1 asserts that the buffer's other entries are untouched, while its state holds a single entry, so the assertion is vacuous. The multi-entry removal the implementation had covered on its own had no interface counterpart at all, which is exactly the class of gap that reuse makes visible.

**F. An algorithm with no home.** `low/workspace_work.pyi` requires `compute_role_work_queue` to return its ready and blocked items "sorted topologically", and the library implements the ordering privately. Nothing documents it. `control_work_scheduler` orders by the topological depth of declared role dependencies, which orders roles rather than units, and the work manager does not import `dag_subgraph`, which computes a dependency-first topological order over graph storage. The implementation canvas instead declares the algorithm as a local provision, `[role_work_queue_algorithm]`, alongside `[part_unit_discovery_mechanics]` and `[auditor_dirtiness_evaluation_mechanics]`: three algorithms the canvas expects the implementer to supply from grounding weights while the interface demands their results. Under the rule in Section 5.2 these are unhomed realizations. The remedy is an external component whose hand-written specifications state the ordering, its tie-breaking, its cycle handling, and what makes two units incomparable, so the algorithm is documented rather than inferred. A draft now exists at [high/topological_order_ext.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/topological_order_ext.md) with its [low/topological_order_ext.pyi](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/low/topological_order_ext.pyi) stub, stating dependency-first traversal, lexical tie-breaking, undeclared dependencies ignored, cycle-closing edges not followed, and single emission. Those are the rules the library already applies privately, so the component documents the algorithm rather than changing it; what remains is the consumer cascade that makes the work manager ground on it. The ordering is the clearest case; the canvas's other algorithmic provisions, `[part_unit_discovery_mechanics]` and `[auditor_dirtiness_evaluation_mechanics]`, are the next candidates to test against the same rule.

### 6.5 What Passed

The outcome surface is sound where it is stated: the item and summary records, the ready and blocked partition, the pending-dirty refusal with its force condition, strict removal, contract resolution, and the individual buffer operations are all contracted and implementable. The interface stub's import list is already minimal. The failures are not exotic; they are ordinary translation losses of the kind a holistic prose comparison absorbs, and they concentrate where a requirement exists in the canvas and never became a postcondition.

---

## 7. Artifact Format and Lifecycle

Scenarios live in a dedicated `scenarios/<name>.md` plane beside `high/`, `planning/`, `low/`, `lib/`, and `tests/`. They are not embedded in the HLS, which has a closed two-section layout and a term ontology of its own, and they are not embedded in the planning canvas, whose headings are closed and whose purpose is the grounding DAG rather than a witness corpus.

The separation is epistemic rather than tidy. A scenario is derived from the high-level specification and then used to judge the translation, which makes it the only artifact that can hold planning itself to account. Were scenarios written inside the canvas, their author would be the planning author, and a requirement omitted from planning would never have produced a scenario at all: planning would be the accused, the witness, and the judge at once, in the way a test authored by the implementer grades its own homework. Keeping the plane separate is what lets the triage in Section 8.2 blame the canvas when a requirement never became a contract, and blame the stub when it became a contract and stopped there. It also keeps two different objects apart. The canvas states unordered atomic facts carrying slugs; a scenario is a sequence of state transitions carrying literal values. Merging them would either force chronology into the canvas or strip the scenario of its steps.

```
update_with_ai/parts/<part>/
  high/<name>.md          # source, unchanged
  planning/<name>.md      # unchanged
  low/<name>.pyi          # translation under evaluation
  scenarios/<name>.md     # concrete scenarios (new)
  lib/<name>.py           # unchanged
  tests/<name>_test.py    # unchanged
```

A scenario file is dirty when the source hash of its specification or of its translation changes, or when any scenario file in its import closure changes, reusing the in-band metadata mechanism from [in_band_source_metadata.md](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/in_band_source_metadata.md). Because scenarios are written upstream first, the dirtiness cascade follows the import DAG the way the cleaning cascade does.

The sample files are hand-written demonstrations rather than mined artifacts. Work discovery is unaffected by the new directory, because unit discovery reads `high/*.md` and role source patterns rather than directory listings.

---

## 8. Integration with the Pipeline

**8.1 Where it runs.** A separate arbiter role, `scenario`, is the better fit than a sub-pass inside `spec_qa`: it preserves the existing insulation, since `spec_qa` remains a declarative prose judge while the scenario role owns writing, the two evaluations, and the triage, and it gives the scenarios their own dirtiness, blame, and attestation.

**8.2 Blame routing.** A finding names the action, the scenario, and the culprit artifact. An unsupported observation blames the low-level specification when the requirement is in the canvas and the interface specification when it is not. An ungrounded realization blames the implementation specification. A floating realization blames whichever specification should have provided the capability. The one-culprit-per-turn rule and the existing planning bridge are preserved.

**8.3 Isolation.** Scenarios are public between the specification and its translation and are shared with neither the library author nor the test author beyond what the contracts already expose, so the information-flow invariant `I(P; V | S) = 0` is untouched. An interface scenario must never have seen the implementation; an implementation scenario may see the interface it implements and its own imports, and nothing else.

The same isolation holds one tier up, between the scenario and the translation artifacts it will be used to judge: scenario authorship carries no information about the planning canvas or the stub beyond what the specification implies, `I(scenario; planning ∪ low | high) = 0`. That is what makes a scenario an external witness rather than a restatement of the canvas, and it is why the confined authorship workspace in Section 4.3 leaves the canvas and the stub unreadable rather than merely off-limits. The invariant binds the author and not the evaluation, since the arbiter must read the stub in order to judge it; what the arbiter receives is a scenario that was frozen before the translation was read.

**8.4 Relationship to tests.** A scenario is not a test. The test role certifies that the library adheres to the LLS; the scenario role certifies that the LLS adheres to the HLS. Once a gap is fixed, the scenario is a legitimate non-contaminating seed for a contract test, because it came from the specification and not from the implementation.

---

## 9. Risks and Open Questions

**9.1 Risks.**

- *Paraphrase drift.* A scenario that restates its requirement evaluates nothing. The concreteness tests in Section 4.2 are the guard, and a scenario whose observation can be matched against a requirement sentence should be discarded.
- *Contaminated visibility.* An interface scenario that names a collaborator, a configured role, or a repository path proves the author read something else, and the earlier draft of this sample did exactly that when it closed each scenario with a note about the interface being thin.
- *Unrepresentative scenarios.* Passing scenarios can be mistaken for completeness. Section 5.3 is the only defence, and it is a decision procedure rather than a measurement.
- *False confidence.* The output is localized questions and candidate findings, never a certificate, and a clean run must be reported as bounded evidence.

**9.2 Open questions.**

1. How is an implementation-only scenario delimited from a missing interface scenario? Re-deriving the interface set settles realizability for the shared subset, but a behaviour with no interface scenario may be genuinely implementation-level, as auditor dirtiness appears to be, or an interface capability the interface set never exercised, as judging a pending target's dirtiness appears to be.
2. How should the triage in Section 5.3 record its outcome — as a work item to add a scenario, or as a decision to prune the requirement? An implicit waiver is not enough, because the point of the triage is that a requirement no scenario reaches has not been evaluated.
3. What is the smallest useful scenario set per component — one per caller flow, one per interaction, or one per boundary partition?
4. Does the computational shape codified in [high_level_spec_format.md §4.4](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md) generalize? The draft in finding F states input and output domains, traversal, dependency order, root order, undeclared references, cycle rule, and determinism; the other two unhomed algorithms named in finding F are the test of whether that is the shape or one instance of it.
5. Are scenarios a committed artifact plane or an auditor technique applied on demand? A committed plane gives review and regression value and pays for it in dirtiness churn, and Section 7 assumes the plane. The leading candidate is a committed plane for the interfaces other components integrate against, and generation on demand for lower-tier utilities where the churn outweighs the regression value.
6. Does the instrument measurably catch translation losses that `spec_qa` misses? The findings in Section 6.4 are the first evidence, but they have not been compared against a `spec_qa` pass on the same artifacts.

---

## 10. References

- [High-Level Specification Format](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md) — literate prose, semantic italics, closed two-section layout, and the ban on prose that names collaborators.
- [Low-Level Specification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md) — invariants, preconditions, postconditions, and `GROUNDING:` arguments that name collaborators.
- [paper_submission_design_doc.md §1.3.1](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md) — why specifications are untestable and the regress of interpretations.
- [paper_submission_design_doc.md §2.6](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md) — the CUJ trap, the code coverage illusion, and branch mining.
- [Auditor Roles & Verification Dirtiness Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/auditor_roles_and_dirtiness_architecture.md) — in-band attestations and auditor dirtiness.
- [In-Band Source Metadata & State Persistence](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/in_band_source_metadata.md) — source hashes and forward dirty evaluation.
- [spec_qa arbiter guide](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/guides/spec_qa.md) — the existing HLS-to-LLS semantic gate.
- Working example: [high/workspace_work.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_work.md), [high/workspace_work_impl.md](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_work_impl.md), [low/workspace_work.pyi](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work.pyi), [low/workspace_work_impl.pyi](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/low/workspace_work_impl.pyi).
