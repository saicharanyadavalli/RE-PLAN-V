"""Synthetic controlled visual scene generator with ground-truth extraction."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw

from core.contracts import BoundingBox, DetectedObject, FactSchema, VisualSceneProposal


@dataclass
class GroundTruthScene:
    image: Image.Image
    objects: List[DetectedObject]
    spatial_facts: List[FactSchema]

    def to_png_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        return buf.getvalue()


class SyntheticSceneGenerator:
    """Renders 2D tabletop block scenes with known ground truth geometry and relations."""

    COLOR_MAP = {
        "red": (230, 50, 50),
        "blue": (50, 100, 230),
        "green": (50, 200, 50),
        "yellow": (230, 210, 40),
        "purple": (160, 50, 200),
    }

    def __init__(self, width: int = 400, height: int = 400) -> None:
        self.width = width
        self.height = height
        self.table_y = height - 60

    def generate_tabletop_scene(
        self,
        block_configs: List[Dict[str, str]],
        stacks: Optional[List[Tuple[str, str]]] = None,
    ) -> GroundTruthScene:
        """Renders blocks on a table.

        block_configs: list of {"name": str, "color": str, "shape": str}
        stacks: list of (top_block_name, bottom_block_name)
        """
        img = Image.new("RGB", (self.width, self.height), color=(240, 240, 245))
        draw = ImageDraw.Draw(img)

        # Draw Table
        draw.rectangle(
            [(20, self.table_y), (self.width - 20, self.table_y + 40)],
            fill=(180, 140, 100),
            outline=(120, 90, 60),
            width=2,
        )

        stack_map: Dict[str, str] = dict(stacks or [])
        bottom_blocks = [b for b in block_configs if b["name"] not in stack_map]

        block_width = 60
        block_height = 50
        spacing = 40
        start_x = 40

        obj_positions: Dict[str, BoundingBox] = {}
        detected_objects: List[DetectedObject] = []
        spatial_facts: List[FactSchema] = []

        # 1. Position bottom blocks on table
        curr_x = start_x
        for b_conf in bottom_blocks:
            name = b_conf["name"]
            color_name = b_conf.get("color", "blue").lower()
            shape_name = b_conf.get("shape", "box").lower()
            rgb = self.COLOR_MAP.get(color_name, (100, 100, 100))

            bx = curr_x
            by = self.table_y - block_height
            bbox = BoundingBox(x=bx, y=by, width=block_width, height=block_height)
            obj_positions[name] = bbox

            # Draw block
            draw.rectangle([(bx, by), (bx + block_width, by + block_height)], fill=rgb, outline=(30, 30, 30), width=2)
            draw.text((bx + 15, by + 18), name[:4], fill=(255, 255, 255))

            detected_objects.append(
                DetectedObject(name=name, object_type="block", color=color_name, shape=shape_name, bbox=bbox)
            )
            spatial_facts.append(FactSchema(predicate="on_table", arguments=(name,)))
            curr_x += block_width + spacing

        # 2. Position stacked blocks on top of bottom blocks
        for top_name, bot_name in stack_map.items():
            if bot_name in obj_positions:
                bot_bbox = obj_positions[bot_name]
                top_conf = next((b for b in block_configs if b["name"] == top_name), {"color": "red", "shape": "box"})
                color_name = top_conf.get("color", "red").lower()
                shape_name = top_conf.get("shape", "box").lower()
                rgb = self.COLOR_MAP.get(color_name, (200, 50, 50))

                top_x = bot_bbox.x
                top_y = bot_bbox.y - block_height
                top_bbox = BoundingBox(x=top_x, y=top_y, width=block_width, height=block_height)
                obj_positions[top_name] = top_bbox

                draw.rectangle([(top_x, top_y), (top_x + block_width, top_y + block_height)], fill=rgb, outline=(30, 30, 30), width=2)
                draw.text((top_x + 15, top_y + 18), top_name[:4], fill=(255, 255, 255))

                detected_objects.append(
                    DetectedObject(name=top_name, object_type="block", color=color_name, shape=shape_name, bbox=top_bbox)
                )
                spatial_facts.append(FactSchema(predicate="on", arguments=(top_name, bot_name)))

        # 3. Derive clear(?b)
        all_block_names = {b["name"] for b in block_configs}
        under_block_names = set(stack_map.values())
        for name in all_block_names:
            if name not in under_block_names:
                spatial_facts.append(FactSchema(predicate="clear", arguments=(name,)))

        spatial_facts.append(FactSchema(predicate="handempty", arguments=()))

        return GroundTruthScene(image=img, objects=detected_objects, spatial_facts=spatial_facts)
