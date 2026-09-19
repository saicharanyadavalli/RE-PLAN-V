"""Default system configurations for RE-PLAN-V."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    title: str = "RE-PLAN-V: Research & Demo Platform"
    static_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "app" / "static")


@dataclass
class PlanningConfig:
    default_algorithm: str = "A*"
    max_search_depth: int = 50
    max_nodes_expanded: int = 5000
    timeout_seconds: float = 10.0


@dataclass
class VerificationConfig:
    max_plan_length: int = 100
    strict_invariants: bool = True


@dataclass
class RepairConfig:
    max_repair_iterations: int = 5
    loop_detection: bool = True
    no_progress_limit: int = 3
    allow_local_replanning: bool = True


@dataclass
class BenchmarkConfig:
    default_seed: int = 42
    output_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "evaluation" / "reports")


@dataclass
class VisionConfig:
    backend: str = "synthetic"  # "synthetic", "opencv", "vlm"
    canvas_width: int = 400
    canvas_height: int = 400


@dataclass
class LLMConfig:
    provider: str = "mock"  # "mock", "gemini"
    temperature: float = 0.0
    timeout_seconds: float = 10.0


@dataclass
class SystemConfig:
    app: AppConfig = field(default_factory=AppConfig)
    planning: PlanningConfig = field(default_factory=PlanningConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    repair: RepairConfig = field(default_factory=RepairConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


default_config = SystemConfig()
