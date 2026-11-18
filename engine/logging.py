"""Structured logging + error classification (§19).

JSON-lines file log (datasets/logs/engine.jsonl) for auditability; console
handler keeps CLI output human-readable. Errors carry a category so reports
can distinguish network / auth / parse / schema / access-block failures.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from engine.config import DEFAULT_CONFIG


def classify_error(exc: BaseException) -> str:
    name = type(exc).__name__
    text = str(exc).lower()
    if "challenge" in name.lower() or "captcha" in text or "turnstile" in text:
        return "access_block"
    if "401" in text or "403" in text or "api key" in text or "token" in text:
        return "auth"
    if "timeout" in name.lower() or "timed out" in text:
        return "network_timeout"
    if "connection" in name.lower() or "network" in text or "url" in name.lower():
        return "network"
    if "schema" in name.lower():
        return "schema"
    if "json" in name.lower() or "parse" in text or "decode" in text:
        return "parse"
    if "not found" in text or "404" in text:
        return "not_found"
    return "internal"


class JsonLineHandler(logging.Handler):
    def __init__(self, path: Path):
        super().__init__()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "event": record.getMessage(),
            }
            extra = getattr(record, "structured", None)
            if extra:
                entry.update(extra)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        root = logging.getLogger("engine")
        root.setLevel(logging.INFO)
        if not root.handlers:
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(logging.Formatter("%(message)s"))
            root.addHandler(console)
            root.addHandler(JsonLineHandler(DEFAULT_CONFIG.datasets_dir / "logs" / "engine.jsonl"))
        _configured = True
    return logger


def log_event(logger: logging.Logger, event: str, **fields):
    logger.info(event, extra={"structured": fields})
