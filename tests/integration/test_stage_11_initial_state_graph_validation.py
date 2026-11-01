"""Stage 11 Integration Tests: Fail-closed initial state invariant validation across Model B, Pipeline, REST, and WebSocket."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.pipeline import PipelineOrchestrator
from core.actions.domain import create_blocks_world_domain
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.world.constraints import NegativeFactInvariant
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


@pytest.fixture
def client():
    return TestClient(create_app())


def test_model_b_enumerator_rejects_invariant_violating_initial_state():
    """Verify Model B enumerator immediately fails closed if initial state violates invariants."""
    from core.domains import registry
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["a", "b", "c"]:
        reg.register_object(b, "block")

    # Contradictory initial state: block 'a' is simultaneously on 'b' and on 'c'
    bad_init_state = SymbolicState([
        Fact("on", ["a", "b"]),
        Fact("on", ["a", "c"]),
        Fact("on_table", ["b"]),
        Fact("on_table", ["c"]),
        Fact("clear", ["a"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on_table", ["a"])]

    problem = SymbolicProblem(
        name="test_bad_init",
        domain_name=domain.domain_id,
        registry=reg,
        initial_state=bad_init_state,
        goal_conditions=goals,
    )

    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=300)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.total_nodes == 0
    assert graph.stats.total_edges == 0
    assert graph.stats.is_complete is False
    assert graph.stats.truncation_reason is not None
    assert graph.stats.truncation_reason.startswith("INITIAL_STATE_INVARIANT_VIOLATION")


def test_model_b_enumerator_rejects_problem_level_invariant_in_initial_state():
    """Verify Model B enumerator fails closed if initial state violates problem-level NegativeFactInvariant."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("glass", "block")

    init_state = SymbolicState([
        Fact("holding", ["glass"]),
    ])
    goals = [Fact("on_table", ["glass"])]

    # Problem specifies invariant: never allow holding(glass)
    inv = NegativeFactInvariant(Fact("holding", ["glass"]))
    problem = SymbolicProblem(
        name="test_inv_init",
        domain_name=domain.name,
        registry=reg,
        initial_state=init_state,
        goal_conditions=goals,
        invariants=[inv],
    )

    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=300)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.total_nodes == 0
    assert graph.stats.total_edges == 0
    assert graph.stats.is_complete is False
    assert "INITIAL_STATE_INVARIANT_VIOLATION" in graph.stats.truncation_reason


def test_pipeline_orchestrator_rejects_invariant_violating_state():
    """Verify PipelineOrchestrator halts with INVARIANT_VIOLATION if proposal initial state is invalid."""
    from core.contracts import FactSchema, TaskProposalSchema
    from interpretation.llm.base import BaseLLMProvider

    class InvariantViolatingMockProvider(BaseLLMProvider):
        def interpret(self, prompt: str, domain):
            return TaskProposalSchema(
                task_id="t_inv_fail",
                domain_id="blocks_world",
                entities={"a": "block"},
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=["a"]),
                    FactSchema(predicate="holding", arguments=["a"]),
                ],
                goal_facts=[FactSchema(predicate="on_table", arguments=["a"])],
            )

    orchestrator = PipelineOrchestrator(llm_provider=InvariantViolatingMockProvider())
    result = orchestrator.run(prompt="Do something with block a.")

    assert result.status in ("INVALID_PROPOSAL", "INVARIANT_VIOLATION")
    assert result.candidate_plan.is_success is False
    assert result.final_verification.is_valid is False
