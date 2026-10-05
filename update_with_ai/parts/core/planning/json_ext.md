<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: 18c4d77cf85b
-->

# json_ext external component

## Intent

Standard JSON encoders and parsers operate over complete, well-formed document structures. When large language model completions stream or exhaust token context budgets mid-payload, language models emit truncated or structurally incomplete JSON text with unclosed string literals, unmatched braces, unmatched brackets, or trailing comma syntax. Direct coupling between language model drivers and ad-hoc bracket-matching routines leads to fragmented error recovery, duplicate repair implementations, and brittle string parsing logic across loop drivers.

The json_ext external component encapsulates standard JSON encoding and decoding alongside deterministic token repair and bracket balancing mechanics. By establishing a uniform boundary for serialization, deserialization, and truncated token salvaging, the external boundary protects driver components from malformed JSON payloads and token exhaustion errors.

## Factored Contracts

### Contracts

- A caller supplies JSON formatted text when parsing data. [parse_input_supplied]
- A caller supplies a native data structure when serializing data. [dump_input_supplied]
- A caller supplies potentially truncated JSON text when repairing payloads. [repair_input_supplied]
- JSON parsing converts valid JSON text into native data structures. [parse_valid_json]
- JSON parsing raises a decoding error when text is malformed. [parse_malformed_error]
- JSON serialization converts native data structures into standard JSON text. [serialize_native_data]
- JSON serialization sorts dictionary keys deterministically. [serialize_sorted_keys]
- Truncated repair trims outer whitespace from input text. [repair_strip_whitespace]
- Truncated repair locates the first opening object brace. [repair_locate_opening_brace]
- Truncated repair balances unclosed string literal quotes. [repair_balance_string_quotes]
- Truncated repair strips dangling trailing comma delimiters. [repair_strip_trailing_commas]
- Truncated repair closes open container delimiters in reverse nesting order. [repair_close_nested_containers]
- Truncated repair synthesizes an empty object when no opening brace exists. [repair_empty_object_fallback]

## Woven Contracts

- When parsing JSON text, valid formatted input is converted into native data structures. [parse_input_supplied, parse_valid_json]
- When serializing native data structures, keys are sorted deterministically into standard JSON text. [dump_input_supplied, serialize_native_data, serialize_sorted_keys]
- When repairing truncated JSON text, string quotes are balanced, trailing commas are stripped, and unclosed containers are closed in reverse order. [repair_input_supplied, repair_strip_whitespace, repair_locate_opening_brace, repair_balance_string_quotes, repair_strip_trailing_commas, repair_close_nested_containers]
- When repairing text lacking an opening brace, an empty object is returned. [repair_input_supplied, repair_empty_object_fallback]
