"""Central Domain Registry for RE-PLAN-V.

Thread-safe registry mapping domain IDs and aliases to BaseDomain instances.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.domains.base import BaseDomain


class DomainRegistry:
    """Registry maintaining active planning domains across the system."""

    def __init__(self) -> None:
        self._domains: Dict[str, BaseDomain] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, domain: BaseDomain, aliases: Optional[List[str]] = None) -> None:
        """Registers a domain and its optional aliases."""
        d_id = domain.domain_id.lower().strip()
        self._domains[d_id] = domain
        if aliases:
            for al in aliases:
                self._aliases[al.lower().strip()] = d_id

    def get(self, domain_id: str) -> Optional[BaseDomain]:
        """Looks up a domain by ID or alias (case-insensitive)."""
        key = domain_id.lower().strip()
        target = self._aliases.get(key, key)
        return self._domains.get(target)

    def has(self, domain_id: str) -> bool:
        """Returns True if the domain ID or alias is registered."""
        key = domain_id.lower().strip()
        target = self._aliases.get(key, key)
        return target in self._domains

    def list_domains(self) -> List[BaseDomain]:
        """Returns all registered unique domains."""
        return list(self._domains.values())

    def get_metadata_summary(self) -> List[Dict[str, Any]]:
        """Returns metadata dictionaries for all domains (used by REST API and UI)."""
        return [d.to_dict() for d in self._domains.values()]


# Global singleton registry instance
registry = DomainRegistry()
