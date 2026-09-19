"""Vision evaluation metrics comparing detected scenes with ground truth."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple
from core.contracts import BoundingBox, DetectedObject, FactSchema, VisualSceneProposal
from interpretation.vision.scene_generator import GroundTruthScene


def calculate_iou(boxA: BoundingBox, boxB: BoundingBox) -> float:
    """Calculates Intersection over Union for two bounding boxes."""
    xA = max(boxA.x, boxB.x)
    yA = max(boxA.y, boxB.y)
    xB = min(boxA.x + boxA.width, boxB.x + boxB.width)
    yB = min(boxA.y + boxA.height, boxB.y + boxB.height)

    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    inter_area = inter_width * inter_height

    areaA = boxA.width * boxA.height
    areaB = boxB.width * boxB.height
    union_area = float(areaA + areaB - inter_area)

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class VisionEvaluator:
    """Computes precision, recall, and IoU metrics for perception against ground truth."""

    def evaluate(
        self,
        proposal: VisualSceneProposal,
        ground_truth: GroundTruthScene,
    ) -> Dict[str, float]:
        # 1. Object recall and precision
        det_names = {obj.name for obj in proposal.detected_objects}
        gt_names = {obj.name for obj in ground_truth.objects}

        tp_objs = len(det_names.intersection(gt_names))
        precision_objs = tp_objs / max(1, len(det_names))
        recall_objs = tp_objs / max(1, len(gt_names))

        # 2. Mean IoU
        gt_box_map = {obj.name: obj.bbox for obj in ground_truth.objects}
        ious: List[float] = []
        for det in proposal.detected_objects:
            if det.name in gt_box_map:
                ious.append(calculate_iou(det.bbox, gt_box_map[det.name]))
        mean_iou = sum(ious) / max(1, len(ious)) if ious else 0.0

        # 3. Spatial relation recall and precision
        det_facts: Set[Tuple[str, Tuple[str, ...]]] = {
            (f.predicate.lower(), tuple(f.arguments)) for f in proposal.extracted_facts
        }
        gt_facts: Set[Tuple[str, Tuple[str, ...]]] = {
            (f.predicate.lower(), tuple(f.arguments)) for f in ground_truth.spatial_facts
        }

        tp_facts = len(det_facts.intersection(gt_facts))
        precision_facts = tp_facts / max(1, len(det_facts))
        recall_facts = tp_facts / max(1, len(gt_facts))

        return {
            "object_precision": precision_objs,
            "object_recall": recall_objs,
            "mean_iou": mean_iou,
            "relation_precision": precision_facts,
            "relation_recall": recall_facts,
        }
