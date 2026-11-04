"""Integration tests for cleaned .xlsx ingestion handler workflows."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import openpyxl
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Document, Message, User

from src.bot.handlers.ingest_cleaned import (
    handle_confirm_ingestion,
    handle_new_instructions_text,
    handle_uploaded_document,
    prompt_upload_cleaned_file,
)
from src.bot.states import IngestStates
from src.database.repository import DatabaseRepository


@pytest.fixture
def fsm_context():
    """Create a test FSMContext instance."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=1001, user_id=1001)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
def sample_cleaned_xlsx(tmp_path: Path) -> Path:
    """Create a sample cleaned transactions workbook."""
    file_path = tmp_path / "valid_cleaned.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cleaned_Data"
    ws.append(["Room", "Resident", "Amount_IRR", "Type"])
    ws.append([101, "Ali", 4500000, "RENT"])
    ws.append([102, "Sara", 6000000, "DEPOSIT"])
    wb.save(file_path)
    return file_path


@pytest.mark.asyncio
async def test_prompt_upload_cleaned_file(fsm_context: FSMContext):
    """Test /ingest_cleaned sets state to waiting_for_file."""
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()

    await prompt_upload_cleaned_file(message, fsm_context)

    state = await fsm_context.get_state()
    assert state == IngestStates.waiting_for_file.state
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_uploaded_cleaned_document(
    test_db: DatabaseRepository,
    fsm_context: FSMContext,
    sample_cleaned_xlsx: Path,
    monkeypatch,
):
    """Test uploading a cleaned .xlsx file generates dry-run preview and extracts metadata."""
    monkeypatch.setattr("src.bot.handlers.ingest_cleaned.get_db", lambda: test_db)

    bot = AsyncMock()
    async def mock_download(doc, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(sample_cleaned_xlsx.read_bytes())

    bot.download = AsyncMock(side_effect=mock_download)

    progress_msg = AsyncMock()
    progress_msg.edit_text = AsyncMock()

    message = AsyncMock(spec=Message)
    message.from_user = User(id=1001, is_bot=False, first_name="Manager")
    message.caption = "Special instruction: categorize rent strictly"
    doc = Document(
        file_id="doc1",
        file_unique_id="doc_u1",
        file_name="valid_cleaned.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    message.document = doc
    message.answer = AsyncMock(return_value=progress_msg)

    await handle_uploaded_document(message, fsm_context, bot)

    state = await fsm_context.get_state()
    assert state == IngestStates.preview_and_confirm.state

    data = await fsm_context.get_data()
    assert data["file_name"] == "valid_cleaned.xlsx"
    assert len(data["rows"]) == 2
    assert "special instruction" in data["instructions"].lower()

    progress_msg.edit_text.assert_awaited_once()
    args, _ = progress_msg.edit_text.call_args
    assert "Cleaned Spreadsheet Ingestion Preview" in args[0]
    assert "<b>Total Rows:</b> <b>2</b>" in args[0]


@pytest.mark.asyncio
async def test_confirm_ingestion_success(
    test_db: DatabaseRepository,
    fsm_context: FSMContext,
    monkeypatch,
):
    """Test confirming ingestion records rows in database and clears FSM."""
    monkeypatch.setattr("src.bot.handlers.ingest_cleaned.get_db", lambda: test_db)

    # Populate state data
    await fsm_context.set_state(IngestStates.preview_and_confirm)
    await fsm_context.update_data(
        file_name="clean.xlsx",
        headers=["Room", "Amount"],
        rows=[{"Room": 201, "Amount": 5000000}],
        row_hashes=["dummy_hash_123"],
        instructions="Post to ledger",
        duplicate_hashes=[],
    )

    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "ingest:confirm"
    callback.from_user = User(id=1001, is_bot=False, first_name="Manager")
    callback.answer = AsyncMock()

    status_msg = AsyncMock(spec=Message)
    status_msg.edit_text = AsyncMock(return_value=status_msg)
    callback.message = status_msg

    bot = AsyncMock()

    await handle_confirm_ingestion(callback, fsm_context, bot)

    # State cleared
    state = await fsm_context.get_state()
    assert state is None

    # Database recorded the transaction
    existing = await test_db.check_row_hashes(["dummy_hash_123"])
    assert "dummy_hash_123" in existing

    status_msg.edit_text.assert_awaited()
    last_call = status_msg.edit_text.call_args_list[-1]
    assert "Succeeded:</b> 1 rows" in last_call[0][0]
