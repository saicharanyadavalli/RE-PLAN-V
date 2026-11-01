"""Resource budget policy, validation, and process-wide concurrency management for graph enumeration."""

from __future__ import annotations

import asyncio
import math
import threading
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class GraphBudgetLimits:
    """Hard ceiling constants for Model B graph exploration."""
    MIN_NODES: int = 1
    MAX_NODES: int = 5000
    MAX_CORE_NODES: int = 50000
    DEFAULT_NODES: int = 300
    DEFAULT_MAX_NODES: int = 300

    MIN_EDGES: int = 0
    MAX_EDGES: int = 20000
    MAX_CORE_EDGES: int = 100000
    DEFAULT_EDGES: int = 1000
    DEFAULT_MAX_EDGES: int = 1000

    MIN_TIMEOUT: float = 0.000001
    MAX_TIMEOUT: float = 30.0
    MAX_CORE_TIMEOUT: float = 60.0
    DEFAULT_TIMEOUT: float = 5.0
    MIN_TIMEOUT_SECONDS: float = 0.000001
    MAX_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_TIMEOUT_SECONDS: float = 5.0

    MAX_CONCURRENT_ENUMERATIONS: int = 2


class GraphBudgetConfig(BaseModel):
    """Validated resource budget parameters shared across REST and WebSocket."""
    domain_id: Optional[str] = "blocks_world"
    prompt: Optional[str] = "Stack the red box on the blue box."
    max_nodes: int = Field(default=GraphBudgetLimits.DEFAULT_NODES)
    max_edges: int = Field(default=GraphBudgetLimits.DEFAULT_EDGES)
    timeout_seconds: float = Field(default=GraphBudgetLimits.DEFAULT_TIMEOUT)

    @field_validator("max_nodes", mode="before")
    @classmethod
    def validate_nodes(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid node limits.")
        try:
            val = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid max_nodes value: {v}")
        if val < GraphBudgetLimits.MIN_NODES:
            raise ValueError(f"max_nodes must be >= {GraphBudgetLimits.MIN_NODES}, got {val}")
        if val > GraphBudgetLimits.MAX_NODES:
            raise ValueError(f"max_nodes cannot exceed hard maximum {GraphBudgetLimits.MAX_NODES}, got {val}")
        return val

    @field_validator("max_edges", mode="before")
    @classmethod
    def validate_edges(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid edge limits.")
        try:
            val = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid max_edges value: {v}")
        if val < GraphBudgetLimits.MIN_EDGES:
            raise ValueError(f"max_edges must be >= {GraphBudgetLimits.MIN_EDGES}, got {val}")
        if val > GraphBudgetLimits.MAX_EDGES:
            raise ValueError(f"max_edges cannot exceed hard maximum {GraphBudgetLimits.MAX_EDGES}, got {val}")
        return val

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def validate_timeout(cls, v: Any) -> float:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid timeout values.")
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid timeout_seconds value: {v}")
        if not math.isfinite(val) or math.isnan(val):
            raise ValueError("timeout_seconds must be a finite number.")
        if val < GraphBudgetLimits.MIN_TIMEOUT:
            raise ValueError(f"timeout_seconds must be >= {GraphBudgetLimits.MIN_TIMEOUT}, got {val}")
        if val > GraphBudgetLimits.MAX_TIMEOUT:
            raise ValueError(f"timeout_seconds cannot exceed hard maximum {GraphBudgetLimits.MAX_TIMEOUT}, got {val}")
        return val


class GraphConcurrencyManager:
    """Process-wide bounded concurrency manager for graph enumeration."""
    _instance: Optional[GraphConcurrencyManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> GraphConcurrencyManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._semaphore = threading.BoundedSemaphore(
                    GraphBudgetLimits.MAX_CONCURRENT_ENUMERATIONS
                )
                cls._instance._active_count = 0
                cls._instance._count_lock = threading.Lock()
            return cls._instance

    def try_acquire(self) -> bool:
        """Attempts to acquire a slot without blocking. Returns True if acquired."""
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._count_lock:
                self._active_count += 1
        return acquired

    def acquire(self, blocking: bool = False) -> bool:
        """Alias for try_acquire / acquire."""
        if not blocking:
            return self.try_acquire()
        self._semaphore.acquire(blocking=True)
        with self._count_lock:
            self._active_count += 1
        return True

    def release(self) -> None:
        """Releases an acquired concurrency slot."""
        with self._count_lock:
            if self._active_count > 0:
                self._active_count -= 1
                self._semaphore.release()

    @property
    def max_concurrent(self) -> int:
        return GraphBudgetLimits.MAX_CONCURRENT_ENUMERATIONS

    @property
    def active_count(self) -> int:
        with self._count_lock:
            return self._active_count


# Global singleton instance
concurrency_manager = GraphConcurrencyManager()
graph_concurrency_manager = concurrency_manager
