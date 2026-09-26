# Lost Functionality Ledger

This ledger records functionality, automated checks, or translation mechanics intentionally deprecated, dropped, or shifted to manual verification during the transition to the new High-Level Specification (HLS), Groundtalk grounding specification, and alignment framework.

---

## 1. Grounding Specification Mechanics & Tooling

### Dropped: Automated Inheritance Synchronization & Duplication
- **Previous Behavior**: `grounding_tool.py` automatically computed and injected `INHERITED_REQUIREMENTS:`, `INHERITED_ASSUMPTIONS:`, and synthetic `@override` stubs into `_impl.pyi` stubs. It rejected files where inherited requirements were missing or modified.
- **New Behavior**: Implementation specifications (`_impl.pyi`) omit `INHERITED_REQUIREMENTS:` and `INHERITED_ASSUMPTIONS:`. The implementer and test generator resolve inherited contracts transitively by inspecting the imported interface `.pyi` specifications directly.
- **Rationale**: Eliminates redundant string copying, reduces stub file churn, prevents AST bloating, and avoids synchronization lag between interface and implementation stubs.

### Dropped: Step Mode Unbounded File Checking for Grounding
- **Previous Behavior**: In step mode, the grounding validator or runner checked the unbounded/uncommitted file state across multiple nodes.
- **New Behavior**: Unbounded file checking in step mode is discontinued. Verification operates against the target's explicit file state and declared dependencies.
- **Rationale**: Simplifies step mode verification, isolates subagent evaluations, and aligns with the multi-node task runner boundaries.

### Dropped: Translating Asks for `lib/*.py` Files into `grounding/*.pyi` Files
- **Previous Behavior**: When a request or edit was prompted for a library file (`lib/*.py`), tools or workflows attempted to back-translate or mirror asks into grounding stubs (`grounding/*.pyi`).
- **New Behavior**: Strictly unidirectional pipeline: `HLS` $\to$ `Grounding` $\to$ `Library` $\to$ `Unit Tests`. Asks for `lib/*.py` are never translated back into `grounding/*.pyi`. Any contract change must be initiated at the HLS level.
- **Rationale**: Enforces the specification-first Cleanroom principle and eliminates cycles in the generation pipeline.

---

## 2. Linters & Verification Checks

### Deprecated Linter Checks in `grounding_tool.py`
- Dropped checking for `PURPOSE:` and `INHERITANCE:` headers in docstrings.
- Dropped checking for `FRESH_REQUIREMENTS:` vs `INHERITED_REQUIREMENTS:` distinction. Replaced by direct `REQUIREMENTS:`.
- Dropped checking for `FRESH_ASSUMPTIONS:` vs `INHERITED_ASSUMPTIONS:` distinction. Replaced by direct `ASSUMPTIONS:`.
- Added recognition of Groundtalk sections: `GROUNDING_PROVISIONS:`, `GROUNDING_REQUIREMENTS:`, `GROUNDING_ASSUMPTIONS:`, `GROUNDING_IMPLEMENTS:`, and `GROUNDING_ARGUMENT:`.
- Replaced rigid string checks on grounding arguments with Groundtalk logic contract verification (or deferred to manual inspection until the Groundtalk solver engine is implemented).

### Deprecated Linter Checks in `test_lint.py`
- Dropped requiring `# Requirement:` citations to match only `_impl.pyi` local requirements.
- Updated `test_lint.py` to search imported interface `.pyi` stubs for cited `# Requirement:` strings.

---

## 3. Structural & Semantic Simplifications

### Dropped: Dual-Term Phrasing and Redundant Gloss
- Opposing dual-term pairs (e.g. active vs inactive, draft vs synced) are eliminated in favor of single canonical terms with boolean qualifiers or negations.
- Redundant explanatory gloss trailing type names is omitted.
