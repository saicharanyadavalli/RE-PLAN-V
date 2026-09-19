"""VLM adapter for visual scene understanding using shared structured schema."""

from __future__ import annotations

from typing import Optional
from PIL import Image
from core.contracts import VisualSceneProposal
from interpretation.vision.detector import DeterministicSceneDetector


class VLMVisionAdapter:
    """Adapter for multimodal VLM perception with fallback to deterministic detector."""

    def __init__(self, fallback_detector: Optional[DeterministicSceneDetector] = None) -> None:
        self.detector = fallback_detector or DeterministicSceneDetector()

    def perceive(self, image: Image.Image, scene_id: str = "vlm_scene") -> VisualSceneProposal:
        """Processes visual input and returns structured scene proposal conforming to contract."""
        # For Tier-1 zero-API core, uses the deterministic vision engine
        return self.detector.detect(image, scene_id=scene_id)
