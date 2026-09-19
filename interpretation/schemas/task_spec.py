"""Task proposal schemas for neural interpretation."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from core.contracts import FactSchema, TaskProposalSchema


class TaskProposal(BaseModel):
    """Pydantic validated proposal from natural language interpretation."""
    task_id: str = "task_01"
    raw_prompt: str
    entities: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of entity names to their types, e.g. {'red_box': 'block', 'table': 'surface'}"
    )
    initial_facts: List[FactSchema] = Field(
        default_factory=list,
        description="Declared starting conditions"
    )
    goal_facts: List[FactSchema] = Field(
        default_factory=list,
        description="Target conditions to achieve"
    )
    negative_constraints: List[FactSchema] = Field(
        default_factory=list,
        description="Prohibited conditions, e.g. 'not(holding(glass))'"
    )
    invariants: List[FactSchema] = Field(
        default_factory=list,
        description="Properties that must hold continuously"
    )
    confidence: float = 1.0

    def to_contract_schema(self) -> TaskProposalSchema:
        return TaskProposalSchema(
            task_id=self.task_id,
            raw_prompt=self.raw_prompt,
            entities=dict(self.entities),
            initial_facts=list(self.initial_facts),
            goal_facts=list(self.goal_facts),
            negative_constraints=list(self.negative_constraints),
            invariants=list(self.invariants),
            confidence=self.confidence,
        )
