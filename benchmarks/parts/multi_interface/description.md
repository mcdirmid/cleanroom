# multi_interface

The `multi_interface` benchmark evaluates Pretense state machine synthesis and verification for implementation components realizing multiple distinct interface protocols.

## Architecture

The benchmark contains two interface components and one concrete implementation component:

1. **`stream_reader`**: Defines the abstract `StreamReader` protocol and read operations (`read()`, `has_data`, `unread_count`).
2. **`stream_writer`**: Defines the abstract `StreamWriter` protocol, operational error hierarchy (`StreamWriterError`, `PayloadEmptyError`), and write operations (`write()`, `clear()`, `written_count`).
3. **`multi_interface_impl`**: Realizes both `StreamReader` and `StreamWriter` protocols within a single concrete stream buffer singleton (`StreamBuffer`).

## Multi-Interface State Contracts

The benchmark exercises core Pretense multiple-inheritance capabilities:
- Composite state models (`CombinedBufferState`) inheriting fields from multiple interface states (`StreamReaderState`, `StreamWriterState`).
- Multi-interface pseudo-state machines inheriting transitions from multiple parent state machines (`StreamReaderStateMachine`, `StreamWriterStateMachine`).
- Hypothesis fuzz testing interleaving operations across both interfaces against the single concrete implementation instance.
