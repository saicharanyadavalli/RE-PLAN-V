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
    timeout_seconds: float = Field(default=GraphBudgetLimits.DEFAULT_TIMEOUT_SECONDS)

    @field_validator("max_nodes", mode="before")
    @classmethod
    def validate_nodes(cls, v: Any) -> int:
        if v is None:
            raise ValueError("max_nodes cannot be None.")
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid integer limits.")
        if isinstance(v, float):
            raise ValueError("Float values are not valid integer limits.")
        if isinstance(v, str):
            if "." in v:
                raise ValueError("Fractional string values are not valid integer limits.")
            if v.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "+infinity"):
                raise ValueError("Non-finite values are not valid integer limits.")
            try:
                val = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid max_nodes value: {v}")
        elif isinstance(v, int):
            val = v
        else:
            try:
                val = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid max_nodes value: {v}")

        if not (GraphBudgetLimits.MIN_NODES <= val <= GraphBudgetLimits.MAX_NODES):
            raise ValueError(
                f"max_nodes must be between {GraphBudgetLimits.MIN_NODES} and {GraphBudgetLimits.MAX_NODES}, got {val}"
            )
        return val

    @field_validator("max_edges", mode="before")
    @classmethod
    def validate_edges(cls, v: Any) -> int:
        if v is None:
            raise ValueError("max_edges cannot be None.")
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid integer limits.")
        if isinstance(v, float):
            raise ValueError("Float values are not valid integer limits.")
        if isinstance(v, str):
            if "." in v:
                raise ValueError("Fractional string values are not valid integer limits.")
            if v.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "+infinity"):
                raise ValueError("Non-finite values are not valid integer limits.")
            try:
                val = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid max_edges value: {v}")
        elif isinstance(v, int):
            val = v
        else:
            try:
                val = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid max_edges value: {v}")

        if not (GraphBudgetLimits.MIN_EDGES <= val <= GraphBudgetLimits.MAX_EDGES):
            raise ValueError(
                f"max_edges must be between {GraphBudgetLimits.MIN_EDGES} and {GraphBudgetLimits.MAX_EDGES}, got {val}"
            )
        return val

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def validate_timeout(cls, v: Any) -> float:
        if v is None:
            raise ValueError("timeout_seconds cannot be None.")
        if isinstance(v, bool):
            raise ValueError("Boolean values are not valid timeout values.")
        if isinstance(v, str):
            if v.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "+infinity"):
                raise ValueError("timeout_seconds must be a finite number.")
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid timeout_seconds value: {v}")

        if math.isnan(val) or math.isinf(val) or not math.isfinite(val):
            raise ValueError("timeout_seconds must be a finite number.")

        if val <= 0.0 or val < GraphBudgetLimits.MIN_TIMEOUT_SECONDS or val > GraphBudgetLimits.MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between {GraphBudgetLimits.MIN_TIMEOUT_SECONDS} and {GraphBudgetLimits.MAX_TIMEOUT_SECONDS}, got {val}"
            )
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
        """Acquires a concurrency slot (non-blocking by default). Returns True if acquired."""
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
                try:
                    self._semaphore.release()
                except ValueError:
                    pass

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

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
