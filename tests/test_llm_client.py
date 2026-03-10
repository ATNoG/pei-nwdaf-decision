"""Tests for LLM client."""

import json
import pytest
from unittest.mock import patch, AsyncMock, mock_open

from src.schemas import DecisionRequest
from src.services.llm_client import LLMClient


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("LLM_URL", "http://localhost:11434/api/generate")
    monkeypatch.setenv("LLM_MODEL", "llama3")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key-123")


@pytest.fixture
def mock_files():
    """Mock the prompt and system files."""
    files = {
        "llm/prompt.txt": "Analyze this:\n{data}\n\nDecisions:\n{decisions}",
        "llm/system.txt": "You are a 5G NWDAF assistant.",
    }

    def open_side_effect(path, *args, **kwargs):
        if path in files:
            return mock_open(read_data=files[path])()
        raise FileNotFoundError(path)

    return patch("builtins.open", side_effect=open_side_effect)


@pytest.fixture
def client(mock_env, mock_files):
    """Create LLMClient with mocked dependencies."""
    with mock_files:
        return LLMClient()


@pytest.fixture
def demo_request():
    """Sample DecisionRequest for testing."""
    return DecisionRequest(
        domain="anomaly",
        data=[
            {
                "model_state": {"mse": 0.0023, "accuracy": 0.94},
                "model_output": "latency_mean",
                "model_data": {
                    "predicted_latency_ms": 145.2,
                    "baseline_latency_ms": 42.0,
                    "anomaly_score": 0.92,
                },
            }
        ],
        decisions=["scale_up", "redirect_traffic", "do_nothing"],
    )


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_calls_api(self, client, demo_request):
        mock_response = {
            "response": json.dumps(
                {
                    "decision": "scale_up",
                    "reasoning": "High latency detected",
                    "alternatives": ["redirect_traffic"],
                }
            )
        }

        with patch("httpx.AsyncClient") as mock_client:
            from unittest.mock import MagicMock

            # httpx response.json() is sync, so use MagicMock
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.query(demo_request)

            mock_instance.post.assert_called_once()
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_query_increments_call_count(self, client, demo_request):
        with patch("httpx.AsyncClient") as mock_client:
            from unittest.mock import MagicMock

            mock_resp = MagicMock()
            mock_resp.json.return_value = {}
            mock_resp.raise_for_status = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_client.return_value.__aenter__.return_value = mock_instance

            assert client._call_count == 0
            await client.query(demo_request)
            assert client._call_count == 1
