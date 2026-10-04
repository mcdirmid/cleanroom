<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-04T02:03:40Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: new file
-->

# Guide: Low-Level to Static Python Grounding Alignment

## Summary

The artifact is a Python grounding module (`grounding/<name>.py`, `grounding/<name>_impl.py`, or assembly module `grounding/<name>_asm.py`) that structurally formalizes `low/<name>.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple grounding specifications are processed together by package-relative alias path. Grounding modules provide static constructive feasibility proofs in a straight-line, highly typed subset of Python. Grounding's sole responsibility is proving static constructive feasibility (type soundness, collaborator availability, metadata accessibility, and straight-line condition/consequent evaluation). Dynamic runtime execution and algorithmic control flow (such as loops, conditionals, branching ladders, exception handling, and socket/disk operations) are exclusively the concern of `lib/` and must neither be audited nor reported as uncovered requirements in grounding; Pyright performs 100% static type checking with zero dynamic execution.

The grounding process achieves 100% symbol parity, member parity, and contractual clause accountability from `low/<name>.pyi`: every class, protocol, data type, parameter type, and variant declared in `low/<name>.pyi` is represented in `grounding/<name>.py`, and all declared methods and properties are declared. Interface components (`grounding/<name>.py`) define abstract protocols and structural types without requiring a paired local implementation module (`grounding/<name>_impl.py`) in the same package or part; interface protocols may be implemented by concrete `_impl` components located in other components or parts. Abstract methods and properties declared on interface protocols (`Protocol`) provide capabilities to external callers and collaborators, but cannot provide values or implementations to themselves; requirements whose return values or behaviors originate from an implementation source (backing storage, configuration files, environment variables, or algorithm execution) are left uncovered in interface protocols and cataloged under `DEFERRED:`, to be refined and discharged by implementing components. As an edge case, `@data_type` classes extending a `@poly_type` protocol must have all deferred knowledge requirements satisfied immediately in the interface module with straight-line feasibility proofs under `COVERED:` (zero `DEFERRED:` entries); these data types are the only types implemented in an interface component. Writing `COVERED:` on a method or property whose body is an ellipsis `...` or bare `raise NotImplementedError` without proof statements is strictly prohibited. Every contractual postcondition (`WHEN <condition>, MUST <consequent>`) and invariant from `low/<name>.pyi` is quoted verbatim in member docstrings under `COVERED:` (for postconditions substantiated by straight-line typed feasibility proofs) or `DEFERRED:` (for abstract obligations on non-`_impl` singletons and polytypes awaiting subtype refinement), with class-level `DISCHARGED:` summaries in `_impl.py` modules confirming that all inherited interface obligations have been resolved. For every postcondition under `COVERED:`, the method body contains typed straight-line code expressions substantiating both condition knowledge (evaluating parameter flags, key presence, line bounds, error feedback) and consequent knowledge (constructing diagnostic failure responses citing exact parameter/tool names, evaluating callbacks, applying defaults, converting wire values, invoking collaborator operations); generic mock returns or empty returns that bypass condition and consequent evaluation are prohibited. Every argument passed into an output record constructor, dataclass instantiation, or collaborator call must demonstrate genuine data provenance—derived directly from method parameters, queried from collaborator singletons via `self.get_singleton(...)`, transformed from validated inputs, or explicitly mandated as a literal constant by the contract; fabricating arbitrary placeholder literals or dummy structures to pacify constructor signatures (Constructor Pacification via Phantom Literals) is strictly classified as a mock bypass and is prohibited. When an output record requires fields whose data sources or derivation mechanics cannot be traced to declared parameters, collaborators, or contract-specified defaults, the grounding specification must not invent placeholder literals, escalating the ungrounded contract upstream. Feasibility of failure outcomes (`WHEN ... fails, MUST fail`) is proven by evaluating condition checks and constructing failure responses in typed local variables without runtime failure propagation. Method bodies consist strictly of straight-line assignments, collaborator lookups via `self.get_singleton(...)`, single-element collection operations (`key`, `value`, `only_elem` from `support.lib.grounding_support`), and terminate with `raise NotImplementedError`; `return` statements, conditionals (`if/else`, ternary `x if c else y`), loops (`for`, `while`), exception handling (`try/except`), and non-`NotImplementedError` raises are prohibited.

> META: "Grounding modules construct straight-line, typed Python feasibility proofs terminating with raise NotImplementedError from low-level stubs, documenting covered, deferred, and discharged requirements while allowing non-impl singletons and polytypes to defer state obligations to refining subtypes."

## Lint checks

- [ ] Control flow statements (`If`, `IfExp`, `For`, `AsyncFor`, `While`, `Try`, `With`, `Match`, `Yield`, `Assert`, comprehensions) are strictly prohibited
- [ ] Return statements are strictly prohibited; proof outcomes are assigned to typed local variables
- [ ] Ellipsis `...` in executable bodies is strictly prohibited; ellipsis is permitted only in type annotations (e.g. `Callable[..., T]`)
- [ ] Every function and method (except `__init__` and `__initialize__`) terminates strictly with `raise NotImplementedError`
- [ ] No dead code statements appear after terminal `raise NotImplementedError`
- [ ] Direct self-recursion (`self.foo(...)` inside `foo`) is strictly prohibited
- [ ] Every class, protocol, data type, parameter type, and variant name matches its corresponding declaration in `low/<name>.pyi`
- [ ] In implementation specifications (`grounding/<name>_impl.py`), every class declared in `low/<name>_impl.pyi` is implemented
- [ ] Every method, property, and initialization sequence declared in `low/<name>.pyi` is declared on the corresponding grounding class, and implemented in non-interface modules
- [ ] Methods and properties claiming requirements under `COVERED:` have non-empty proof statements before terminal `raise NotImplementedError`
- [ ] Abstract methods and properties on interface protocols (`Protocol`) whose values originate from implementation sources catalog requirements under `DEFERRED:`, never `COVERED:`, with body `raise NotImplementedError`
- [ ] Member docstring requirement sections are restricted to `COVERED:` and `DEFERRED:`, with class-level summaries in `_impl.py` modules using `DISCHARGED:`
- [ ] Every postcondition clause and invariant from `low/<name>.pyi` is quoted verbatim under `COVERED:` or `DEFERRED:`
- [ ] Open obligations under `DEFERRED:` are permitted on `@singleton_type` and `@poly_type` classes in interface specifications; interface components do not require local `_impl` modules
- [ ] Data types (`@data_type`) and variants (`@variant`) cover all requirements immediately without `DEFERRED:` entries; data types extending a `@poly_type` protocol satisfy all inherited knowledge requirements immediately under `COVERED:`
- [ ] Implementation modules (`grounding/<name>_impl.py`), when present, discharge all inherited `DEFERRED:` obligations with zero remaining `DEFERRED:` entries
- [ ] Single-element collection helper functions (`key`, `value`, `only_elem`) are imported from `support.lib.grounding_support`
- [ ] Lifecycle tier capabilities inherit from `InTier[TierType]` imported from `support.lib.grounding_support`; domain-specific tier classes declared in the low file are re-declared in grounding modules, inheriting from the appropriate support tier base (e.g., `SystemTier`, `AgentSessionTier`)
- [ ] Method bodies contain strictly assignments, member accesses, call expressions, and terminal `raise NotImplementedError`

## Document layout and imports

- [ ] Grounding modules import type annotations (`Any`, `Callable`, `Iterable`, `Mapping`, `Optional`, `Protocol`, `Sequence`, `Set`, `cast`) from `typing`
- [ ] Grounding modules import single-element helpers (`key`, `value`, `only_elem`) from `support.lib.grounding_support`; tier base capabilities (`InTier`, `SystemTier`) are imported from `support.lib.grounding_support`, while domain-specific tier classes (e.g., `AgentSessionTier`) declared in the low file must be re-declared in the grounding module, inheriting from the appropriate support tier base
- [ ] Domain types and stubs are imported from sibling grounding modules or declared with equivalent signatures
- [ ] The `__all__` list in grounding modules exports only domain types declared in the corresponding low file, not support/library types such as `InTier`, `SystemTier`, or helper functions
- [ ] Implementation grounding modules (`grounding/<name>_impl.py`) import their base interface grounding module directly
- [ ] Classes are separated by two blank lines, and class members are separated by one blank line
- [ ] Triple-quoted docstrings summarize class and member purposes and catalog requirement coverage

## Structural and symbol parity

- [ ] Every class, protocol, parameter type, and helper declared in `low/<name>.pyi` is declared in `grounding/<name>.py`
- [ ] In `grounding/<name>_impl.py`, all inherited and newly declared classes from `low/<name>_impl.pyi` are declared and implemented
- [ ] Every method and property signature matches the parameter names, default values, and type annotations declared in `low/<name>.pyi`
- [ ] Implementation classes override and implement every operation and property inherited from base protocols
- [ ] Helper classes, variant types, and specialized parameter types declared in `low/*.pyi` are fully materialized in grounding modules

## Requirement decomposition and clause accountability

- [ ] 100% of contractual postconditions (`WHEN ... MUST ...`) and invariants from `low/<name>.pyi` are accounted for in member docstrings
- [ ] Every postcondition clause is quoted verbatim starting with `- ` under `COVERED:` (substantiated by straight-line typed feasibility proofs) or `DEFERRED:` (abstract obligations on non-`_impl` singletons and polytypes awaiting subtype refinement)
- [ ] No postcondition clause from `low/<name>.pyi` is silently dropped, summarized away, or omitted
- [ ] Contractual postconditions (`WHEN ... MUST ...`) are decomposed into atomic condition knowledge and consequent knowledge requirements
- [ ] Postconditions whose condition expressions and consequent constructions are proven in straight-line code are cataloged under `COVERED:`
- [ ] Uncovered requirements depending on internal state, implementation configuration, or subtype specialization in non-`_impl` singletons and polytypes are cataloged under `DEFERRED:`
- [ ] Abstract methods and properties on interface protocols that declare capabilities for callers without an internal backing data source are cataloged under `DEFERRED:`, never `COVERED:`
- [ ] All contractual postconditions in `_impl.py` are claimed and proven under `COVERED:` via straight-line representative dataflows, leaving dynamic control flow (runtime branching `if/else`, iteration loops, and exception handling) as an implementation detail of `lib/`
- [ ] Data type and variant classes never declare `DEFERRED:` requirements; all value properties, constructors, and inherited polytype requirements on data types extending polytypes are covered immediately
- [ ] Implementation specifications (`grounding/<name>_impl.py`) declare the resolution and discharge of all inherited `DEFERRED:` obligations via class-level `DISCHARGED:` summaries confirming that all inherited interface obligations have been resolved
- [ ] Caller assumptions under `ASSUMPTIONS:` in `low/<name>.pyi` are accepted axiomatically and require zero knowledge derivation, zero checks, zero branching, and zero test coverage
- [ ] Callee components never verify or check caller assumptions in grounding proofs
- [ ] Grounding alignment checks must evaluate only symbol parity, member parity, type soundness, verbatim postcondition quoting, and straight-line dataflow proofs. Assessments of grounding health must never inspect, check, or report on dynamic runtime control flow or algorithmic execution.

## Straight-line knowledge proofs and anti-mechanistic feasibility

- [ ] For every postcondition under `COVERED:`, the method body contains explicit, typed straight-line code expressions evaluating its condition knowledge
- [ ] Condition knowledge expressions evaluate parameter flags (`is_required`), test key presence in dictionaries, inspect error attributes, or evaluate boundary conditions
- [ ] For every postcondition under `COVERED:`, the method body contains explicit, typed straight-line code expressions constructing its consequent knowledge
- [ ] Consequent knowledge expressions construct failure responses citing exact parameter or tool names, invoke callback functions, apply default bindings, convert wire values, and invoke collaborator methods
- [ ] For postconditions specifying failure outcomes, failure response construction expressions are assigned to typed local variables (`_fail_response`) to verify diagnostic handling feasibility without runtime failure propagation
- [ ] Generic mock returns that bypass constructive feasibility are prohibited; outcomes are assigned to typed local variables
- [ ] Every intermediate computation, attribute access, and collaborator response inspection is assigned to a typed local variable to verify feasibility
- [ ] Every method body terminates strictly with `raise NotImplementedError`

## Data provenance and prohibition of phantom literals

- [ ] Every argument passed into an output record constructor, dataclass instantiation, or collaborator call has demonstrable data provenance: drawn directly from input arguments, extracted from collaborator queries (`self.get_singleton(...)`), transformed from accessible inputs, or explicitly mandated as a literal constant by the low-level contract
- [ ] Fabricating arbitrary string literals, numbers, or mock structures to satisfy constructor signatures (such as inventing placeholder guide summaries, fake task prompts, or arbitrary URLs to pacify constructors) is strictly classified as a prohibited mock bypass
- [ ] When an output record requires fields whose data sources or derivation mechanics cannot be traced to declared parameters, collaborators, or contract-specified defaults, inventing placeholder literals is prohibited; the grounding specification escalates the gap upstream demanding that the contract specify data provenance
- [ ] Constructor arguments for composite data types substantiate the complete dataflow from condition inputs and collaborator queries through to the constructed record without phantom substitutions

## Control flow and straight-line dataflows

- [ ] Every method execution path is completely straight-line and sequential from entry to terminal `raise NotImplementedError`
- [ ] Conditional branching statements (`if`, `elif`, `else`) and ternary expressions (`x if c else y`) are omitted; dataflow follows the primary constructive pathway
- [ ] Iteration statements (`for`, `while`) and list, dict, or set comprehensions are omitted in favor of single-element operations
- [ ] Exception handling blocks (`try`, `except`, `finally`) are omitted
- [ ] Return statements, early returns, `break`, `continue`, and generators (`yield`) are omitted
- [ ] Non-`NotImplementedError` exception raises are omitted; methods terminate strictly with `raise NotImplementedError`

## Information accessibility and metadata verification

- [ ] Every parameter metadata attribute required for validation in `low/<name>.pyi` contracts is accessed and assigned in the dataflow
- [ ] Parameter requirement flags (`is_required`) are accessed to verify that presence checks can be performed
- [ ] Default values (`default_value`) are accessed and typed to verify that fallback substitution is feasible
- [ ] Missing message callbacks (`missing_message`) are invoked or typed to verify callable signatures
- [ ] Wire-format conversion methods (`wire_type`, `convert`) are called on representative inputs to prove type transformation validity
- [ ] Result inspection attributes (`is_failed`, `content`, `reminder`) are accessed on collaborator responses to verify diagnostic handling feasibility
- [ ] Collection inspection attributes (such as `keys()`) are accessed to prove dictionary diagnostic formatting feasibility

## Single-element collection abstractions

- [ ] Collections are manipulated using representative element projections rather than loops or indexed sweeps
- [ ] Keys of associative mappings are projected via `key(mapping)`
- [ ] Values of associative mappings are projected via `value(mapping)` or direct subscripting `mapping[key(mapping)]`
- [ ] Elements of sequences and iterables are projected via `only_elem(iterable)`
- [ ] Associative arguments to collaborator operations are constructed using representative key-value bindings (e.g. `{param: actual_value}`)
- [ ] Sequence arguments to collaborator operations are constructed using single-element lists (e.g. `[converted_item]`)

## Lifecycle tiers and singleton capabilities

- [ ] Active service singletons express lifecycle tier membership by inheriting `InTier[TierType]`
- [ ] Collaborator singletons are resolved on demand via `self.get_singleton(CollaboratorClass)`
- [ ] Singletons in `SystemTier` only resolve collaborator singletons belonging to `SystemTier`
- [ ] Singletons in `AgentSessionTier` resolve collaborator singletons belonging to `SystemTier` or `AgentSessionTier`
- [ ] Global or ambient singleton accessors outside `InTier` are avoided in grounding proofs

## Obligation propagation and implementation refinement

- [ ] Interface grounding modules (`grounding/<name>.py`) implement all operations whose dataflow dependencies are known at the interface level, while leaving state-dependent protocol operations under `DEFERRED:` without requiring a local `_impl` module
- [ ] Operations requiring implementation-specific backing state declare abstract methods or open hook attributes
- [ ] Data types extending a polytype protocol are implemented directly in the defining interface module with all requirements covered immediately
- [ ] Implementation grounding modules (`grounding/<name>_impl.py`) declare internal backing collections and state fields
- [ ] Implementation grounding modules override and discharge all open obligations inherited from interface grounding modules
- [ ] Assembly modules (`grounding/<name>_asm.py`) declare constituent initialization sequences proving mutual resolution across all singletons
