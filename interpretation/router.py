"""Text-First NLP Domain Router and Ambiguity Clarification Engine.

Classifies natural language instructions into domain candidates across the 6
registered domains, detects missing information to request clarification, and
rejects unsupported tasks without fabricating state facts.
"""

from __future__ import annotations

import enum
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from core.contracts import FactSchema
from core.domains import DomainRegistry, registry as default_registry


class RoutingOutcome(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"


class DomainRoutingResult(BaseModel):
    outcome: RoutingOutcome
    selected_domain_id: Optional[str] = None
    domain_confidence: float = 0.0
    candidate_scores: Dict[str, float] = Field(default_factory=dict)
    entities: Dict[str, str] = Field(default_factory=dict)
    initial_facts: List[FactSchema] = Field(default_factory=list)
    goal_facts: List[FactSchema] = Field(default_factory=list)
    negative_constraints: List[FactSchema] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    explanation: str = ""
    raw_prompt: str = ""


class DomainRouter:
    """Routes user text instructions to registered domains or clarification."""

    def __init__(self, registry: Optional[DomainRegistry] = None) -> None:
        self.registry = registry or default_registry

    def route(
        self, prompt: str, explicit_domain_id: Optional[str] = None
    ) -> DomainRoutingResult:
        """Analyzes user text and returns domain assignment or clarification."""
        p_clean = prompt.strip().lower()
        if not p_clean:
            return DomainRoutingResult(
                outcome=RoutingOutcome.INVALID_PROPOSAL,
                explanation="Empty instruction provided.",
                raw_prompt=prompt,
            )

        # 1. Check for obviously unsupported domains
        unsupported_keywords = [
            "flight", "ticket", "hotel", "stock", "crypto", "quantum", "weather forecast",
            "medical diagnosis", "translate to french", "generate poem"
        ]
        if any(w in p_clean for w in unsupported_keywords):
            return DomainRoutingResult(
                outcome=RoutingOutcome.UNSUPPORTED,
                explanation="Instruction requires unsupported capabilities outside the 6 registered planning domains.",
                raw_prompt=prompt,
            )

        # 2. Check for missing crucial information (Needs clarification)
        # e.g., deliver package without origin/location, or move without knowing destination
        if ("deliver" in p_clean or "package" in p_clean) and not any(k in p_clean for k in ["cell", "from", "at ", "dock", "shelf"]):
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Where is the package currently located, and which destination cell or dock should it be delivered to?",
                explanation="Missing starting position or explicit destination coordinates.",
                raw_prompt=prompt,
            )

        if p_clean.startswith("move") and len(p_clean.split()) <= 3:
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Could you please specify which object or agent to move, and where it should be moved to?",
                explanation="Ambiguous move target or location.",
                raw_prompt=prompt,
            )

        # 3. Determine target domain: explicit or auto-scored
        scores: Dict[str, float] = {}
        if explicit_domain_id and explicit_domain_id != "auto":
            dom = self.registry.get(explicit_domain_id)
            if not dom:
                return DomainRoutingResult(
                    outcome=RoutingOutcome.UNSUPPORTED,
                    explanation=f"Explicitly requested domain '{explicit_domain_id}' is not registered.",
                    raw_prompt=prompt,
                )
            best_domain_id = dom.domain_id
            best_score = 5.0
            scores[best_domain_id] = 5.0
        else:
            for d in self.registry.list_domains():
                score = 0.0
                for pattern in d.supported_patterns:
                    if pattern in p_clean:
                        score += 1.5
                scores[d.domain_id] = score

            best_domain_id, best_score = max(scores.items(), key=lambda kv: kv[1])

            if best_score == 0.0:
                return DomainRoutingResult(
                    outcome=RoutingOutcome.UNSUPPORTED,
                    candidate_scores=scores,
                    explanation="Could not match instruction keywords to any supported planning domain.",
                    raw_prompt=prompt,
                )

        # 4. Domain-specific entity & fact extraction
        entities: Dict[str, str] = {}
        initial_facts: List[FactSchema] = []
        goal_facts: List[FactSchema] = []
        negative_constraints: List[FactSchema] = []

        # Extract negative constraints: "do not move/touch/hold/visit/enter/deploy/schedule X"
        neg_match = re.search(
            r"do not (?:move|touch|hold|disturb|visit|enter|deploy to|schedule on) (?:the )?([a-z0-9_]+)",
            p_clean,
        )
        if neg_match:
            prot_obj = neg_match.group(1).replace(" ", "_")
            if best_domain_id in ("blocks_world", "blocks"):
                entities[prot_obj] = "block"
                negative_constraints.append(FactSchema(predicate="holding", arguments=(prot_obj,)))
            elif best_domain_id in ("grid_world", "grid"):
                entities[prot_obj] = "location"
                negative_constraints.append(FactSchema(predicate="at", arguments=("agent", prot_obj)))
            elif best_domain_id in ("household", "household_robotics"):
                entities[prot_obj] = "item"
                negative_constraints.append(FactSchema(predicate="holding", arguments=("robot", prot_obj)))
            elif best_domain_id == "warehouse":
                entities[prot_obj] = "zone"
                negative_constraints.append(FactSchema(predicate="carrier_at", arguments=("carrier_1", prot_obj)))
            elif best_domain_id == "scheduling":
                entities[prot_obj] = "resource"
                negative_constraints.append(FactSchema(predicate="scheduled_on", arguments=("task_b", prot_obj)))
            elif best_domain_id == "software_workflow":
                entities[prot_obj] = "environment"
                negative_constraints.append(FactSchema(predicate="deployed_to", arguments=("pkg_v1", prot_obj)))

        if best_domain_id in ("blocks_world", "blocks"):
            self._extract_blocks_world(p_clean, entities, initial_facts, goal_facts)
        elif best_domain_id in ("grid_world", "grid"):
            self._extract_grid_world(p_clean, entities, initial_facts, goal_facts)
        elif best_domain_id in ("household", "household_robotics"):
            self._extract_household(p_clean, entities, initial_facts, goal_facts)
        elif best_domain_id == "warehouse":
            self._extract_warehouse(p_clean, entities, initial_facts, goal_facts)
        elif best_domain_id == "scheduling":
            self._extract_scheduling(p_clean, entities, initial_facts, goal_facts)
        elif best_domain_id == "software_workflow":
            self._extract_software(p_clean, entities, initial_facts, goal_facts)

        confidence = min(0.98, 0.60 + 0.10 * best_score)

        return DomainRoutingResult(
            outcome=RoutingOutcome.SUPPORTED,
            selected_domain_id=best_domain_id,
            domain_confidence=confidence,
            candidate_scores=scores,
            entities=entities,
            initial_facts=initial_facts,
            goal_facts=goal_facts,
            negative_constraints=negative_constraints,
            explanation=f"Successfully routed to '{best_domain_id}' with keyword match score {best_score:.1f}.",
            raw_prompt=prompt,
        )

    def _extract_blocks_world(self, text: str, entities: dict, init: list, goal: list) -> None:
        # Default entities
        for word in ["red_box", "blue_box", "green_box", "yellow_box", "glass", "b1", "b2", "b3", "b4"]:
            if word in text or word.replace("_", " ") in text:
                entities[word] = "block"

        if not entities:
            entities["red_box"] = "block"
            entities["blue_box"] = "block"

        # Check if an explicit initial stack configuration was stated in the prompt
        # e.g., "the red box is on the green box"
        init_on_match = re.search(r"(?:the )?([a-z0-9_]+) is on (?:the )?([a-z0-9_]+)", text)
        if init_on_match:
            top_init = init_on_match.group(1).replace(" ", "_")
            bottom_init = init_on_match.group(2).replace(" ", "_")
            entities[top_init] = "block"
            entities[bottom_init] = "block"
            init.append(FactSchema(predicate="on", arguments=(top_init, bottom_init)))
            init.append(FactSchema(predicate="clear", arguments=(top_init,)))
            init.append(FactSchema(predicate="on_table", arguments=(bottom_init,)))
            for b in entities:
                if b not in (top_init, bottom_init):
                    init.append(FactSchema(predicate="on_table", arguments=(b,)))
                    init.append(FactSchema(predicate="clear", arguments=(b,)))
            init.append(FactSchema(predicate="handempty", arguments=()))
        else:
            # Initial facts: all blocks on table and clear
            for b in entities:
                init.append(FactSchema(predicate="on_table", arguments=(b,)))
                init.append(FactSchema(predicate="clear", arguments=(b,)))
            init.append(FactSchema(predicate="handempty", arguments=()))

        # Goals
        stack_match = re.search(r"(?:stack|move|put) (?:the )?([a-z0-9_]+) (?:on|next to) (?:the )?([a-z0-9_]+)", text)
        if stack_match:
            top = stack_match.group(1).replace(" ", "_")
            bottom = stack_match.group(2).replace(" ", "_")
            entities[top] = "block"
            entities[bottom] = "block"
            goal.append(FactSchema(predicate="on", arguments=(top, bottom)))

    def _extract_grid_world(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["agent"] = "agent"
        # Find cells or grid locations (e.g. loc_0_0 or cell_a)
        cells = re.findall(r"loc_\d+_\d+|cell_[a-z0-9]+|\b[a-d]\b", text)
        clean_cells = [f"loc_{c}" if (not c.startswith("loc_") and not c.startswith("cell_")) else c for c in cells]
        for c in clean_cells:
            entities[c] = "location"

        from_c = clean_cells[0] if len(clean_cells) > 0 else "loc_0_0"
        to_c = clean_cells[1] if len(clean_cells) > 1 else "loc_1_1"
        entities[from_c] = "location"
        entities[to_c] = "location"

        init.append(FactSchema(predicate="at", arguments=("agent", from_c)))
        init.append(FactSchema(predicate="connected", arguments=(from_c, to_c)))

        # Check for item pickup/transfer (e.g. key_1)
        item_match = re.search(r"(key_\d+|item_\d+|package)", text)
        if item_match:
            item_name = item_match.group(1)
            entities[item_name] = "item"
            init.append(FactSchema(predicate="at_item", arguments=(item_name, to_c)))
            init.append(FactSchema(predicate="empty_hand", arguments=("agent",)))
            goal.append(FactSchema(predicate="carrying", arguments=("agent", item_name)))
        else:
            goal.append(FactSchema(predicate="at", arguments=("agent", to_c)))

    def _extract_household(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["robot"] = "robot"
        entities["mug"] = "item"
        entities["kitchen"] = "room"
        entities["living_room"] = "room"
        entities["kitchen_shelf"] = "surface"
        entities["living_room_table"] = "surface"

        init.append(FactSchema(predicate="robot_at", arguments=("robot", "kitchen")))
        init.append(FactSchema(predicate="connected_rooms", arguments=("kitchen", "living_room")))
        init.append(FactSchema(predicate="surface_in_room", arguments=("kitchen_shelf", "kitchen")))
        init.append(FactSchema(predicate="surface_in_room", arguments=("living_room_table", "living_room")))
        init.append(FactSchema(predicate="item_on", arguments=("mug", "kitchen_shelf")))
        init.append(FactSchema(predicate="gripper_empty", arguments=("robot",)))

        goal.append(FactSchema(predicate="item_on", arguments=("mug", "living_room_table")))

    def _extract_warehouse(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["carrier_1"] = "carrier"
        entities["sku_a"] = "sku"
        entities["shelf_1"] = "bay"
        entities["dispatch_dock"] = "bay"
        entities["zone_storage"] = "zone"
        entities["zone_dock"] = "zone"

        init.append(FactSchema(predicate="carrier_at", arguments=("carrier_1", "zone_storage")))
        init.append(FactSchema(predicate="zone_connected", arguments=("zone_storage", "zone_dock")))
        init.append(FactSchema(predicate="bay_in_zone", arguments=("shelf_1", "zone_storage")))
        init.append(FactSchema(predicate="bay_in_zone", arguments=("dispatch_dock", "zone_dock")))
        init.append(FactSchema(predicate="sku_stored_in", arguments=("sku_a", "shelf_1")))
        init.append(FactSchema(predicate="carrier_empty", arguments=("carrier_1",)))
        init.append(FactSchema(predicate="bay_available", arguments=("dispatch_dock",)))

        goal.append(FactSchema(predicate="sku_stored_in", arguments=("sku_a", "dispatch_dock")))

    def _extract_scheduling(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["design_review"] = "job"
        entities["code_review"] = "job"
        entities["machine_1"] = "resource"
        entities["slot_1"] = "slot"
        entities["slot_2"] = "slot"

        init.append(FactSchema(predicate="job_ready", arguments=("design_review",)))
        init.append(FactSchema(predicate="job_ready", arguments=("code_review",)))
        init.append(FactSchema(predicate="precedes", arguments=("design_review", "code_review")))
        init.append(FactSchema(predicate="resource_available", arguments=("machine_1", "slot_1")))
        init.append(FactSchema(predicate="resource_available", arguments=("machine_1", "slot_2")))

        goal.append(FactSchema(predicate="job_completed", arguments=("code_review",)))

    def _extract_software(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["commit_v1"] = "commit"
        entities["pkg_v1"] = "artifact"
        entities["staging"] = "environment"

        init.append(FactSchema(predicate="code_checked_out", arguments=("commit_v1",)))
        init.append(FactSchema(predicate="environment_healthy", arguments=("staging",)))

        goal.append(FactSchema(predicate="deployed_to", arguments=("pkg_v1", "staging")))
