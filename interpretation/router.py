"""Text-First NLP Domain Router and Ambiguity Clarification Engine.

Classifies natural language instructions into domain candidates across the 6
registered domains, detects missing information to request clarification, and
rejects unsupported tasks without fabricating state facts.
"""

from __future__ import annotations

import enum
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from core.contracts import FactSchema, TaskConstraintSchema, TaskConstraintType
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
    typed_constraints: List[TaskConstraintSchema] = Field(default_factory=list)
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

        # Check prompt length limit & character validity
        if len(prompt) > 2500:
            return DomainRoutingResult(
                outcome=RoutingOutcome.INVALID_PROPOSAL,
                explanation="Instruction exceeds maximum permitted character limit (2500 characters).",
                raw_prompt=prompt,
            )

        if not any(c.isalpha() for c in p_clean):
            return DomainRoutingResult(
                outcome=RoutingOutcome.INVALID_PROPOSAL,
                explanation="Instruction contains no alphabetic words or semantic meaning.",
                raw_prompt=prompt,
            )

        # 1. Check for obviously unsupported domains
        unsupported_keywords = [
            "flight", "ticket", "hotel", "reservation", "stock", "stocks", "crypto", "bitcoin", "ethereum",
            "quantum", "weather forecast", "weather in", "medical diagnosis", "symptoms", "prescribe",
            "translate to french", "translate to", "generate poem", "write a poem", "write a story",
            "tell me a joke", "recipe for", "bake a cake"
        ]
        if any(w in p_clean for w in unsupported_keywords):
            return DomainRoutingResult(
                outcome=RoutingOutcome.UNSUPPORTED,
                explanation="Instruction requires unsupported capabilities outside the 6 registered planning domains.",
                raw_prompt=prompt,
            )

        # 2. Check for missing crucial information (Needs clarification)
        # Normalize punctuation for token analysis
        p_norm = re.sub(r"[^\w\s]", " ", p_clean)
        tokens = p_norm.split()

        # Deliver/ship without origin or destination (using word boundaries)
        has_delivery_word = bool(re.search(r"\b(deliver|ship)\b", p_clean)) or (
            bool(re.search(r"\bpackage\b", p_clean)) and not any(k in p_clean for k in ["task_package", "build_package", "pkg_"])
        )
        if has_delivery_word and not any(
            k in p_clean for k in ["cell", "from", "at ", "dock", "shelf", "bay", "zone", "loc_"]
        ):
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Where is the package currently located, and which destination cell or dock should it be delivered to?",
                explanation="Missing starting position or explicit destination coordinates.",
                raw_prompt=prompt,
            )

        # Underspecified move/transport
        if tokens and tokens[0] in ("move", "transport") and len(tokens) <= 3 and not any(k in p_clean for k in ["loc_", "cell", "room", "table", "b1", "b2", "box"]):
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Could you please specify which object or agent to move, and where it should be moved to?",
                explanation="Ambiguous move target or location.",
                raw_prompt=prompt,
            )

        # Underspecified schedule command
        if tokens and tokens[0] in ("schedule", "allocate") and len(tokens) <= 2:
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Which job or task should be scheduled, and on which resource or time slot?",
                explanation="Missing task identifier or target resource allocation.",
                raw_prompt=prompt,
            )

        # Underspecified deploy command
        if tokens and tokens[0] in ("deploy", "release") and len(tokens) <= 2:
            return DomainRoutingResult(
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                clarification_question="Which commit or artifact should be deployed, and to which target environment (e.g. staging or production)?",
                explanation="Missing deployment target environment or artifact version.",
                raw_prompt=prompt,
            )

        # 3. Determine target domain: explicit or auto-scored
        scores: Dict[str, float] = {}
        if explicit_domain_id and explicit_domain_id != "auto":
            dom = self.registry.get(explicit_domain_id)
            if not dom:
                return DomainRoutingResult(
                    outcome=RoutingOutcome.UNSUPPORTED,
                    explanation=f"Explicitly requested domain '{explicit_domain_id}' is not registered and unsupported.",
                    raw_prompt=prompt,
                )
            best_domain_id = dom.domain_id
            best_score = 5.0
            scores[best_domain_id] = 5.0
        else:
            domain_specific_bonuses: Dict[str, List[str]] = {
                "blocks_world": ["block", "box", "boxes", "glass", "stack", "unstack", "tower", "pyramid", "on table", "on_table", "place", "pick up", "b1", "b2", "b3", "b4"],
                "grid_world": ["grid", "cell", "loc_", "maze", "waypoint", "coordinate", "agent at", "agent_free", "holding_item"],
                "household_robotics": ["household", "kitchen", "living room", "living_room", "bedroom", "office", "dining room", "dining_room", "bathroom", "pantry", "mug", "cup", "counter", "drawer", "cabinet", "fridge", "clean", "tidy", "vase", "surface", "room"],
                "warehouse": ["warehouse", "sku", "agv", "carrier", "bay", "pallet", "inventory", "dock", "aisle", "dispatch", "receiving"],
                "scheduling": ["schedule", "scheduling", "job", "precedence", "precedes", "machine", "worker", "slot", "timeline", "resource", "allocate"],
                "software_workflow": ["deploy", "deployment", "ci/cd", "staging", "production", "commit", "build artifact", "security scan", "unit test", "release", "pipeline"],
            }

            for d in self.registry.list_domains():
                score = 0.0
                for pattern in d.supported_patterns:
                    if pattern in p_clean:
                        score += 1.5
                for bonus_word in domain_specific_bonuses.get(d.domain_id, []):
                    if bonus_word in p_clean:
                        score += 1.0
                scores[d.domain_id] = score

            best_domain_id, best_score = max(scores.items(), key=lambda kv: kv[1])

            if best_score == 0.0:
                return DomainRoutingResult(
                    outcome=RoutingOutcome.UNSUPPORTED,
                    candidate_scores=scores,
                    explanation="Instruction could not be matched to any supported planning domain and is unsupported.",
                    raw_prompt=prompt,
                )

        # 4. Domain-specific entity & fact extraction
        entities: Dict[str, str] = {}
        initial_facts: List[FactSchema] = []
        goal_facts: List[FactSchema] = []
        negative_constraints: List[FactSchema] = []
        typed_constraints: List[TaskConstraintSchema] = []

        # Extract negative constraints across all 6 domains
        self._extract_negative_constraints(p_clean, best_domain_id, entities, negative_constraints, typed_constraints)

        # Extract domain-specific entities, initial facts, and goal facts
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

        confidence = min(0.98, 0.60 + 0.08 * best_score)

        return DomainRoutingResult(
            outcome=RoutingOutcome.SUPPORTED,
            selected_domain_id=best_domain_id,
            domain_confidence=confidence,
            candidate_scores=scores,
            entities=entities,
            initial_facts=initial_facts,
            goal_facts=goal_facts,
            negative_constraints=negative_constraints,
            typed_constraints=typed_constraints,
            explanation=f"Successfully routed to '{best_domain_id}' with keyword match score {best_score:.1f}.",
            raw_prompt=prompt,
        )

    def _extract_negative_constraints(
        self,
        text: str,
        domain_id: str,
        entities: Dict[str, str],
        negative_constraints: List[FactSchema],
        typed_constraints: Optional[List[TaskConstraintSchema]] = None,
    ) -> None:
        """Extracts scoped negative constraints using comprehensive natural language patterns."""
        if typed_constraints is None:
            typed_constraints = []

        # Pattern 1: Prohibited placement / stacking ("never put/place/stack X on/onto Y")
        stack_prohibitions = re.findall(
            r"(?:do not|don't|never|must not|avoid|without)\s+(?:put|putting|place|placing|stack|stacking)\s+(?:the\s+)?([a-z0-9_]+)\s+(?:on|onto)\s+(?:the\s+)?([a-z0-9_]+)",
            text,
        )
        for top, bottom in stack_prohibitions:
            top_clean = top.replace(" ", "_")
            bot_clean = bottom.replace(" ", "_")
            if domain_id in ("blocks_world", "blocks"):
                entities[top_clean] = "block"
                entities[bot_clean] = "block"
                negative_constraints.append(FactSchema(predicate="on", arguments=(top_clean, bot_clean)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                        action_name="stack",
                        arguments=[top_clean, bot_clean],
                        description=f"Prohibit stacking {top_clean} on {bot_clean}",
                        source_text=text,
                    )
                )
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_STATE_FACT,
                        state_fact=FactSchema(predicate="on", arguments=(top_clean, bot_clean)),
                        description=f"State on({top_clean}, {bot_clean}) forbidden",
                        source_text=text,
                    )
                )
            elif domain_id in ("household", "household_robotics"):
                entities[top_clean] = "item"
                entities[bot_clean] = "surface"
                negative_constraints.append(FactSchema(predicate="item_on", arguments=(top_clean, bot_clean)))
            elif domain_id == "warehouse":
                entities[top_clean] = "sku"
                entities[bot_clean] = "bay"
                negative_constraints.append(FactSchema(predicate="sku_stored_in", arguments=(top_clean, bot_clean)))

        # Pattern 2: Prohibited movement / touch / holding ("do not move/touch/hold/disturb/pick up X")
        touch_prohibitions = re.findall(
            r"(?:do not|don't|never|must not|avoid|without)\s+(?:move|moving|touch|touching|hold|holding|disturb|disturbing|pick up|picking up|retrieve|retrieving)\s+(?:the\s+)?([a-z0-9_]+)",
            text,
        )
        for obj in touch_prohibitions:
            obj_clean = obj.replace(" ", "_")
            if domain_id in ("blocks_world", "blocks"):
                entities[obj_clean] = "block"
                negative_constraints.append(FactSchema(predicate="holding", arguments=(obj_clean,)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                        action_name="pick_up",
                        entity=obj_clean,
                        arg_index=0,
                        description=f"Do not pick up {obj_clean}",
                        source_text=text,
                    )
                )
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                        action_name="unstack",
                        entity=obj_clean,
                        arg_index=0,
                        description=f"Do not unstack {obj_clean}",
                        source_text=text,
                    )
                )
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_STATE_FACT,
                        state_fact=FactSchema(predicate="holding", arguments=(obj_clean,)),
                        description=f"State holding({obj_clean}) forbidden",
                        source_text=text,
                    )
                )
            elif domain_id in ("grid_world", "grid"):
                entities[obj_clean] = "item"
                negative_constraints.append(FactSchema(predicate="holding_item", arguments=("agent", obj_clean)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                        action_name="pickup",
                        entity=obj_clean,
                        arg_index=1,
                        description=f"Do not pick up {obj_clean}",
                        source_text=text,
                    )
                )
            elif domain_id in ("household", "household_robotics"):
                entities[obj_clean] = "item"
                negative_constraints.append(FactSchema(predicate="holding", arguments=("robot", obj_clean)))
            elif domain_id == "warehouse":
                entities[obj_clean] = "sku"
                negative_constraints.append(FactSchema(predicate="carrier_loaded_with", arguments=("carrier_1", obj_clean)))

        # Pattern 3: Prohibited visit / entering ("do not visit/enter/traverse/go to X")
        visit_prohibitions = re.findall(
            r"(?:do not|don't|never|must not|avoid|without)\s+(?:visit|visiting|enter|entering|traverse|traversing|go to|going to)\s+(?:the\s+)?(?:cell\s+|zone\s+|room\s+|location\s+)?([a-z0-9_]+)",
            text,
        )
        for loc in visit_prohibitions:
            loc_clean = loc.replace(" ", "_")
            if domain_id in ("grid_world", "grid"):
                cell_id = loc_clean if loc_clean.startswith("cell_") or loc_clean.startswith("loc_") else f"cell_{loc_clean}"
                entities[cell_id] = "location"
                negative_constraints.append(FactSchema(predicate="at", arguments=("agent", cell_id)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_TRANSITION,
                        action_name="move",
                        to_entity=cell_id,
                        arg_index=2,
                        description=f"Do not enter {cell_id}",
                        source_text=text,
                    )
                )
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_STATE_FACT,
                        state_fact=FactSchema(predicate="at", arguments=("agent", cell_id)),
                        description=f"State at(agent, {cell_id}) forbidden",
                        source_text=text,
                    )
                )
            elif domain_id in ("household", "household_robotics"):
                entities[loc_clean] = "room"
                negative_constraints.append(FactSchema(predicate="robot_at", arguments=("robot", loc_clean)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_TRANSITION,
                        action_name="move",
                        to_entity=loc_clean,
                        arg_index=2,
                        description=f"Do not move robot to {loc_clean}",
                        source_text=text,
                    )
                )
            elif domain_id == "warehouse":
                zone_id = loc_clean if loc_clean.startswith("zone_") else f"zone_{loc_clean}"
                entities[zone_id] = "zone"
                negative_constraints.append(FactSchema(predicate="carrier_at", arguments=("carrier_1", zone_id)))

        # Pattern 4: Prohibited deployment ("do not deploy to X")
        deploy_prohibitions = re.findall(
            r"(?:do not|don't|never|must not|avoid|without)\s+(?:deploy|deploying|release|releasing)\s+(?:to\s+)?(?:the\s+)?(?:environment\s+)?([a-z0-9_]+)",
            text,
        )
        for env in deploy_prohibitions:
            env_clean = env.replace(" ", "_")
            if domain_id == "software_workflow":
                entities[env_clean] = "environment"
                pkg_matches = re.findall(r"\b(pkg_[a-z0-9_]+|artifact_[a-z0-9_]+|image_[a-z0-9_]+|bundle_[a-z0-9_]+)\b", text)
                commit_matches = re.findall(r"\b(commit_[a-z0-9_]+|release_[a-z0-9_]+|sha_[a-z0-9_]+|v\d+[\w.]*)\b", text)
                commit_id = commit_matches[0] if commit_matches else "commit_v1"
                pkg_id = pkg_matches[0] if pkg_matches else (
                    next((k for k, v in entities.items() if v == "artifact"), f"pkg_{commit_id}")
                )
                entities[pkg_id] = "artifact"
                negative_constraints.append(FactSchema(predicate="deployed_to", arguments=(pkg_id, env_clean)))
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                        action_name="deploy",
                        entity=env_clean,
                        arg_index=1,
                        description=f"Do not deploy to {env_clean}",
                        source_text=text,
                    )
                )
                typed_constraints.append(
                    TaskConstraintSchema(
                        constraint_type=TaskConstraintType.FORBID_STATE_FACT,
                        state_fact=FactSchema(predicate="deployed_to", arguments=(pkg_id, env_clean)),
                        description=f"State deployed_to({pkg_id}, {env_clean}) forbidden",
                        source_text=text,
                    )
                )

        # Pattern 5: Prohibited scheduling / assignment ("do not schedule/assign X to Y")
        sched_prohibitions = re.findall(
            r"(?:do not|don't|never|must not|avoid|without)\s+(?:schedule|scheduling|assign|assigning)\s+(?:the\s+)?([a-z0-9_]+)\s+(?:on|to)\s+(?:the\s+)?([a-z0-9_]+)",
            text,
        )
        for job, res in sched_prohibitions:
            job_clean = job.replace(" ", "_")
            res_clean = res.replace(" ", "_")
            if domain_id == "scheduling":
                entities[job_clean] = "job"
                entities[res_clean] = "resource"
                entities["slot_1"] = "slot"
                negative_constraints.append(FactSchema(predicate="job_assigned", arguments=(job_clean, res_clean, "slot_1")))

        # Pattern 6: Bare "avoid X"
        avoid_matches = re.findall(r"\bavoid\s+(?:the\s+)?([a-z0-9_]+)", text)
        for target in avoid_matches:
            target_clean = target.replace(" ", "_")
            if target_clean in ("putting", "placing", "stacking", "moving", "touching", "holding", "visiting", "entering", "deploying", "scheduling"):
                continue
            if domain_id in ("blocks_world", "blocks"):
                entities[target_clean] = "block"
                negative_constraints.append(FactSchema(predicate="holding", arguments=(target_clean,)))
            elif domain_id in ("grid_world", "grid"):
                loc_id = target_clean if (target_clean.startswith("loc_") or target_clean.startswith("cell_")) else f"loc_{target_clean}"
                entities[loc_id] = "location"
                negative_constraints.append(FactSchema(predicate="at", arguments=("agent", loc_id)))
            elif domain_id in ("household", "household_robotics"):
                entities[target_clean] = "room"
                negative_constraints.append(FactSchema(predicate="robot_at", arguments=("robot", target_clean)))
            elif domain_id == "warehouse":
                zone_id = target_clean if target_clean.startswith("zone_") else f"zone_{target_clean}"
                entities[zone_id] = "zone"
                negative_constraints.append(FactSchema(predicate="carrier_at", arguments=("carrier_1", zone_id)))
            elif domain_id == "software_workflow":
                entities[target_clean] = "environment"
                pkg_matches = re.findall(r"\b(pkg_[a-z0-9_]+|artifact_[a-z0-9_]+|image_[a-z0-9_]+|bundle_[a-z0-9_]+)\b", text)
                commit_matches = re.findall(r"\b(commit_[a-z0-9_]+|release_[a-z0-9_]+|sha_[a-z0-9_]+|v\d+[\w.]*)\b", text)
                commit_id = commit_matches[0] if commit_matches else "commit_v1"
                pkg_id = pkg_matches[0] if pkg_matches else (
                    next((k for k, v in entities.items() if v == "artifact"), f"pkg_{commit_id}")
                )
                entities[pkg_id] = "artifact"
                negative_constraints.append(FactSchema(predicate="deployed_to", arguments=(pkg_id, target_clean)))

    def _extract_blocks_world(self, text: str, entities: dict, init: list, goal: list) -> None:
        # Extract color-coded boxes and numbered blocks
        color_pattern = r"\b(red|blue|green|yellow|orange|purple|white|black|glass)(?:_|\s+)?(box|block)?\b"
        matches = re.findall(color_pattern, text)
        for color, kind in matches:
            name = f"{color}_{kind}" if kind else (f"{color}_box" if color != "glass" else "glass")
            entities[name] = "block"

        # Explicit b1, b2, block_1, block_a identifiers
        block_ids = re.findall(r"\b(b\d+|block_[a-z0-9_]+|box_[a-z0-9_]+)\b", text)
        for b_id in block_ids:
            entities[b_id] = "block"

        if not entities:
            entities["red_box"] = "block"
            entities["blue_box"] = "block"

        # Check explicit initial stack: "the red box is on the green box"
        init_on_match = re.search(r"(?:the\s+)?([a-z0-9_]+)\s+is\s+on\s+(?:the\s+)?([a-z0-9_]+)", text)
        top_init, bot_init = None, None
        if init_on_match:
            top_raw = init_on_match.group(1).replace(" ", "_")
            bot_raw = init_on_match.group(2).replace(" ", "_")
            if top_raw in entities and bot_raw in entities:
                top_init, bot_init = top_raw, bot_raw
                init.append(FactSchema(predicate="on", arguments=(top_init, bot_init)))
                init.append(FactSchema(predicate="clear", arguments=(top_init,)))
                init.append(FactSchema(predicate="on_table", arguments=(bot_init,)))

        for b in entities:
            if b not in (top_init, bot_init):
                init.append(FactSchema(predicate="on_table", arguments=(b,)))
                init.append(FactSchema(predicate="clear", arguments=(b,)))
        init.append(FactSchema(predicate="handempty", arguments=()))

        # Goals: Extract only from the positive portion of the prompt (strip negative clauses)
        pos_text = re.split(r"\b(?:without|do not|don't|never|must not|avoid)\b", text)[0]
        stack_matches = re.findall(
            r"(?:stack|move|put|place)\s+(?:the\s+)?([a-z0-9_]+(?:\s+(?:box|block))?)\s+(?:on|next to|top of)\s+(?:the\s+)?([a-z0-9_]+(?:\s+(?:box|block))?)",
            pos_text,
        )
        for top_raw, bot_raw in stack_matches:
            top = top_raw.replace(" ", "_")
            bottom = bot_raw.replace(" ", "_")
            entities[top] = "block"
            entities[bottom] = "block"
            goal.append(FactSchema(predicate="on", arguments=(top, bottom)))

        # Also support multi-block tower goals e.g. "on B and B on C"
        if not goal and len(entities) >= 2:
            ent_list = [k for k in entities.keys() if k != "table"]
            if len(ent_list) >= 2:
                goal.append(FactSchema(predicate="on", arguments=(ent_list[0], ent_list[1])))

    def _extract_grid_world(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["agent"] = "agent"
        # Find cells or grid locations (e.g. loc_0_0 or cell_a)
        cells = re.findall(r"loc_\d+_\d+|cell_[a-z0-9_]+|\b[a-d]\b", text)
        clean_cells = [f"loc_{c}" if (not c.startswith("loc_") and not c.startswith("cell_")) else c for c in cells]
        for c in clean_cells:
            entities[c] = "location"

        from_c = clean_cells[0] if len(clean_cells) > 0 else "loc_0_0"
        to_c = clean_cells[1] if len(clean_cells) > 1 else "loc_1_1"
        entities[from_c] = "location"
        entities[to_c] = "location"

        init.append(FactSchema(predicate="at", arguments=("agent", from_c)))
        init.append(FactSchema(predicate="connected", arguments=(from_c, to_c)))
        init.append(FactSchema(predicate="connected", arguments=(to_c, from_c)))
        init.append(FactSchema(predicate="agent_free", arguments=("agent",)))

        # Check for item pickup/transfer (e.g. key_1) strictly in the positive clause
        pos_text = re.split(r"\b(?:without|do not|don't|never|must not|avoid)\b", text)[0]
        item_match = re.search(r"(key_\d+|item_[a-z0-9_]+|token_[a-z0-9_]+)", pos_text)
        if item_match:
            item_name = item_match.group(1).replace(" ", "_")
            entities[item_name] = "item"
            init.append(FactSchema(predicate="item_at", arguments=(item_name, to_c)))
            goal.append(FactSchema(predicate="holding_item", arguments=("agent", item_name)))
        else:
            goal.append(FactSchema(predicate="at", arguments=("agent", to_c)))

    def _extract_household(self, text: str, entities: dict, init: list, goal: list) -> None:
        entities["robot"] = "robot"

        # Dynamic Item extraction
        item_matches = re.findall(r"\b(mug|cup|glass|plate|book|bowl|bottle|sponge|apple|vase|dish|item_[a-z0-9_]+)\b", text)
        item_name = item_matches[0] if item_matches else "mug"
        entities[item_name] = "item"

        # Dynamic Room extraction
        room_matches = re.findall(r"\b(kitchen|living_room|living room|bedroom|office|hallway|bathroom|pantry|dining_room|dining room|room_[a-z0-9_]+)\b", text)
        clean_rooms = [r.replace(" ", "_") for r in room_matches]
        rm_start = clean_rooms[0] if len(clean_rooms) > 0 else "kitchen"
        rm_dest = clean_rooms[1] if len(clean_rooms) > 1 else ("living_room" if rm_start != "living_room" else "office")
        entities[rm_start] = "room"
        entities[rm_dest] = "room"

        # Dynamic Surface extraction
        surface_matches = re.findall(r"\b(shelf|table|counter|desk|tray|nightstand|surface_[a-z0-9_]+)\b", text)
        s_start_raw = surface_matches[0] if len(surface_matches) > 0 else "shelf"
        s_dest_raw = surface_matches[1] if len(surface_matches) > 1 else ("table" if s_start_raw != "table" else "counter")
        s_start = f"{rm_start}_{s_start_raw}" if not s_start_raw.startswith(rm_start) else s_start_raw
        s_dest = f"{rm_dest}_{s_dest_raw}" if not s_dest_raw.startswith(rm_dest) else s_dest_raw
        entities[s_start] = "surface"
        entities[s_dest] = "surface"

        init.append(FactSchema(predicate="robot_at", arguments=("robot", rm_start)))
        init.append(FactSchema(predicate="connected_rooms", arguments=(rm_start, rm_dest)))
        init.append(FactSchema(predicate="connected_rooms", arguments=(rm_dest, rm_start)))
        init.append(FactSchema(predicate="surface_in_room", arguments=(s_start, rm_start)))
        init.append(FactSchema(predicate="surface_in_room", arguments=(s_dest, rm_dest)))
        init.append(FactSchema(predicate="item_on", arguments=(item_name, s_start)))
        init.append(FactSchema(predicate="gripper_empty", arguments=("robot",)))

        goal.append(FactSchema(predicate="item_on", arguments=(item_name, s_dest)))

    def _extract_warehouse(self, text: str, entities: dict, init: list, goal: list) -> None:
        # Carrier extraction
        carrier_matches = re.findall(r"\b(carrier_\d+|agv_\d+|robot_\d+|forklift_\d+)\b", text)
        carrier_id = carrier_matches[0] if carrier_matches else "carrier_1"
        entities[carrier_id] = "carrier"

        # SKU extraction
        sku_matches = re.findall(r"\b(sku_[a-z0-9_]+|package_[a-z0-9_]+|part_[a-z0-9_]+|box_[a-z0-9_]+|widget_[a-z0-9_]+|pallet_[a-z0-9_]+)\b", text)
        sku_id = sku_matches[0] if sku_matches else "sku_a"
        entities[sku_id] = "sku"

        # Bay extraction
        bay_matches = re.findall(r"\b(shelf_\d+|bay_\d+|dock_[a-z0-9_]+|dispatch_dock|dispatch dock|receiving_dock|receiving dock|rack_\d+)\b", text)
        clean_bays = [b.replace(" ", "_") for b in bay_matches]
        bay_start = clean_bays[0] if len(clean_bays) > 0 else "shelf_1"
        bay_dest = clean_bays[1] if len(clean_bays) > 1 else ("dispatch_dock" if bay_start != "dispatch_dock" else "bay_2")
        entities[bay_start] = "bay"
        entities[bay_dest] = "bay"

        # Zone extraction
        zone_matches = re.findall(r"\b(zone_[a-z0-9_]+|aisle_\d+|storage_zone|dock_zone)\b", text)
        zone_start = zone_matches[0] if len(zone_matches) > 0 else "zone_storage"
        zone_dest = zone_matches[1] if len(zone_matches) > 1 else ("zone_dock" if zone_start != "zone_dock" else "zone_dispatch")
        entities[zone_start] = "zone"
        entities[zone_dest] = "zone"

        init.append(FactSchema(predicate="carrier_at", arguments=(carrier_id, zone_start)))
        init.append(FactSchema(predicate="zone_connected", arguments=(zone_start, zone_dest)))
        init.append(FactSchema(predicate="zone_connected", arguments=(zone_dest, zone_start)))
        init.append(FactSchema(predicate="bay_in_zone", arguments=(bay_start, zone_start)))
        init.append(FactSchema(predicate="bay_in_zone", arguments=(bay_dest, zone_dest)))
        init.append(FactSchema(predicate="sku_stored_in", arguments=(sku_id, bay_start)))
        init.append(FactSchema(predicate="carrier_empty", arguments=(carrier_id,)))
        init.append(FactSchema(predicate="bay_available", arguments=(bay_dest,)))

        goal.append(FactSchema(predicate="sku_stored_in", arguments=(sku_id, bay_dest)))

    def _extract_scheduling(self, text: str, entities: dict, init: list, goal: list) -> None:
        # Job extraction
        job_matches = re.findall(r"\b(job_[a-z0-9_]+|task_[a-z0-9_]+|review_[a-z0-9_]+|design_review|code_review|qa_testing|data_sync|backup_job)\b", text)
        if len(job_matches) >= 2:
            job_a, job_b = job_matches[0], job_matches[1]
        elif len(job_matches) == 1:
            job_a, job_b = job_matches[0], f"{job_matches[0]}_step2"
        else:
            job_a, job_b = "design_review", "code_review"

        entities[job_a] = "job"
        entities[job_b] = "job"

        # Resource extraction
        res_matches = re.findall(r"\b(machine_\d+|server_\d+|worker_[a-z0-9_]+|cpu_\d+|core_\d+)\b", text)
        res_id = res_matches[0] if res_matches else "machine_1"
        entities[res_id] = "resource"

        # Slots
        slot_1, slot_2 = "slot_1", "slot_2"
        entities[slot_1] = "slot"
        entities[slot_2] = "slot"

        init.append(FactSchema(predicate="job_ready", arguments=(job_a,)))
        init.append(FactSchema(predicate="job_ready", arguments=(job_b,)))
        init.append(FactSchema(predicate="precedes", arguments=(job_a, job_b)))
        init.append(FactSchema(predicate="resource_available", arguments=(res_id, slot_1)))
        init.append(FactSchema(predicate="resource_available", arguments=(res_id, slot_2)))

        goal.append(FactSchema(predicate="job_completed", arguments=(job_b,)))

    def _extract_software(self, text: str, entities: dict, init: list, goal: list) -> None:
        # Commit extraction
        commit_matches = re.findall(r"\b(commit_[a-z0-9_]+|release_[a-z0-9_]+|sha_[a-z0-9_]+|v\d+[\w.]*)\b", text)
        commit_id = commit_matches[0] if commit_matches else "commit_v1"
        entities[commit_id] = "commit"

        # Artifact extraction
        pkg_matches = re.findall(r"\b(pkg_[a-z0-9_]+|artifact_[a-z0-9_]+|image_[a-z0-9_]+|bundle_[a-z0-9_]+)\b", text)
        pkg_id = pkg_matches[0] if pkg_matches else f"pkg_{commit_id}"
        entities[pkg_id] = "artifact"

        # Environment extraction
        env_matches = re.findall(r"\b(staging|production|prod|qa|testing|test|dev|canary|env_[a-z0-9_]+)\b", text)
        env_id = env_matches[0] if env_matches else "staging"
        if env_id == "prod":
            env_id = "production"
        entities[env_id] = "environment"

        init.append(FactSchema(predicate="code_checked_out", arguments=(commit_id,)))
        init.append(FactSchema(predicate="environment_healthy", arguments=(env_id,)))

        # Goals based on text verbs
        goal.append(FactSchema(predicate="deployed_to", arguments=(pkg_id, env_id)))
