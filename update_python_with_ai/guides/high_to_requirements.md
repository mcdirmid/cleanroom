# Guide: High-Level to Requirements Specification Alignment

## Summary

The artifact is a requirements specification (`requirements/<name>.md`) that extracts and atomizes normative behavioral contracts from a High-Level Specification (`high/<name>.md`), submitted via `submit(target="<target_file>", change_summary="...")` (in single-target sessions, the target parameter may be omitted). In a multi-node session, multiple requirements specifications are processed together, each identified by its package-relative file alias path. The artifact conforms to this guide and the requirements architecture described in the design documents. When starting from a template, the template's inline instructions guide creating a minimal artifact that satisfies initial verification before advancing.

Requirements specifications partition contracts into caller preconditions and environmental invariants (`### Assumptions`) and binding behavioral guarantees, observable outcomes, state transitions, and explicit failure-handling obligations (`### Requirements`). An optional `## Grounding Facts` section serves as a prose-based planning layer that identifies the pieces of knowledge and actions needed to satisfy requirements, preventing premature AST pattern matching. Each requirement item is a single, self-contained, declarative natural language sentence without mathematical formula syntax, AST variables, or quantifiers. Structural record fields, static type facts, domain purpose clauses, and procedural implementation mechanisms are excluded from requirements.

> META: "Requirements specifications extract atomic, declarative natural-language behavioral contracts from high-level specifications and plan required knowledge and actions in prose, strictly separating caller assumptions from binding component guarantees."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface` or `implementation`
- [ ] Front-matter ordering places `imports:` first (if any), followed by `implements:` (for implementation components)
- [ ] Implementation specifications (`requirements/<name>_impl.md`) declare `implements: <interface>` listing the implemented interface component name
- [ ] Interface specifications (`requirements/<name>.md`) never declare `implements:`
- [ ] Front-matter never contains `types from <dep>:` or `assembles:` statements
- [ ] Section inventory is closed to `## Assumptions and Requirements` and optional `## Grounding Facts`
- [ ] Subsections under `## Assumptions and Requirements` are closed strictly to `### Assumptions` and `### Requirements`
- [ ] `### Requirements` is mandatory in every requirements specification
- [ ] When `### Assumptions` is present, it precedes `### Requirements`
- [ ] When `## Grounding Facts` is present, it follows `## Assumptions and Requirements`
- [ ] Subsections under `## Grounding Facts` describe `### Knowledge Needed` or `### Actions Needed`
- [ ] Sub-headers under `## Assumptions and Requirements` beyond `### Assumptions` and `### Requirements` are strictly prohibited
- [ ] Assumption and requirement items are numbered list entries or bulleted sub-notes
- [ ] Every assumption and requirement sentence ends with a period (`.`)
- [ ] Sentences in `## Assumptions and Requirements` never contain formula variables (`v_call`, `v_param`), quantifiers (`for any`, `there exists`), or equality operators (`==`, `!=`)

## Document structure and front-matter

- [ ] An interface requirements specification (`requirements/<name>.md`) defines caller preconditions and public behavioral guarantees for the interface
- [ ] An implementation requirements specification (`requirements/<name>_impl.md`) specifies concrete algorithmic contracts, validation boundaries, and model boundary defenses without duplicating interface contracts
- [ ] Implementation specifications declare `implements: <interface>` naming the interface component implemented
- [ ] Front-matter `imports:` lists only imported component names separated by commas
- [ ] Imported components in `imports:` reflect components whose types or concepts are referenced in requirements
- [ ] Assembly components (`high/<name>_asm.md`) and external boundary components (`high/<name>_ext.md`) do not define standalone requirements specifications; assembly logic is structural and external boundaries contain no Python code

## Assumptions and preconditions

- [ ] The `### Assumptions` section contains caller obligations, environmental prerequisites, and invariant preconditions assumed by the component
- [ ] Assumption failure results in undefined behavior unless an explicit requirement mandates detection or failure handling
- [ ] Preconditions on operations invoked by client components are declared under `### Assumptions` in interface specifications
- [ ] Downstream implementation components never introduce failure-handling requirements for operations whose interface definitions specify no failure contract
- [ ] Unmet operational preconditions without an explicit failure requirement in the interface represent assumption violations resulting in undefined behavior
- [ ] When a requirement specifies behavior under a specific assumption, the assumption reference is cited using `- (woven with assumption [<id>]): <sentence>.`
- [ ] Assumptions describe concrete invocation or environmental conditions rather than passive global facts

## Requirements and behavioral guarantees

