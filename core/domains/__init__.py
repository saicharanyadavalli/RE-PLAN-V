"""RE-PLAN-V Multi-Domain Planning Framework.

Auto-registers all 6 canonical domains into the global DomainRegistry.
"""

from core.domains.base import BaseDomain
from core.domains.registry import DomainRegistry, registry
from core.domains.blocks_world import BlocksWorldDomain
from core.domains.grid_world import GridWorldDomain
from core.domains.household import HouseholdRoboticsDomain
from core.domains.warehouse import WarehouseDomain
from core.domains.scheduling import SchedulingDomain
from core.domains.software_workflow import SoftwareWorkflowDomain

# Auto-register canonical domains with practical aliases
registry.register(BlocksWorldDomain(), aliases=["blocks", "blocksworld", "tabletop"])
registry.register(GridWorldDomain(), aliases=["grid", "gridworld", "navigation"])
registry.register(HouseholdRoboticsDomain(), aliases=["household", "robotics", "domestic"])
registry.register(WarehouseDomain(), aliases=["logistics", "warehouse_ops", "inventory"])
registry.register(SchedulingDomain(), aliases=["schedule", "job_shop", "resource_allocation"])
registry.register(SoftwareWorkflowDomain(), aliases=["software", "cicd", "workflow", "devops"])

__all__ = [
    "BaseDomain",
    "DomainRegistry",
    "registry",
    "BlocksWorldDomain",
    "GridWorldDomain",
    "HouseholdRoboticsDomain",
    "WarehouseDomain",
    "SchedulingDomain",
    "SoftwareWorkflowDomain",
]
