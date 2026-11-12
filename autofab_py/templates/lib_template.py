from __future__ import annotations

from support.lib.lifecycle import get_singleton, singleton

# Cleanroom library module.
# Implement classes, methods, and lifecycle functions directly from the low-level specification (.pyi)
# following your Companion Guide (guides/low_to_lib.md).
# Interface service protocols inherit Singleton[TierType] and Protocol matching low/<name>.pyi.
# Implementation classes implement the interface protocol directly matching low/<name>_impl.pyi,
# are decorated with @singleton, declare class-level tier matching their declared lifecycle tier,
# never append bare Singleton or duplicate Singleton[TierType], and initialize backing state
# via __init__(self) -> None or the inherited hook def initialize(self) -> None:.
# Lifecycle registration is completely automatic: implementation modules NEVER define __initialize__.
#
# Example:
#   @singleton
#   class ExampleServiceImpl(ExampleService):
#       tier = "system"
#
#       def __init__(self) -> None:
#           self._state: dict[str, str] = {}

