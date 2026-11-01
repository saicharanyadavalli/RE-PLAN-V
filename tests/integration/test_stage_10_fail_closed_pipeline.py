"""Integration tests for Stage 10 DEF-10.1: Fail-closed pipeline and routing.

Verifies:
1. Scenario 1: Unrelated task ("book a flight from JFK to LHR") with domain_id="auto"
   fails closed without defaulting to Blocks World.
2. Scenario 2: Unrelated query ("What is the weather in Tokyo?") with domain_id="auto"
   fails closed without defaulting to Blocks World.
3. Scenario 3: Ambiguous or underspecified command returns clarification request
   without defaulting to Blocks World.
4. Scenario 4: Explicit invalid domain:
   - PipelineOrchestrator(domain_id="nonexistent") raises ValueError.
   - PipelineOrchestrator.run(domain_id="nonexistent") returns INVALID_DOMAIN.
   - POST /api/pipeline/run with nonexistent domain returns 404.
   - POST /api/llm/formalize with nonexistent domain returns 404.
   - WebSocket with nonexistent domain emits ERROR.
5. MockLLMProvider fails closed on unsupported prompts for any domain.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.pipeline import PipelineOrchestrator
from core.actions.domain import create_blocks_world_domain
from core.domains import registry
from interpretation.llm.mock import MockLLMProvider
from interpretation.router import DomainRouter, RoutingOutcome


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()


def test_scenario_1_unsupported_flight_fails_closed(orchestrator: PipelineOrchestrator):
    prompt = "book a flight from JFK to LHR"
    router = DomainRouter(registry=registry)
    routing = router.route(prompt)
    assert routing.outcome == RoutingOutcome.UNSUPPORTED
    assert routing.selected_domain_id is None

    res = orchestrator.run(prompt=prompt, domain_id="auto")
    assert res.is_verified is False
    assert res.status == "UNSUPPORTED"
    assert res.domain_id is None
    assert len(res.candidate_plan.actions) == 0
    assert "unsupported" in res.validation.errors[0].lower() or "unsupported" in res.candidate_plan.failure_reason.lower()
    # Confirm no blocks world entities or actions were fabricated
    assert "b1" not in res.interpretation.entities
    assert "b2" not in res.interpretation.entities


def test_scenario_2_unsupported_weather_fails_closed(orchestrator: PipelineOrchestrator):
    prompt = "What is the weather in Tokyo?"
    router = DomainRouter(registry=registry)
    routing = router.route(prompt)
    assert routing.outcome == RoutingOutcome.UNSUPPORTED

    res = orchestrator.run(prompt=prompt, domain_id="auto")
    assert res.is_verified is False
    assert res.status == "UNSUPPORTED"
    assert len(res.candidate_plan.actions) == 0


def test_scenario_3_underspecified_prompt_fails_closed(orchestrator: PipelineOrchestrator):
    prompt = "Deliver the package to the destination."
    router = DomainRouter(registry=registry)
    routing = router.route(prompt)
    assert routing.outcome == RoutingOutcome.NEEDS_CLARIFICATION
    assert routing.clarification_question is not None

    res = orchestrator.run(prompt=prompt, domain_id="auto")
    assert res.is_verified is False
    assert res.status == "NEEDS_CLARIFICATION"
    assert len(res.candidate_plan.actions) == 0


def test_scenario_4_unregistered_domain_constructor():
    with pytest.raises(ValueError, match="Unregistered domain 'nonexistent_domain'"):
        PipelineOrchestrator(domain_id="nonexistent_domain")


def test_scenario_4_unregistered_domain_run(orchestrator: PipelineOrchestrator):
    res = orchestrator.run(prompt="stack b1 on b2", domain_id="nonexistent_domain")
    assert res.is_verified is False
    assert res.status == "INVALID_DOMAIN"
    assert res.domain_id == "nonexistent_domain"
    assert len(res.candidate_plan.actions) == 0


def test_scenario_4_api_pipeline_run_404(client: TestClient):
    resp = client.post("/api/pipeline/run", json={
        "prompt": "stack b1 on b2",
        "domain_id": "nonexistent_domain",
    })
    assert resp.status_code == 404
    assert "not registered" in resp.json()["detail"]


def test_scenario_4_api_formalize_404(client: TestClient):
    resp = client.post("/api/llm/formalize", json={
        "prompt": "stack b1 on b2",
        "domain_id": "nonexistent_domain",
        "provider": "mock",
    })
    assert resp.status_code == 404
    assert "not registered" in resp.json()["detail"]


def test_scenario_4_websocket_unregistered_domain(client: TestClient):
    with client.websocket_connect("/ws/pipeline") as ws:
        ws.send_json({
            "prompt": "move b1 to b2",
            "domain_id": "nonexistent_domain",
            "step_delay": 0.0,
        })
        msg1 = ws.receive_json()
        assert msg1["stage"] == "PIPELINE_STARTED"
        msg2 = ws.receive_json()
        assert msg2["stage"] == "ERROR"
        assert "not registered" in msg2["message"]


def test_scenario_4_websocket_unsupported_prompt(client: TestClient):
    with client.websocket_connect("/ws/pipeline") as ws:
        ws.send_json({
            "prompt": "book a flight from JFK to LHR",
            "domain_id": "auto",
            "step_delay": 0.0,
        })
        msg1 = ws.receive_json()
        assert msg1["stage"] == "PIPELINE_STARTED"
        msg2 = ws.receive_json()
        assert msg2["stage"] == "TASK_UNSUPPORTED"


def test_scenario_4_websocket_clarification_prompt(client: TestClient):
    with client.websocket_connect("/ws/pipeline") as ws:
        ws.send_json({
            "prompt": "Deliver the package to the destination.",
            "domain_id": "auto",
            "step_delay": 0.0,
        })
        msg1 = ws.receive_json()
        assert msg1["stage"] == "PIPELINE_STARTED"
        msg2 = ws.receive_json()
        assert msg2["stage"] == "CLARIFICATION_REQUIRED"


def test_mock_llm_provider_fails_closed_on_unsupported_prompts():
    provider = MockLLMProvider()
    bw_domain = create_blocks_world_domain()
    # Unrelated prompt passed directly to Blocks World
    proposal = provider.interpret("book flight ticket to Rome", domain=bw_domain)
    assert proposal.confidence == 0.0
    assert len(proposal.entities) == 0
    assert len(proposal.goal_facts) == 0

    # Non-blocks domain with unrelated prompt
    grid_domain = registry.get("grid_world")
    proposal_grid = provider.interpret("book flight ticket to Rome", domain=grid_domain)
    assert proposal_grid.confidence == 0.0
    assert len(proposal_grid.entities) == 0
    assert len(proposal_grid.goal_facts) == 0