- [ ] The `### Requirements` section defines binding guarantees, state transitions, observable outcomes, and explicit failure-handling obligations
- [ ] Components on external AI model interaction boundaries define explicit failure-handling requirements protecting against non-conforming model inputs
- [ ] Lookup and registry contracts express discovery and retrieval guarantees directly without prescribing internal indexing algorithms or data structures
- [ ] Environmental sanitization, path masking, and data transformations are stated as observable output guarantees
- [ ] Operations that can fail specify the exact failure conditions and the diagnostic guidance or error messages returned
- [ ] Every requirement is deterministically satisfiable by the component using only declared collaborators, configuration, and inputs in scope
- [ ] Requirements never assume external capabilities or custody of data without an explicit derivation path from declared inputs or dependencies

## Sentence formulation and atomization

- [ ] Each assumption and requirement is expressed as a single, clear, declarative English sentence ending with a period (`.`)
- [ ] Sentences state observable behavioral outcomes rather than procedural execution recipes or step-by-step algorithms
- [ ] Mathematical formula notation, AST predicates, boolean algebra symbols, and pseudo-code are excluded
- [ ] Universal and existential quantifiers (`for any`, `there exists`) and variable prefixes (`v_call`, `v_param`) are excluded
- [ ] Compound failure requirements that combine trigger conditions with response messaging are decomposed into atomic failure predicates and diagnostic postconditions
- [ ] Prioritized or ordered failure ladders declare failure conditions monotonically and define response dispatch as ordered decision statements
- [ ] Sentences employ canonical domain terminology established in the High-Level Specification without introducing competing synonyms

## Scope attribution and boundary filtering

- [ ] Requirements attribute responsibilities to active singleton services or polymorphic operations in scope
- [ ] Passive data types define only operator-like behaviors intrinsic to the values themselves, such as string formatting, display representations, or structural comparisons
- [ ] Property derivation, field calculation, and validation constraints belong to active services that construct or manage the data type, never to the passive data type itself
- [ ] Requirements describing data type property formation that cannot be bound to an active service in scope are omitted or attributed to the managing service
- [ ] Constituent property enumerations that introduce or list data fields of a record belong to static type definitions and are excluded from requirements
- [ ] Static type relationships and algebraic definitions belong to type annotations and are excluded from requirements
- [ ] Domain purpose explanations and clauses explaining what a flag or field indicates are excluded from requirements
- [ ] Trivial state setters and basic registration mechanics are omitted when lookup and discovery requirements already verify availability

## Grounding facts planning

- [ ] The `## Grounding Facts` section serves as an explicit prose-based planning layer identifying knowledge and actions needed to achieve requirements before formal typing occurs
- [ ] Under `### Knowledge Needed`, specify what items, concepts, inputs, or states need to be known, not what the knowledge values, constants, or contents actually are
- [ ] Under `### Actions Needed`, specify what external collaborator operations, boundary calls, or transformations are needed to fulfill requirements
- [ ] Descriptions use simple, direct prose identifying the concept (e.g. cache inactivity threshold, session status, target file path) without dumping literals or implementation algorithms
- [ ] Action descriptions identify collaborator capabilities and external effects needed to fulfill each requirement without prematurely writing code

## Common pitfalls

- [ ] Compound sentences — combining failure predicates, diagnostic text, and follow-up directives into a single compound requirement
- [ ] Formula notation — using mathematical symbols or AST variables instead of clear natural language sentences
- [ ] Fabricated failures — adding failure-handling requirements for operations whose interface specifies no failure behavior
- [ ] Structural duplication — listing data fields, dataclass properties, or static type bounds as requirements
- [ ] Passive data type derivation — requiring passive data types to compute or validate their own properties instead of attributing to active services
- [ ] Purpose statements — including clauses that explain what a configuration or flag indicates rather than stating behavioral constraints
- [ ] Trivial setter clutter — writing separate requirement sentences for basic property setters or registration when retrieval contracts already cover them
- [ ] Imperative steps — phrasing requirements as procedural algorithms or chronological execution recipes instead of declarative guarantees
- [ ] Unbounded derivation — specifying that a component computes or resolves data without an explicit derivation path from inputs or collaborators
- [ ] Missing period — terminating an assumption or requirement sentence without a period
- [ ] Describing knowledge values — enumerating exact constants, environment variable string names, literal values, or parser rules instead of specifying what needs to be known
- [ ] Skipping grounding planning — jumping directly from requirements to AST stubs without planning required knowledge and actions in prose, leading to pattern-matched tautologies
