from __future__ import annotations

# Cleanroom library module.
# Implement classes, methods, and lifecycle functions directly from the low-level specification (.pyi)
# following your Companion Guide (guides/low_to_lib.md).
# Interface service protocols inherit Singleton[TierType] and Protocol matching low/<name>.pyi.
# Implementation classes implement the interface protocol directly matching low/<name>_impl.pyi,
# specify class-level tier matching their declared lifecycle tier, never append bare Singleton or duplicate Singleton[TierType],
# and initialize backing state via __init__(self) -> None or the inherited hook def initialize(self) -> None:.
# Module registration is handled via auto-generated __initialize__(registry=None); classes never define __initialize__.
