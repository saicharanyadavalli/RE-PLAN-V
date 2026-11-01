"""Automated Evaluation Suite for the 145-Prompt Multi-Domain NLP Corpus."""

import pytest
from core.contracts import TaskProposalSchema, ValidationStatus
from core.domains import registry
from interpretation.llm.mock import MockLLMProvider
from interpretation.router import DomainRouter, RoutingOutcome
from interpretation.validator.validator import ConsistencyValidator
from tests.fixtures.nlp_corpus import (
    BLOCKS_WORLD_CORPUS,
    GRID_WORLD_CORPUS,
    HOUSEHOLD_CORPUS,
    WAREHOUSE_CORPUS,
    SCHEDULING_CORPUS,
    SOFTWARE_WORKFLOW_CORPUS,
    CLARIFICATION_CORPUS,
    UNSUPPORTED_CORPUS,
    INVALID_CORPUS,
)


@pytest.fixture
def router() -> DomainRouter:
    return DomainRouter(registry=registry)


@pytest.fixture
def validator() -> ConsistencyValidator:
    return ConsistencyValidator()


@pytest.mark.parametrize("case", BLOCKS_WORLD_CORPUS, ids=lambda c: c.prompt_id)
def test_blocks_world_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    if case.expected_entities:
        for ent in case.expected_entities:
            assert ent in res.entities

    # Validate symbolic consistency
    domain = registry.get("blocks_world")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", GRID_WORLD_CORPUS, ids=lambda c: c.prompt_id)
def test_grid_world_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    domain = registry.get("grid_world")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", HOUSEHOLD_CORPUS, ids=lambda c: c.prompt_id)
def test_household_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    domain = registry.get("household_robotics")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", WAREHOUSE_CORPUS, ids=lambda c: c.prompt_id)
def test_warehouse_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    domain = registry.get("warehouse")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", SCHEDULING_CORPUS, ids=lambda c: c.prompt_id)
def test_scheduling_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    domain = registry.get("scheduling")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", SOFTWARE_WORKFLOW_CORPUS, ids=lambda c: c.prompt_id)
def test_software_workflow_corpus(router: DomainRouter, validator: ConsistencyValidator, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id == case.expected_domain

    if case.expected_negative_pred:
        assert len(res.negative_constraints) >= 1
        assert any(nc.predicate == case.expected_negative_pred for nc in res.negative_constraints)

    domain = registry.get("software_workflow")
    proposal = TaskProposalSchema(
        task_id=f"corpus_{case.prompt_id}",
        raw_prompt=case.prompt,
        entities=res.entities,
        initial_facts=res.initial_facts,
        goal_facts=res.goal_facts,
        negative_constraints=res.negative_constraints,
    )
    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid, f"Validation failed for {case.prompt_id}: {val_res.errors}"


@pytest.mark.parametrize("case", CLARIFICATION_CORPUS, ids=lambda c: c.prompt_id)
def test_clarification_corpus(router: DomainRouter, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.clarification_question is not None
    assert len(res.clarification_question) > 5


@pytest.mark.parametrize("case", UNSUPPORTED_CORPUS, ids=lambda c: c.prompt_id)
def test_unsupported_corpus(router: DomainRouter, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id is None
    assert "unsupported" in res.explanation.lower()


@pytest.mark.parametrize("case", INVALID_CORPUS, ids=lambda c: c.prompt_id)
def test_invalid_corpus(router: DomainRouter, case):
    res = router.route(case.prompt)
    assert res.outcome == case.expected_outcome
    assert res.selected_domain_id is None


def test_mock_llm_provider_offline_multi_domain():
    provider = MockLLMProvider()
    prompts = {
        "blocks_world": "Stack the red box on the blue box.",
        "grid_world": "Move the agent from cell_a to cell_b.",
        "household_robotics": "Move the mug from the kitchen shelf to the living room table.",
        "warehouse": "Move SKU_A from shelf_1 to dispatch dock.",
        "scheduling": "Schedule design_review before code_review on machine_1.",
        "software_workflow": "Build and test commit_v1, then deploy to staging environment.",
    }
    for d_id, prompt in prompts.items():
        dom = registry.get(d_id)
        assert dom is not None
        proposal = provider.interpret(prompt, dom)
        assert isinstance(proposal, TaskProposalSchema)
        assert len(proposal.entities) > 0
        assert len(proposal.goal_facts) > 0
