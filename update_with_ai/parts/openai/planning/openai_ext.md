# openai_ext external component

## Intent

Direct coupling between domain components and remote model API endpoints creates network fragility, vendor transport coupling, and inconsistent error handling. The openai_ext external component establishes an external boundary that encapsulates HTTP transport mechanics, request payload translation, and token usage accounting reported by OpenAI-compatible endpoints.

By defining explicit payload schemas and mapping HTTP status codes to domain error representations, the external component insulates the system from network quirks and wire protocol details.

## Grounding

### Knowledge Provisions

- OpenAI chat completion wire protocol schemas, HTTPS transport, and response parsing. [openai_wire_operations]
