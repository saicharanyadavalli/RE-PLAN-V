"""Unit tests for LM Studio Local Model and Gemini API integrations."""

import json
import pytest
from unittest.mock import MagicMock, patch
import httpx

from core.actions.domain import create_blocks_world_domain
from core.contracts import TaskProposalSchema
from interpretation.llm.live import LiveLLMProvider, SYSTEM_FORMALIZER_PROMPT
from app.services.pipeline import PipelineOrchestrator


SAMPLE_LLM_OUTPUT = json.dumps({
    "task_id": "test_lm_task",
    "raw_prompt": "Move the red box on the blue box.",
    "entities": {"red_box": "block", "blue_box": "block"},
    "initial_facts": [
        {"predicate": "on_table", "arguments": ["red_box"]},
        {"predicate": "on_table", "arguments": ["blue_box"]},
        {"predicate": "clear", "arguments": ["red_box"]},
        {"predicate": "clear", "arguments": ["blue_box"]},
        {"predicate": "handempty", "arguments": []}
    ],
    "goal_facts": [
        {"predicate": "on", "arguments": ["red_box", "blue_box"]}
    ],
    "negative_constraints": [],
    "invariants": [],
    "confidence": 0.98
})


def test_lm_studio_native_v1_api():
    """Tests LM Studio Native v1 REST API (/api/v1/chat)."""
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(provider="lmstudio", endpoint="http://127.0.0.1:1234")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": SAMPLE_LLM_OUTPUT
    }

    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.json.return_value = {"data": [{"id": "meta-llama-3.1-8b"}]}

    with patch("httpx.Client.get", return_value=mock_get):
        with patch("httpx.Client.post", return_value=mock_resp):
            proposal = provider.interpret("Move the red box on the blue box.", domain)
            assert isinstance(proposal, TaskProposalSchema)
            assert "red_box" in proposal.entities
            assert "blue_box" in proposal.entities
            assert len(proposal.goal_facts) == 1
            assert proposal.goal_facts[0].predicate == "on"
            assert proposal.goal_facts[0].arguments == ("red_box", "blue_box")
            assert proposal.confidence == 0.98


def test_lm_studio_openai_compatible_endpoint():
    """Tests LM Studio OpenAI-compatible endpoint (/v1/chat/completions) with model detection."""
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(provider="lmstudio", endpoint="http://127.0.0.1:1234")

    # Native fails, OpenAI compatible succeeds
    def mock_post(url, *args, **kwargs):
        resp = MagicMock()
        if "/api/v1/chat" in url:
            resp.status_code = 404
            return resp
        elif "/v1/chat/completions" in url:
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": SAMPLE_LLM_OUTPUT}}]
            }
            return resp
        resp.status_code = 500
        return resp

    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200
    mock_models_resp.json.return_value = {
        "data": [{"id": "meta-llama-3.1-8b-instruct"}]
    }

    with patch("httpx.Client.post", side_effect=mock_post):
        with patch("httpx.Client.get", return_value=mock_models_resp):
            proposal = provider.interpret("Move the red box on the blue box.", domain)
            assert isinstance(proposal, TaskProposalSchema)
            assert "red_box" in proposal.entities
            assert proposal.goal_facts[0].predicate == "on"


def test_lm_studio_offline_fallback():
    """Ensures fallback to deterministic zero-API mock when LM Studio is unreachable."""
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(provider="lmstudio", endpoint="http://127.0.0.1:1234")

    # Simulate connection error
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        proposal = provider.interpret("Move the red box next to the blue box. Do not move the glass.", domain)
        assert isinstance(proposal, TaskProposalSchema)
        # Should gracefully return mock proposal
        assert "red_box" in proposal.entities
        assert "blue_box" in proposal.entities


def test_gemini_api_call():
    """Tests Google Gemini API integration."""
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(provider="gemini", api_key="test_dummy_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": SAMPLE_LLM_OUTPUT}]
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        proposal = provider.interpret("Move the red box on the blue box.", domain)
        assert isinstance(proposal, TaskProposalSchema)
        assert proposal.confidence == 0.98
        assert proposal.goal_facts[0].arguments == ("red_box", "blue_box")


def test_pipeline_orchestrator_with_lm_studio():
    """Tests end-to-end pipeline execution using LM Studio provider."""
    orchestrator = PipelineOrchestrator()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": SAMPLE_LLM_OUTPUT
    }

    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.json.return_value = {"data": [{"id": "meta-llama-3.1-8b"}]}

    with patch("httpx.Client.get", return_value=mock_get):
        with patch("httpx.Client.post", return_value=mock_resp):
            result = orchestrator.run(
                prompt="Move the red box on the blue box.",
                algorithm="A*",
                provider_type="lmstudio"
            )
            assert result.validation.is_valid is True
            assert len(result.candidate_plan.actions) > 0
            assert result.initial_verification.is_valid is True
            assert result.final_verification.is_valid is True
