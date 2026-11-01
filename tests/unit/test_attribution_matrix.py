"""Tests for the 5-Class Fault Attribution Confusion Matrix experiment runner."""

import pytest
from evaluation.experiments.fault_matrix import AttributionMatrixExperiment


def test_attribution_matrix_evaluation_structure():
    runner = AttributionMatrixExperiment()
    results = runner.run_evaluation(instances_per_class=2, seed=42)

    assert "accuracy" in results
    assert "macro_f1" in results
    assert "per_class" in results
    assert "confusion_matrix" in results
    assert len(results["confusion_matrix"]) == 5
    assert results["total_evaluated"] == 10
    assert results["accuracy"] >= 0.70
