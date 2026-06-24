"""Tests for logging.setup_logging."""
import logging
from ethics_canvas.logging import setup_logging


def test_setup_logging_returns_logger():
    log = setup_logging("INFO")
    assert isinstance(log, logging.Logger)
    assert log.name == "ethics_canvas"
    assert log.level == logging.INFO


def test_setup_logging_respects_level():
    log = setup_logging("DEBUG")
    assert log.level == logging.DEBUG
