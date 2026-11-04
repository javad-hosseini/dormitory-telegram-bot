"""Unit tests for AuthMiddleware and AlbumMiddleware."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.types import CallbackQuery, Message, User
from src.config import Settings
from src.middlewares.album import AlbumMiddleware
from src.middlewares.auth import AuthMiddleware


@pytest.mark.asyncio
async def test_auth_middleware_allowed_user():
    """Verify that whitelisted user passes through to handler."""
    settings = Settings(ALLOWED_TELEGRAM_USER_IDS=[111, 222])
    middleware = AuthMiddleware(settings)

    handler = AsyncMock(return_value="OK")
    user = User(id=111, is_bot=False, first_name="Admin")
    message = MagicMock(spec=Message)
    message.from_user = user

    result = await middleware(handler, message, {"event_from_user": user})
    assert result == "OK"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_middleware_unauthorized_user():
    """Verify that non-whitelisted user is rejected and event is dropped."""
    settings = Settings(ALLOWED_TELEGRAM_USER_IDS=[111, 222])
    middleware = AuthMiddleware(settings)

    handler = AsyncMock(return_value="OK")
    user = User(id=999, is_bot=False, first_name="Stranger")
    message = MagicMock(spec=Message)
    message.from_user = user
    message.answer = AsyncMock()

    result = await middleware(handler, message, {"event_from_user": user})
    assert result is None
    handler.assert_not_awaited()
    message.answer.assert_awaited_once()
    args, _ = message.answer.call_args
    assert "⛔ Unauthorized access" in args[0]
    assert "999" in args[0]


@pytest.mark.asyncio
async def test_auth_middleware_unauthorized_callback_query():
    """Verify callback query rejection with alert."""
    settings = Settings(ALLOWED_TELEGRAM_USER_IDS=[111, 222])
    middleware = AuthMiddleware(settings)

    handler = AsyncMock(return_value="OK")
    user = User(id=999, is_bot=False, first_name="Stranger")
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = user
    callback.answer = AsyncMock()

    result = await middleware(handler, callback, {"event_from_user": user})
    assert result is None
    handler.assert_not_awaited()
    callback.answer.assert_awaited_once()
    _, kwargs = callback.answer.call_args
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_album_middleware_aggregation():
    """Verify AlbumMiddleware aggregates media group messages within latency window."""
    middleware = AlbumMiddleware(latency=0.05)
    handler = AsyncMock(return_value="PROCESSED_ALBUM")

    m1 = MagicMock(spec=Message)
    m1.media_group_id = "grp_100"
    m2 = MagicMock(spec=Message)
    m2.media_group_id = "grp_100"

    data = {}

    # Fire both concurrently
    task1 = asyncio.create_task(middleware(handler, m1, data))
    await asyncio.sleep(0.01)  # small yield so m1 enters sleep
    task2 = asyncio.create_task(middleware(handler, m2, data))

    res1, res2 = await asyncio.gather(task1, task2)

    # m2 was secondary, so it should return None
    assert res2 is None
    # m1 was primary, so it should execute handler with data["album"] containing [m1, m2]
    assert res1 == "PROCESSED_ALBUM"
    assert "album" in data
    assert len(data["album"]) == 2
