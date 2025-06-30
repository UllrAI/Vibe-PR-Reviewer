
import importlib
import os
import pytest

from core import config

def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test_github_token")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_api_key")
    monkeypatch.setenv("AI_MODEL_NAME", "test-model")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("INCLUDE_FILE_CONTEXT", "false")

    importlib.reload(config)
    settings = config.Settings()

    assert settings.GITHUB_TOKEN == "test_github_token"
    assert settings.GEMINI_API_KEY == "test_gemini_api_key"
    assert settings.AI_MODEL_NAME == "test-model"
    assert settings.PORT == 9000
    assert settings.INCLUDE_FILE_CONTEXT is False

def test_settings_default_values(monkeypatch):
    # Ensure required variables are set for the test to pass
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_github_token")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_gemini_api_key")

    # Unset optional variables to check default values
    monkeypatch.delenv("AI_MODEL_NAME", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("INCLUDE_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("MAX_PROMPT_LENGTH", raising=False)
    monkeypatch.delenv("OUTPUT_LANGUAGE", raising=False)

    importlib.reload(config)
    settings = config.Settings()

    assert settings.AI_MODEL_NAME == "gemini-1.5-pro-latest"
    assert settings.PORT == 8080
    assert settings.INCLUDE_FILE_CONTEXT is True
    assert settings.MAX_PROMPT_LENGTH == 200000
    assert settings.OUTPUT_LANGUAGE == "english"

def test_settings_missing_required_env_vars(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    importlib.reload(config)
    with pytest.raises(ValueError):
        settings = config.Settings()
        settings.validate_settings()
