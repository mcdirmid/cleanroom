# loop_conversation interface component

imports: tool_provider

## Assumptions and Requirements

### Requirements

1. Initial messages can seed the conversation at session start.
2. Appending messages and tool responses adds them in chronological order.
3. Stubs previous responses and correlating tool arguments identified by a suppression key.
4. The conversation produces a model request prepared for transmission to a language model.

## Grounding Facts

### Knowledge Needed

- Initial seeding messages.
- Appended message and tool response chronology.
- Response suppression keys.
- Model request payload format.

### Actions Needed

- Seed conversation with startup messages.
- Append messages and tool responses chronologically.
- Stub superseded responses matching suppression keys.
- Assemble prepared model request.
