# Requirements specified in template_format.pyi
from typing import Any, Mapping, NewType, Protocol

TemplateText = NewType("TemplateText", str)
TemplateKey = NewType("TemplateKey", str)
FormattedText = NewType("FormattedText", str)


class TemplateFormatter(Protocol):
    def format_template(
        self, text: TemplateText, parameters: Mapping[TemplateKey, Any]
    ) -> FormattedText: ...
