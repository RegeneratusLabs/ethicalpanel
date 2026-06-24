"""Tests for config.Settings."""
import pytest
from pydantic import ValidationError
from ethics_canvas.config import Settings


def test_minimal_valid_settings(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    s = Settings(_env_file=None)
    assert s.deepseek_api_key == "sk-test"
    assert s.deepseek_model == "deepseek-v4-flash"
    assert s.deepseek_base_url == "https://api.deepseek.com/anthropic"
    assert s.idea_max_length == 5000
    assert s.log_level == "INFO"
    assert s.request_timeout_s == 60


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ETHICS_FILTER_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "api_key" in str(exc_info.value).lower()


def test_overrides_take_effect(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "custom-model")
    monkeypatch.setenv("IDEA_MAX_LENGTH", "1000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings(_env_file=None)
    assert s.deepseek_model == "custom-model"
    assert s.idea_max_length == 1000
    assert s.log_level == "DEBUG"
