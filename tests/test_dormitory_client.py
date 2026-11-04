"""Unit tests for Dormitory client implementations and factory."""

import pytest
import httpx
from src.config import Settings
from src.services.dormitory_client import (
    AgentWebhookClient,
    MockDryRunClient,
    get_dormitory_client,
)


@pytest.mark.asyncio
async def test_mock_dry_run_client():
    """Verify mock dry run processes rows successfully and handles simulation triggers."""
    client = MockDryRunClient()
    rows = [
        {"Room": 101, "Amount": 5000000},
        {"Room": 102, "Amount": 3000000, "simulate_error": True},
    ]
    hashes = ["h1", "h2"]
    results = await client.process_rows(rows, hashes, "Process these rows")

    assert len(results) == 2
    assert results[0].success is True
    assert results[0].response_data is not None
    assert results[1].success is False
    assert "Simulated validation error" in (results[1].error_message or "")


@pytest.mark.asyncio
async def test_agent_webhook_client_success(monkeypatch):
    """Verify AgentWebhookClient handles HTTP 200 batch response."""
    async def mock_post(self, url, **kwargs):
        mock_response = httpx.Response(
            status_code=200,
            json={"status": "BATCH_ACCEPTED", "count": 2},
            request=httpx.Request("POST", url),
        )
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = AgentWebhookClient("https://agent.example.com/api", "secret-token")
    rows = [{"Room": 201}, {"Room": 202}]
    hashes = ["hash1", "hash2"]
    results = await client.process_rows(rows, hashes, "Instructions")

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is True


def test_get_dormitory_client_factory():
    """Verify factory returns appropriate client based on settings."""
    s_mock = Settings(INGESTION_MODE="mock_dry_run")
    assert isinstance(get_dormitory_client(s_mock), MockDryRunClient)

    s_webhook = Settings(
        INGESTION_MODE="agent_webhook",
        DORMITORY_AGENT_API_URL="https://agent.example.com",
    )
    assert isinstance(get_dormitory_client(s_webhook), AgentWebhookClient)
