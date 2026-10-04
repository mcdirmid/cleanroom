"""Loop subsystem assembly grounding specification module."""

from __future__ import annotations

from parts.loop.grounding import loop_cleaner_impl
from parts.loop.grounding import loop_guard_impl
from parts.loop.grounding import loop_node_cleaner_impl
from parts.openai.grounding import openai_conversation_impl
from parts.openai.grounding import openai_driver_impl

CONSTITUENTS = (
    loop_cleaner_impl,
    loop_guard_impl,
    loop_node_cleaner_impl,
    openai_conversation_impl,
    openai_driver_impl,
)


def __initialize__() -> None:
    """Aggregates turn loop execution, prompt conversation history formatting, loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.

    CONSTITUENTS:
    - loop_cleaner_impl
    - loop_guard_impl
    - loop_node_cleaner_impl
    - openai_conversation_impl
    - openai_driver_impl
    """
    loop_cleaner_impl.__initialize__()
    loop_guard_impl.__initialize__()
    loop_node_cleaner_impl.__initialize__()
