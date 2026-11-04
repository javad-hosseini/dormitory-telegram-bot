"""Pytest fixtures for unit and integration testing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator

import pytest
from PIL import Image as PILImage

from src.config import Settings
from src.database.repository import DatabaseRepository


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def test_settings(tmp_data_dir: Path) -> Settings:
    """Provide test settings with isolated directories."""
    return Settings(
        BOT_TOKEN="123456789:TEST_MOCK_TOKEN_ABCD1234efgh",
        ALLOWED_TELEGRAM_USER_IDS=[111222, 333444],
        DATA_DIR=tmp_data_dir,
        DB_PATH=tmp_data_dir / "test.db",
        SESSIONS_DIR=tmp_data_dir / "sessions",
        MAX_IMAGE_DIMENSION_PX=200,
        INGESTION_MODE="mock_dry_run",
    )


@pytest.fixture
async def test_db(test_settings: Settings) -> AsyncGenerator[DatabaseRepository, None]:
    """Provide an initialized DatabaseRepository backed by a temporary file."""
    repo = DatabaseRepository(test_settings.DB_PATH)
    await repo.init_db()
    yield repo


@pytest.fixture
def sample_image_path(tmp_path: Path) -> Path:
    """Generate a sample JPEG receipt image for testing."""
    img_path = tmp_path / "test_receipt.jpg"
    img = PILImage.new("RGB", (400, 600), color=(240, 240, 240))
    img.save(img_path, format="JPEG")
    return img_path
