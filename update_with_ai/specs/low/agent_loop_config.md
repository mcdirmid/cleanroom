<!-- Dependencies (md files to read alongside this one):
  - agent_loop.md
-->

# Interface LLS: agent_loop_config

## Data Types
```python
from dataclasses import dataclass
from typing import Optional, Protocol
from agent_loop import TerminationReminderGenerator

@dataclass
class AgentLoopConfig:
    base_url: str
    api_key: str
    model: str
    max_iterations: int = 10
    temperature: float = 0.0
    timeout: float = 60.0
    max_tokens: Optional[int] = None
    termination_reminder_generator: Optional[TerminationReminderGenerator] = None
    continuation_prompt: Optional[str] = None

class AgentLoopConfigProvider(Protocol):
    def construct(self, base_url: str, api_key: str, model: str, max_iterations: int = 10, temperature: float = 0.0, timeout: float = 60.0, max_tokens: Optional[int] = None, termination_reminder_generator: Optional[TerminationReminderGenerator] = None, continuation_prompt: Optional[str] = None) -> AgentLoopConfig: ...
```

`AgentLoopConfig` is the exchanged configuration value: the run's connection
and processing parameters, supplied when an agent loop is constructed. The
defaults match the pins in the consuming implementation's HLS Deltas (ten iterations,
0.0 temperature, 60-second timeout). `AgentLoopConfigProvider` documents the
construction operation; the dataclass constructor is the concrete
construction entry point, so the Protocol's name takes the provider role
rather than the component name (the component name collides with the type it
holds). Field meanings:

- `base_url`: Server endpoint for the language model service
- `api_key`: API key for authentication
- `model`: Model name to use
- `max_iterations`: Maximum loop iterations before failure (default: 10)
- `temperature`: Sampling temperature (default: 0.0)
- `timeout`: Request timeout in seconds (default: 60.0)
- `max_tokens`: Maximum tokens to generate (default: None, service default)
- `termination_reminder_generator`: Optional generator for termination reminders
- `continuation_prompt`: Prompt appended to resume generation when the model response is truncated (default: None, implementation default used)

## Term definitions

- **agent-loop configuration** → the `AgentLoopConfig` dataclass (definition in Data Types)

## Component-Provided Operations

### `construct`

```python
def construct(self, base_url: str, api_key: str, model: str, max_iterations: int = 10, temperature: float = 0.0, timeout: float = 60.0, max_tokens: Optional[int] = None, termination_reminder_generator: Optional[TerminationReminderGenerator] = None, continuation_prompt: Optional[str] = None) -> AgentLoopConfig: ...
```

**Purpose:** Construct an agent-loop configuration from the run's connection and processing parameters.

**Preconditions:**
- `base_url`, `api_key`, and `model` are provided.

**Postconditions:**
- Provides an `AgentLoopConfig` whose fields are exactly the supplied values; unset optional fields take the documented defaults.

**Failure Handling:**
- No expected failures: construction is a value operation.

**HLS Justification:** "Construct an agent-loop configuration."

## Invariants

- An `AgentLoopConfig` carries its parameter values unchanged between construction and consumption.
- No persistent state is held across constructions.

## Non-Concerns

- The meaning of individual parameters: they pass through unchanged to the agent loop construction.
- The selection and loading of configuration values: the producing component's concern.
- **Protocol naming:** the Protocol takes the provider role (`AgentLoopConfigProvider`) because the component name collides with the `AgentLoopConfig` type it holds; the component-named-Protocol rule cannot apply here.
