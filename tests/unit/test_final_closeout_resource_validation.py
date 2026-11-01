"""Unit tests for Stage 11 closeout: Resource budget validation, hard ceilings, and process-wide concurrency control."""

from __future__ import annotations

import math
import pytest
from pydantic import ValidationError

from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.graph.resource_limits import (
    GraphBudgetConfig,
    GraphBudgetLimits,
    GraphConcurrencyManager,
    graph_concurrency_manager,
)


# ==============================================================================
# GraphBudgetConfig Validation Tests
# ==============================================================================

def test_graph_budget_config_rejects_booleans():
    """Verify GraphBudgetConfig strictly rejects boolean values for max_nodes, max_edges, and timeout_seconds."""
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=True)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=False)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges=True)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges=False)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=True)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=False)


def test_graph_budget_config_rejects_fractional_floats_and_strings():
    """Verify GraphBudgetConfig rejects float with fractional part (e.g. 3.7) and string with fractional float ("3.7")."""
    # Float fractional values
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=3.7)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges=12.5)

    # String fractional values
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes="3.7")

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges="12.5")


def test_graph_budget_config_rejects_nan_and_inf():
    """Verify GraphBudgetConfig strictly rejects NaN, +inf, and -inf for all parameters."""
    # timeout_seconds float NaN and Inf
    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=float("nan"))

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=float("inf"))

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=float("-inf"))

    # timeout_seconds string NaN and Inf
    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds="nan")

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds="inf")

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds="-inf")

    # max_nodes / max_edges string NaN and Inf
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes="nan")

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges="inf")


def test_graph_budget_config_rejects_non_positive_and_negative():
    """Verify GraphBudgetConfig rejects <=0 nodes, <0 edges, and <=0 timeout."""
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=0)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=-10)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges=-1)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=0.0)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=-3.5)


def test_graph_budget_config_rejects_above_hard_ceilings():
    """Verify GraphBudgetConfig rejects max_nodes > 5000, max_edges > 20000, timeout > 30.0."""
    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_nodes=5001)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(max_edges=20001)

    with pytest.raises(ValidationError):
        GraphBudgetConfig(timeout_seconds=30.001)

    # Valid boundary limits must succeed
    cfg_max = GraphBudgetConfig(max_nodes=5000, max_edges=20000, timeout_seconds=30.0)
    assert cfg_max.max_nodes == 5000
    assert cfg_max.max_edges == 20000
    assert cfg_max.timeout_seconds == 30.0

    cfg_min = GraphBudgetConfig(max_nodes=1, max_edges=0, timeout_seconds=0.001)
    assert cfg_min.max_nodes == 1
    assert cfg_min.max_edges == 0
    assert cfg_min.timeout_seconds == 0.001


# ==============================================================================
# CompleteReachableGraphEnumerator Constructor Validation Tests
# ==============================================================================

def test_complete_reachable_graph_enumerator_constructor_validation():
    """Verify CompleteReachableGraphEnumerator constructor rejects bool, NaN, inf, and out-of-bound values."""
    # Rejects booleans
    with pytest.raises(ValueError, match="integer|bool"):
        CompleteReachableGraphEnumerator(max_nodes=True)

    with pytest.raises(ValueError, match="integer|bool"):
        CompleteReachableGraphEnumerator(max_edges=False)

    with pytest.raises(ValueError, match="float|number|bool"):
        CompleteReachableGraphEnumerator(timeout_seconds=True)

    # Rejects fractional floats for integer limits
    with pytest.raises(ValueError, match="integer|got float"):
        CompleteReachableGraphEnumerator(max_nodes=3.7)

    with pytest.raises(ValueError, match="integer|got float"):
        CompleteReachableGraphEnumerator(max_edges=10.5)

    # Rejects NaN and inf for timeout_seconds
    with pytest.raises(ValueError, match="finite"):
        CompleteReachableGraphEnumerator(timeout_seconds=float("nan"))

    with pytest.raises(ValueError, match="finite"):
        CompleteReachableGraphEnumerator(timeout_seconds=float("inf"))

    # Rejects out-of-bound values
    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(max_nodes=0)

    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(max_nodes=GraphBudgetLimits.MAX_CORE_NODES + 1)

    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(max_edges=-1)

    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(max_edges=GraphBudgetLimits.MAX_CORE_EDGES + 1)

    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(timeout_seconds=0.0)

    with pytest.raises(ValueError, match="out of bounds"):
        CompleteReachableGraphEnumerator(timeout_seconds=GraphBudgetLimits.MAX_TIMEOUT_SECONDS + 1.0)


# ==============================================================================
# GraphConcurrencyManager Tests
# ==============================================================================

def test_graph_concurrency_manager_bounds_and_release():
    """Verify GraphConcurrencyManager allows 2 concurrent acquisitions, 3rd returns False, and release restores capacity."""
    # Ensure starting from clean 0 active count
    while graph_concurrency_manager.active_count > 0:
        graph_concurrency_manager.release()

    # Slot 1
    slot1 = graph_concurrency_manager.acquire()
    assert slot1 is True
    assert graph_concurrency_manager.active_count == 1

    # Slot 2
    slot2 = graph_concurrency_manager.acquire()
    assert slot2 is True
    assert graph_concurrency_manager.active_count == 2

    # Slot 3: Capacity is 2, so 3rd acquire must return False
    slot3 = graph_concurrency_manager.acquire()
    assert slot3 is False
    assert graph_concurrency_manager.active_count == 2

    # Release slot 1
    graph_concurrency_manager.release()
    assert graph_concurrency_manager.active_count == 1

    # Now an acquisition must succeed
    slot4 = graph_concurrency_manager.acquire()
    assert slot4 is True
    assert graph_concurrency_manager.active_count == 2

    # Clean up
    graph_concurrency_manager.release()
    graph_concurrency_manager.release()
    assert graph_concurrency_manager.active_count == 0


def test_graph_concurrency_manager_works_safely_across_exceptions():
    """Verify GraphConcurrencyManager works safely and does not leak slots across exceptions."""
    while graph_concurrency_manager.active_count > 0:
        graph_concurrency_manager.release()

    initial_count = graph_concurrency_manager.active_count

    try:
        acquired = graph_concurrency_manager.acquire()
        assert acquired is True
        assert graph_concurrency_manager.active_count == initial_count + 1
        raise RuntimeError("Simulated processing error inside enumeration")
    except RuntimeError:
        pass
    finally:
        graph_concurrency_manager.release()

    assert graph_concurrency_manager.active_count == initial_count

    # Verify context manager behavior if implemented
    try:
        with graph_concurrency_manager as acq:
            if acq:
                raise ValueError("Error inside context block")
    except ValueError:
        pass

    assert graph_concurrency_manager.active_count == initial_count
