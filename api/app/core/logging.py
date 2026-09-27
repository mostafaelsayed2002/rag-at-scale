"""App-wide logging: plain text in dev, one JSON object per line in production."""

import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Writes each log line as JSON, so log tools can filter by field."""

    def format(self, record: logging.LogRecord) -> str:
        payload = dict(getattr(record, "extra_data", {}))
        payload.update(
            {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", as_json: bool = True) -> None:
    """Set up app-wide logging. Replaces old handlers, so lines never print twice."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        JSONFormatter() if as_json else logging.Formatter("%(levelname)-7s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
