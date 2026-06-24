from unittest.mock import MagicMock, patch

import pytest

from app.core.llm import get_llm_provider
from app.core.llm.anthropic import AnthropicProvider
from app.core.llm.gemini import GeminiProvider
from app.core.llm.openai import OpenAIProvider


@pytest.fixture
def mock_db_settings():
    with patch("app.models.db.get_setting", return_value=None):
        yield


def test_factory_get_llm_provider(mock_db_settings):
    # Test fallback to environment variables
    with patch("app.core.llm.LLM_PROVIDER", "openai"):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)

    with patch("app.core.llm.LLM_PROVIDER", "anthropic"):
        provider = get_llm_provider()
        assert isinstance(provider, AnthropicProvider)

    with patch("app.core.llm.LLM_PROVIDER", "gemini"):
        provider = get_llm_provider()
        assert isinstance(provider, GeminiProvider)

    # Test settings override
    with patch("app.models.db.get_setting", return_value="openai"):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)


def test_openai_provider_analyze_submission(mock_db_settings):
    provider = OpenAIProvider()

    # Mock OpenAI client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content='{"scores": {"Innovation": 4.5}, "impact_score": 4.2, "judges_feedback": []}')
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    with (
        patch.object(provider, "_get_client", return_value=mock_client),
        patch("app.models.db.get_criteria", return_value=[{"name": "Innovation", "weight": 20, "active": True}]),
        patch(
            "app.models.db.get_personas",
            return_value=[{"name": "Steve", "prompt": "Cares about design", "active": True}],
        ),
        patch("app.models.db.get_ai_response_languages", return_value=["English"]),
    ):
        result = provider.analyze_submission(
            model_name="gpt-4o-mini", text_content="print('hello')", previous_evaluations_json=None, is_final=False
        )
        assert result["impact_score"] == 4.2
        assert result["scores"]["Innovation"] == 4.5
        mock_client.chat.completions.create.assert_called_once()


def test_anthropic_provider_analyze_submission(mock_db_settings):
    provider = AnthropicProvider()

    # Mock Anthropic client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {"scores": {"Innovation": 4.0}, "impact_score": 4.0, "judges_feedback": []}
    mock_response.content = [mock_tool_use]
    mock_client.messages.create.return_value = mock_response

    with (
        patch.object(provider, "_get_client", return_value=mock_client),
        patch("app.models.db.get_criteria", return_value=[{"name": "Innovation", "weight": 20, "active": True}]),
        patch(
            "app.models.db.get_personas",
            return_value=[{"name": "Steve", "prompt": "Cares about design", "active": True}],
        ),
        patch("app.models.db.get_ai_response_languages", return_value=["English"]),
    ):
        result = provider.analyze_submission(
            model_name="claude-3-5-sonnet-20241022",
            text_content="print('hello')",
            previous_evaluations_json=None,
            is_final=False,
        )
        assert result["impact_score"] == 4.0
        assert result["scores"]["Innovation"] == 4.0
        mock_client.messages.create.assert_called_once()
