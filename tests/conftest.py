"""Pytest fixtures and configuration for RE-PLAN-V tests."""

import pytest
from configs.default import SystemConfig, default_config


@pytest.fixture
def base_config() -> SystemConfig:
    return default_config
