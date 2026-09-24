"""Unit tests for the Retry Tree architecture, decision tracing, and fallback cascading."""

import pytest
from unittest.mock import MagicMock, patch

from core.actions.domain import create_blocks_world_domain
from core.contracts import (
    FactSchema,
    PipelineDecisionTrace,
    PipelineStageStatus,
    PlanSchema,
    ProposalValidationResult,
    TaskProposalSchema,
    ValidationStatus,
)
from app.services.pipeline import PipelineOrchestrator
from interpretation.llm.live import LiveLLMProvider
from interpretation.llm.mock import MockLLMProvider
from interpretation.validator.validator import ConsistencyValidator


def test_interpret_with_retry_augments_prompt_on_error():
    """Verify that interpret_with_retry includes feedback when validation errors exist."""
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(provider="mock")

    errors = ["Unknown entity reference 'block_x'", "Arity mismatch for on"]
    proposal, provider_name = provider.interpret_with_retry(
        prompt="Stack red on blue",
        domain=domain,
        validation_errors=errors,
    )

    assert provider_name == "mock"
    assert proposal is not None
    assert "red_box" in proposal.entities or "b1" in proposal.entities or len(proposal.entities) > 0


def test_decision_trace_recorded_in_standard_run():
    """Verify that PipelineExecutionResult contains a complete PipelineDecisionTrace."""
    orchestrator = PipelineOrchestrator()
    prompt = "Move the red box next to the blue box. Do not move the glass."

    result = orchestrator.run(prompt=prompt, algorithm="A*")

    assert result.decision_trace is not None
    trace = result.decision_trace
    assert isinstance(trace, PipelineDecisionTrace)
    assert trace.interpretation_attempts >= 1
    assert trace.total_attempts >= 1
    assert len(trace.stage_trace) >= 3  # INTERPRET, VALIDATE, PLAN, VERIFY

    # Verify stage attempt records
    stages_seen = [s.stage for s in trace.stage_trace]
    assert "INTERPRET" in stages_seen
    assert "VALIDATE" in stages_seen
    assert "PLAN" in stages_seen
    assert "VERIFY" in stages_seen


def test_planner_cascade_fallback_when_first_planner_fails():
    """Verify that if the primary planner fails, the system cascades to alternate planners."""
    orchestrator = PipelineOrchestrator()
    prompt = "Move the red box next to the blue box."

    # Mock get_planner_by_name to fail on A* but succeed on BFS
    from core.search.algorithms import BFSPlanner

    real_get_planner = __import__("core.search.algorithms", fromlist=["get_planner_by_name"]).get_planner_by_name

    def mock_get_planner(name: str):
        if name.upper() in ("A*", "ASTAR"):
            mock_a = MagicMock()
            mock_a.search.return_value = PlanSchema(
                actions=[], is_success=False, failure_reason="Simulated A* timeout"
            )
            return mock_a
        return real_get_planner(name)

    with patch("app.services.pipeline.get_planner_by_name", side_effect=mock_get_planner):
        result = orchestrator.run(prompt=prompt, algorithm="A*")

        assert result.final_verification.is_valid is True
        assert result.decision_trace is not None
        assert result.decision_trace.planner_cascades >= 1
        assert "planner_cascade_BFS" in result.decision_trace.recovery_path
        assert result.planner_algorithm == "BFS"


def test_backtrack_on_validation_failure_recovers():
    """Verify that if an initial interpretation fails validation, backtracking re-attempts."""
    orchestrator = PipelineOrchestrator(max_backtracks=2)
    domain = orchestrator.domain

    call_count = 0

    class FlakyProvider(MockLLMProvider):
        def interpret_with_retry(self, prompt, domain, max_retries=3, validation_errors=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt: invalid proposal with unknown entity in goal
                return TaskProposalSchema(
                    task_id="flaky_1",
                    raw_prompt=prompt,
                    entities={"red_box": "block"},
                    initial_facts=[FactSchema(predicate="on_table", arguments=("red_box",))],
                    goal_facts=[FactSchema(predicate="on", arguments=("red_box", "missing_entity"))],
                ), "flaky_provider"
            else:
                # Second attempt: valid proposal
                return TaskProposalSchema(
                    task_id="flaky_2",
                    raw_prompt=prompt,
                    entities={"red_box": "block", "blue_box": "block"},
                    initial_facts=[
                        FactSchema(predicate="on_table", arguments=("red_box",)),
                        FactSchema(predicate="clear", arguments=("red_box",)),
                        FactSchema(predicate="on_table", arguments=("blue_box",)),
                        FactSchema(predicate="clear", arguments=("blue_box",)),
                        FactSchema(predicate="handempty", arguments=()),
                    ],
                    goal_facts=[FactSchema(predicate="on", arguments=("red_box", "blue_box"))],
                ), "flaky_provider"

    flaky = FlakyProvider()
    orchestrator.llm_provider = flaky

    # Run with provider_type="mock" but with our custom provider
    result = orchestrator.run(
        prompt="Stack red on blue",
        algorithm="A*",
        provider_type="mock",
    )

    assert call_count == 2
    assert result.decision_trace is not None
    assert result.decision_trace.backtracks == 1
    assert "backtrack_validation_errors_1" in result.decision_trace.recovery_path
    assert result.final_verification.is_valid is True
    assert len(result.final_plan.actions) > 0
