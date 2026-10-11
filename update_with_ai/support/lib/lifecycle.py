"""Forwarding alias for lifecycle runtime primitives."""
import sys as _sys
import update_python_with_ai.support.lib.lifecycle as _lifecycle

_sys.modules[__name__] = _lifecycle
