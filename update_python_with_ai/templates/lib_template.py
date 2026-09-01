"""
<TODO: module docstring — the LLS this module implements (interface or implementation)>
"""

from __future__ import annotations

# TODO: import the interface types this module implements and uses, e.g.
# from .inventory import Inventory, Sku, Quantity


class <Name>(Protocol):  # interface module: delete when this is an implementation module
    """<TODO: interface operations become the Protocol's methods>"""

    def operation(self, param: str) -> str:
        """<TODO: operation contract per the interface LLS>"""
        ...


class <Name>Impl(<Interface>):  # implementation module: delete when this is an interface module
    """<TODO: fulfills the <Interface> contract per its LLS>"""

    def __init__(self, config: <Config>) -> None:
        """<TODO: configuration per the implementation LLS (capability bundling)>"""
        ...

    def operation(self, param: str) -> str:
        """<TODO: implement each operation per the interface LLS —
        signatures verbatim, preconditions honored, postconditions satisfied,
        expected failures as the LLS's return signals>"""
        raise NotImplementedError


# TODO: work through this module:
#   - the LLS is the contract; implement every operation, invariant, and pin
#   - keep the module layout and stubs the template provides; replace placeholders
#   - expected failures use the LLS's return signals; unexpected failures propagate

