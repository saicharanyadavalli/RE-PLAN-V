"""Unit tests for the Generic Domain Framework and Domain Registry."""

import pytest
from core.domains.base import BaseDomain
from core.domains.registry import DomainRegistry, registry
from core.world.predicates import Fact, PredicateDefinition
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry, TypeHierarchy
from core.actions.definition import ActionDefinition, ActionParameter


class DummyTestDomain(BaseDomain):
    def __init__(self):
        th = TypeHierarchy()
        th.add_type("item", "object")
        super().__init__(
            domain_id="dummy_test",
            name="Dummy Test Domain",
            version="1.0.0",
            description="Domain for testing the registry",
            type_hierarchy=th,
            predicates=[PredicateDefinition("at", ["item", "item"])],
            actions=[],
            task_examples=[{"prompt": "Test prompt", "expected_outcome": "SUPPORTED"}],
            supported_patterns=["test"],
            unsupported_features=["time_travel"],
        )


def test_domain_registry_registration_and_lookup():
    reg = DomainRegistry()
    domain = DummyTestDomain()
    reg.register(domain)

    assert reg.has("dummy_test")
    assert reg.has("DUMMY_TEST")  # Case insensitive
    fetched = reg.get("dummy_test")
    assert fetched is not None
    assert fetched.name == "Dummy Test Domain"
    assert "dummy_test" in [d.domain_id for d in reg.list_domains()]


def test_domain_metadata_summary():
    reg = DomainRegistry()
    domain = DummyTestDomain()
    reg.register(domain)

    summary = reg.get_metadata_summary()
    assert len(summary) == 1
    d_meta = summary[0]
    assert d_meta["domain_id"] == "dummy_test"
    assert d_meta["name"] == "Dummy Test Domain"
    assert "unsupported_features" in d_meta
    assert "task_examples" in d_meta


def test_domain_canonical_state_key():
    domain = DummyTestDomain()
    s1 = SymbolicState([Fact("at", ["a", "b"]), Fact("at", ["c", "d"])])
    s2 = SymbolicState([Fact("at", ["c", "d"]), Fact("at", ["a", "b"])])
    
    key1 = domain.canonical_state_key(s1)
    key2 = domain.canonical_state_key(s2)
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex string
