"""Integration tests for raw data collection handler workflows."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Message, PhotoSize, User

from src.bot.handlers.raw_data import (
    handle_finish_export,
    handle_next_row,
    handle_start_raw_data,
    handle_collecting_row_input,
)
from src.bot.states import RawDataStates
from src.config import Settings
from src.database.repository import DatabaseRepository


@pytest.fixture
def fsm_context():
    """Create a test FSMContext instance."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=1001, user_id=1001)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_start_raw_data_fresh(test_db: DatabaseRepository, fsm_context: FSMContext, monkeypatch):
    """Test starting a fresh raw data session when none exists."""
    monkeypatch.setattr("src.bot.handlers.raw_data.get_db", lambda: test_db)

    message = AsyncMock(spec=Message)
    message.from_user = User(id=1001, is_bot=False, first_name="Manager")
    message.answer = AsyncMock()

    await handle_start_raw_data(message, fsm_context)

    state = await fsm_context.get_state()
    assert state == RawDataStates.collecting_row.state
    data = await fsm_context.get_data()
    assert "session_id" in data

    # Verify session in DB
    session = await test_db.get_active_session(1001)
    assert session is not None
    assert session.session_id == data["session_id"]
    assert session.current_row_index == 1

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.call_args
    assert "Raw Data Session Started" in args[0]


@pytest.mark.asyncio
async def test_input_photo_with_caption(test_db: DatabaseRepository, fsm_context: FSMContext, sample_image_path: Path, monkeypatch):
    """Test that photo with caption creates an IMAGE block and an automatic TEXT block in the next column."""
    monkeypatch.setattr("src.bot.handlers.raw_data.get_db", lambda: test_db)

    # Initialize active session
    session = await test_db.create_session(1001, "sess_caption_test")
    await fsm_context.set_state(RawDataStates.collecting_row)
    await fsm_context.update_data(session_id="sess_caption_test")

    bot = AsyncMock()
    # Mock bot.download to write to destination
    async def mock_download(file, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(sample_image_path.read_bytes())

    bot.download = AsyncMock(side_effect=mock_download)

    photo_size = PhotoSize(file_id="p1", file_unique_id="pu1", width=100, height=100)
    message = AsyncMock(spec=Message)
    message.from_user = User(id=1001, is_bot=False, first_name="Manager")
    message.photo = [photo_size]
    message.document = None
    message.text = None
    message.caption = "Room 304 - 6,000,000 IRR Deposit"
    message.answer = AsyncMock()

    await handle_collecting_row_input(message, fsm_context, bot)

    blocks = await test_db.get_blocks_for_row("sess_caption_test", 1)
    assert len(blocks) == 2
    assert blocks[0].block_type == "IMAGE"
    assert blocks[0].col_index == 1
    assert blocks[1].block_type == "TEXT"
    assert blocks[1].col_index == 2
    assert blocks[1].text_content == "Room 304 - 6,000,000 IRR Deposit"


@pytest.mark.asyncio
async def test_next_row_empty_guard(test_db: DatabaseRepository, fsm_context: FSMContext, monkeypatch):
    """Test that next_row blocks moving if current row is empty."""
    monkeypatch.setattr("src.bot.handlers.raw_data.get_db", lambda: test_db)
    session = await test_db.create_session(1001, "sess_guard")
    await fsm_context.update_data(session_id="sess_guard")

    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = User(id=1001, is_bot=False, first_name="Manager")
    callback.answer = AsyncMock()

    await handle_next_row(callback, fsm_context)

    callback.answer.assert_awaited_once()
    args, kwargs = callback.answer.call_args
    assert "Current row is empty" in args[0]
    assert kwargs.get("show_alert") is True
