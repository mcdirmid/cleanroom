# file_reader_impl

fulfills: file_reader
imports: tool_provider (tool results, tool failures, tool call)
terms (from file_reader): virtual name, line-numbered view, session-start read
terms (from tool_provider): tool failure, tool call, tool result

## Deltas

- Precomputes a real-to-virtual path mapping sorted by length in descending order for robust sanitization.
- Formats line numbers as `1 | line text` when `include_line_numbers` is True.
- Enforces the search result limit when limit is omitted; provides `offset` and remaining count notes on search.
- Suppresses content of matches found in writable files during search.

## Non-concerns

- Output formatting of file text: exact line-number delimiter spacing is an implementation detail.
