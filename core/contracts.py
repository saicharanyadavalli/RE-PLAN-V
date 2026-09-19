"""Universal typed contracts and data schemas for RE-PLAN-V.

Every stage communicates through structured typed schemas defined here.
Avoid passing uncontrolled strings or arbitrary untyped dictionaries between modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. Core Symbolic Representation Contracts
# ==============================================================================

class FactSchema(BaseModel):
    """Represents a ground logical atom / fact in the symbolic world."""
    model_config = ConfigDict(frozen=True)

    predicate: str = Field(description="Name of the relation/predicate, e.g., 'on', 'clear', 'at'")
    arguments: Tuple[str, ...] = Field(default_factory=tuple, description="Objects involved, e.g. ('box1', 'table')")
    is_negated: bool = Field(default=False, description="True if this is a negated fact (not(P))")

    def to_string(self) -> str:
        args_str = ", ".join(self.arguments)
        base = f"{self.predicate}({args_str})"
        return f"not({base})" if self.is_negated else base

    def __str__(self) -> str:
        return self.to_string()


class SymbolicStateSchema(BaseModel):
    """Serializable snapshot of a symbolic state."""
    model_config = ConfigDict(frozen=True)

    facts: Tuple[FactSchema, ...] = Field(default_factory=tuple, description="Sorted tuple of positive facts holding in state")
    objects: Dict[str, str] = Field(default_factory=dict, description="Mapping object name -> type name")
    step_index: int = Field(default=0, description="Step index along plan execution trace")

    def contains_fact(self, fact: FactSchema) -> bool:
        if fact.is_negated:
            pos = FactSchema(predicate=fact.predicate, arguments=fact.arguments, is_negated=False)
            return pos not in self.facts
        return fact in self.facts


class ActionDefSchema(BaseModel):
    """Declaration of an action schema in a domain."""
    name: str = Field(description="Action schema operator name, e.g. 'move', 'stack'")
    parameters: List[Tuple[str, str]] = Field(description="List of (param_name, type_name)")
    preconditions: List[FactSchema] = Field(default_factory=list, description="Preconditions required to execute")
    add_effects: List[FactSchema] = Field(default_factory=list, description="Facts added to state upon execution")
    del_effects: List[FactSchema] = Field(default_factory=list, description="Facts removed from state upon execution")
    cost: float = Field(default=1.0, description="Execution action step cost")


class GroundActionSchema(BaseModel):
    """Ground instantiated action with concrete arguments."""
    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Operator name")
    arguments: Tuple[str, ...] = Field(default_factory=tuple, description="Ground argument names")
    cost: float = Field(default=1.0, description="Step cost")

    def to_string(self) -> str:
        args_str = ", ".join(self.arguments)
        return f"{self.name}({args_str})"

    def __str__(self) -> str:
        return self.to_string()


class PlanSchema(BaseModel):
    """Ordered candidate sequence of instantiated actions."""
    actions: List[GroundActionSchema] = Field(default_factory=list)
    algorithm: str = Field(default="A*", description="Search algorithm used")
    total_cost: float = Field(default=0.0)
    planning_time_ms: float = Field(default=0.0)
    nodes_expanded: int = Field(default=0)
    nodes_generated: int = Field(default=0)
    is_success: bool = Field(default=True)
    failure_reason: Optional[str] = Field(default=None)


# ==============================================================================
# 2. Verification Contracts
# ==============================================================================

class ViolationType(str, Enum):
    NONE = "NONE"
    INVALID_ACTION = "INVALID_ACTION"
    PRECONDITION_UNMET = "PRECONDITION_UNMET"
    INVARIANT_VIOLATED = "INVARIANT_VIOLATED"
    HARD_CONSTRAINT_VIOLATED = "HARD_CONSTRAINT_VIOLATED"
    FORBIDDEN_TRANSITION = "FORBIDDEN_TRANSITION"
    GOAL_UNMET = "GOAL_UNMET"


class VerificationTraceStep(BaseModel):
    step_index: int
    action: Optional[GroundActionSchema]
    pre_state_facts_count: int
    post_state_facts_count: int
    is_valid: bool
    violation: Optional[str] = None


class VerificationResultSchema(BaseModel):
    """Independent formal verification verdict."""
    is_valid: bool = Field(description="True if and only if every step and goal are satisfied")
    failed_step_index: Optional[int] = Field(default=None, description="Index of first failing step (0-indexed)")
    failed_action: Optional[GroundActionSchema] = Field(default=None, description="Offending action at failure")
    violated_condition: Optional[FactSchema] = Field(default=None, description="Exact violated precondition/invariant/goal")
    violation_type: ViolationType = Field(default=ViolationType.NONE)
    pre_state: Optional[SymbolicStateSchema] = Field(default=None, description="State immediately before failure")
    post_state: Optional[SymbolicStateSchema] = Field(default=None, description="State immediately after (if applicable)")
    trace: List[VerificationTraceStep] = Field(default_factory=list)
    verification_time_ms: float = Field(default=0.0)
    explanation: str = Field(default="")


# ==============================================================================
# 3. Counterexample & Witness Contracts
# ==============================================================================

class CounterexampleSchema(BaseModel):
    """Machine-readable witness of a verification failure."""
    counterexample_id: str
    action_index: int
    offending_action: GroundActionSchema
    violated_condition: FactSchema
    expected_truth: bool
    actual_truth: bool
    failure_category: ViolationType
    affected_entities: List[str] = Field(default_factory=list)
    state_snapshot: SymbolicStateSchema
    trace_summary: str = ""
    explanation: str = ""


# ==============================================================================
# 4. Fault Attribution Taxonomy & Contracts
# ==============================================================================

class FaultClass(str, Enum):
    PERCEPTION_ERROR = "PERCEPTION_ERROR"
    FORMALIZATION_ERROR = "FORMALIZATION_ERROR"
    PLANNING_ERROR = "PLANNING_ERROR"
    ENVIRONMENT_CHANGE = "ENVIRONMENT_CHANGE"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"


class FaultAttributionSchema(BaseModel):
    """Diagnostic judgment tracing failure to its root cause."""
    fault_class: FaultClass
    confidence: float = Field(ge=0.0, le=1.0)
    affected_stage: str
    evidence: List[str] = Field(default_factory=list)
    alternative_hypotheses: List[str] = Field(default_factory=list)
    explanation: str = ""


# ==============================================================================
# 5. Repair and Replanning Contracts
# ==============================================================================

class RepairType(str, Enum):
    FORBID_GROUND_ACTION = "FORBID_GROUND_ACTION"
    FORBID_ACTION_IN_STATE = "FORBID_ACTION_IN_STATE"
    ADD_ORDERING_CONSTRAINT = "ADD_ORDERING_CONSTRAINT"
    STATE_BELIEF_CORRECTION = "STATE_BELIEF_CORRECTION"
    REFRESH_OBSERVATION = "REFRESH_OBSERVATION"


class RepairConstraintSchema(BaseModel):
    """Explicit constraint or modification injected into search during replanning."""
    repair_id: str
    repair_type: RepairType
    description: str
    source_counterexample_id: str
    forbidden_action: Optional[GroundActionSchema] = None
    forbidden_state_facts: Optional[List[FactSchema]] = None
    before_action: Optional[GroundActionSchema] = None
    after_action: Optional[GroundActionSchema] = None
    state_corrections_add: Optional[List[FactSchema]] = None
    state_corrections_del: Optional[List[FactSchema]] = None


class ReplanningResultSchema(BaseModel):
    """Complete record of the repair and replanning loop."""
    success: bool
    original_plan: PlanSchema
    repaired_plan: Optional[PlanSchema] = None
    iterations: int = 0
    repairs_applied: List[RepairConstraintSchema] = Field(default_factory=list)
    final_verification: Optional[VerificationResultSchema] = None
    replanning_time_ms: float = 0.0
    status: str = Field(description="'VERIFIED', 'NO_VERIFIED_PLAN', 'MAX_ITERATIONS_REACHED', 'LOOP_DETECTED'")
    history: List[Dict[str, Any]] = Field(default_factory=list)


# ==============================================================================
# 6. Neural Interpretation Contracts
# ==============================================================================

class TaskProposalSchema(BaseModel):
    """Structured proposal generated by neural interpreter from natural language."""
    task_id: str = ""
    raw_prompt: str = ""
    entities: Dict[str, str] = Field(default_factory=dict, description="object_name -> type_name")
    initial_facts: List[FactSchema] = Field(default_factory=list)
    goal_facts: List[FactSchema] = Field(default_factory=list)
    negative_constraints: List[FactSchema] = Field(default_factory=list, description="e.g. not(holding(glass))")
    invariants: List[FactSchema] = Field(default_factory=list)
    confidence: float = 1.0


class ValidationStatus(str, Enum):
    VALID = "VALID"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    ARITY_MISMATCH = "ARITY_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    CONTRADICTION = "CONTRADICTION"
    UNSUPPORTED_OPERATOR = "UNSUPPORTED_OPERATOR"


class ProposalValidationResult(BaseModel):
    status: ValidationStatus
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_proposal: Optional[TaskProposalSchema] = None


# ==============================================================================
# 7. Vision Contracts
# ==============================================================================

class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class DetectedObject(BaseModel):
    name: str
    object_type: str
    color: str
    shape: str
    bbox: BoundingBox
    attributes: Dict[str, Any] = Field(default_factory=dict)


class VisualSceneProposal(BaseModel):
    scene_id: str
    detected_objects: List[DetectedObject] = Field(default_factory=list)
    extracted_facts: List[FactSchema] = Field(default_factory=list)
    confidence: float = 1.0


# ==============================================================================
# 8. Dynamic Environment Contracts
# ==============================================================================

class WorldDeltaSchema(BaseModel):
    """Delta between old world belief and new observation."""
    delta_id: str
    added_facts: List[FactSchema] = Field(default_factory=list)
    removed_facts: List[FactSchema] = Field(default_factory=list)
    affected_entities: List[str] = Field(default_factory=list)
    is_plan_invalidating: bool = False
    invalidated_action_index: Optional[int] = None
    explanation: str = ""


# ==============================================================================
# 9. Benchmark & Evaluation Contracts
# ==============================================================================

class BenchmarkInstanceSchema(BaseModel):
    """A procedural benchmark problem."""
    instance_id: str
    domain: str
    name: str
    difficulty: str = "medium"
    objects: Dict[str, str] = Field(default_factory=dict)
    initial_facts: List[FactSchema] = Field(default_factory=list)
    goal_facts: List[FactSchema] = Field(default_factory=list)
    constraints: List[FactSchema] = Field(default_factory=list)
    invariants: List[FactSchema] = Field(default_factory=list)
    natural_language_prompt: str = ""
    injected_fault_type: Optional[FaultClass] = None
    known_optimal_cost: Optional[float] = None


class EvaluationMetricsSchema(BaseModel):
    """Evaluation summary metrics."""
    experiment_id: str
    total_instances: int = 0
    valid_plan_rate: float = 0.0
    goal_success_rate: float = 0.0
    constraint_violation_rate: float = 0.0
    repair_success_rate: float = 0.0
    avg_repair_iterations: float = 0.0
    avg_planning_time_ms: float = 0.0
    avg_verification_time_ms: float = 0.0
    avg_repair_time_ms: float = 0.0
    avg_nodes_expanded: float = 0.0
    avg_plan_cost: float = 0.0
    fault_attribution_accuracy: float = 0.0
    recovery_advantage_over_regeneration: float = 0.0
