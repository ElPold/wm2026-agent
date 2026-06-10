import os

from src.sources.config import Settings


def test_timezone_strips_windows_line_endings(monkeypatch):
    monkeypatch.setenv("TIMEZONE", "Europe/Berlin\r")
    settings = Settings.load(env_file="/nonexistent/.env")
    assert settings.timezone == "Europe/Berlin"
