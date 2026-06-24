"""Centralized stdlib logging setup.

Idempotent: calling `setup_logging` multiple times updates the level
and handler config rather than stacking handlers.
"""
from __future__ import annotations
import logging
import sys

_LOGGER_NAME = "ethics_canvas"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the `ethics_canvas` logger and return it."""
    log = logging.getLogger(_LOGGER_NAME)
    log.setLevel(level.upper())
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        log.addHandler(handler)
    else:
        log.setLevel(level.upper())
        for h in log.handlers:
            h.setLevel(level.upper())
    log.propagate = False
    return log
