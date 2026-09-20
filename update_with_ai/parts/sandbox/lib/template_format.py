# Requirements specified in template_format.pyi
from typing import Any, Mapping, Protocol


class TemplateFormatter(Protocol):
    def format_template(self, text: str, parameters: Mapping[str, Any]) -> str: ...
