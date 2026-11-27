"""
Open BOS Stream Logging
"""

import logging
import re

# Gastlink-Codes und Token in Pfaden bzw. Parametern nie ins Journal
# schreiben: Wer das Protokoll lesen kann, könnte sie sonst benutzen.
SECRET_PATHS = (
    (re.compile(r"(/g/)[^/?\s\"]+"), r"\1***"),
    (re.compile(r"(?i)([?&](?:token|password|pass|key|streamid)=)[^&\s\"]+"), r"\1***"),
)


def redact_secrets(text: str) -> str:
    for pattern, replacement in SECRET_PATHS:
        text = pattern.sub(replacement, text)
    return text


class SecretPathFilter(logging.Filter):
    """Maskiert Geheimnisse in Zugriffsprotokollen (uvicorn.access)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_secrets(item) if isinstance(item, str) else item
                for item in record.args
            )
        elif isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        return True


def setup_logging():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, SecretPathFilter) for item in access.filters):
        access.addFilter(SecretPathFilter())
