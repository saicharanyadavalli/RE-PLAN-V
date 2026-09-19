"""Unit tests for Stage 9: Neural Interpretation & Untrusted Schema Validation."""

import pytest
from core.actions.domain import create_blocks_world_domain
from core.contracts import FactSchema, TaskProposalSchema, ValidationStatus
from interpretation.llm.live import LiveLLMProvider
from interpretation.llm.mock import MockLLMProvider
from interpretation.validator.validator import ConsistencyValidator


def test_mock_llm_provider_dod_prompt():
    domain = create_blocks_world_domain()
    provider = MockLLMProvider()

    prompt = "Move the red box next to the blue box. Do not move the glass."
    proposal = provider.interpret(prompt, domain)

    assert "red_box" in proposal.entities
    assert "blue_box" in proposal.entities
    assert "glass" in proposal.entities
    assert len(proposal.negative_constraints) == 1
    assert proposal.negative_constraints[0].arguments == ("glass",)


def test_mock_llm_provider_stack_prompt():
    domain = create_blocks_world_domain()
    provider = MockLLMProvider()

    prompt = "Stack b1 on b2"
    proposal = provider.interpret(prompt, domain)

    assert proposal.entities == {"b1": "block", "b2": "block"}
    assert len(proposal.goal_facts) == 1
    assert proposal.goal_facts[0].predicate == "on"
    assert proposal.goal_facts[0].arguments == ("b1", "b2")


def test_consistency_validator_valid_proposal():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="valid_task",
        raw_prompt="stack b1 on b2",
        entities={"b1": "block", "b2": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=("b1",)),
            FactSchema(predicate="clear", arguments=("b1",)),
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b2",)),
            FactSchema(predicate="handempty", arguments=()),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=("b1", "b2"))],
        negative_constraints=[],
    )

    res = validator.validate(proposal, domain)
    assert res.is_valid
    assert res.status == ValidationStatus.VALID

    # Convert to problem
    problem = validator.convert_to_problem(proposal, domain)
    assert problem.name == "neural_task"
    assert problem.domain_name == "blocks_world"
    assert len(problem.goal_conditions) == 1


def test_consistency_validator_unknown_entity():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="bad_entity",
        raw_prompt="stack b1 on b2",
        entities={"b1": "block"},  # b2 omitted from entities
        initial_facts=[FactSchema(predicate="on_table", arguments=("b1",))],
        goal_facts=[FactSchema(predicate="on", arguments=("b1", "b2"))],
    )

    res = validator.validate(proposal, domain)
    assert not res.is_valid
    assert res.status == ValidationStatus.UNKNOWN_ENTITY
    assert "Unknown entity" in res.errors[0]


def test_consistency_validator_arity_mismatch():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="bad_arity",
        raw_prompt="invalid arity",
        entities={"b1": "block", "b2": "block"},
        initial_facts=[FactSchema(predicate="on", arguments=("b1",))],  # on expects 2 args
        goal_facts=[],
    )

    res = validator.validate(proposal, domain)
    assert not res.is_valid
    assert res.status == ValidationStatus.ARITY_MISMATCH
    assert "Arity mismatch" in res.errors[0]


def test_consistency_validator_unsupported_predicate():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="bad_pred",
        raw_prompt="fly to moon",
        entities={"b1": "block"},
        initial_facts=[FactSchema(predicate="teleported_to", arguments=("b1",))],
        goal_facts=[],
    )

    res = validator.validate(proposal, domain)
    assert not res.is_valid
    assert res.status == ValidationStatus.UNSUPPORTED_OPERATOR


def test_consistency_validator_direct_contradiction():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="contradictory",
        raw_prompt="contradictory",
        entities={"b1": "block"},
        initial_facts=[
            FactSchema(predicate="clear", arguments=("b1",), is_negated=False),
            FactSchema(predicate="clear", arguments=("b1",), is_negated=True),
        ],
        goal_facts=[],
    )

    res = validator.validate(proposal, domain)
    assert not res.is_valid
    assert res.status == ValidationStatus.CONTRADICTION
    assert "Contradiction in initial state" in res.errors[0]


def test_consistency_validator_mutex_contradiction():
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="mutex_fail",
        raw_prompt="mutex fail",
        entities={"b1": "block"},
        initial_facts=[
            FactSchema(predicate="holding", arguments=("b1",)),
            FactSchema(predicate="handempty", arguments=()),
        ],
        goal_facts=[],
    )

    res = validator.validate(proposal, domain)
    assert not res.is_valid
    assert "Contradictory state" in res.errors[0]


def test_live_llm_provider_fallback():
    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(api_key=None)  # No key -> fallback to mock
    proposal = provider.interpret("stack b1 on b2", domain)
    assert proposal.entities == {"b1": "block", "b2": "block"}


def test_task_proposal_schema_conversion():
    from interpretation.schemas.task_spec import TaskProposal

    tp = TaskProposal(
        task_id="t1",
        raw_prompt="stack b1 on b2",
        entities={"b1": "block", "b2": "block"},
        initial_facts=[FactSchema(predicate="clear", arguments=("b1",))],
        goal_facts=[FactSchema(predicate="on", arguments=("b1", "b2"))],
        negative_constraints=[FactSchema(predicate="holding", arguments=("b2",))],
        invariants=[],
        confidence=0.95,
    )
    contract = tp.to_contract_schema()
    assert contract.task_id == "t1"
    assert contract.entities["b1"] == "block"
    assert contract.confidence == 0.95
    assert len(contract.initial_facts) == 1
    assert len(contract.goal_facts) == 1

