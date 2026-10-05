# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 87470767e54d
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Cleanroom Bazel OpenAI loop root system assembly grounding specification module."""

from __future__ import annotations

from parts.bazel.grounding import bazel_asm
from parts.bazel.grounding import bazel_loop_impl
from parts.bazel.grounding import bazel_openai_config_impl
from parts.core.grounding import runner_logger_impl
from parts.dag.grounding import dag_asm
from parts.loop.grounding import loop_asm
from parts.sandbox.grounding import sandbox_asm

CONSTITUENTS = (
    bazel_asm,
    bazel_loop_impl,
    bazel_openai_config_impl,
    dag_asm,
    loop_asm,
    runner_logger_impl,
    sandbox_asm,
)


def __initialize__() -> None:
    """Aggregates the Bazel, DAG, loop, and sandbox assemblies along with the Bazel loop, Bazel OpenAI configuration, and runner logger implementations into the complete Cleanroom Bazel OpenAI loop root system assembly.

    CONSTITUENTS:
    - bazel_asm
    - bazel_loop_impl
    - bazel_openai_config_impl
    - dag_asm
    - loop_asm
    - runner_logger_impl
    - sandbox_asm
    """
    bazel_asm.__initialize__()
    bazel_loop_impl.__initialize__()
    bazel_openai_config_impl.__initialize__()
    dag_asm.__initialize__()
    loop_asm.__initialize__()
    runner_logger_impl.__initialize__()
    sandbox_asm.__initialize__()
