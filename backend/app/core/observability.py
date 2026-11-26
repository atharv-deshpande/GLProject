import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
SENSITIVE_KEY = re.compile(r"(password|token|secret|authorization|api[_-]?key|credential)", re.I)
EMAIL = re.compile(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b")


def new_request_id(value: str | None = None) -> str:
    if value and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", value):
        return value
    return str(uuid.uuid4())


def redact(value, key: str = ""):
    if SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return EMAIL.sub("[REDACTED_EMAIL]", value)
    return value


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    if not any(getattr(h, "_ekip_json", False) for h in root.handlers):
        handler._ekip_json = True
        root.addHandler(handler)
    root.setLevel(logging.INFO)
