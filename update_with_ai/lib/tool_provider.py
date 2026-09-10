from typing import Any, Optional, Protocol, Set, Tuple, Type, Union
from dataclasses import dataclass

@dataclass(frozen=True, init=False)
class WireType:
    pass

@dataclass(frozen=True)
class String(WireType):
    pass

@dataclass(frozen=True)
class Integer(WireType):
    pass

@dataclass(frozen=True)
class Boolean(WireType):
    pass

class ParameterConverter(Protocol):
    @property
    def actual_type(self) -> Type:
        ...

    @property
    def wire_type(self) -> WireType:
        ...

    def convert(self, wire_value: Any) -> Any:
        ...

class IdentityParameterConverter(ParameterConverter, Protocol):
    pass

class StringParameterConverter(IdentityParameterConverter, Protocol):
    @property
    def actual_type(self) -> Type:
        ...

    @property
    def wire_type(self) -> WireType:
        ...

    def convert(self, wire_value: Any) -> str:
        ...

class IntegerParameterConverter(IdentityParameterConverter, Protocol):
    @property
    def actual_type(self) -> Type:
        ...

    @property
    def wire_type(self) -> WireType:
        ...

    def convert(self, wire_value: Any) -> int:
        ...

class BooleanParameterConverter(IdentityParameterConverter, Protocol):
    @property
    def actual_type(self) -> Type:
        ...

    @property
    def wire_type(self) -> WireType:
        ...

    def convert(self, wire_value: Any) -> bool:
        ...


@dataclass(frozen=True)
class Parameter:
    name: str
    description: str
    parameter_converter: ParameterConverter
    is_required: bool = True

@dataclass(frozen=True)
class ActualParameterBindings:
    bindings: Set[Tuple[Parameter, Any]]

@dataclass(frozen=True)
class WireParameterBindings:
    bindings: Set[Tuple[str, Union[str, int, bool]]]

@dataclass(frozen=True)
class Response:
    is_failed: bool
    is_terminated: bool
    content: str
    reminder: Optional[str] = None
    suppression_key: Optional[str] = None

class Tool(Protocol):
    @property
    def name(self) -> str:
        ...

    @property
    def description(self) -> str:
        ...

    @property
    def parameters(self) -> Set[Parameter]:
        ...

    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
        ...

class ToolManager(Protocol):
    @property
    def installed_tools(self) -> Set[Tool]:
        ...

    def install_tool(self, tool: Tool) -> None:
        ...

    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
        ...

