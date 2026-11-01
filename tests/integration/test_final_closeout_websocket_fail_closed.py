"""Integration tests for Stage 11 closeout: WebSocket fail-closed behavior on initial state invariant violations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.contracts import FactSchema, TaskProposalSchema
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.search.algorithms import AStarPlanner, BasePlanner


@pytest.fixture
def client():
    return TestClient(create_app())


def test_websocket_fail_closed_on_problem_invariant_violation(client: TestClient):
    """Test WebSocket handler with initial state violating a problem invariant (e.g. negative fact constraint):
    
    - Assert INITIAL_STATE_INVARIANT_VIOLATION event is emitted.
    - Assert CompleteReachableGraphEnumerator.enumerate_graph is NEVER called (call_count == 0).
    - Assert planner.search is NEVER called (call_count == 0).
    - Assert handler returns immediately and does not emit GRAPH_ENUMERATION_STARTED or PLANNING_STARTED.
    """
    # Proposal violating problem invariant: glass cannot be held, but initial state has holding(glass)
    inv_violating_proposal = TaskProposalSchema(
        task_id="t_inv_problem",
        domain_id="blocks_world",
        entities={"glass": "block"},
        initial_facts=[
            FactSchema(predicate="holding", arguments=["glass"]),
        ],
        goal_facts=[FactSchema(predicate="on_table", arguments=["glass"])],
        negative_constraints=[
            FactSchema(predicate="holding", arguments=["glass"], is_negated=True),
        ],
    )

    with patch("interpretation.llm.mock.MockLLMProvider.interpret", return_value=inv_violating_proposal), \
         patch.object(CompleteReachableGraphEnumerator, "enumerate_graph", autospec=True) as mock_enumerate, \
         patch.object(AStarPlanner, "search", autospec=True) as mock_astar_search, \
         patch.object(BasePlanner, "search", autospec=True) as mock_base_search:

        received_events = []
        with client.websocket_connect("/ws/pipeline") as ws:
            ws.send_json({
                "prompt": "Stack glass on table",
                "domain_id": "blocks_world",
                "enumerate_graph": True,
                "step_delay": 0.0,
            })

            # Read events emitted until terminal event or disconnect
            for _ in range(10):
                try:
                    event = ws.receive_json()
                    received_events.append(event)
                    if event.get("stage") in (
                        "INITIAL_STATE_INVARIANT_VIOLATION",
                        "GRAPH_ENUMERATION_COMPLETED",
                        "PIPELINE_FINISHED",
                        "ERROR",
                    ):
                        break
                except Exception:
                    break

        stages = [e.get("stage") for e in received_events]

        # 1. Assert INITIAL_STATE_INVARIANT_VIOLATION event is emitted
        assert "INITIAL_STATE_INVARIANT_VIOLATION" in stages, f"Stages received: {stages}"

        # 2. Assert enumerate_graph was NEVER called
        assert mock_enumerate.call_count == 0, (
            f"enumerate_graph should have 0 calls, but was called {mock_enumerate.call_count} times"
        )

        # 3. Assert planner.search was NEVER called
        assert mock_astar_search.call_count == 0, (
            f"AStarPlanner.search should have 0 calls, but was called {mock_astar_search.call_count} times"
        )
        assert mock_base_search.call_count == 0, (
            f"BasePlanner.search should have 0 calls, but was called {mock_base_search.call_count} times"
        )

        # 4. Assert handler did NOT emit graph enumeration or planning started events
        assert "GRAPH_ENUMERATION_STARTED" not in stages, "GRAPH_ENUMERATION_STARTED must not be emitted on invariant violation"
        assert "PLANNER_SEARCH_STARTED" not in stages, "PLANNER_SEARCH_STARTED must not be emitted on invariant violation"
        assert "PLANNING_STARTED" not in stages, "PLANNING_STARTED must not be emitted on invariant violation"


def test_websocket_fail_closed_on_domain_invariant_violation(client: TestClient):
    """Test WebSocket handler with initial state violating a domain invariant:
    
    - Assert INITIAL_STATE_INVARIANT_VIOLATION event is emitted.
    - Assert CompleteReachableGraphEnumerator.enumerate_graph is NEVER called (call_count == 0).
    - Assert planner.search is NEVER called (call_count == 0).
    - Assert handler returns immediately and does not emit GRAPH_ENUMERATION_STARTED or PLANNING_STARTED.
    """
    valid_syntax_proposal = TaskProposalSchema(
        task_id="t_inv_domain",
        domain_id="blocks_world",
        entities={"b1": "block", "b2": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=["b1"]),
            FactSchema(predicate="clear", arguments=["b1"]),
            FactSchema(predicate="on_table", arguments=["b2"]),
            FactSchema(predicate="clear", arguments=["b2"]),
            FactSchema(predicate="handempty", arguments=[]),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=["b1", "b2"])],
    )

    # Force domain.check_invariants on initial state to fail
    with patch("interpretation.llm.mock.MockLLMProvider.interpret", return_value=valid_syntax_proposal), \
         patch("core.domains.blocks_world.BlocksWorldDomain.check_invariants", return_value=(False, "Domain invariant check failed")), \
         patch.object(CompleteReachableGraphEnumerator, "enumerate_graph", autospec=True) as mock_enumerate, \
         patch.object(AStarPlanner, "search", autospec=True) as mock_astar_search:

        received_events = []
        with client.websocket_connect("/ws/pipeline") as ws:
            ws.send_json({
                "prompt": "Stack b1 on b2",
                "domain_id": "blocks_world",
                "enumerate_graph": True,
                "step_delay": 0.0,
            })

            for _ in range(10):
                try:
                    event = ws.receive_json()
                    received_events.append(event)
                    if event.get("stage") in (
                        "INITIAL_STATE_INVARIANT_VIOLATION",
                        "GRAPH_ENUMERATION_COMPLETED",
                        "PIPELINE_FINISHED",
                        "ERROR",
                    ):
                        break
                except Exception:
                    break

        stages = [e.get("stage") for e in received_events]

        assert "INITIAL_STATE_INVARIANT_VIOLATION" in stages, f"Stages received: {stages}"
        assert mock_enumerate.call_count == 0
        assert mock_astar_search.call_count == 0
        assert "GRAPH_ENUMERATION_STARTED" not in stages
        assert "PLANNER_SEARCH_STARTED" not in stages
        assert "PLANNING_STARTED" not in stages
