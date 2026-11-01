# Domain Authoring Guide: Extending RE-PLAN-V

RE-PLAN-V is built with a pluggable domain architecture. To author a new planning domain or extend existing ones, follow the specifications outlined in this guide.

---

## 1. Subclassing `BaseDomain`

Every planning domain must inherit from `core.domains.base.BaseDomain` and implement the required abstract methods:

```python
from typing import List, Set, Tuple
from core.domains.base import BaseDomain, ActionSchema, PredicateDefinition
from core.world.predicates import Fact
from core.world.state import SymbolicState
from core.world.types import TypeHierarchy

class MyCustomDomain(BaseDomain):
    def __init__(self):
        super().__init__(
            domain_id="my_custom_domain",
            display_name="Custom Domain",
            description="A custom domain for autonomous reasoning.",
            complexity_rating="Small (50-200 states)",
        )

    def _setup_type_hierarchy(self) -> TypeHierarchy:
        hierarchy = TypeHierarchy()
        hierarchy.add_type("item")
        hierarchy.add_type("location")
        return hierarchy

    def _setup_predicates(self) -> List[PredicateDefinition]:
        return [
            PredicateDefinition(name="at", arg_types=["item", "location"]),
            PredicateDefinition(name="connected", arg_types=["location", "location"]),
        ]

    def _setup_actions(self) -> List[ActionSchema]:
        return [
            ActionSchema(
                name="teleport",
                parameters=[("i", "item"), ("from_loc", "location"), ("to_loc", "location")],
                preconditions=[
                    Fact("at", ["?i", "?from_loc"]),
                    Fact("connected", ["?from_loc", "?to_loc"]),
                ],
                positive_effects=[Fact("at", ["?i", "?to_loc"])],
                negative_effects=[Fact("at", ["?i", "?from_loc"])],
                cost=1.0,
            )
        ]

    def check_invariants(self, state: SymbolicState) -> Tuple[bool, str]:
        # Enforce that an item cannot be in two locations simultaneously
        locations_by_item = {}
        for fact in state.facts:
            if fact.predicate == "at":
                item, loc = fact.arguments[0], fact.arguments[1]
                if item in locations_by_item and locations_by_item[item] != loc:
                    return False, f"Item {item} present in multiple locations!"
                locations_by_item[item] = loc
        return True, ""
```

---

## 2. Registering with `DomainRegistry`

Register your domain in `core/domains/__init__.py`:

```python
from core.domains.registry import registry
from .my_domain import MyCustomDomain

registry.register(MyCustomDomain())
```

Once registered, your domain will automatically appear in:
1. `GET /api/domains` endpoint.
2. The interactive frontend **Domain Studio**.
3. The NLP **Domain Router** for natural language instruction routing.
4. The **State Space Explorer** for complete reachable-graph exploration.

---

## 3. Authoring Guidelines & Invariants

1. **Deterministic Hashing**: `BaseDomain.get_canonical_state_hash(state)` generates a SHA-256 digest over sorted, ground fact strings. Ensure your facts use canonical argument ordering.
2. **STRIPS Transitions**: `apply_action(state, action)` applies negative effects first, followed by positive effects.
3. **Explicit Boundary Declarations**: In your domain definition, implement `get_supported_features()` and `get_unsupported_features()` to state explicitly what physical dynamics are modeled versus out-of-scope.
