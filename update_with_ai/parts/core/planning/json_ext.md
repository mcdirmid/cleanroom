# json_ext external component

## Intent

Standard JSON encoders and parsers operate over complete, well-formed document structures. When large language model completions stream or exhaust token context budgets mid-payload, language models emit truncated or structurally incomplete JSON text with unclosed string literals, unmatched braces, unmatched brackets, or trailing comma syntax. Direct coupling between language model drivers and ad-hoc bracket-matching routines leads to fragmented error recovery, duplicate repair implementations, and brittle string parsing logic across loop drivers.

The json_ext external component encapsulates standard JSON encoding and decoding alongside deterministic token repair and bracket balancing mechanics. By establishing a uniform boundary for serialization, deserialization, and truncated token salvaging, the external boundary protects driver components from malformed JSON payloads and token exhaustion errors.

## Grounding

### Knowledge Provisions

- JSON encoding, decoding, and truncated token salvage and repair. [json_operations]
