"""Stage 11 Security & Sandbox Boundary Tests: Schema Tampering, Unregistered Actions, and Side-Effect Isolation."""

from __future__ import annotations

import subprocess
import pytest
from app.services.pipeline import PipelineOrchestrator
from core.actions.domain import create_blocks_world_domain
from core.contracts import FactSchema, TaskConstraintSchema, TaskConstraintType, TaskProposalSchema
from interpretation.validator.validator import ConsistencyValidator


def test_unregistered_action_in_typed_constraints_fails_closed():
    """Verify that a typed constraint attempting to reference an unregistered action is rejected by validator."""
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="t_malicious_action",
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
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION,
                action_name="exec_system_command_rm_rf",
                description="Malicious action injection",
            )
        ],
    )

    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid is False
    assert any("unsupported action 'exec_system_command_rm_rf'" in err for err in val_res.errors)


def test_unregistered_entity_in_typed_constraints_fails_closed():
    """Verify that referencing an uncataloged entity in a constraint is strictly rejected."""
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="t_unknown_entity",
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
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="pick_up",
                entity="unregistered_phantom_block",
            )
        ],
    )

    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid is False
    assert any("unknown entity 'unregistered_phantom_block'" in err for err in val_res.errors)


def test_side_effect_spy_pipeline_execution(monkeypatch):
    """Spy test verifying that pipeline execution never triggers subprocess or OS execution."""
    subprocess_called = []

    def fake_popen(*args, **kwargs):
        subprocess_called.append(args)
        raise RuntimeError("UNAUTHORIZED_SUBPROCESS_EXECUTION_DETECTED")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    orchestrator = PipelineOrchestrator()
    res = orchestrator.run(
        prompt="Move the red box next to the blue box. Do not move the glass.",
        domain_id="blocks_world",
    )

    assert len(subprocess_called) == 0
    assert res.status == "COMPLETED"
    assert res.final_plan is not None
    assert res.final_verification.is_valid is True
