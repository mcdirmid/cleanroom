# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: dc09adf5c1d7
# --- END CLEANROOM METADATA ---

# Requirements specified in template_format.pyi
from typing import Any, Mapping, NewType, Protocol

TemplateText = NewType("TemplateText", str)
TemplateKey = NewType("TemplateKey", str)
FormattedText = NewType("FormattedText", str)


class TemplateFormatter(Protocol):
    def format_template(
        self, text: TemplateText, parameters: Mapping[TemplateKey, Any]
    ) -> FormattedText: ...
