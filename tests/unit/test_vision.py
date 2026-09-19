"""Unit tests for Stage 10: Controlled Vision Perception."""

import pytest
from core.contracts import VisualSceneProposal
from interpretation.vision.detector import DeterministicSceneDetector
from interpretation.vision.evaluator import VisionEvaluator
from interpretation.vision.scene_generator import SyntheticSceneGenerator
from interpretation.vision.vlm_adapter import VLMVisionAdapter


def test_synthetic_scene_generator():
    gen = SyntheticSceneGenerator(width=400, height=400)
    blocks = [
        {"name": "red_box", "color": "red", "shape": "box"},
        {"name": "blue_box", "color": "blue", "shape": "box"},
    ]
    scene = gen.generate_tabletop_scene(blocks, stacks=[("red_box", "blue_box")])

    assert len(scene.objects) == 2
    assert any(f.predicate == "on" and f.arguments == ("red_box", "blue_box") for f in scene.spatial_facts)
    assert any(f.predicate == "on_table" and f.arguments == ("blue_box",) for f in scene.spatial_facts)
    assert any(f.predicate == "clear" and f.arguments == ("red_box",) for f in scene.spatial_facts)


def test_deterministic_scene_detector_and_evaluation():
    gen = SyntheticSceneGenerator(width=400, height=400)
    blocks = [
        {"name": "red_box", "color": "red", "shape": "box"},
        {"name": "blue_box", "color": "blue", "shape": "box"},
    ]
    gt_scene = gen.generate_tabletop_scene(blocks, stacks=[("red_box", "blue_box")])

    detector = DeterministicSceneDetector(table_y=gen.table_y)
    proposal = detector.detect(gt_scene.image, scene_id="test_scene_01")

    assert len(proposal.detected_objects) == 2
    detected_names = {obj.name for obj in proposal.detected_objects}
    assert "red_box" in detected_names
    assert "blue_box" in detected_names

    # Check extracted facts
    fact_strs = [f.to_string() for f in proposal.extracted_facts]
    assert "on(red_box, blue_box)" in fact_strs
    assert "on_table(blue_box)" in fact_strs
    assert "clear(red_box)" in fact_strs

    # Evaluate against ground truth
    evaluator = VisionEvaluator()
    metrics = evaluator.evaluate(proposal, gt_scene)

    assert metrics["object_precision"] == 1.0
    assert metrics["object_recall"] == 1.0
    assert metrics["mean_iou"] > 0.85
    assert metrics["relation_precision"] >= 0.90
    assert metrics["relation_recall"] >= 0.90


def test_vlm_adapter():
    gen = SyntheticSceneGenerator(width=400, height=400)
    blocks = [{"name": "green_box", "color": "green", "shape": "box"}]
    gt_scene = gen.generate_tabletop_scene(blocks)

    vlm = VLMVisionAdapter()
    proposal = vlm.perceive(gt_scene.image, scene_id="vlm_test")

    assert isinstance(proposal, VisualSceneProposal)
    assert len(proposal.detected_objects) == 1
    assert proposal.detected_objects[0].color == "green"
