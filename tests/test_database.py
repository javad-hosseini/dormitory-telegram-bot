"""Unit tests for SQLite repository persistence, crash recovery, and idempotency."""

import pytest
from src.database.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_session_lifecycle(test_db: DatabaseRepository):
    """Test creating, fetching, updating, and completing raw sessions."""
    user_id = 998877

    # Initially no session
    active = await test_db.get_active_session(user_id)
    assert active is None

    # Create session
    session = await test_db.create_session(user_id, "session_001")
    assert session.session_id == "session_001"
    assert session.current_row_index == 1
    assert session.status == "ACTIVE"

    # Fetch active
    active = await test_db.get_active_session(user_id)
    assert active is not None
    assert active.session_id == "session_001"

    # Advance row
    await test_db.update_session_row("session_001", 2)
    updated = await test_db.get_session("session_001")
    assert updated is not None
    assert updated.current_row_index == 2

    # Mark completed
    await test_db.set_session_status("session_001", "COMPLETED")
    active_after = await test_db.get_active_session(user_id)
    assert active_after is None


@pytest.mark.asyncio
async def test_blocks_and_undo(test_db: DatabaseRepository):
    """Test appending blocks, undoing last block, and clearing a row."""
    session = await test_db.create_session(12345, "sess_blocks")
    s_id = session.session_id

    # Add text block to Row 1
    b1 = await test_db.add_block(s_id, row_index=1, block_type="TEXT", text_content="Room 101 - 5M IRR")
    assert b1.col_index == 1

    # Add image block to Row 1
    b2 = await test_db.add_block(s_id, row_index=1, block_type="IMAGE", file_path="/app/data/test.jpg")
    assert b2.col_index == 2

    blocks_row_1 = await test_db.get_blocks_for_row(s_id, 1)
    assert len(blocks_row_1) == 2

    # Undo last block (b2 should be removed)
    removed, resulting_row = await test_db.undo_last_block(s_id, 1)
    assert removed is not None
    assert removed.id == b2.id
    assert resulting_row == 1

    remaining = await test_db.get_blocks_for_row(s_id, 1)
    assert len(remaining) == 1
    assert remaining[0].id == b1.id

    # Test undo on empty row 2 stepping back to row 1
    await test_db.update_session_row(s_id, 2)
    stepback_removed, stepback_row = await test_db.undo_last_block(s_id, 2)
    assert stepback_removed is None
    assert stepback_row == 1


@pytest.mark.asyncio
async def test_clear_row(test_db: DatabaseRepository):
    """Test clearing all blocks in a row."""
    session = await test_db.create_session(12345, "sess_clear")
    s_id = session.session_id

    await test_db.add_block(s_id, 1, "TEXT", "Note 1")
    await test_db.add_block(s_id, 1, "TEXT", "Note 2")

    cleared = await test_db.clear_row(s_id, 1)
    assert len(cleared) == 2

    blocks_after = await test_db.get_blocks_for_row(s_id, 1)
    assert len(blocks_after) == 0


@pytest.mark.asyncio
async def test_idempotency_and_hash_tracking(test_db: DatabaseRepository):
    """Test checking existing row hashes to prevent double-insertions."""
    hashes = ["hash_abc", "hash_def", "hash_ghi"]
    existing = await test_db.check_row_hashes(hashes)
    assert len(existing) == 0

    await test_db.record_ingested_transaction(
        row_hash="hash_abc",
        file_name="clean.xlsx",
        row_index=2,
        data_json='{"amount": 1000}',
        status="SUCCESS",
        user_id=12345,
    )

    existing_after = await test_db.check_row_hashes(hashes)
    assert existing_after == {"hash_abc"}
