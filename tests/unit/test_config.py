"""Tests for configuration defaults and env overrides."""

from __future__ import annotations

from bluestar.core.config import AppSettings, LLMConfig


def test_default_settings():
    settings = AppSettings()
    assert settings.environment == "dev"
    assert settings.llm.provider == "mock"


def test_llm_config_defaults():
    config = LLMConfig()
    assert config.provider == "mock"
    assert config.temperature == 0.0
    assert config.slm_n_threads == 4
