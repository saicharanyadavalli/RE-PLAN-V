"""Unit tests for Stage 0: contracts, configuration, and logging."""

from core.contracts import (
    FactSchema,
    SymbolicStateSchema,
    GroundActionSchema,
    PlanSchema,
    VerificationResultSchema,
    ViolationType,
    CounterexampleSchema,
    FaultClass,
    FaultAttributionSchema,
    RepairType,
    RepairConstraintSchema,
    ReplanningResultSchema,
    TaskProposalSchema,
    ProposalValidationResult,
    ValidationStatus,
    WorldDeltaSchema,
    BenchmarkInstanceSchema,
    EvaluationMetricsSchema,
)
from core.logger import get_logger
from configs.default import default_config


def test_fact_schema_immutability_and_string():
    fact = FactSchema(predicate="on", arguments=("boxA", "boxB"))
    assert fact.predicate == "on"
    assert fact.arguments == ("boxA", "boxB")
    assert not fact.is_negated
    assert fact.to_string() == "on(boxA, boxB)"
    assert str(fact) == "on(boxA, boxB)"

    neg_fact = FactSchema(predicate="clear", arguments=("boxA",), is_negated=True)
    assert neg_fact.to_string() == "not(clear(boxA))"


def test_symbolic_state_schema():
    f1 = FactSchema(predicate="on", arguments=("boxA", "table"))
    f2 = FactSchema(predicate="clear", arguments=("boxA",))
    state = SymbolicStateSchema(facts=(f1, f2), objects={"boxA": "box", "table": "surface"})
    
    assert state.contains_fact(f1)
    assert state.contains_fact(f2)
    # Negated lookup
    f_neg = FactSchema(predicate="on", arguments=("boxB", "table"), is_negated=True)
    assert state.contains_fact(f_neg)


def test_ground_action_and_plan_schema():
    action = GroundActionSchema(name="pick_up", arguments=("boxA",), cost=1.0)
    assert str(action) == "pick_up(boxA)"
    
    plan = PlanSchema(actions=[action], algorithm="A*", total_cost=1.0)
    assert len(plan.actions) == 1
    assert plan.algorithm == "A*"
    assert plan.is_success


def test_verification_result_schema():
    res = VerificationResultSchema(
        is_valid=False,
        failed_step_index=0,
        violation_type=ViolationType.PRECONDITION_UNMET,
        explanation="Precondition clear(boxA) failed."
    )
    assert not res.is_valid
    assert res.failed_step_index == 0
    assert res.violation_type == ViolationType.PRECONDITION_UNMET


def test_counterexample_and_fault_attribution():
    f = FactSchema(predicate="clear", arguments=("boxA",))
    act = GroundActionSchema(name="pick_up", arguments=("boxA",))
    st = SymbolicStateSchema(facts=(), objects={"boxA": "box"})
    
    cex = CounterexampleSchema(
        counterexample_id="CEX-1",
        action_index=0,
        offending_action=act,
        violated_condition=f,
        expected_truth=True,
        actual_truth=False,
        failure_category=ViolationType.PRECONDITION_UNMET,
        affected_entities=["boxA"],
        state_snapshot=st,
        explanation="Action requires clear(boxA) which was false."
    )
    assert cex.counterexample_id == "CEX-1"
    assert cex.affected_entities == ["boxA"]

    attrib = FaultAttributionSchema(
        fault_class=FaultClass.PLANNING_ERROR,
        confidence=0.95,
        affected_stage="Search/Planner",
        evidence=["Planner selected pick_up without clearing first."]
    )
    assert attrib.fault_class == FaultClass.PLANNING_ERROR
    assert attrib.confidence == 0.95


def test_repair_and_replanning_schema():
    repair = RepairConstraintSchema(
        repair_id="REP-1",
        repair_type=RepairType.FORBID_GROUND_ACTION,
        description="Forbid pick_up(boxA) at step 0",
        source_counterexample_id="CEX-1",
        forbidden_action=GroundActionSchema(name="pick_up", arguments=("boxA",))
    )
    assert repair.repair_type == RepairType.FORBID_GROUND_ACTION
    
    orig_plan = PlanSchema(actions=[GroundActionSchema(name="pick_up", arguments=("boxA",))])
    replan = ReplanningResultSchema(
        success=True,
        original_plan=orig_plan,
        iterations=1,
        repairs_applied=[repair],
        status="VERIFIED"
    )
    assert replan.success
    assert replan.iterations == 1


def test_logger_and_config():
    logger = get_logger("test_replan", json_mode=False)
    assert logger.name == "test_replan"
    assert default_config.planning.default_algorithm == "A*"


def test_contract_serialization_round_trips():
    import json
    from core.graph.models import GraphNode, GraphEdge, GraphStats, ReachableStateGraph

    # FactSchema round trip
    f = FactSchema(predicate="holding", arguments=("b1",), is_negated=False)
    f_json = f.model_dump_json()
    f_restored = FactSchema.model_validate_json(f_json)
    assert f == f_restored

    # SymbolicStateSchema round trip
    st = SymbolicStateSchema(facts=(f,), objects={"b1": "block"}, step_index=2)
    st_json = st.model_dump_json()
    st_restored = SymbolicStateSchema.model_validate_json(st_json)
    assert st == st_restored

    # PlanSchema round trip
    act = GroundActionSchema(name="pick_up", arguments=("b1",), cost=1.0)
    plan = PlanSchema(actions=[act], algorithm="A*", total_cost=1.0, is_success=True)
    plan_json = plan.model_dump_json()
    plan_restored = PlanSchema.model_validate_json(plan_json)
    assert plan == plan_restored

    # Graph models round trip
    node = GraphNode(node_id="n1", facts=["on_table(b1)"], depth=0, is_initial=True, is_goal=False, partially_expanded=False)
    edge = GraphEdge(edge_id="e1", source_id="n1", target_id="n2", action_name="pick_up", action_args=["b1"], action_label="pick_up(b1)", cost=1.0)
    stats = GraphStats(total_nodes=1, total_edges=1, is_complete=True)
    graph = ReachableStateGraph(graph_id="g1", domain_id="blocks_world", problem_name="test_p", nodes={"n1": node}, edges=[edge], stats=stats)
    graph_json = graph.model_dump_json()
    graph_restored = ReachableStateGraph.model_validate_json(graph_json)
    assert graph_restored.graph_id == "g1"
    assert "n1" in graph_restored.nodes
    assert len(graph_restored.edges) == 1
    assert graph_restored.edges[0].action_label == "pick_up(b1)"
