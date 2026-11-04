"""Unit tests for configuration loading and validation."""

from pathlib import Path
from src.config import Settings


def test_settings_allowed_user_ids_parsing():
    """Verify parsing comma-separated strings and integer lists."""
    s1 = Settings(ALLOWED_TELEGRAM_USER_IDS="1001, 1002, 1003")  # type: ignore
    assert s1.ALLOWED_TELEGRAM_USER_IDS == [1001, 1002, 1003]

    s2 = Settings(ALLOWED_TELEGRAM_USER_IDS=[2001, 2002])
    assert s2.ALLOWED_TELEGRAM_USER_IDS == [2001, 2002]

    s3 = Settings(ALLOWED_TELEGRAM_USER_IDS="")  # type: ignore
    assert s3.ALLOWED_TELEGRAM_USER_IDS == []


def test_settings_default_instructions(tmp_path: Path):
    """Verify fallback to config/default_agent_instructions.md if instructions are not set."""
    s = Settings(DEFAULT_AGENT_INSTRUCTIONS="")
    instructions = s.get_effective_default_instructions()
    assert len(instructions) > 0
    assert "Dormitory" in instructions or "transaction" in instructions.lower()


def test_settings_ensure_directories(tmp_path: Path):
    """Verify that ensure_directories creates required directories."""
    data_dir = tmp_path / "custom_data"
    sessions_dir = data_dir / "sessions"
    db_path = data_dir / "bot.db"

    s = Settings(DATA_DIR=data_dir, SESSIONS_DIR=sessions_dir, DB_PATH=db_path)
    s.ensure_directories()

    assert data_dir.exists()
    assert sessions_dir.exists()
