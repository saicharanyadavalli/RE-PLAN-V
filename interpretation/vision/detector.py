"""Deterministic vision detector extracting objects and spatial relations."""

from __future__ import annotations

import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple

from core.contracts import BoundingBox, DetectedObject, FactSchema, VisualSceneProposal
from interpretation.vision.scene_generator import SyntheticSceneGenerator


class DeterministicSceneDetector:
    """Perception detector that extracts blocks, colors, bounding boxes, and spatial relations."""

    def __init__(self, table_y: int = 340) -> None:
        self.table_y = table_y

    def detect(self, image: Image.Image, scene_id: str = "scene_01") -> VisualSceneProposal:
        """Analyzes RGB image to detect objects and relational facts."""
        img_rgb = image.convert("RGB")
        w, h = img_rgb.size
        arr = np.array(img_rgb)

        detected_objects: List[DetectedObject] = []
        extracted_facts: List[FactSchema] = []

        # Color centers in RGB
        color_targets = {
            "red": np.array([230, 50, 50]),
            "blue": np.array([50, 100, 230]),
            "green": np.array([50, 200, 50]),
            "yellow": np.array([230, 210, 40]),
            "purple": np.array([160, 50, 200]),
        }

        # Locate bounding boxes by color masks
        for color_name, rgb_val in color_targets.items():
            # Pixel distance
            diff = np.abs(arr.astype(int) - rgb_val)
            dist = np.sum(diff, axis=-1)
            mask = dist < 50

            ys, xs = np.where(mask)
            if len(xs) > 100:  # Minimum pixel threshold for a block
                min_x, max_x = int(np.min(xs)), int(np.max(xs))
                min_y, max_y = int(np.min(ys)), int(np.max(ys))
                bbox = BoundingBox(
                    x=min_x,
                    y=min_y,
                    width=max_x - min_x,
                    height=max_y - min_y,
                )
                obj_name = f"{color_name}_box"
                detected_objects.append(
                    DetectedObject(
                        name=obj_name,
                        object_type="block",
                        color=color_name,
                        shape="box",
                        bbox=bbox,
                    )
                )

        # Infer spatial relations from 2D geometry
        stacked_on: Dict[str, str] = {}  # top -> bottom

        for top in detected_objects:
            # Check if top is directly on another block
            found_under = False
            for bot in detected_objects:
                if top.name == bot.name:
                    continue
                # If bottom of top is close to top of bottom, and horizontal centers align
                top_bottom_edge = top.bbox.y + top.bbox.height
                bot_top_edge = bot.bbox.y
                horizontal_dist = abs(
                    (top.bbox.x + top.bbox.width / 2) - (bot.bbox.x + bot.bbox.width / 2)
                )

                if abs(top_bottom_edge - bot_top_edge) < 15 and horizontal_dist < 25:
                    extracted_facts.append(FactSchema(predicate="on", arguments=(top.name, bot.name)))
                    stacked_on[top.name] = bot.name
                    found_under = True
                    break

            if not found_under:
                # Top is on the table
                extracted_facts.append(FactSchema(predicate="on_table", arguments=(top.name,)))

        # Determine clear(?b)
        under_objects = set(stacked_on.values())
        for obj in detected_objects:
            if obj.name not in under_objects:
                extracted_facts.append(FactSchema(predicate="clear", arguments=(obj.name,)))

        extracted_facts.append(FactSchema(predicate="handempty", arguments=()))

        return VisualSceneProposal(
            scene_id=scene_id,
            detected_objects=detected_objects,
            extracted_facts=extracted_facts,
            confidence=0.98,
        )
