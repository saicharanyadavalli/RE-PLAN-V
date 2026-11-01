"""Warehouse Operations & Inventory Movement Domain."""

from __future__ import annotations

from typing import Any, Dict, List
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.constraints import FunctionalDependencyInvariant
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class WarehouseDomain(BaseDomain):
    """Warehouse inventory handling, SKU retrieval, and AGV transit domain."""

    def __init__(self) -> None:
        th = TypeHierarchy()
        th.add_type("carrier", "object")
        th.add_type("zone", "object")
        th.add_type("sku", "object")
        th.add_type("bay", "object")

        preds = [
            PredicateDefinition("carrier_at", ["carrier", "zone"]),
            PredicateDefinition("zone_connected", ["zone", "zone"], is_static=True),
            PredicateDefinition("bay_in_zone", ["bay", "zone"], is_static=True),
            PredicateDefinition("sku_stored_in", ["sku", "bay"]),
            PredicateDefinition("carrier_loaded_with", ["carrier", "sku"]),
            PredicateDefinition("carrier_empty", ["carrier"]),
            PredicateDefinition("bay_occupied", ["bay"]),
            PredicateDefinition("bay_available", ["bay"]),
            PredicateDefinition("restricted_zone", ["zone"], is_static=True),
        ]

        transit = ActionDefinition(
            name="transit",
            parameters=[
                ActionParameter("c", "carrier"),
                ActionParameter("from_z", "zone"),
                ActionParameter("to_z", "zone"),
            ],
            preconditions=[
                Fact("carrier_at", ["?c", "?from_z"]),
                Fact("zone_connected", ["?from_z", "?to_z"]),
            ],
            add_effects=[Fact("carrier_at", ["?c", "?to_z"])],
            del_effects=[Fact("carrier_at", ["?c", "?from_z"])],
            cost=2.0,
            description="Carrier / AGV travels between connected warehouse zones",
        )

        retrieve = ActionDefinition(
            name="retrieve_sku",
            parameters=[
                ActionParameter("c", "carrier"),
                ActionParameter("it", "sku"),
                ActionParameter("b", "bay"),
                ActionParameter("z", "zone"),
            ],
            preconditions=[
                Fact("carrier_at", ["?c", "?z"]),
                Fact("bay_in_zone", ["?b", "?z"]),
                Fact("sku_stored_in", ["?it", "?b"]),
                Fact("carrier_empty", ["?c"]),
            ],
            add_effects=[
                Fact("carrier_loaded_with", ["?c", "?it"]),
                Fact("bay_available", ["?b"]),
            ],
            del_effects=[
                Fact("sku_stored_in", ["?it", "?b"]),
                Fact("carrier_empty", ["?c"]),
                Fact("bay_occupied", ["?b"]),
            ],
            cost=1.0,
            description="Retrieve an SKU unit from a storage bay into the carrier",
        )

        deposit = ActionDefinition(
            name="deposit_sku",
            parameters=[
                ActionParameter("c", "carrier"),
                ActionParameter("it", "sku"),
                ActionParameter("b", "bay"),
                ActionParameter("z", "zone"),
            ],
            preconditions=[
                Fact("carrier_at", ["?c", "?z"]),
                Fact("bay_in_zone", ["?b", "?z"]),
                Fact("carrier_loaded_with", ["?c", "?it"]),
                Fact("bay_available", ["?b"]),
            ],
            add_effects=[
                Fact("sku_stored_in", ["?it", "?b"]),
                Fact("carrier_empty", ["?c"]),
                Fact("bay_occupied", ["?b"]),
            ],
            del_effects=[
                Fact("carrier_loaded_with", ["?c", "?it"]),
                Fact("bay_available", ["?b"]),
            ],
            cost=1.0,
            description="Deposit loaded SKU into an available storage or packing bay",
        )

        examples = [
            {
                "prompt": "Move SKU_A from shelf_1 to packing_dock.",
                "domain": "warehouse",
                "goal": "sku_stored_in(sku_a, packing_dock)",
            },
            {
                "prompt": "Retrieve pallet_4 from aisle_2 and deposit at dispatch_zone. Avoid restricted zone aisle_3.",
                "domain": "warehouse",
                "goal": "sku_stored_in(pallet_4, dispatch_zone)",
            },
        ]

        super().__init__(
            domain_id="warehouse",
            name="Warehouse Operations",
            version="1.0.0",
            description="Logistics inventory movement, SKU storage bay allocation, and AGV transit domain.",
            type_hierarchy=th,
            predicates=preds,
            actions=[transit, retrieve, deposit],
            default_invariants=[FunctionalDependencyInvariant("carrier_at", 0, 1), FunctionalDependencyInvariant("sku_stored_in", 0, 1)],
            task_examples=examples,
            supported_patterns=[
                "warehouse", "sku", "bay", "dock", "pallet", "carrier", "agv", "inventory", "transit", "store"
            ],
            unsupported_features=[
                "fleet collision avoidance at millisecond resolution", "barcode scanner optical models"
            ],
        )
