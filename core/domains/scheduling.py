"""Scheduling and Resource Allocation Domain."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.constraints import FunctionalDependencyInvariant, PrecedenceInvariant
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class SchedulingDomain(BaseDomain):
    """Job scheduling, resource assignment, and precedence-constrained task sequencing domain."""

    def __init__(self) -> None:
        th = TypeHierarchy()
        th.add_type("job", "object")
        th.add_type("resource", "object")
        th.add_type("slot", "object")

        preds = [
            PredicateDefinition("job_ready", ["job"]),
            PredicateDefinition("job_completed", ["job"]),
            PredicateDefinition("resource_available", ["resource", "slot"]),
            PredicateDefinition("resource_busy", ["resource", "slot"]),
            PredicateDefinition("job_assigned", ["job", "resource", "slot"]),
            PredicateDefinition("precedes", ["job", "job"], is_static=True),
        ]

        def _check_independent_job_applicability(state: Any, args: Sequence[str]) -> Tuple[bool, Optional[str]]:
            if not args:
                return True, None
            j = args[0]
            # A job with a predecessor constraint cannot be scheduled as an independent job;
            # it must be scheduled using schedule_dependent_job after its prerequisite completes.
            for f in state.facts:
                if f.predicate == "precedes" and len(f.arguments) >= 2 and f.arguments[1] == j:
                    return False, f"Job '{j}' has predecessor constraint and must use schedule_dependent_job"
            return True, None

        schedule_independent = ActionDefinition(
            name="schedule_independent_job",
            parameters=[
                ActionParameter("j", "job"),
                ActionParameter("r", "resource"),
                ActionParameter("s", "slot"),
            ],
            preconditions=[
                Fact("job_ready", ["?j"]),
                Fact("resource_available", ["?r", "?s"]),
            ],
            add_effects=[
                Fact("job_completed", ["?j"]),
                Fact("job_assigned", ["?j", "?r", "?s"]),
                Fact("resource_busy", ["?r", "?s"]),
            ],
            del_effects=[
                Fact("job_ready", ["?j"]),
                Fact("resource_available", ["?r", "?s"]),
            ],
            cost=1.0,
            description="Assign and complete an independent job on an available resource slot",
            applicability_check=_check_independent_job_applicability,
        )

        schedule_dependent = ActionDefinition(
            name="schedule_dependent_job",
            parameters=[
                ActionParameter("j_prior", "job"),
                ActionParameter("j", "job"),
                ActionParameter("r", "resource"),
                ActionParameter("s", "slot"),
            ],
            preconditions=[
                Fact("precedes", ["?j_prior", "?j"]),
                Fact("job_completed", ["?j_prior"]),
                Fact("job_ready", ["?j"]),
                Fact("resource_available", ["?r", "?s"]),
            ],
            add_effects=[
                Fact("job_completed", ["?j"]),
                Fact("job_assigned", ["?j", "?r", "?s"]),
                Fact("resource_busy", ["?r", "?s"]),
            ],
            del_effects=[
                Fact("job_ready", ["?j"]),
                Fact("resource_available", ["?r", "?s"]),
            ],
            cost=1.0,
            description="Schedule a dependent job after its prerequisite completes",
        )

        examples = [
            {
                "prompt": "Schedule design_review before implementation_review on machine_1.",
                "domain": "scheduling",
                "goal": "job_completed(implementation_review)",
            },
            {
                "prompt": "Allocate job_alpha to worker_a slot_1, then allocate job_beta to worker_b slot_2.",
                "domain": "scheduling",
                "goal": "job_completed(job_alpha), job_completed(job_beta)",
            },
        ]

        super().__init__(
            domain_id="scheduling",
            name="Scheduling & Resource Allocation",
            version="1.0.0",
            description="Discrete job-shop allocation, machine assignment, and precedence-ordered timeline sequencing.",
            type_hierarchy=th,
            predicates=preds,
            actions=[schedule_independent, schedule_dependent],
            default_invariants=[FunctionalDependencyInvariant("job_assigned", 0, 1), PrecedenceInvariant()],
            task_examples=examples,
            supported_patterns=[
                "schedule", "allocate", "machine", "job", "slot", "resource", "precedence", "task", "timeline"
            ],
            unsupported_features=[
                "continuous millisecond jitter scheduling", "mixed-integer non-linear programming"
            ],
        )

    def applicable_actions(
        self, state: Any, registry: Any
    ) -> List[Any]:
        """Filters out independent job actions when a job has an uncompleted predecessor."""
        actions = super().applicable_actions(state, registry)
        filtered = []
        for act in actions:
            if act.name == "schedule_independent_job" and act.arguments:
                j = act.arguments[0]
                has_predecessor = any(
                    f.predicate == "precedes" and len(f.arguments) >= 2 and f.arguments[1] == j
                    for f in state.facts
                )
                if has_predecessor:
                    continue
            filtered.append(act)
        return filtered
