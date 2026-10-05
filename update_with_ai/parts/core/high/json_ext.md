<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: 8fdff390d9ae
-->

# json_ext external component

## Purpose

The json_ext external component defines external JSON serialization, deserialization, and truncated token salvage mechanics.

Standard JSON encoders and parsers operate over complete, well-formed document structures. When large language model completions stream or exhaust token context budgets mid-payload, language models emit truncated or structurally incomplete JSON text with unclosed string literals, unmatched braces, unmatched brackets, or trailing comma syntax. Direct coupling between language model drivers and ad-hoc bracket-matching routines leads to fragmented error recovery, duplicate repair implementations, and brittle string parsing logic across loop drivers. The json_ext external component encapsulates standard JSON encoding and decoding alongside deterministic token repair and bracket balancing mechanics, ensuring that driver components interface with external JSON representations through a robust, standardized boundary.

**Out of scope:** The json_ext external component does not evaluate tool semantics, validate parameter types, or execute downstream function calls; these are handled by other components.

## Grounding Gaps Covered

The json_ext component provides external formatting knowledge and token mechanics for standard JSON parsing, serialization, and salvaging truncated JSON responses emitted by language models.

Grounding gaps covered include:

- Standard JSON deserialization: Parses JSON formatted text into native Python data structures including mappings, lists, strings, numbers, booleans, and null values, distinguishing valid structures from syntax errors.

- Deterministic JSON serialization: Serializes native data structures into standard UTF-8 JSON text formatting, with support for deterministic key sorting to guarantee reproducible representations.

- Truncated token and bracket repair: Identifies incomplete or truncated JSON text caused by token exhaustion or generation limits, salvaging valid data by balancing unclosed string quotes, resolving dangling escape sequences, stripping trailing commas, and closing unclosed braces and brackets in correct reverse nesting order.

- Malformed payload detection and fallback: Recognizes unrecoverable or malformed payloads lacking object opening markers, falling back to an empty object representation.
